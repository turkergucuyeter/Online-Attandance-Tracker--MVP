import csv
import json
import os
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from . import db
from .services import attendance, audit, notifications
from .utils.http import parse_json_body, send_json, send_no_content
from .utils.security import decode_jwt, encode_jwt, hash_password, verify_password

JWT_SECRET = os.getenv('JWT_SECRET', 'super-secret-key')
SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.getenv('SERVER_PORT', '8000'))


class Route:
    def __init__(self, method: str, path: str, handler: Callable[["AppHandler", Dict[str, str]], None], roles: Optional[List[str]] = None):
        self.method = method
        self.path = path
        self.handler = handler
        self.roles = roles


class AppHandler(BaseHTTPRequestHandler):
    routes: List[Route] = []

    def log_message(self, format: str, *args: Any) -> None:
        return

    def end_headers(self) -> None:
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PATCH(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def _dispatch(self):
        parsed = urlparse(self.path)
        for route in self.routes:
            params = self._match_route(route.path, parsed.path)
            if params is not None and self.command == route.method:
                if route.roles:
                    identity = self.authenticate(route.roles)
                    if not identity:
                        return
                    self.identity = identity
                else:
                    self.identity = None
                self.query = parse_qs(parsed.query)
                route.handler(self, params)
                return
        self.send_error(HTTPStatus.NOT_FOUND, 'Bulunamadı')

    def _match_route(self, route_path: str, request_path: str) -> Optional[Dict[str, str]]:
        route_parts = route_path.strip('/').split('/') if route_path != '/' else ['']
        request_parts = request_path.strip('/').split('/') if request_path != '/' else ['']
        if len(route_parts) != len(request_parts):
            return None
        params: Dict[str, str] = {}
        for route_part, req_part in zip(route_parts, request_parts):
            if route_part.startswith(':'):
                params[route_part[1:]] = req_part
            elif route_part != req_part:
                return None
        return params

    def authenticate(self, roles: List[str]):
        auth = self.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '):
            self.send_error(HTTPStatus.UNAUTHORIZED, 'Yetkisiz erişim')
            return None
        token = auth.split(' ')[1]
        try:
            payload = decode_jwt(token, JWT_SECRET)
        except Exception:
            self.send_error(HTTPStatus.UNAUTHORIZED, 'Geçersiz oturum')
            return None
        user = db.fetch_one('SELECT id, role, name, email, is_active FROM users WHERE id = ?', (payload['sub'],))
        if not user or not user['is_active']:
            self.send_error(HTTPStatus.UNAUTHORIZED, 'Kullanıcı pasif')
            return None
        if user['role'] not in roles:
            self.send_error(HTTPStatus.FORBIDDEN, 'Yetkiniz yok')
            return None
        return user


def route(method: str, path: str, roles: Optional[List[str]] = None):
    def decorator(func: Callable[[AppHandler, Dict[str, str]], None]):
        AppHandler.routes.append(Route(method, path, func, roles))
        return func
    return decorator


@route('POST', '/auth/login')
def login(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Email ve şifre zorunludur')
        return
    user = db.fetch_one('SELECT id, role, name, email, password_hash FROM users WHERE email = ?', (email.lower(),))
    if not user or not verify_password(password, user['password_hash']):
        handler.send_error(HTTPStatus.UNAUTHORIZED, 'Geçersiz bilgiler')
        return
    token = encode_jwt({'sub': user['id'], 'role': user['role']}, JWT_SECRET, expires_in=12 * 3600)
    send_json(handler, {
        'token': token,
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role']
        }
    })


@route('GET', '/notifications', roles=['supervisor', 'teacher', 'student'])
def get_notifications(handler: AppHandler, params: Dict[str, str]):
    data = notifications.list_notifications(handler.identity['id'])
    send_json(handler, data)


@route('POST', '/notifications/:id/read', roles=['supervisor', 'teacher', 'student'])
def read_notification(handler: AppHandler, params: Dict[str, str]):
    notifications.mark_as_read(int(params['id']), handler.identity['id'])
    send_no_content(handler)


@route('POST', '/notifications/test', roles=['supervisor'])
def create_test_notification(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    title = data.get('title', 'Test bildirimi')
    body = data.get('body', 'Bu bir test mesajıdır')
    target_user = data.get('user_id', handler.identity['id'])
    notifications.create_notification(target_user, 'inapp', title, body)
    send_no_content(handler)


# Supervisor routes

@route('GET', '/supervisor/teachers', roles=['supervisor'])
def list_teachers(handler: AppHandler, params: Dict[str, str]):
    rows = db.fetch_all(
        """
        SELECT t.id, u.name, u.email, t.display_color, u.is_active
        FROM teachers t
        JOIN users u ON u.id = t.id
        ORDER BY u.name
        """
    )
    send_json(handler, rows)


@route('POST', '/supervisor/teachers', roles=['supervisor'])
def create_teacher(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    name = data.get('name')
    email = data.get('email')
    password = data.get('password', 'Ogretmen123!')
    color = data.get('display_color', '#2563eb')
    if not name or not email:
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Zorunlu alanlar eksik')
        return
    email = email.lower()
    hashed = hash_password(password)
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO users (role, name, email, password_hash) VALUES ('teacher', ?, ?, ?)",
            (name, email, hashed)
        )
        teacher_id = cur.lastrowid
        conn.execute(
            "INSERT INTO teachers (id, display_color) VALUES (?, ?)",
            (teacher_id, color)
        )
    audit.log_action(handler.identity['id'], 'create', 'teacher', str(teacher_id), {'email': email})
    send_json(handler, {'id': teacher_id}, status=HTTPStatus.CREATED)


@route('PATCH', '/supervisor/teachers/:id', roles=['supervisor'])
def update_teacher(handler: AppHandler, params: Dict[str, str]):
    teacher_id = int(params['id'])
    data = parse_json_body(handler)
    if data is None:
        return
    updates = []
    values: List[Any] = []
    if 'name' in data:
        updates.append('name = ?')
        values.append(data['name'])
    if 'email' in data:
        updates.append('email = ?')
        values.append(data['email'].lower())
    if 'password' in data:
        updates.append('password_hash = ?')
        values.append(hash_password(data['password']))
    if updates:
        values.append(teacher_id)
        db.execute(f"UPDATE users SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?", values)
    if 'display_color' in data:
        db.execute("UPDATE teachers SET display_color = ? WHERE id = ?", (data['display_color'], teacher_id))
    audit.log_action(handler.identity['id'], 'update', 'teacher', str(teacher_id), data)
    send_no_content(handler)


@route('DELETE', '/supervisor/teachers/:id', roles=['supervisor'])
def delete_teacher(handler: AppHandler, params: Dict[str, str]):
    teacher_id = int(params['id'])
    db.execute('DELETE FROM users WHERE id = ?', (teacher_id,))
    audit.log_action(handler.identity['id'], 'delete', 'teacher', str(teacher_id))
    send_no_content(handler)


@route('GET', '/supervisor/students', roles=['supervisor'])
def list_students(handler: AppHandler, params: Dict[str, str]):
    rows = db.fetch_all(
        """
        SELECT s.id, u.name, u.email, s.student_no, s.guardian_contact, u.is_active
        FROM students s
        JOIN users u ON u.id = s.id
        ORDER BY u.name
        """
    )
    send_json(handler, rows)


@route('POST', '/supervisor/students', roles=['supervisor'])
def create_student(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    name = data.get('name')
    email = data.get('email')
    student_no = data.get('student_no')
    guardian = data.get('guardian_contact')
    password = data.get('password', 'Ogrenci123!')
    if not name or not email or not student_no:
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Zorunlu alanlar eksik')
        return
    hashed = hash_password(password)
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO users (role, name, email, password_hash) VALUES ('student', ?, ?, ?)",
            (name, email.lower(), hashed)
        )
        student_id = cur.lastrowid
        conn.execute(
            "INSERT INTO students (id, student_no, guardian_contact) VALUES (?, ?, ?)",
            (student_id, student_no, guardian)
        )
    audit.log_action(handler.identity['id'], 'create', 'student', str(student_id), {'student_no': student_no})
    send_json(handler, {'id': student_id}, status=HTTPStatus.CREATED)


@route('POST', '/supervisor/students/bulk', roles=['supervisor'])
def bulk_students(handler: AppHandler, params: Dict[str, str]):
    data = handler.rfile.read(int(handler.headers.get('Content-Length', 0))).decode('utf-8')
    reader = csv.DictReader(data.splitlines())
    inserted, errors = [], []
    for index, row in enumerate(reader, start=1):
        try:
            name = row['name']
            email = row['email'].lower()
            student_no = row['student_no']
        except KeyError:
            errors.append({'line': index, 'error': 'Eksik sütun'})
            continue
        try:
            with db.transaction() as conn:
                cur = conn.execute(
                    "INSERT INTO users (role, name, email, password_hash) VALUES ('student', ?, ?, ?)",
                    (name, email, hash_password('Ogrenci123!'))
                )
                student_id = cur.lastrowid
                conn.execute(
                    "INSERT INTO students (id, student_no) VALUES (?, ?)",
                    (student_id, student_no)
                )
            inserted.append(student_no)
        except Exception as exc:  # broad
            errors.append({'line': index, 'error': str(exc)})
    audit.log_action(handler.identity['id'], 'bulk_create', 'student', None, {'inserted': inserted, 'errors': errors})
    send_json(handler, {'inserted': inserted, 'errors': errors})


@route('PATCH', '/supervisor/students/:id', roles=['supervisor'])
def update_student(handler: AppHandler, params: Dict[str, str]):
    student_id = int(params['id'])
    data = parse_json_body(handler)
    if data is None:
        return
    updates_user = []
    values_user: List[Any] = []
    if 'name' in data:
        updates_user.append('name = ?')
        values_user.append(data['name'])
    if 'email' in data:
        updates_user.append('email = ?')
        values_user.append(data['email'].lower())
    if 'password' in data:
        updates_user.append('password_hash = ?')
        values_user.append(hash_password(data['password']))
    if updates_user:
        values_user.append(student_id)
        db.execute(f"UPDATE users SET {', '.join(updates_user)}, updated_at = datetime('now') WHERE id = ?", values_user)
    updates_student = []
    values_student: List[Any] = []
    if 'student_no' in data:
        updates_student.append('student_no = ?')
        values_student.append(data['student_no'])
    if 'guardian_contact' in data:
        updates_student.append('guardian_contact = ?')
        values_student.append(data['guardian_contact'])
    if updates_student:
        values_student.append(student_id)
        db.execute(f"UPDATE students SET {', '.join(updates_student)} WHERE id = ?", values_student)
    audit.log_action(handler.identity['id'], 'update', 'student', str(student_id), data)
    send_no_content(handler)


@route('DELETE', '/supervisor/students/:id', roles=['supervisor'])
def delete_student(handler: AppHandler, params: Dict[str, str]):
    student_id = int(params['id'])
    db.execute('DELETE FROM users WHERE id = ?', (student_id,))
    audit.log_action(handler.identity['id'], 'delete', 'student', str(student_id))
    send_no_content(handler)


@route('GET', '/supervisor/classes', roles=['supervisor'])
def list_classes(handler: AppHandler, params: Dict[str, str]):
    rows = db.fetch_all(
        """
        SELECT c.id, c.name, c.grade, c.branch, c.created_at,
               u.name AS supervisor_name
        FROM classes c
        JOIN users u ON u.id = c.created_by
        ORDER BY c.grade, c.branch
        """
    )
    send_json(handler, rows)


@route('POST', '/supervisor/classes', roles=['supervisor'])
def create_class(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    required = ['name', 'grade', 'branch']
    if not all(field in data for field in required):
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Zorunlu alanlar eksik')
        return
    class_id = db.execute_and_return_id(
        "INSERT INTO classes (name, grade, branch, created_by) VALUES (?, ?, ?, ?)",
        (data['name'], data['grade'], data['branch'], handler.identity['id'])
    )
    audit.log_action(handler.identity['id'], 'create', 'class', str(class_id), data)
    send_json(handler, {'id': class_id}, status=HTTPStatus.CREATED)


@route('PATCH', '/supervisor/classes/:id', roles=['supervisor'])
def update_class(handler: AppHandler, params: Dict[str, str]):
    class_id = int(params['id'])
    data = parse_json_body(handler)
    if data is None:
        return
    updates = []
    values: List[Any] = []
    for field in ['name', 'grade', 'branch']:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])
    if updates:
        values.append(class_id)
        db.execute(f"UPDATE classes SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?", values)
    audit.log_action(handler.identity['id'], 'update', 'class', str(class_id), data)
    send_no_content(handler)


@route('DELETE', '/supervisor/classes/:id', roles=['supervisor'])
def delete_class(handler: AppHandler, params: Dict[str, str]):
    class_id = int(params['id'])
    db.execute('DELETE FROM classes WHERE id = ?', (class_id,))
    audit.log_action(handler.identity['id'], 'delete', 'class', str(class_id))
    send_no_content(handler)


@route('POST', '/supervisor/classes/:id/students', roles=['supervisor'])
def assign_student_to_class(handler: AppHandler, params: Dict[str, str]):
    class_id = int(params['id'])
    data = parse_json_body(handler)
    if data is None:
        return
    student_id = data.get('student_id')
    if not student_id:
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Öğrenci seçilmelidir')
        return
    db.execute(
        "INSERT OR REPLACE INTO class_students (class_id, student_id, aktif_mi) VALUES (?, ?, 1)",
        (class_id, student_id)
    )
    audit.log_action(handler.identity['id'], 'assign', 'class_student', f"{class_id}-{student_id}")
    send_no_content(handler)


@route('GET', '/supervisor/courses', roles=['supervisor'])
def list_courses(handler: AppHandler, params: Dict[str, str]):
    rows = db.fetch_all(
        """
        SELECT c.id, c.name, c.code, c.weekly_hours,
               cls.name AS class_name,
               u.name AS teacher_name,
               t.display_color
        FROM courses c
        JOIN classes cls ON cls.id = c.class_id
        JOIN teachers t ON t.id = c.teacher_id
        JOIN users u ON u.id = t.id
        ORDER BY cls.name, c.name
        """
    )
    send_json(handler, rows)


@route('POST', '/supervisor/courses', roles=['supervisor'])
def create_course(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    required = ['class_id', 'name', 'code', 'teacher_id']
    if not all(field in data for field in required):
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Zorunlu alanlar eksik')
        return
    course_id = db.execute_and_return_id(
        "INSERT INTO courses (class_id, name, code, teacher_id, weekly_hours) VALUES (?, ?, ?, ?, ?)",
        (data['class_id'], data['name'], data['code'], data['teacher_id'], data.get('weekly_hours', 1))
    )
    audit.log_action(handler.identity['id'], 'create', 'course', str(course_id), data)
    send_json(handler, {'id': course_id}, status=HTTPStatus.CREATED)


@route('PATCH', '/supervisor/courses/:id', roles=['supervisor'])
def update_course(handler: AppHandler, params: Dict[str, str]):
    course_id = int(params['id'])
    data = parse_json_body(handler)
    if data is None:
        return
    updates = []
    values: List[Any] = []
    for field in ['class_id', 'name', 'code', 'teacher_id', 'weekly_hours']:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])
    if updates:
        values.append(course_id)
        db.execute(f"UPDATE courses SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?", values)
    audit.log_action(handler.identity['id'], 'update', 'course', str(course_id), data)
    send_no_content(handler)


