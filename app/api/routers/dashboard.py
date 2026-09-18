# app/api/routers/dashboard.py
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from app.core.security import current_user, optional_user
from app.services.data_service import (
    equipment,
    failures,
    facilities,
    scope_filter,
    maintenance,
)
from app.core.db import db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(u=Depends(optional_user)):
    eq = scope_filter(equipment(), u)
    fs = scope_filter(facilities(), u)

    # Get alerts directly from database
    with db() as c:
        alert_rows = c.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC"
        ).fetchall()
        all_alerts = [dict(r) for r in alert_rows]
        filtered_alerts = scope_filter(all_alerts, u)

    # Get maintenance work orders
    with db() as c:
        wo_rows = c.execute(
            "SELECT * FROM maintenance_work_orders ORDER BY created_at DESC"
        ).fetchall()
        all_wo = [dict(r) for r in wo_rows]
        filtered_wo = (
            scope_filter(all_wo, u) if u["scope_type"] != "national" else all_wo
        )

    # Calculate metrics
    total_equipment = len(eq)
    total_facilities = len(fs)
    open_alerts = len(
        [
            a
            for a in filtered_alerts
            if a.get("status") in ["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"]
        ]
    )
    critical_alerts = len(
        [
            a
            for a in filtered_alerts
            if a.get("severity") == "CRITICAL" and a.get("status") != "RESOLVED"
        ]
    )
    pending_maintenance = len([w for w in filtered_wo if w.get("status") == "OPEN"])

    # Equipment status breakdown
    operational = len([e for e in eq if e.get("status") == "OPERATIONAL"])
    maintenance_mode = len([e for e in eq if e.get("status") == "MAINTENANCE"])
    decommissioned = len([e for e in eq if e.get("status") == "DECOMMISSIONED"])

    # Recent alerts (last 7 days)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recent_alerts = [a for a in filtered_alerts if a.get("created_at", "") > week_ago]

    return {
        "total_equipment": total_equipment,
        "total_facilities": total_facilities,
        "open_alerts": open_alerts,
        "critical_alerts": critical_alerts,
        "pending_maintenance": pending_maintenance,
        "operational_equipment": operational,
        "maintenance_mode_equipment": maintenance_mode,
        "decommissioned_equipment": decommissioned,
        "recent_alerts_count": len(recent_alerts),
        "role": u["role"],
        "scope_type": u["scope_type"],
        "scope_id": u["scope_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
