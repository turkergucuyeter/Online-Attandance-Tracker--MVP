from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import func, Column, Integer, String, ForeignKey, DateTime, Enum, UniqueConstraint, Text
from sqlalchemy.orm import relationship

from . import db, login_manager


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    color = Column(String(20))

    teacher_courses = relationship('Course', secondary='course_teachers', back_populates='teachers')
    teacher_classes = relationship('ClassRoom', secondary='class_teachers', back_populates='teachers')
    student_profile = relationship('Student', uselist=False, back_populates='user')
    attendance_records = relationship('AttendanceRecord', back_populates='teacher')

    def is_supervisor(self):
        return self.role == 'supervisor'

    def is_teacher(self):
        return self.role == 'teacher'

    def is_student(self):
        return self.role == 'student'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class ClassRoom(TimestampMixin, db.Model):
    __tablename__ = 'classrooms'

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text)

    students = relationship('Student', back_populates='classroom', cascade='all, delete')
    courses = relationship('Course', secondary='course_classes', back_populates='classrooms')
    teachers = relationship('User', secondary='class_teachers', back_populates='teacher_classes')
    attendance_records = relationship('AttendanceRecord', back_populates='classroom')


class Course(TimestampMixin, db.Model):
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    max_excused_percentage = Column(Integer, default=30)
    max_unexcused_percentage = Column(Integer, default=20)

    classrooms = relationship('ClassRoom', secondary='course_classes', back_populates='courses')
    teachers = relationship('User', secondary='course_teachers', back_populates='teacher_courses')
    students = relationship('Student', secondary='student_courses', back_populates='courses')
    attendance_records = relationship('AttendanceRecord', back_populates='course')


class Student(TimestampMixin, db.Model):
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    student_number = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=True)
    classroom_id = Column(Integer, ForeignKey('classrooms.id'), nullable=False)

    classroom = relationship('ClassRoom', back_populates='students')
    courses = relationship('Course', secondary='student_courses', back_populates='students')
    user = relationship('User', back_populates='student_profile')
    attendance_entries = relationship('AttendanceEntry', back_populates='student')


class CourseClass(db.Model):
    __tablename__ = 'course_classes'
    course_id = Column(Integer, ForeignKey('courses.id'), primary_key=True)
    classroom_id = Column(Integer, ForeignKey('classrooms.id'), primary_key=True)


class CourseTeacher(db.Model):
    __tablename__ = 'course_teachers'
    course_id = Column(Integer, ForeignKey('courses.id'), primary_key=True)
    teacher_id = Column(Integer, ForeignKey('users.id'), primary_key=True)


class ClassTeacher(db.Model):
    __tablename__ = 'class_teachers'
    classroom_id = Column(Integer, ForeignKey('classrooms.id'), primary_key=True)
    teacher_id = Column(Integer, ForeignKey('users.id'), primary_key=True)


class StudentCourse(db.Model):
    __tablename__ = 'student_courses'
    student_id = Column(Integer, ForeignKey('students.id'), primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), primary_key=True)
    __table_args__ = (UniqueConstraint('student_id', 'course_id', name='uq_student_course'),)


class AttendanceRecord(TimestampMixin, db.Model):
    __tablename__ = 'attendance_records'

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    classroom_id = Column(Integer, ForeignKey('classrooms.id'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    course = relationship('Course', back_populates='attendance_records')
    classroom = relationship('ClassRoom', back_populates='attendance_records')
    teacher = relationship('User', back_populates='attendance_records')
    entries = relationship('AttendanceEntry', back_populates='record', cascade='all, delete')


class AttendanceEntry(TimestampMixin, db.Model):
    __tablename__ = 'attendance_entries'

    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, ForeignKey('attendance_records.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    status = Column(Enum('present', 'excused', 'absent', name='attendance_status'), default='present', nullable=False)

    record = relationship('AttendanceRecord', back_populates='entries')
    student = relationship('Student', back_populates='attendance_entries')

    __table_args__ = (UniqueConstraint('record_id', 'student_id', name='uq_record_student'),)


def attendance_statistics_for_student(student: Student):
    total_by_course = {}
    for course in student.courses:
        total_sessions = (
            AttendanceEntry.query.join(AttendanceRecord)
            .filter(
                AttendanceRecord.course_id == course.id,
                AttendanceEntry.student_id == student.id,
            )
            .count()
        )
        if total_sessions == 0:
            total_by_course[course.id] = {
                'course': course,
                'present': 0,
                'excused': 0,
                'absent': 0,
                'total': 0,
            }
            continue

        excused = (
            AttendanceEntry.query.join(AttendanceRecord)
            .filter(
                AttendanceRecord.course_id == course.id,
                AttendanceEntry.student_id == student.id,
                AttendanceEntry.status == 'excused',
            )
            .count()
        )
        absent = (
            AttendanceEntry.query.join(AttendanceRecord)
            .filter(
                AttendanceRecord.course_id == course.id,
                AttendanceEntry.student_id == student.id,
                AttendanceEntry.status == 'absent',
            )
            .count()
        )
        present = total_sessions - excused - absent

        total_by_course[course.id] = {
            'course': course,
            'present': present,
            'excused': excused,
            'absent': absent,
            'total': total_sessions,
        }
    return total_by_course
