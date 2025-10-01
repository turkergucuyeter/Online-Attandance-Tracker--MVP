from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

from .. import db
from ..models import (
    AttendanceEntry,
    AttendanceRecord,
    ClassRoom,
    Course,
    Student,
    User,
)
from ..utils.accounts import generate_student_credentials
from ..utils.decorators import role_required
from ..utils.exporters import generate_csv, generate_pdf
from ..utils.importers import parse_csv, parse_pdf, parse_excel


supervisor_bp = Blueprint('supervisor', __name__, url_prefix='/supervisor')


@supervisor_bp.route('/panel')
@role_required('supervisor')
def dashboard():
    stats = {
        'teacher_count': User.query.filter_by(role='teacher').count(),
        'student_count': Student.query.count(),
        'course_count': Course.query.count(),
        'class_count': ClassRoom.query.count(),
        'attendance_count': AttendanceRecord.query.count(),
    }
    latest_records = (
        AttendanceRecord.query.order_by(AttendanceRecord.session_date.desc())
        .limit(5)
        .all()
    )
    return render_template('supervisor/dashboard.html', stats=stats, latest_records=latest_records)


# ------------------ TEACHERS ------------------ #
@supervisor_bp.route('/ogretmenler')
@role_required('supervisor')
def teachers():
    query = request.args.get('q', '').strip()
    teachers = User.query.filter_by(role='teacher')
    if query:
        like_query = f"%{query}%"
        teachers = teachers.filter(or_(User.full_name.ilike(like_query), User.email.ilike(like_query)))
    teachers = teachers.order_by(User.full_name).all()
    courses = Course.query.order_by(Course.name).all()
    classes = ClassRoom.query.order_by(ClassRoom.name).all()
    return render_template('supervisor/teachers.html', teachers=teachers, courses=courses, classes=classes, query=query)


@supervisor_bp.route('/ogretmenler/ekle', methods=['POST'])
@role_required('supervisor')
def add_teacher():
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    password = request.form.get('password')
    color = request.form.get('color')
    course_ids = [int(cid) for cid in request.form.getlist('course_ids') if cid]
    class_ids = [int(cid) for cid in request.form.getlist('class_ids') if cid]

    if User.query.filter_by(email=email).first():
        flash('Bu e-posta zaten kayıtlı.', 'danger')
        return redirect(url_for('supervisor.teachers'))

    teacher = User(full_name=full_name, email=email, role='teacher', color=color)
    teacher.password_hash = generate_password_hash(password)
    if course_ids:
        teacher.teacher_courses = Course.query.filter(Course.id.in_(course_ids)).all()
    if class_ids:
        teacher.teacher_classes = ClassRoom.query.filter(ClassRoom.id.in_(class_ids)).all()

    db.session.add(teacher)
    db.session.commit()
    flash('Öğretmen başarıyla eklendi.', 'success')
    return redirect(url_for('supervisor.teachers'))


