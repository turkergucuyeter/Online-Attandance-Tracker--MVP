"""Utilities for managing account-related helpers."""
from __future__ import annotations

import secrets
import string
import unicodedata

from typing import Tuple

from ..models import User


STUDENT_EMAIL_DOMAIN = 'ogrenci.okul'


def _slugify(value: str) -> str:
    """Create an ASCII slug from the given value using ``unicodedata``."""
    if not value:
        return ''
    normalized = unicodedata.normalize('NFKD', value)
    ascii_str = normalized.encode('ascii', 'ignore').decode('ascii')
    cleaned = ''.join(ch if ch.isalnum() else '-' for ch in ascii_str.lower())
    parts = [part for part in cleaned.split('-') if part]
    return '-'.join(parts)


def _generate_password(length: int = 12) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_student_credentials(full_name: str, student_number: str) -> Tuple[str, str]:
    """Return a unique email and strong password for a student."""
    slug = _slugify(full_name) or 'ogrenci'
    base_local = f"{student_number}"
    if slug:
        base_local = f"{slug}.{student_number}"

    counter = 0
    while True:
        suffix = f"-{counter}" if counter else ''
        local_part = f"{base_local}{suffix}"
        email_candidate = f"{local_part}@{STUDENT_EMAIL_DOMAIN}"
        existing = User.query.filter_by(email=email_candidate).first()
        if not existing:
            break
        counter += 1

    password = _generate_password()
    return email_candidate, password
