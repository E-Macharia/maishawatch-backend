# app/api/routers/notifications.py
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field
from app.core.db import db
from app.core.security import require_roles, current_user, optional_user
from app.core.audit import audit
from app.services.email_service import send_email

router = APIRouter(prefix="/notifications", tags=["Notifications & Email"])


class Notification(BaseModel):
    subject: str
    body: str
    role: Optional[str] = None
    user_ids: list[str] = Field(default_factory=list)
    send_email_now: bool = True


@router.get("")
def mine(u=Depends(optional_user)):
    """Get current user's notifications"""
    with db() as c:
        rows = c.execute(
            """
            SELECT id, user_id, email, subject, body, status, notification_type, 
                   created_at, sent_at, read_at 
            FROM notification_queue 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 100
        """,
            (u["id"],),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/unread-count")
def unread_count(u=Depends(optional_user)):
    """Get count of unread notifications for current user"""
    with db() as c:
        row = c.execute(
            """
            SELECT COUNT(*) AS count 
            FROM notification_queue 
            WHERE user_id = ? AND read_at IS NULL
        """,
            (u["id"],),
        ).fetchone()
    return {"count": int(row["count"])}


@router.get("/queue")
def get_notification_queue(
    status: Optional[str] = Query(None, description="Filter by status"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(100, description="Number of records to return"),
    u=Depends(optional_user),
):
    """Get notification queue with optional filters (Admin only)"""
    with db() as c:
        query = "SELECT * FROM notification_queue WHERE 1=1"
        params = []

        if status:
            query += " AND status=?"
            params.append(status)
        if notification_type:
            query += " AND notification_type=?"
            params.append(notification_type)

        # Filter by user scope
        if u["scope_type"] != "national":
            query += " AND facility_id=?"
            params.append(u["scope_id"])

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = [dict(r) for r in c.execute(query, params).fetchall()]

        # Add facility names for better readability
        for row in rows:
            if row.get("facility_id"):
                facility = c.execute(
                    "SELECT facility_name FROM hospitals WHERE facility_id=?",
                    (row["facility_id"],),
                ).fetchone()
                if facility:
                    row["facility_name"] = facility["facility_name"]

        return rows


@router.patch("/{notification_id}/read")
def mark_read(notification_id: int, u=Depends(optional_user)):
    """Mark a notification as read"""
    now = datetime.now(timezone.utc).isoformat()
    with db() as c:
        row = c.execute(
            "SELECT id, user_id FROM notification_queue WHERE id=?", (notification_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Notification not found")
        if str(row["user_id"]) != str(u["id"]):
            raise HTTPException(403, "You can only modify your own notifications.")
        c.execute(
            "UPDATE notification_queue SET read_at=? WHERE id=?", (now, notification_id)
        )
    return {
        "message": "Notification marked as read",
        "notification_id": notification_id,
        "read_at": now,
    }


@router.patch("/read-all")
def mark_all_read(u=Depends(optional_user)):
    """Mark all notifications as read"""
    now = datetime.now(timezone.utc).isoformat()
    with db() as c:
        result = c.execute(
            "UPDATE notification_queue SET read_at=? WHERE user_id=? AND read_at IS NULL",
            (now, u["id"]),
        )
    return {
        "message": "All notifications marked as read",
        "updated": result.rowcount,
        "read_at": now,
    }


@router.post("/send")
def send(
    n: Notification,
    u=Depends(
        require_roles(
            "system_administrator", "national_administrator", "facility_manager"
        )
    ),
):
    """Send a manual notification to users"""
    with db() as c:
        # Get target users
        if n.user_ids:
            q = ",".join("?" * len(n.user_ids))
            users = [
                dict(x)
                for x in c.execute(
                    f"SELECT id, name, email, role, scope_type, scope_id FROM users WHERE id IN ({q}) AND active=1",
                    n.user_ids,
                )
            ]
        elif n.role:
            users = [
                dict(x)
                for x in c.execute(
                    "SELECT id, name, email, role, scope_type, scope_id FROM users WHERE role=? AND active=1",
                    (n.role,),
                )
            ]
        else:
            users = [
                dict(x)
                for x in c.execute(
                    "SELECT id, name, email, role, scope_type, scope_id FROM users WHERE active=1"
                )
            ]

        # Filter by scope
        if str(u["scope_type"]) != "national":
            users = [x for x in users if str(x["scope_id"]) == str(u["scope_id"])]

        if not users:
            return {
                "message": "No users to notify",
                "queued": 0,
                "emails_sent": 0,
                "pending": 0,
                "results": [],
            }

        now = datetime.now(timezone.utc).isoformat()
        results = []

        for user in users:
            status = "PENDING"
            detail = "queued"

            if n.send_email_now:
                try:
                    ok, detail = send_email(user["email"], n.subject, n.body)
                    status = "SENT" if ok else "PENDING"
                except Exception as exc:
                    detail = str(exc)
                    status = "PENDING"

            c.execute(
                """
                INSERT INTO notification_queue 
                (user_id, email, subject, body, status, created_at, sent_at, notification_type, read_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user["id"],
                    user["email"],
                    n.subject,
                    n.body,
                    status,
                    now,
                    now if status == "SENT" else None,
                    "MANUAL",
                    None,
                ),
            )

            results.append(
                {
                    "user_id": user["id"],
                    "email": user["email"],
                    "role": user["role"],
                    "status": status,
                    "detail": detail,
                }
            )

    sent = sum(r["status"] == "SENT" for r in results)
    audit(
        u,
        "SEND_NOTIFICATION",
        "notification",
        details={"recipients": len(results), "emails_sent": sent, "subject": n.subject},
    )

    return {
        "queued": len(results),
        "emails_sent": sent,
        "pending": len(results) - sent,
        "results": results,
    }


@router.delete("/{notification_id}")
def delete_notification(notification_id: int, u=Depends(optional_user)):
    """Delete a notification"""
    with db() as c:
        row = c.execute(
            "SELECT id, user_id FROM notification_queue WHERE id=?", (notification_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Notification not found")
        if str(row["user_id"]) != str(u["id"]):
            raise HTTPException(403, "You can only delete your own notifications.")
        c.execute("DELETE FROM notification_queue WHERE id=?", (notification_id,))

    audit(u, "DELETE_NOTIFICATION", "notification", str(notification_id))
    return {"message": "Notification deleted", "notification_id": notification_id}


@router.delete("/clear-all")
def clear_all_notifications(u=Depends(optional_user)):
    """Delete all notifications for current user"""
    with db() as c:
        result = c.execute("DELETE FROM notification_queue WHERE user_id=?", (u["id"],))

    audit(
        u,
        "CLEAR_ALL_NOTIFICATIONS",
        "notification",
        details={"deleted": result.rowcount},
    )
    return {"message": "All notifications cleared", "deleted": result.rowcount}


@router.get("/stats")
def get_notification_stats(u=Depends(optional_user)):
    """Get notification statistics"""
    with db() as c:
        # Total notifications
        total = c.execute(
            "SELECT COUNT(*) as count FROM notification_queue WHERE user_id=?",
            (u["id"],),
        ).fetchone()

        # Unread count
        unread = c.execute(
            "SELECT COUNT(*) as count FROM notification_queue WHERE user_id=? AND read_at IS NULL",
            (u["id"],),
        ).fetchone()

        # By type
        by_type = c.execute(
            """
            SELECT notification_type, COUNT(*) as count 
            FROM notification_queue 
            WHERE user_id=? 
            GROUP BY notification_type
        """,
            (u["id"],),
        ).fetchall()

        # Recent (last 7 days)
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        recent = c.execute(
            """
            SELECT COUNT(*) as count 
            FROM notification_queue 
            WHERE user_id=? AND created_at > ?
        """,
            (u["id"], week_ago),
        ).fetchone()

    return {
        "total": total["count"] if total else 0,
        "unread": unread["count"] if unread else 0,
        "by_type": [dict(r) for r in by_type],
        "recent_7_days": recent["count"] if recent else 0,
    }
