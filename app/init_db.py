"""Veritabanını hazırlamak ve ilk kullanıcıları eklemek için yardımcı betik."""
from getpass import getpass

from werkzeug.security import generate_password_hash

from . import create_app, db
from .models import User


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        if User.query.filter_by(role='supervisor').first():
            print('Zaten en az bir yönetici mevcut.')
            return
        print('Yeni yönetici (supervisor) hesabı oluşturulacak.')
        full_name = input('Ad Soyad: ')
        email = input('E-posta: ')
        password = getpass('Şifre: ')
        user = User(full_name=full_name, email=email, role='supervisor')
        user.password_hash = generate_password_hash(password)
        db.session.add(user)
        db.session.commit()
        print('Yönetici hesabı oluşturuldu.')


if __name__ == '__main__':
    main()
