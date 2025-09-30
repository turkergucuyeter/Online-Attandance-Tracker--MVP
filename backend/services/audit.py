import json
from typing import Any, Dict, Optional

from .. import db


def log_action(user_id: int, action: str, entity: str, entity_id: Optional[str], meta: Optional[Dict[str, Any]] = None):
    db.execute(
        "INSERT INTO audit_logs (user_id, action, entity, entity_id, meta_json) VALUES (?, ?, ?, ?, ?)",
        (user_id, action, entity, entity_id, json.dumps(meta or {}, ensure_ascii=False))
    )
