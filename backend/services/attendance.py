import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .. import db
from . import audit, notifications

STATUS_LABELS = {
    'present': 'Var',
    'excused': 'İzinli',
    'unexcused': 'İzinsiz'
}


def get_feature_flags() -> Dict[str, Dict]:
    rows = db.fetch_all("SELECT key, value_json FROM feature_flags")
    return {row['key']: json.loads(row['value_json']) for row in rows}


def absence_should_count(status: str, flags: Dict[str, Dict]) -> bool:
    only_unexcused = flags.get('absence_only_unexcused', {}).get('enabled', False)
    if only_unexcused:
        return status == 'unexcused'
    return status != 'present'


def get_grace_period_minutes(flags: Dict[str, Dict]) -> int:
    return int(flags.get('attendance_grace_period', {}).get('minutes', 0))


def lock_session_if_needed(session_id: int, current_time: datetime):
    session = db.fetch_one("SELECT id, date, start_time, end_time, is_locked FROM schedule_sessions WHERE id = ?", (session_id,))
    if not session:
        return
    if session['is_locked']:
        return
    flags = get_feature_flags()
    grace = get_grace_period_minutes(flags)
    end_dt = datetime.fromisoformat(f"{session['date']}T{session['end_time']}") + timedelta(minutes=grace)
    if current_time >= end_dt:
        db.execute("UPDATE schedule_sessions SET is_locked = 1 WHERE id = ?", (session_id,))


def upsert_attendance(session_id: int, student_id: int, status: str, teacher_id: int):
    existing = db.fetch_one(
        "SELECT id FROM attendances WHERE schedule_session_id = ? AND student_id = ?",
        (session_id, student_id)
    )
    if existing:
        db.execute(
            "UPDATE attendances SET status = ?, taken_by = ?, updated_at = datetime('now') WHERE id = ?",
            (status, teacher_id, existing['id'])
        )
    else:
        db.execute(
            "INSERT INTO attendances (schedule_session_id, student_id, status, taken_by) VALUES (?, ?, ?, ?)",
            (session_id, student_id, status, teacher_id)
        )


def calculate_percentages_for_course(course_id: int, student_id: Optional[int] = None):
    params = [course_id]
    student_filter = ''
    if student_id is not None:
        params.append(student_id)
        student_filter = ' AND a.student_id = ?'

    rows = db.fetch_all(
        f"""
        SELECT a.student_id, 
               SUM(CASE WHEN a.status != 'present' THEN 1 ELSE 0 END) AS total_absent,
               SUM(CASE WHEN a.status = 'unexcused' THEN 1 ELSE 0 END) AS total_unexcused,
               COUNT(*) AS total_sessions
        FROM attendances a
        JOIN schedule_sessions s ON s.id = a.schedule_session_id
        WHERE s.course_id = ?{student_filter}
        GROUP BY a.student_id
        """,
        params
    )
    return rows


def get_course_threshold(course_id: int) -> float:
    row = db.fetch_one(
        "SELECT t.absence_threshold_percent AS threshold FROM schedule_sessions s JOIN terms t ON t.id = s.term_id WHERE s.course_id = ? LIMIT 1",
        (course_id,)
    )
    if row:
        return float(row['threshold'])
    term = db.fetch_one("SELECT absence_threshold_percent FROM terms ORDER BY id DESC LIMIT 1")
    return float(term['absence_threshold_percent']) if term else 30.0


def evaluate_thresholds_for_session(session_id: int, teacher_id: int):
    flags = get_feature_flags()
    rows = db.fetch_all(
        """
        SELECT a.student_id, a.status, s.course_id
        FROM attendances a
        JOIN schedule_sessions s ON s.id = a.schedule_session_id
        WHERE a.schedule_session_id = ?
        """,
        (session_id,)
    )
    for row in rows:
        course_id = row['course_id']
        student_id = row['student_id']
        percentages = calculate_percentages_for_course(course_id, student_id)
        if not percentages:
            continue
        stats = percentages[0]
        total_sessions = stats['total_sessions']
        if total_sessions == 0:
            continue
        total_absences = stats['total_absent']
        total_unexcused = stats['total_unexcused']
        threshold = get_course_threshold(course_id)
        count_value = total_unexcused if flags.get('absence_only_unexcused', {}).get('enabled') else total_absences
        percent = (count_value / total_sessions) * 100
        if percent >= threshold:
            course = db.fetch_one("SELECT name FROM courses WHERE id = ?", (course_id,))
            student = db.fetch_one("SELECT name FROM users WHERE id = ?", (student_id,))
            title = f"{course['name']} dersinde devamsızlık uyarısı"
            body = f"{student['name']} için devamsızlık oranı %{percent:.1f} seviyesine ulaştı (eşik %{threshold})."
            notifications.create_notification(student_id, 'inapp', title, body)
            notifications.create_notification(student_id, 'webpush', title, body)
            audit.log_action(teacher_id, 'absence_threshold_triggered', 'attendance', str(session_id), {
                'student_id': student_id,
                'percent': percent,
                'threshold': threshold
            })


def list_attendance_for_session(session_id: int):
    return db.fetch_all(
        """
        SELECT a.id, a.student_id, u.name AS student_name, a.status, a.updated_at
        FROM class_students cs
        JOIN students st ON st.id = cs.student_id
        JOIN users u ON u.id = st.id
        LEFT JOIN attendances a ON a.student_id = st.id AND a.schedule_session_id = ?
        WHERE cs.class_id = (
            SELECT c.id FROM schedule_sessions s JOIN courses c ON c.id = s.course_id WHERE s.id = ?
        )
        ORDER BY u.name
        """,
        (session_id, session_id)
    )
