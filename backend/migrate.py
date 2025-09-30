import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'app.db'
MIGRATIONS_DIR = BASE_DIR / 'migrations'


def apply_migration(cursor, sql: str):
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    for statement in statements:
        cursor.execute(statement)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('PRAGMA foreign_keys = ON;')
        cursor = conn.cursor()
        for migration in sorted(MIGRATIONS_DIR.glob('*.sql')):
            sql = migration.read_text(encoding='utf-8')
            apply_migration(cursor, sql)
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
