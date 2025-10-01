import os
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager


db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'cok-gizli-anahtar')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///attendance.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=6)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .routes.auth import auth_bp
    from .routes.supervisor import supervisor_bp
    from .routes.teacher import teacher_bp
    from .routes.student import student_bp
    from .routes.general import general_bp

    app.register_blueprint(general_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(supervisor_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)

    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()

    return app
