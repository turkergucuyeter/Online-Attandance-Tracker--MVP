from flask import Blueprint, redirect, url_for
from flask_login import current_user


general_bp = Blueprint('general', __name__)


@general_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_supervisor():
            return redirect(url_for('supervisor.dashboard'))
        if current_user.is_teacher():
            return redirect(url_for('teacher.dashboard'))
        if current_user.is_student():
            return redirect(url_for('student.dashboard'))
    return redirect(url_for('auth.login'))