@supervisor_bp.route('/ogretmenler/<int:teacher_id>/duzenle', methods=['POST'])
@role_required('supervisor')
def edit_teacher(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    teacher.full_name = request.form.get('full_name')
    teacher.email = request.form.get('email')
    password = request.form.get('password')
    teacher.color = request.form.get('color')

    if password:
        teacher.password_hash = generate_password_hash(password)

    course_ids = [int(cid) for cid in request.form.getlist('course_ids') if cid]
    class_ids = [int(cid) for cid in request.form.getlist('class_ids') if cid]
    teacher.teacher_courses = Course.query.filter(Course.id.in_(course_ids)).all()
    teacher.teacher_classes = ClassRoom.query.filter(ClassRoom.id.in_(class_ids)).all()

    db.session.commit()
    flash('Öğretmen bilgileri güncellendi.', 'success')
    return redirect(url_for('supervisor.teachers'))


@supervisor_bp.route('/ogretmenler/<int:teacher_id>/sil', methods=['POST'])
@role_required('supervisor')
def delete_teacher(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    db.session.delete(teacher)
    db.session.commit()
    flash('Öğretmen silindi.', 'info')
    return redirect(url_for('supervisor.teachers'))


# ------------------ COURSES ------------------ #
@supervisor_bp.route('/dersler')
@role_required('supervisor')
def courses_view():
    courses = Course.query.order_by(Course.name).all()
    classes = ClassRoom.query.order_by(ClassRoom.name).all()
    teachers = User.query.filter_by(role='teacher').order_by(User.full_name).all()
    return render_template('supervisor/courses.html', courses=courses, classes=classes, teachers=teachers)


@supervisor_bp.route('/dersler/ekle', methods=['POST'])
@role_required('supervisor')
def add_course():
    name = request.form.get('name')
    code = request.form.get('code')
    excused = int(request.form.get('max_excused_percentage') or 0)
    unexcused = int(request.form.get('max_unexcused_percentage') or 0)
    class_ids = [int(cid) for cid in request.form.getlist('class_ids') if cid]
    teacher_ids = [int(tid) for tid in request.form.getlist('teacher_ids') if tid]

    if Course.query.filter_by(code=code).first():
        flash('Bu ders kodu zaten kayıtlı.', 'danger')
        return redirect(url_for('supervisor.courses_view'))

    course = Course(
        name=name,
        code=code,
        max_excused_percentage=excused,
        max_unexcused_percentage=unexcused,
    )
    if class_ids:
        course.classrooms = ClassRoom.query.filter(ClassRoom.id.in_(class_ids)).all()
    if teacher_ids:
        course.teachers = User.query.filter(User.id.in_(teacher_ids)).all()

    db.session.add(course)
    db.session.commit()
    flash('Ders eklendi.', 'success')
    return redirect(url_for('supervisor.courses_view'))


@supervisor_bp.route('/dersler/<int:course_id>/duzenle', methods=['POST'])
@role_required('supervisor')
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.name = request.form.get('name')
    course.code = request.form.get('code')
    course.max_excused_percentage = int(request.form.get('max_excused_percentage') or 0)
    course.max_unexcused_percentage = int(request.form.get('max_unexcused_percentage') or 0)

    class_ids = [int(cid) for cid in request.form.getlist('class_ids') if cid]
    teacher_ids = [int(tid) for tid in request.form.getlist('teacher_ids') if tid]

    course.classrooms = ClassRoom.query.filter(ClassRoom.id.in_(class_ids)).all()
    course.teachers = User.query.filter(User.id.in_(teacher_ids)).all()

    db.session.commit()
    flash('Ders bilgileri güncellendi.', 'success')
    return redirect(url_for('supervisor.courses_view'))


@supervisor_bp.route('/dersler/<int:course_id>/sil', methods=['POST'])
@role_required('supervisor')
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Ders silindi.', 'info')
    return redirect(url_for('supervisor.courses_view'))


# ------------------ CLASSES ------------------ #
@supervisor_bp.route('/siniflar')
@role_required('supervisor')
def classes_view():
    classes = ClassRoom.query.order_by(ClassRoom.name).all()
    courses = Course.query.order_by(Course.name).all()
    teachers = User.query.filter_by(role='teacher').order_by(User.full_name).all()
    return render_template('supervisor/classes.html', classes=classes, courses=courses, teachers=teachers)


@supervisor_bp.route('/siniflar/ekle', methods=['POST'])
@role_required('supervisor')
def add_class():
    name = request.form.get('name')
    description = request.form.get('description')
    course_ids = [int(cid) for cid in request.form.getlist('course_ids') if cid]
    teacher_ids = [int(tid) for tid in request.form.getlist('teacher_ids') if tid]

    if ClassRoom.query.filter_by(name=name).first():
        flash('Bu sınıf adı zaten kayıtlı.', 'danger')
        return redirect(url_for('supervisor.classes_view'))

    classroom = ClassRoom(name=name, description=description)
    classroom.courses = Course.query.filter(Course.id.in_(course_ids)).all()
    classroom.teachers = User.query.filter(User.id.in_(teacher_ids)).all()

    db.session.add(classroom)
    db.session.commit()
    flash('Sınıf oluşturuldu.', 'success')
    return redirect(url_for('supervisor.classes_view'))


@supervisor_bp.route('/siniflar/<int:class_id>/duzenle', methods=['POST'])
@role_required('supervisor')
def edit_class(class_id):
    classroom = ClassRoom.query.get_or_404(class_id)
    classroom.name = request.form.get('name')
    classroom.description = request.form.get('description')

    course_ids = [int(cid) for cid in request.form.getlist('course_ids') if cid]
    teacher_ids = [int(tid) for tid in request.form.getlist('teacher_ids') if tid]
    classroom.courses = Course.query.filter(Course.id.in_(course_ids)).all()
    classroom.teachers = User.query.filter(User.id.in_(teacher_ids)).all()

    db.session.commit()
    flash('Sınıf bilgileri güncellendi.', 'success')
    return redirect(url_for('supervisor.classes_view'))


@supervisor_bp.route('/siniflar/<int:class_id>/sil', methods=['POST'])
@role_required('supervisor')
def delete_class(class_id):
    classroom = ClassRoom.query.get_or_404(class_id)
    db.session.delete(classroom)
    db.session.commit()
    flash('Sınıf silindi.', 'info')
    return redirect(url_for('supervisor.classes_view'))


# ------------------ STUDENTS ------------------ #
@supervisor_bp.route('/ogrenciler')
@role_required('supervisor')
def students_view():
    classes = ClassRoom.query.order_by(ClassRoom.name).all()
    courses = Course.query.order_by(Course.name).all()
    class_filter = request.args.get('class_id', type=int)
    course_filter = request.args.get('course_id', type=int)

    students_query = Student.query
    if class_filter:
        students_query = students_query.filter_by(classroom_id=class_filter)
    if course_filter:
        students_query = students_query.join(Student.courses).filter(Course.id == course_filter)

    students = students_query.order_by(Student.full_name).all()
    generated_credentials = session.get('new_student_credentials', [])
    import_report = session.pop('last_import_report', None)

    return render_template(
        'supervisor/students.html',
        students=students,
        classes=classes,
        courses=courses,
        class_filter=class_filter,
        course_filter=course_filter,
        generated_credentials=generated_credentials,
        import_report=import_report,
    )


@supervisor_bp.route('/ogrenciler/ekle', methods=['POST'])
@role_required('supervisor')
def add_student():
    full_name = request.form.get('full_name')
    student_number = request.form.get('student_number')
    classroom_id = request.form.get('classroom_id', type=int)
    course_ids = [int(cid) for cid in request.form.getlist('course_ids') if cid]
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    email_generated = False
    password_generated = False

    if not email or not password:
        generated_email, generated_password = generate_student_credentials(full_name, student_number)
        if not email:
            email = generated_email
            email_generated = True
        if not password:
            password = generated_password
            password_generated = True

    if Student.query.filter_by(student_number=student_number).first():
        flash('Bu okul numarası zaten kayıtlı.', 'danger')
        return redirect(url_for('supervisor.students_view'))

    user = None
    if email:
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.role != 'student':
                flash('Bu e-posta farklı bir kullanıcıya ait.', 'danger')
                return redirect(url_for('supervisor.students_view'))
            user = existing_user
            if password:
                user.password_hash = generate_password_hash(password)
        else:
            user = User(full_name=full_name, email=email, role='student')
            user.password_hash = generate_password_hash(password)
            db.session.add(user)
            db.session.flush()

    student = Student(full_name=full_name, student_number=student_number, classroom_id=classroom_id)
    if user:
        student.user_id = user.id
        user.full_name = full_name
    student.courses = Course.query.filter(Course.id.in_(course_ids)).all()
    db.session.add(student)
    db.session.commit()

    if email_generated or password_generated:
        _store_generated_credentials(
            full_name,
            student_number,
            email,
            password,
            email_generated,
            password_generated,
        )

    flash('Öğrenci eklendi.', 'success')
    return redirect(url_for('supervisor.students_view'))


@supervisor_bp.route('/ogrenciler/<int:student_id>/duzenle', methods=['POST'])
@role_required('supervisor')
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    student.full_name = request.form.get('full_name')
    student.student_number = request.form.get('student_number')
    student.classroom_id = request.form.get('classroom_id', type=int)
    course_ids = [int(cid) for cid in request.form.getlist('course_ids') if cid]
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    email_generated = False
    password_generated = False

    if not email or not password:
        generated_email, generated_password = generate_student_credentials(
            student.full_name,
            student.student_number,
        )
        if not email:
            email = generated_email
            email_generated = True
        if not password:
            password = generated_password
            password_generated = True

    student.courses = Course.query.filter(Course.id.in_(course_ids)).all()

    if email:
        existing_user = User.query.filter_by(email=email).first()
        current_user_id = student.user.id if student.user else None
        if existing_user and existing_user.id != current_user_id:
            if existing_user.role != 'student':
                flash('Bu e-posta farklı bir kullanıcıya ait.', 'danger')
                return redirect(url_for('supervisor.students_view'))
            student.user = existing_user
        if not student.user:
            user = User(full_name=student.full_name, email=email, role='student')
            user.password_hash = generate_password_hash(password)
            db.session.add(user)
            db.session.flush()
            student.user = user
        else:
            student.user.email = email
            if password:
                student.user.password_hash = generate_password_hash(password)
        student.user.full_name = student.full_name
    elif student.user:
        student.user.full_name = student.full_name

    if email_generated or password_generated:
        _store_generated_credentials(
            student.full_name,
            student.student_number,
            email,
            password,
            email_generated,
            password_generated,
        )

    db.session.commit()
    flash('Öğrenci güncellendi.', 'success')
    return redirect(url_for('supervisor.students_view'))


@supervisor_bp.route('/ogrenciler/yeni-kimlik-bilgileri.csv')
@role_required('supervisor')
def download_generated_credentials():
    credentials = session.get('new_student_credentials', [])
    if not credentials:
        flash('İndirilecek yeni kimlik bilgisi bulunmuyor.', 'info')
        return redirect(url_for('supervisor.students_view'))

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ad Soyad', 'Okul No', 'E-posta', 'Şifre', 'E-posta Otomatik', 'Şifre Otomatik'])
    for item in credentials:
        writer.writerow(
            [
                item.get('full_name', ''),
                item.get('student_number', ''),
                item.get('email', ''),
                item.get('password', ''),
                'Evet' if item.get('auto_email') else 'Hayır',
                'Evet' if item.get('auto_password') else 'Hayır',
            ]
        )

    output.seek(0)
    filename = f"ogrenci_kimlikleri_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv; charset=utf-8',
    )


def _store_generated_credentials(
    full_name: str,
    student_number: str,
    email: str,
    password: str,
    auto_email: bool,
    auto_password: bool,
) -> None:
    credentials = session.get('new_student_credentials', [])
    credentials.append(
        {
            'full_name': full_name,
            'student_number': student_number,
            'email': email,
            'password': password,
            'auto_email': auto_email,
            'auto_password': auto_password,
        }
    )
    session['new_student_credentials'] = credentials


@supervisor_bp.route('/ogrenciler/<int:student_id>/sil', methods=['POST'])
@role_required('supervisor')
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash('Öğrenci silindi.', 'info')
    return redirect(url_for('supervisor.students_view'))


@supervisor_bp.route('/ogrenciler/iceri-aktar', methods=['POST'])
@role_required('supervisor')
def import_students():
    file = request.files.get('file')
    if not file or not file.filename:
        flash('Lütfen bir dosya seçin.', 'warning')
        return redirect(url_for('supervisor.students_view'))

    try:
        source_label, students_data = _parse_student_file(file)
        if not students_data:
            raise ValueError('Dosyada aktarılabilir öğrenci verisi bulunamadı.')
        result = _bulk_create_students(students_data)
    except Exception as exc:  # noqa: BLE001
        flash(str(exc), 'danger')
        return redirect(url_for('supervisor.students_view'))

    for credential in result['credentials']:
        _store_generated_credentials(**credential)

    session['last_import_report'] = {
        'source': source_label,
        'total': len(students_data),
        'created': result['created'],
        'skipped_rows': result['skipped_rows'],
    }

    if result['created']:
        flash(
            f"{result['created']} öğrenci {source_label} dosyasından başarıyla aktarıldı.",
            'success',
        )
    if result['skipped_rows']:
        flash(
            f"{len(result['skipped_rows'])} satır atlandı. Ayrıntılar sonuç panelinde listelendi.",
            'warning',
        )
    return redirect(url_for('supervisor.students_view'))


def _parse_student_file(file_storage):
    filename = (file_storage.filename or '').lower()
    extension = Path(filename).suffix
    mimetype = (file_storage.mimetype or '').lower()

    if extension == '.csv':
        return 'CSV', parse_csv(file_storage)
    if extension in {'.xls', '.xlsx'}:
        return 'Excel', parse_excel(file_storage)
    if extension == '.pdf':
        return 'PDF', parse_pdf(file_storage)

    if 'pdf' in mimetype:
        return 'PDF', parse_pdf(file_storage)
    if 'excel' in mimetype or 'spreadsheet' in mimetype:
        return 'Excel', parse_excel(file_storage)
    if 'csv' in mimetype or mimetype == 'text/plain':
        return 'CSV', parse_csv(file_storage)

    raise ValueError('Desteklenmeyen dosya türü. Lütfen CSV, Excel veya PDF yükleyin.')


def _bulk_create_students(students_data):
    created_count = 0
    skipped_rows = []
    generated_credentials = []

    for fallback_index, student_info in enumerate(students_data, start=2):
        row_number = student_info.get('source_row', fallback_index)
        student_number = student_info.get('student_number', '').strip()
        if not student_number:
            skipped_rows.append({'row': row_number, 'reason': 'Okul numarası eksik.'})
            continue

        existing = Student.query.filter_by(student_number=student_number).first()
        if existing:
            skipped_rows.append({'row': row_number, 'reason': 'Okul numarası zaten kayıtlı.'})
            continue

        class_name = student_info.get('class_name', '').strip() or 'Genel'
        classroom = ClassRoom.query.filter_by(name=class_name).first()
        if not classroom:
            classroom = ClassRoom(name=class_name)
            db.session.add(classroom)
            db.session.flush()

        full_name = student_info.get('full_name', '').strip() or 'İsimsiz Öğrenci'
        email, password = generate_student_credentials(full_name, student_number)

        user = User(full_name=full_name, email=email, role='student')
        user.password_hash = generate_password_hash(password)
        db.session.add(user)
        db.session.flush()

        student = Student(
            full_name=full_name,
            student_number=student_number,
            classroom_id=classroom.id,
            user_id=user.id,
        )
        student.courses = list(classroom.courses)
        db.session.add(student)

        generated_credentials.append(
            {
                'full_name': full_name,
                'student_number': student_number,
                'email': email,
                'password': password,
                'auto_email': True,
                'auto_password': True,
            }
        )
        created_count += 1

    db.session.commit()

    return {
        'created': created_count,
        'skipped_rows': skipped_rows,
        'credentials': generated_credentials,
    }


# ------------------ ATTENDANCE ------------------ #
@supervisor_bp.route('/yoklamalar')
@role_required('supervisor')
def attendance_overview():
    classes = ClassRoom.query.order_by(ClassRoom.name).all()
    courses = Course.query.order_by(Course.name).all()
    teachers = User.query.filter_by(role='teacher').order_by(User.full_name).all()

    class_filter = request.args.get('class_id', type=int)
    course_filter = request.args.get('course_id', type=int)
    teacher_filter = request.args.get('teacher_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    records_query = AttendanceRecord.query.order_by(AttendanceRecord.session_date.desc())
    if class_filter:
        records_query = records_query.filter_by(classroom_id=class_filter)
    if course_filter:
        records_query = records_query.filter_by(course_id=course_filter)
    if teacher_filter:
        records_query = records_query.filter_by(teacher_id=teacher_filter)
    if date_from:
        try:
            start = datetime.strptime(date_from, '%Y-%m-%d')
            records_query = records_query.filter(AttendanceRecord.session_date >= start)
        except ValueError:
            flash('Başlangıç tarihi geçersiz.', 'warning')
    if date_to:
        try:
            end = datetime.strptime(date_to, '%Y-%m-%d')
            records_query = records_query.filter(AttendanceRecord.session_date <= end)
        except ValueError:
            flash('Bitiş tarihi geçersiz.', 'warning')

    records = records_query.all()
    return render_template(
        'supervisor/attendance.html',
        records=records,
        classes=classes,
        courses=courses,
        teachers=teachers,
        class_filter=class_filter,
        course_filter=course_filter,
        teacher_filter=teacher_filter,
        date_from=date_from,
        date_to=date_to,
    )


@supervisor_bp.route('/yoklamalar/<int:record_id>/duzenle', methods=['GET', 'POST'])
@role_required('supervisor')
def edit_attendance(record_id):
    record = AttendanceRecord.query.get_or_404(record_id)
    if request.method == 'POST':
        for entry in record.entries:
            status = request.form.get(f'status_{entry.id}')
            if status in {'present', 'excused', 'absent'}:
                entry.status = status
        db.session.commit()
        flash('Yoklama güncellendi.', 'success')
        return redirect(url_for('supervisor.attendance_overview'))
    return render_template('supervisor/attendance_edit.html', record=record)


@supervisor_bp.route('/yoklamalar/indir/csv')
@role_required('supervisor')
def export_attendance_csv():
    records = _filtered_records()
    buffer = generate_csv(records)
    filename = f"yoklamalar_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv; charset=utf-8',
    )


@supervisor_bp.route('/yoklamalar/indir/pdf')
@role_required('supervisor')
def export_attendance_pdf():
    records = _filtered_records()
    buffer = generate_pdf(records)
    filename = f"yoklamalar_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


def _filtered_records():
    class_filter = request.args.get('class_id', type=int)
    course_filter = request.args.get('course_id', type=int)
    teacher_filter = request.args.get('teacher_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    records_query = AttendanceRecord.query.order_by(AttendanceRecord.session_date.desc())
    if class_filter:
        records_query = records_query.filter_by(classroom_id=class_filter)
    if course_filter:
        records_query = records_query.filter_by(course_id=course_filter)
    if teacher_filter:
        records_query = records_query.filter_by(teacher_id=teacher_filter)
    if date_from:
        try:
            start = datetime.strptime(date_from, '%Y-%m-%d')
            records_query = records_query.filter(AttendanceRecord.session_date >= start)
        except ValueError:
            pass
    if date_to:
        try:
            end = datetime.strptime(date_to, '%Y-%m-%d')
            records_query = records_query.filter(AttendanceRecord.session_date <= end)
        except ValueError:
            pass

    return records_query.all()
