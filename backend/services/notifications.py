from typing import Optional

from .. import db


def create_notification(user_id: int, channel: str, title: str, body: str):
    db.execute(
        "INSERT INTO notifications (user_id, channel, title, body) VALUES (?, ?, ?, ?)",
        (user_id, channel, title, body)
    )


def list_notifications(user_id: int):
    return db.fetch_all(
        "SELECT id, channel, title, body, read_at, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )


def mark_as_read(notification_id: int, user_id: int):
    db.execute(
        "UPDATE notifications SET read_at = datetime('now') WHERE id = ? AND user_id = ?",
        (notification_id, user_id)
    )
