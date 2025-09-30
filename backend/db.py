import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'app.db'


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


@contextmanager
def transaction():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_one(sql: str, params: Iterable[Any] = ()):  # type: ignore[assignment]
    with get_connection() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchone()


def fetch_all(sql: str, params: Iterable[Any] = ()):  # type: ignore[assignment]
    with get_connection() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()


def execute(sql: str, params: Iterable[Any] = ()):
    with transaction() as conn:
        conn.execute(sql, tuple(params))


def execute_and_return_id(sql: str, params: Iterable[Any] = ()) -> int:
    with transaction() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid
