from datetime import datetime, timedelta

from . import db, migrate
from .utils.security import hash_password


def upsert_user(role: str, name: str, email: str, password: str):
    existing = db.fetch_one('SELECT id FROM users WHERE email = ?', (email,))
    if existing:
        return existing['id']
    return db.execute_and_return_id(
        "INSERT INTO users (role, name, email, password_hash) VALUES (?, ?, ?, ?)",
        (role, name, email, hash_password(password))
    )


def main():
    migrate.main()

    supervisor_id = upsert_user('supervisor', 'Seda Yönetici', 'supervisor@example.com', 'Supervisor123!')
    teacher_id = upsert_user('teacher', 'Talha Öğretmen', 'teacher@example.com', 'Teacher123!')
    student_id = upsert_user('student', 'Ayşe Öğrenci', 'student@example.com', 'Student123!')

    if not db.fetch_one('SELECT id FROM teachers WHERE id = ?', (teacher_id,)):
        db.execute('INSERT INTO teachers (id, display_color) VALUES (?, ?)', (teacher_id, '#f97316'))

    if not db.fetch_one('SELECT id FROM students WHERE id = ?', (student_id,)):
        db.execute('INSERT INTO students (id, student_no, guardian_contact) VALUES (?, ?, ?)', (student_id, '2025001', 'veli@example.com'))

    class_id = db.execute_and_return_id(
        "INSERT INTO classes (name, grade, branch, created_by) VALUES (?, ?, ?, ?)",
        ('10-A', 10, 'A', supervisor_id)
    ) if not db.fetch_one('SELECT id FROM classes WHERE name = ?', ('10-A',)) else db.fetch_one('SELECT id FROM classes WHERE name = ?', ('10-A',))['id']

    if not db.fetch_one('SELECT id FROM class_students WHERE class_id = ? AND student_id = ?', (class_id, student_id)):
        db.execute('INSERT INTO class_students (class_id, student_id) VALUES (?, ?)', (class_id, student_id))

    course = db.fetch_one('SELECT id FROM courses WHERE code = ?', ('MAT101',))
    if course:
        course_id = course['id']
    else:
        course_id = db.execute_and_return_id(
            "INSERT INTO courses (class_id, name, code, teacher_id, weekly_hours) VALUES (?, ?, ?, ?, ?)",
            (class_id, 'Matematik', 'MAT101', teacher_id, 4)
        )

    term = db.fetch_one('SELECT id FROM terms WHERE name = ?', ('2024-2025 Güz',))
    if term:
        term_id = term['id']
    else:
        term_id = db.execute_and_return_id(
            "INSERT INTO terms (name, start_date, end_date, absence_threshold_percent) VALUES (?, ?, ?, ?)",
            ('2024-2025 Güz', '2024-09-01', '2025-01-31', 30)
        )

    if not db.fetch_one('SELECT id FROM schedule_sessions WHERE date = ? AND course_id = ?', ('2025-02-01', course_id)):
        db.execute(
            "INSERT INTO schedule_sessions (course_id, term_id, date, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
            (course_id, term_id, '2025-02-01', '09:00', '09:45')
        )

    if not db.fetch_one('SELECT key FROM feature_flags WHERE key = ?', ('attendance_grace_period',)):
        db.execute(
            "INSERT INTO feature_flags (key, value_json) VALUES (?, ?)",
            ('attendance_grace_period', '{"minutes": 15}')
        )
    if not db.fetch_one('SELECT key FROM feature_flags WHERE key = ?', ('absence_only_unexcused',)):
        db.execute(
            "INSERT INTO feature_flags (key, value_json) VALUES (?, ?)",
            ('absence_only_unexcused', '{"enabled": false}')
        )

    print('Seed verileri yüklendi.')


if __name__ == '__main__':
    main()
