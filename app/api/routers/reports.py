# app/api/routers/reports.py
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timezone
from app.core.security import current_user, optional_user
from app.core.audit import audit
from app.services.data_service import equipment, failures, scope_filter, facilities
from app.core.db import db

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary")
def summary(u=Depends(optional_user)):
    eq = scope_filter(equipment(), u)
    fs = scope_filter(facilities(), u)

    # Get alerts from database
    with db() as c:
        alert_rows = c.execute("SELECT * FROM alerts").fetchall()
        alerts_data = [dict(r) for r in alert_rows]
        filtered_alerts = scope_filter(alerts_data, u)

    audit(u, "GENERATE_REPORT", "report", "summary")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "facilities": len(fs),
        "equipment": len(eq),
        "alerts": len(filtered_alerts),
        "critical_equipment": sum(
            1 for x in eq if str(x.get("criticality", "")).lower() == "critical"
        ),
    }


@router.get("/equipment")
def equipment_report(
    facility_id: str | None = None,
    equipment_type: str | None = None,
    status: str | None = None,
    u=Depends(optional_user),
):
    eq = scope_filter(equipment(), u)

    if facility_id:
        eq = [e for e in eq if str(e.get("facility_id")) == facility_id]
    if equipment_type:
        eq = [
            e
            for e in eq
            if e.get("equipment_type", "").lower() == equipment_type.lower()
        ]
    if status:
        eq = [e for e in eq if e.get("status", "").lower() == status.lower()]

    audit(
        u,
        "GENERATE_EQUIPMENT_REPORT",
        "report",
        details={
            "filters": {
                "facility_id": facility_id,
                "equipment_type": equipment_type,
                "status": status,
            }
        },
    )

    return {
        "total": len(eq),
        "equipment": eq,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/alerts")
def alerts_report(
    facility_id: str | None = None,
    equipment_id: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    u=Depends(optional_user),
):
    with db() as c:
        query = "SELECT * FROM alerts WHERE 1=1"
        params = []

        if facility_id:
            query += " AND facility_id=?"
            params.append(facility_id)
        if equipment_id:
            query += " AND equipment_id=?"
            params.append(equipment_id)
        if severity:
            query += " AND severity=?"
            params.append(severity)
        if status:
            query += " AND status=?"
            params.append(status)

        query += " ORDER BY created_at DESC"
        rows = [dict(r) for r in c.execute(query, params).fetchall()]

    if u["scope_type"] != "national":
        rows = [r for r in rows if str(r.get("facility_id")) == str(u["scope_id"])]

    audit(
        u,
        "GENERATE_ALERTS_REPORT",
        "report",
        details={
            "filters": {
                "facility_id": facility_id,
                "equipment_id": equipment_id,
                "severity": severity,
                "status": status,
            }
        },
    )

    return {
        "total": len(rows),
        "alerts": rows,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
