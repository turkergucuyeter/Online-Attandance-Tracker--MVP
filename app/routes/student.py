from flask import Blueprint, render_template
from flask_login import current_user

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
