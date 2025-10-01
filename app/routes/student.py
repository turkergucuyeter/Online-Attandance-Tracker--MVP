from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from .. import db
from ..models import Student, attendance_statistics_for_student
from ..utils.decorators import role_required


student_bp = Blueprint('student', __name__, url_prefix='/ogrenci')


@student_bp.route('/panel')
@role_required('student')
def dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    raw_stats = attendance_statistics_for_student(student)
    stats = []
    for data in raw_stats.values():
        total = data['total'] or 0
        excused_pct = (data['excused'] / total * 100) if total else 0
        absent_pct = (data['absent'] / total * 100) if total else 0
        warnings = []
        if total:
            if excused_pct > data['course'].max_excused_percentage:
                warnings.append('Mazeretli devamsızlık sınırını aştınız.')
            if absent_pct > data['course'].max_unexcused_percentage:
                warnings.append('Mazeretsiz devamsızlık sınırını aştınız!')
        stats.append(
            {
                'course': data['course'],
                'total': total,
                'present': data['present'],
                'excused': data['excused'],
                'absent': data['absent'],
                'excused_pct': round(excused_pct, 1),
                'absent_pct': round(absent_pct, 1),
                'warnings': warnings,
            }
        )
    return render_template('student/dashboard.html', student=student, stats=stats)


@student_bp.route('/sifre', methods=['GET', 'POST'])
@role_required('student')
def change_password():
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        new_password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not new_password:
            flash('Yeni şifre girmelisiniz.', 'warning')
        elif len(new_password) < 8:
            flash('Şifreniz en az 8 karakter olmalıdır.', 'warning')
        elif new_password != confirm_password:
            flash('Şifreler eşleşmiyor.', 'danger')
        else:
            student.user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Şifreniz başarıyla güncellendi.', 'success')
            return redirect(url_for('student.change_password'))

    return render_template('student/change_password.html', student=student)