@route('DELETE', '/supervisor/courses/:id', roles=['supervisor'])
def delete_course(handler: AppHandler, params: Dict[str, str]):
    course_id = int(params['id'])
    db.execute('DELETE FROM courses WHERE id = ?', (course_id,))
    audit.log_action(handler.identity['id'], 'delete', 'course', str(course_id))
    send_no_content(handler)


@route('GET', '/supervisor/terms', roles=['supervisor'])
def list_terms(handler: AppHandler, params: Dict[str, str]):
    rows = db.fetch_all('SELECT id, name, start_date, end_date, absence_threshold_percent FROM terms ORDER BY start_date DESC')
    send_json(handler, rows)


@route('POST', '/supervisor/terms', roles=['supervisor'])
def create_term(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    required = ['name', 'start_date', 'end_date']
    if not all(field in data for field in required):
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Zorunlu alanlar eksik')
        return
    term_id = db.execute_and_return_id(
        "INSERT INTO terms (name, start_date, end_date, absence_threshold_percent) VALUES (?, ?, ?, ?)",
        (data['name'], data['start_date'], data['end_date'], data.get('absence_threshold_percent', 30))
    )
    audit.log_action(handler.identity['id'], 'create', 'term', str(term_id), data)
    send_json(handler, {'id': term_id}, status=HTTPStatus.CREATED)


@route('PATCH', '/supervisor/terms/:id', roles=['supervisor'])
def update_term(handler: AppHandler, params: Dict[str, str]):
    term_id = int(params['id'])
    data = parse_json_body(handler)
    if data is None:
        return
    updates = []
    values: List[Any] = []
    for field in ['name', 'start_date', 'end_date', 'absence_threshold_percent']:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])
    if updates:
        values.append(term_id)
        db.execute(f"UPDATE terms SET {', '.join(updates)} WHERE id = ?", values)
    audit.log_action(handler.identity['id'], 'update', 'term', str(term_id), data)
    send_no_content(handler)


