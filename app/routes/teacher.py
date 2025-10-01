from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .. import db
from ..models import AttendanceEntry, AttendanceRecord, ClassRoom, Course, Student
from ..utils.decorators import role_required


teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')


@teacher_bp.route('/panel')
@role_required('teacher')
def dashboard():
    course_options = _teacher_course_options(current_user)
    recent_records = (
        AttendanceRecord.query.filter_by(teacher_id=current_user.id)
        .order_by(AttendanceRecord.session_date.desc())
        .limit(5)
        .all()
    )
    return render_template('teacher/dashboard.html', course_options=course_options, recent_records=recent_records)


@teacher_bp.route('/yoklama/olustur', methods=['GET', 'POST'])
@role_required('teacher')
def create_attendance():
    course_id = request.args.get('course_id', type=int) or request.form.get('course_id', type=int)
    class_id = request.args.get('class_id', type=int) or request.form.get('class_id', type=int)
    course = Course.query.get_or_404(course_id) if course_id else None
    classroom = ClassRoom.query.get_or_404(class_id) if class_id else None
    allowed_classes = []
    if course:
        allowed_classes = _teacher_allowed_classes(current_user, course)

    if request.method == 'POST':
        if not course or not classroom:
            flash('Ders ve sınıf seçimi zorunludur.', 'danger')
            return redirect(url_for('teacher.dashboard'))
        if classroom not in allowed_classes:
            flash('Bu sınıf için yetkiniz yok.', 'danger')
            return redirect(url_for('teacher.dashboard'))

        record = AttendanceRecord(course_id=course.id, classroom_id=classroom.id, teacher_id=current_user.id)
        db.session.add(record)
        db.session.flush()

        for student in classroom.students:
            status = request.form.get(f'status_{student.id}', 'present')
            entry = AttendanceEntry(record_id=record.id, student_id=student.id, status=status)
            db.session.add(entry)
        db.session.commit()
        flash('Yoklama kaydedildi.', 'success')
        return redirect(url_for('teacher.history'))

    course_options = _teacher_course_options(current_user)
    students = []
    if course and classroom:
        if classroom not in allowed_classes:
            flash('Bu sınıf için yetkiniz yok.', 'danger')
            return redirect(url_for('teacher.dashboard'))
        students = classroom.students
    return render_template(
        'teacher/create_attendance.html',
        course_options=course_options,
        selected_course=course,
        selected_class=classroom,
        allowed_classes=allowed_classes,
        students=students,
    )


@teacher_bp.route('/yoklama/<int:record_id>/duzenle', methods=['GET', 'POST'])
@role_required('teacher')
def edit_attendance(record_id):
    record = AttendanceRecord.query.get_or_404(record_id)
    if record.teacher_id != current_user.id:
        abort(403)
    if datetime.utcnow() - record.created_at > timedelta(minutes=30):
        flash('Bu yoklama için düzenleme süresi sona erdi.', 'warning')
        return redirect(url_for('teacher.history'))

    if request.method == 'POST':
        for entry in record.entries:
            status = request.form.get(f'status_{entry.id}')
            if status in {'present', 'excused', 'absent'}:
                entry.status = status
        db.session.commit()
        flash('Yoklama güncellendi.', 'success')
        return redirect(url_for('teacher.history'))

    return render_template('teacher/edit_attendance.html', record=record)


@teacher_bp.route('/yoklama/gecmis')
@role_required('teacher')
def history():
    records = (
        AttendanceRecord.query.filter_by(teacher_id=current_user.id)
        .order_by(AttendanceRecord.session_date.desc())
        .all()
    )
    now = datetime.utcnow()
    records_with_status = [
        {
            'record': record,
            'editable': now - record.created_at <= timedelta(minutes=30),
        }
        for record in records
    ]
    return render_template('teacher/history.html', records=records_with_status)


def _teacher_course_options(teacher):
    options = []
    for course in teacher.teacher_courses:
        allowed_classes = _teacher_allowed_classes(teacher, course)
        options.append({'course': course, 'classes': allowed_classes})
    return options


def _teacher_allowed_classes(teacher, course):
    teacher_class_ids = {classroom.id for classroom in teacher.teacher_classes}
    if teacher_class_ids:
        allowed = [classroom for classroom in course.classrooms if classroom.id in teacher_class_ids]
    else:
        allowed = list(course.classrooms)
    return sorted(allowed, key=lambda c: c.name)
