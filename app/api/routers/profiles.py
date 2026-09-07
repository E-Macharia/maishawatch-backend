# app/api/routers/profiles.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.security import current_user
from app.core.audit import audit
from app.core.db import db

router = APIRouter(prefix="/profile", tags=["User Profile"])


@router.get("")
def get_profile(u=Depends(current_user)):
    with db() as c:
        user = c.execute(
            """
            SELECT id, name, email, role, scope_type, scope_id, active, 
                   created_at, last_login 
            FROM users WHERE id=?
        """,
            (u["id"],),
        ).fetchone()
    return dict(user)


@router.patch("")
def update_profile(name: str, u=Depends(current_user)):
    with db() as c:
        c.execute("UPDATE users SET name=? WHERE id=?", (name, u["id"]))
        user = c.execute(
            "SELECT id, name, email, role, scope_type, scope_id FROM users WHERE id=?",
            (u["id"],),
        ).fetchone()

    audit(u, "UPDATE_PROFILE", "user", u["id"])
    return dict(user)