@route('GET', '/supervisor/schedule-sessions', roles=['supervisor'])
def list_sessions(handler: AppHandler, params: Dict[str, str]):
    clauses = []
    values: List[Any] = []
    if 'courseId' in handler.query:
        clauses.append('course_id = ?')
        values.append(handler.query['courseId'][0])
    if 'termId' in handler.query:
        clauses.append('term_id = ?')
        values.append(handler.query['termId'][0])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    rows = db.fetch_all(
        f"SELECT id, course_id, term_id, date, start_time, end_time, is_locked FROM schedule_sessions {where} ORDER BY date",
        values
    )
    send_json(handler, rows)


@route('POST', '/supervisor/schedule-sessions', roles=['supervisor'])
def create_session(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    required = ['course_id', 'term_id', 'date', 'start_time', 'end_time']
    if not all(field in data for field in required):
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Zorunlu alanlar eksik')
        return
    session_id = db.execute_and_return_id(
        "INSERT INTO schedule_sessions (course_id, term_id, date, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
        (data['course_id'], data['term_id'], data['date'], data['start_time'], data['end_time'])
    )
    audit.log_action(handler.identity['id'], 'create', 'schedule_session', str(session_id), data)
    send_json(handler, {'id': session_id}, status=HTTPStatus.CREATED)


@route('GET', '/supervisor/reports/attendance', roles=['supervisor'])
def attendance_report(handler: AppHandler, params: Dict[str, str]):
    class_id = handler.query.get('classId', [None])[0]
    course_id = handler.query.get('courseId', [None])[0]
    date_from = handler.query.get('from', [None])[0]
    date_to = handler.query.get('to', [None])[0]
    format_type = handler.query.get('format', ['json'])[0]

    clauses = []
    values: List[Any] = []
    if class_id:
        clauses.append('cls.id = ?')
        values.append(class_id)
    if course_id:
        clauses.append('c.id = ?')
        values.append(course_id)
    if date_from:
        clauses.append('s.date >= ?')
        values.append(date_from)
    if date_to:
        clauses.append('s.date <= ?')
        values.append(date_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''

    rows = db.fetch_all(
        f"""
        SELECT cls.name AS class_name, c.name AS course_name, u.name AS student_name,
               SUM(CASE WHEN a.status != 'present' THEN 1 ELSE 0 END) AS total_absent,
               SUM(CASE WHEN a.status = 'unexcused' THEN 1 ELSE 0 END) AS total_unexcused,
               COUNT(a.id) AS total_sessions
        FROM attendances a
        JOIN schedule_sessions s ON s.id = a.schedule_session_id
        JOIN courses c ON c.id = s.course_id
        JOIN classes cls ON cls.id = c.class_id
        JOIN students st ON st.id = a.student_id
        JOIN users u ON u.id = st.id
        {where}
        GROUP BY cls.name, c.name, u.name
        ORDER BY cls.name, c.name, u.name
        """,
        values
    )
    if format_type == 'csv':
        import io

        handler.send_response(HTTPStatus.OK)
        handler.send_header('Content-Type', 'text/csv; charset=utf-8')
        handler.send_header('Content-Disposition', 'attachment; filename="yoklama_raporu.csv"')
        handler.end_headers()
        text_stream = io.TextIOWrapper(handler.wfile, encoding='utf-8', newline='')
        writer = csv.DictWriter(
            text_stream,
            fieldnames=['class_name', 'course_name', 'student_name', 'total_absent', 'total_unexcused', 'total_sessions']
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        text_stream.flush()
    else:
        send_json(handler, rows)


@route('GET', '/feature-flags', roles=['supervisor'])
def get_feature_flags(handler: AppHandler, params: Dict[str, str]):
    send_json(handler, attendance.get_feature_flags())


@route('PUT', '/feature-flags/:key', roles=['supervisor'])
def set_feature_flag(handler: AppHandler, params: Dict[str, str]):
    data = parse_json_body(handler)
    if data is None:
        return
    key = params['key']
    db.execute(
        "INSERT INTO feature_flags (key, value_json) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
        (key, json.dumps(data, ensure_ascii=False))
    )
    audit.log_action(handler.identity['id'], 'update', 'feature_flag', key, data)
    send_no_content(handler)


# Teacher endpoints


def ensure_teacher_session_access(handler: AppHandler, session_id: int):
    session = db.fetch_one(
        """
        SELECT s.id, s.course_id, s.date, s.start_time, s.end_time, s.is_locked, c.class_id, c.name AS course_name
        FROM schedule_sessions s
        JOIN courses c ON c.id = s.course_id
        WHERE s.id = ? AND c.teacher_id = ?
        """,
        (session_id, handler.identity['id'])
    )
    if not session:
        handler.send_error(HTTPStatus.FORBIDDEN, 'Derse erişim yetkiniz yok')
        return None
    return session


@route('GET', '/teacher/classes', roles=['teacher'])
def teacher_classes(handler: AppHandler, params: Dict[str, str]):
    rows = db.fetch_all(
        """
        SELECT DISTINCT cls.id, cls.name, cls.grade, cls.branch, t.display_color
        FROM courses c
        JOIN classes cls ON cls.id = c.class_id
        JOIN teachers t ON t.id = c.teacher_id
        WHERE c.teacher_id = ?
        ORDER BY cls.grade, cls.branch
        """,
        (handler.identity['id'],)
    )
    send_json(handler, rows)


@route('GET', '/teacher/classes/:id/sessions', roles=['teacher'])
def teacher_sessions(handler: AppHandler, params: Dict[str, str]):
    class_id = int(params['id'])
    date_filter = handler.query.get('date', [None])[0]
    clauses = ['c.class_id = ?', 'c.teacher_id = ?']
    values: List[Any] = [class_id, handler.identity['id']]
    if date_filter:
        clauses.append('s.date >= ?')
        values.append(date_filter)
    where = ' AND '.join(clauses)
    rows = db.fetch_all(
        f"""
        SELECT s.id, s.date, s.start_time, s.end_time, s.is_locked, c.name AS course_name
        FROM schedule_sessions s
        JOIN courses c ON c.id = s.course_id
        WHERE {where}
        ORDER BY s.date, s.start_time
        """,
        values
    )
    send_json(handler, rows)


@route('GET', '/teacher/sessions/:id/attendance', roles=['teacher'])
def teacher_get_attendance(handler: AppHandler, params: Dict[str, str]):
    session_id = int(params['id'])
    session = ensure_teacher_session_access(handler, session_id)
    if not session:
        return
    rows = attendance.list_attendance_for_session(session_id)
    send_json(handler, {'session': session, 'attendance': rows})


def ensure_session_editable(session: Dict[str, Any]) -> Optional[str]:
    if session['is_locked']:
        return 'Yoklama süresi doldu'
    now = datetime.utcnow()
    start_dt = datetime.fromisoformat(f"{session['date']}T{session['start_time']}")
    end_dt = datetime.fromisoformat(f"{session['date']}T{session['end_time']}")
    flags = attendance.get_feature_flags()
    end_dt += timedelta(minutes=attendance.get_grace_period_minutes(flags))
    if now < start_dt - timedelta(hours=1):
        return 'Ders henüz başlamadı'
    if now > end_dt:
        attendance.lock_session_if_needed(session['id'], now)
        return 'Yoklama süresi doldu'
    return None


@route('POST', '/teacher/sessions/:id/attendance', roles=['teacher'])
def teacher_take_attendance(handler: AppHandler, params: Dict[str, str]):
    session_id = int(params['id'])
    session = ensure_teacher_session_access(handler, session_id)
    if not session:
        return
    error = ensure_session_editable(session)
    if error:
        handler.send_error(HTTPStatus.FORBIDDEN, error)
        return
    data = parse_json_body(handler)
    if data is None:
        return
    items = data if isinstance(data, list) else data.get('items', [])
    valid_statuses = {'present', 'excused', 'unexcused'}
    for item in items:
        if item['status'] not in valid_statuses:
            handler.send_error(HTTPStatus.BAD_REQUEST, 'Geçersiz durum')
            return
        attendance.upsert_attendance(session_id, item['student_id'], item['status'], handler.identity['id'])
    attendance.evaluate_thresholds_for_session(session_id, handler.identity['id'])
    audit.log_action(handler.identity['id'], 'take_attendance', 'session', str(session_id), {'items': len(items)})
    send_no_content(handler)


@route('PATCH', '/teacher/sessions/:id/attendance', roles=['teacher'])
def teacher_update_attendance(handler: AppHandler, params: Dict[str, str]):
    session_id = int(params['id'])
    session = ensure_teacher_session_access(handler, session_id)
    if not session:
        return
    error = ensure_session_editable(session)
    if error:
        handler.send_error(HTTPStatus.FORBIDDEN, error)
        return
    data = parse_json_body(handler)
    if data is None:
        return
    valid_statuses = {'present', 'excused', 'unexcused'}
    for item in data.get('items', []):
        if item['status'] not in valid_statuses:
            handler.send_error(HTTPStatus.BAD_REQUEST, 'Geçersiz durum')
            return
        attendance.upsert_attendance(session_id, item['student_id'], item['status'], handler.identity['id'])
    attendance.evaluate_thresholds_for_session(session_id, handler.identity['id'])
    audit.log_action(handler.identity['id'], 'update_attendance', 'session', str(session_id), {'items': len(data.get('items', []))})
    send_no_content(handler)


@route('GET', '/teacher/reports/courses/:id', roles=['teacher'])
def teacher_course_report(handler: AppHandler, params: Dict[str, str]):
    course_id = int(params['id'])
    course = db.fetch_one('SELECT id FROM courses WHERE id = ? AND teacher_id = ?', (course_id, handler.identity['id']))
    if not course:
        handler.send_error(HTTPStatus.FORBIDDEN, 'Yetkiniz yok')
        return
    stats = attendance.calculate_percentages_for_course(course_id)
    send_json(handler, stats)


# Student endpoints

@route('GET', '/student/courses', roles=['student'])
def student_courses(handler: AppHandler, params: Dict[str, str]):
    rows = db.fetch_all(
        """
        SELECT DISTINCT c.id, c.name, c.code, cls.name AS class_name, t.display_color
        FROM class_students cs
        JOIN courses c ON c.class_id = cs.class_id
        JOIN classes cls ON cls.id = cs.class_id
        JOIN teachers t ON t.id = c.teacher_id
        WHERE cs.student_id = ? AND cs.aktif_mi = 1
        ORDER BY c.name
        """,
        (handler.identity['id'],)
    )
    send_json(handler, rows)


@route('GET', '/student/courses/:id/attendance-summary', roles=['student'])
def student_course_summary(handler: AppHandler, params: Dict[str, str]):
    course_id = int(params['id'])
    belongs = db.fetch_one(
        "SELECT 1 FROM courses c JOIN class_students cs ON cs.class_id = c.class_id WHERE c.id = ? AND cs.student_id = ?",
        (course_id, handler.identity['id'])
    )
    if not belongs:
        handler.send_error(HTTPStatus.FORBIDDEN, 'Yetkiniz yok')
        return
    stats = attendance.calculate_percentages_for_course(course_id, handler.identity['id'])
    threshold = attendance.get_course_threshold(course_id)
    summary = stats[0] if stats else {'total_absent': 0, 'total_unexcused': 0, 'total_sessions': 0}
    total_sessions = summary.get('total_sessions', 0) or 0
    count_value = summary.get('total_unexcused', 0) if attendance.get_feature_flags().get('absence_only_unexcused', {}).get('enabled') else summary.get('total_absent', 0)
    percent = (count_value / total_sessions * 100) if total_sessions else 0
    send_json(handler, {
        'course_id': course_id,
        'percent': percent,
        'threshold': threshold,
        'summary': summary
    })


# Application bootstrap

def run_server():
    migrate_if_needed()
    server = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), AppHandler)
    print(f"Sunucu http://{SERVER_HOST}:{SERVER_PORT} adresinde hazır")
    server.serve_forever()


def migrate_if_needed():
    migrations_dir = Path(__file__).resolve().parent / 'migrations'
    db_path = db.DB_PATH
    if not db_path.exists():
        from . import migrate
        migrate.main()


if __name__ == '__main__':
    run_server()
