# app/core/audit.py
from datetime import datetime, timezone
import json
from app.core.db import db


def audit(
    user, action, resource_type=None, resource_id=None, details=None, scope_id=None
):
    """Log an audit trail entry"""
    # Convert sqlite3.Row to dict if needed
    if user and hasattr(user, "keys"):
        # It's a sqlite3.Row, convert to dict
        user = dict(user)
    elif user is None:
        user = {}

    actor = user or {}

    with db() as c:
        c.execute(
            """
            INSERT INTO audit_logs 
            (actor_user_id, actor_email, actor_role, action, resource_type, resource_id, scope_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                actor.get("id"),
                actor.get("email"),
                actor.get("role"),
                action,
                resource_type,
                resource_id,
                scope_id if scope_id is not None else actor.get("scope_id"),
                json.dumps(details or {}),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
