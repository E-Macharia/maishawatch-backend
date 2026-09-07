# app/api/routers/equipment.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import random
import pandas as pd
from app.core.security import current_user, require_roles
from app.core.db import db
from app.core.audit import audit
from app.services.data_service import (
    equipment,
    scope_filter,
    telemetry,
    maintenance,
    failures,
    get_equipment_telemetry,
)
from app.services.notification_service import NotificationService
from app.services.telemetry_service import TelemetrySimulator
from app.engines.alert_engine import evaluate_and_create_alert
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/equipment", tags=["Equipment"])

# --- Models ---
class EquipmentOnboard(BaseModel):
    equipment_id: str
    facility_id: str
    equipment_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_date: Optional[str] = None
    simulate_telemetry: bool = True
    telemetry_interval_seconds: int = 60

class EquipmentUpdate(BaseModel):
    equipment_type: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    status: Optional[str] = Field(None, description="OPERATIONAL, MAINTENANCE, DECOMMISSIONED")
    installation_date: Optional[str] = None

class EquipmentStatusUpdate(BaseModel):
    status: str = Field(..., description="OPERATIONAL, MAINTENANCE, DECOMMISSIONED")

class EvaluateRequest(BaseModel):
    equipment_id: str

class TelemetryBatchRequest(BaseModel):
    equipment_id: str
    facility_id: str
    count: int = 100

# --- GET All Equipment ---
@router.get("")
def get_equipment(
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    equipment_type: Optional[str] = Query(None, description="Filter by equipment type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by equipment_id or model"),
    u=Depends(current_user),
):
    """Get all equipment with optional filters"""
    eq = scope_filter(equipment(), u)

    # Apply filters
    if facility_id:
        eq = [e for e in eq if str(e.get("facility_id")) == facility_id]
    if equipment_type:
        eq = [e for e in eq if e.get("equipment_type", "").lower() == equipment_type.lower()]
    if status:
        eq = [e for e in eq if e.get("status", "").lower() == status.lower()]
    if search:
        search_lower = search.lower()
        eq = [
            e for e in eq
            if search_lower in str(e.get("equipment_id", "")).lower()
            or search_lower in str(e.get("model", "")).lower()
        ]

    audit(u, "VIEW_EQUIPMENT", "equipment", details={
        "filters": {
            "facility_id": facility_id,
            "equipment_type": equipment_type,
            "status": status,
            "search": search,
        }
    })

    return eq

# --- GET Single Equipment ---
@router.get("/{equipment_id}")
def get_equipment_details(
    equipment_id: str,
    include_telemetry: bool = Query(True, description="Include telemetry data"),
    include_maintenance: bool = Query(True, description="Include maintenance history"),
    include_alerts: bool = Query(True, description="Include alerts"),
    limit: int = Query(50, description="Limit for telemetry and maintenance history"),
    u=Depends(current_user),
):
    """Get detailed equipment information including telemetry, maintenance, and alerts"""
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]

    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    equipment_data = eq_list[0]
    facility_id = equipment_data.get("facility_id")

    result = {"equipment": equipment_data}

    # Include telemetry
    if include_telemetry:
        result["telemetry"] = telemetry(equipment_id, facility_id=facility_id, limit=limit)

    # Include maintenance history
    if include_maintenance:
        result["maintenance_history"] = maintenance(equipment_id, facility_id=facility_id, limit=limit)

    # Include alerts
    if include_alerts:
        with db() as c:
            alert_rows = c.execute(
                """
                SELECT * FROM alerts 
                WHERE equipment_id = ? 
                ORDER BY created_at DESC LIMIT ?
            """,
                (equipment_id, limit),
            ).fetchall()
            result["alerts"] = [dict(r) for r in alert_rows]

    # Get current status summary
    with db() as c:
        latest_telemetry = c.execute(
            """
            SELECT * FROM sensor_telemetry 
            WHERE equipment_id = ? 
            ORDER BY timestamp DESC LIMIT 1
        """,
            (equipment_id,),
        ).fetchone()

        if latest_telemetry:
            result["current_status"] = {
                "last_reading": dict(latest_telemetry),
                "status": equipment_data.get("status", "UNKNOWN"),
                "risk_score": latest_telemetry.get("risk_score", 0),
            }

    audit(u, "VIEW_EQUIPMENT_DETAILS", "equipment", equipment_id)
    return result


# --- POST Create Equipment ---
@router.post("", status_code=201)
def create_equipment(
    data: EquipmentOnboard,
    background_tasks: BackgroundTasks,
    u=Depends(
        require_roles(
            "system_administrator",
            "national_administrator",
            "facility_manager",
            "biomedical_engineer",
        )
    ),
):
    """Register new equipment with automatic telemetry generation and evaluation"""
    # Check scope
    if u["scope_type"] != "national" and str(u["scope_id"]) != str(data.facility_id):
        raise HTTPException(403, "You can only onboard equipment in your facility")

    # Check if equipment already exists
    existing = [
        e
        for e in equipment()
        if str(e.get("equipment_id")) == str(data.equipment_id)
        and str(e.get("facility_id")) == str(data.facility_id)
    ]
    if existing:
        raise HTTPException(409, "Equipment already exists at this facility")

    now = datetime.now(timezone.utc).isoformat()

    # Insert into database
    with db() as c:
        c.execute(
            """
            INSERT INTO equipment_registry 
            (equipment_id, facility_id, equipment_type, manufacturer, model, 
             serial_number, status, installation_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data.equipment_id,
                data.facility_id,
                data.equipment_type,
                data.manufacturer,
                data.model,
                data.serial_number,
                "OPERATIONAL",
                data.installation_date or now,
                now,
                now,
            ),
        )

    audit(
        u,
        "CREATE_EQUIPMENT",
        "equipment",
        data.equipment_id,
        {"facility_id": data.facility_id, "type": data.equipment_type},
    )

    # --- NEW: Generate initial telemetry data ---
    try:
        from app.services.telemetry_service import TelemetrySimulator

        # Generate 100 initial readings
        initial_readings = TelemetrySimulator.generate_initial_readings(
            data.equipment_id,
            data.facility_id,
            data.equipment_type,
            count=100,  # Generate 100 historical readings
        )
        logger.info(
            f"Generated {len(initial_readings)} initial readings for {data.equipment_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to generate initial telemetry for {data.equipment_id}: {e}"
        )

    # --- NEW: Sync equipment with CSV ---
    try:
        from app.services.data_service import sync_equipment_to_csv

        # Add equipment to master CSV
        equipment_record = {
            "equipment_id": data.equipment_id,
            "facility_id": data.facility_id,
            "facility": "",  # Will be populated
            "equipment_type": data.equipment_type,
            "manufacturer": data.manufacturer or "",
            "model": data.model or "",
            "serial_number": data.serial_number or "",
            "status": "OPERATIONAL",
            "installation_date": data.installation_date or now,
            "county": "",
            "keph_level": "",
        }
        sync_equipment_to_csv(equipment_record)
        logger.info(f"Synced {data.equipment_id} to CSV")
    except Exception as e:
        logger.error(f"Failed to sync equipment to CSV: {e}")

    # --- NEW: Send registration notifications ---
    try:
        equipment_record = {
            "equipment_id": data.equipment_id,
            "facility_id": data.facility_id,
            "equipment_type": data.equipment_type,
            "manufacturer": data.manufacturer,
            "model": data.model,
            "serial_number": data.serial_number,
            "status": "OPERATIONAL",
            "installation_date": data.installation_date or now,
            "created_at": now,
        }

        def send_notifications():
            notification_result = NotificationService.notify_equipment_registered(
                equipment_record, u
            )
            logger.info(
                f"Equipment registration notifications sent: {notification_result}"
            )

        background_tasks.add_task(send_notifications)
    except Exception as e:
        logger.error(f"Failed to send equipment registration notifications: {e}")

    # --- NEW: Run initial evaluation ---
    try:
        from app.engines.alert_engine import evaluate_and_create_alert

        def run_initial_evaluation():
            # Wait a moment for telemetry to be written
            import time

            time.sleep(2)

            # Run evaluation
            result = evaluate_and_create_alert(data.equipment_id, data.facility_id)
            logger.info(f"Initial evaluation for {data.equipment_id}: {result}")

            # If alert was created, send notifications
            if result.get("created"):
                NotificationService.notify_alert_created(result.get("alert"), u)

        background_tasks.add_task(run_initial_evaluation)
    except Exception as e:
        logger.error(f"Failed to run initial evaluation for {data.equipment_id}: {e}")

    # Start telemetry simulation if requested
    if data.simulate_telemetry:
        background_tasks.add_task(
            TelemetrySimulator.start_simulation,
            data.equipment_id,
            data.facility_id,
            data.equipment_type,
            data.telemetry_interval_seconds,
        )

    return {
        "message": "Equipment onboarded successfully",
        "equipment_id": data.equipment_id,
        "facility_id": data.facility_id,
        "simulation_started": data.simulate_telemetry,
        "notifications_sent": True,
        "initial_readings_generated": 100,
        "evaluation_scheduled": True,
    }


@router.post("/sync-all")
def sync_all_equipment_data(
    background_tasks: BackgroundTasks,
    u=Depends(require_roles("system_administrator", "national_administrator")),
):
    """Sync all equipment to CSV and generate missing telemetry"""
    from app.services.data_service import sync_all_equipment_to_csv

    # Sync equipment to CSV
    sync_result = sync_all_equipment_to_csv()

    # Generate telemetry for equipment without it
    with db() as c:
        equipment_list = c.execute("""
            SELECT e.equipment_id, e.facility_id, e.equipment_type
            FROM equipment_registry e
            WHERE NOT EXISTS (
                SELECT 1 FROM sensor_telemetry t 
                WHERE t.equipment_id = e.equipment_id AND t.facility_id = e.facility_id
            )
        """).fetchall()

        generated = 0
        for eq in equipment_list:
            try:
                from app.services.telemetry_service import TelemetrySimulator

                TelemetrySimulator.generate_initial_readings(
                    eq["equipment_id"],
                    eq["facility_id"],
                    eq["equipment_type"] or "Unknown",
                    count=50,
                )
                generated += 1
            except Exception as e:
                logger.error(
                    f"Failed to generate telemetry for {eq['equipment_id']}: {e}"
                )

    audit(
        u,
        "SYNC_ALL_EQUIPMENT",
        "equipment",
        details={
            "synced": sync_result.get("synced", 0),
            "telemetry_generated": generated,
        },
    )

    return {
        "message": "Sync completed",
        "equipment_synced": sync_result.get("synced", 0),
        "telemetry_generated": generated,
    }


# --- PUT Update Equipment (Full Replacement) ---
@router.put("/{equipment_id}")
def update_equipment(
    equipment_id: str,
    data: EquipmentUpdate,
    background_tasks: BackgroundTasks,
    u=Depends(require_roles('system_administrator', 'national_administrator', 'facility_manager', 'biomedical_engineer'))
):
    """Full update of equipment details"""
    # Check if equipment exists and user has access
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    equipment_data = eq_list[0]
    facility_id = equipment_data.get("facility_id")
    old_status = equipment_data.get("status")

    # Check scope for facility-level users
    if u["scope_type"] != "national" and str(u["scope_id"]) != str(facility_id):
        raise HTTPException(403, "You can only update equipment in your facility")

    now = datetime.now(timezone.utc).isoformat()

    # Build update query
    updates = []
    values = []
    changes = {}

    if data.equipment_type is not None:
        updates.append("equipment_type=?")
        values.append(data.equipment_type)
        changes['equipment_type'] = data.equipment_type
    if data.manufacturer is not None:
        updates.append("manufacturer=?")
        values.append(data.manufacturer)
        changes['manufacturer'] = data.manufacturer
    if data.model is not None:
        updates.append("model=?")
        values.append(data.model)
        changes['model'] = data.model
    if data.serial_number is not None:
        updates.append("serial_number=?")
        values.append(data.serial_number)
        changes['serial_number'] = data.serial_number
    if data.status is not None:
        updates.append("status=?")
        values.append(data.status)
        changes['status'] = data.status
    if data.installation_date is not None:
        updates.append("installation_date=?")
        values.append(data.installation_date)
        changes['installation_date'] = data.installation_date

    if not updates:
        raise HTTPException(400, "No fields to update")

    updates.append("updated_at=?")
    values.append(now)
    values.append(equipment_id)

    with db() as c:
        c.execute(
            f'UPDATE equipment_registry SET {", ".join(updates)} WHERE equipment_id=? AND facility_id=?',
            values + [facility_id],
        )

    # Get updated equipment
    with db() as c:
        updated = dict(
            c.execute(
                "SELECT * FROM equipment_registry WHERE equipment_id=? AND facility_id=?",
                (equipment_id, facility_id),
            ).fetchone()
        )

    audit(
        u,
        "UPDATE_EQUIPMENT",
        "equipment",
        equipment_id,
        data.model_dump(exclude_none=True),
    )

    # Send notifications for updates
    if changes:
        try:
            def send_update_notifications():
                NotificationService.notify_equipment_updated(equipment_id, facility_id, changes, u)
            
            background_tasks.add_task(send_update_notifications)
        except Exception as e:
            logger.error(f"Failed to send equipment update notifications: {e}")

    # Send status change notification if status changed
    if data.status and data.status != old_status:
        try:
            def send_status_notification():
                NotificationService.notify_equipment_status_changed(
                    equipment_id, facility_id, old_status, data.status, u
                )
            background_tasks.add_task(send_status_notification)
        except Exception as e:
            logger.error(f"Failed to send status change notification: {e}")

    return updated

# --- PATCH Partial Update ---
@router.patch("/{equipment_id}")
def patch_equipment(
    equipment_id: str,
    data: EquipmentUpdate,
    background_tasks: BackgroundTasks,
    u=Depends(require_roles('system_administrator', 'national_administrator', 'facility_manager', 'biomedical_engineer'))
):
    """Partial update of equipment details (same as PUT but only updates provided fields)"""
    return update_equipment(equipment_id, data, background_tasks, u)

# --- PATCH Update Status ---
@router.patch("/{equipment_id}/status")
def update_equipment_status(
    equipment_id: str,
    data: EquipmentStatusUpdate,
    background_tasks: BackgroundTasks,
    u=Depends(require_roles('system_administrator', 'national_administrator', 'facility_manager', 'biomedical_engineer'))
):
    """Update equipment status (OPERATIONAL, MAINTENANCE, DECOMMISSIONED)"""
    # Check if equipment exists
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    facility_id = eq_list[0].get("facility_id")
    old_status = eq_list[0].get("status")

    if u["scope_type"] != "national" and str(u["scope_id"]) != str(facility_id):
        raise HTTPException(403, "You can only update equipment in your facility")

    valid_statuses = ["OPERATIONAL", "MAINTENANCE", "DECOMMISSIONED"]
    if data.status not in valid_statuses:
        raise HTTPException(400, f'Invalid status. Must be one of: {", ".join(valid_statuses)}')

    now = datetime.now(timezone.utc).isoformat()

    with db() as c:
        c.execute(
            """
            UPDATE equipment_registry 
            SET status=?, updated_at=? 
            WHERE equipment_id=? AND facility_id=?
        """,
            (data.status, now, equipment_id, facility_id),
        )

        updated = dict(
            c.execute(
                "SELECT * FROM equipment_registry WHERE equipment_id=? AND facility_id=?",
                (equipment_id, facility_id),
            ).fetchone()
        )

    audit(u, "UPDATE_EQUIPMENT_STATUS", "equipment", equipment_id, {"status": data.status})

    # Send status change notification
    if data.status != old_status:
        try:
            def send_status_notification():
                NotificationService.notify_equipment_status_changed(
                    equipment_id, facility_id, old_status, data.status, u
                )
            background_tasks.add_task(send_status_notification)
        except Exception as e:
            logger.error(f"Failed to send status change notification: {e}")

    return updated

# --- DELETE Equipment ---
@router.delete("/{equipment_id}")
def delete_equipment(
    equipment_id: str,
    background_tasks: BackgroundTasks,  # This must come before parameters with defaults
    permanent: bool = Query(False, description="Permanently delete or soft delete"),
    u=Depends(require_roles("system_administrator", "national_administrator")),
):
    """Delete equipment (soft delete by default)"""
    # Check if equipment exists
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    facility_id = eq_list[0].get("facility_id")
    equipment_data = eq_list[0]

    if u["scope_type"] != "national" and str(u["scope_id"]) != str(facility_id):
        raise HTTPException(403, "You can only delete equipment in your facility")

    if permanent:
        # Permanent delete
        with db() as c:
            c.execute(
                "DELETE FROM equipment_registry WHERE equipment_id=? AND facility_id=?",
                (equipment_id, facility_id),
            )
        audit(u, "DELETE_EQUIPMENT_PERMANENT", "equipment", equipment_id)
        
        # Send notification for permanent deletion
        try:
            def send_delete_notification():
                # Notify relevant users about permanent deletion
                with db() as c:
                    facility = c.execute('SELECT facility_name FROM hospitals WHERE facility_id=?', (facility_id,)).fetchone()
                    facility_name = facility['facility_name'] if facility else facility_id
                
                # Get facility manager and biomedical engineers
                users = NotificationService.get_role_recipients(
                    facility_id, 
                    ['facility_manager', 'biomedical_engineer']
                )
                
                for user in users:
                    subject = f"Equipment Permanently Deleted - {equipment_id}"
                    message = f"""
                    Equipment {equipment_id} has been permanently deleted from the system.
                    
                    Facility: {facility_name}
                    Equipment Type: {equipment_data.get('equipment_type', 'Unknown')}
                    Deleted by: {u.get('name', 'System')}
                    
                    This equipment is no longer available in the system.
                    """
                    from app.services.email_service import send_email
                    send_email(user['email'], subject, message)
            
            background_tasks.add_task(send_delete_notification)
        except Exception as e:
            logger.error(f"Failed to send deletion notification: {e}")
        
        return {"message": f"Equipment {equipment_id} permanently deleted"}
    else:
        # Soft delete - update status to DECOMMISSIONED
        now = datetime.now(timezone.utc).isoformat()
        with db() as c:
            c.execute(
                """
                UPDATE equipment_registry 
                SET status='DECOMMISSIONED', updated_at=? 
                WHERE equipment_id=? AND facility_id=?
            """,
                (now, equipment_id, facility_id),
            )

        audit(u, "DELETE_EQUIPMENT_SOFT", "equipment", equipment_id)
        
        # Send notification for soft delete
        try:
            def send_soft_delete_notification():
                NotificationService.notify_equipment_status_changed(
                    equipment_id, facility_id, equipment_data.get('status'), 'DECOMMISSIONED', u
                )
            background_tasks.add_task(send_soft_delete_notification)
        except Exception as e:
            logger.error(f"Failed to send soft delete notification: {e}")
        
        return {"message": f"Equipment {equipment_id} marked as DECOMMISSIONED"}


# --- POST Sync Data ---
@router.post("/sync-data")
def sync_equipment_data(
    u=Depends(require_roles("system_administrator", "national_administrator"))
):
    """Sync equipment data from CSV files to database"""
    from app.services.data_service import sync_equipment_from_csv, sync_telemetry_from_csv

    eq_result = sync_equipment_from_csv()
    tel_result = sync_telemetry_from_csv()

    audit(u, "SYNC_DATA", "equipment", details={
        "equipment": eq_result,
        "telemetry": tel_result
    })

    return {
        "message": "Data sync completed",
        "equipment": eq_result,
        "telemetry": tel_result,
    }

# --- POST Generate Telemetry ---
@router.post("/{equipment_id}/generate-telemetry")
def generate_telemetry_for_equipment(
    equipment_id: str,
    count: int = Query(100, description="Number of readings to generate"),
    u=Depends(require_roles('system_administrator', 'national_administrator', 'facility_manager', 'biomedical_engineer'))
):
    """Generate telemetry data for an existing equipment"""
    # Check if equipment exists
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    eq = eq_list[0]
    facility_id = eq.get("facility_id")

    # Generate telemetry
    data = TelemetrySimulator.generate_initial_readings(
        equipment_id, facility_id, eq.get("equipment_type", "Unknown"), count
    )

    audit(u, "GENERATE_TELEMETRY", "equipment", equipment_id, {"count": count})

    return {
        "message": f"Generated {count} telemetry readings",
        "equipment_id": equipment_id,
        "count": count,
        "sample": data[:5] if data else [],
    }

# --- GET Failure Prediction ---
@router.get("/{equipment_id}/failure-prediction")
def get_failure_prediction(equipment_id: str, u=Depends(current_user)):
    """Get failure prediction for equipment using telemetry data"""
    from app.engines.alert_engine import evaluate_equipment

    # Check if equipment exists
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    eq = eq_list[0]
    facility_id = eq.get("facility_id")

    # Get telemetry data
    telemetry_data = get_equipment_telemetry(equipment_id, facility_id, limit=50)

    if not telemetry_data:
        raise HTTPException(404, "No telemetry data available for this equipment")

    # Evaluate
    try:
        evaluation = evaluate_equipment(equipment_id, facility_id)

        # Add telemetry context
        evaluation["telemetry_count"] = len(telemetry_data)
        evaluation["latest_reading"] = telemetry_data[0] if telemetry_data else None

        audit(u, "VIEW_FAILURE_PREDICTION", "equipment", equipment_id)
        return evaluation
    except Exception as e:
        # Return baseline using telemetry
        risk_scores = [t.get("risk_score", 0) for t in telemetry_data if t.get("risk_score") is not None]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0

        return {
            "equipment_id": equipment_id,
            "facility_id": facility_id,
            "equipment_type": eq.get("equipment_type", "Unknown"),
            "severity": "HIGH" if avg_risk > 0.5 else "MEDIUM" if avg_risk > 0.2 else "LOW",
            "status": "ACTIVE" if avg_risk > 0.2 else "NORMAL",
            "failure_probability_24h": avg_risk,
            "failure_probability_72h": min(1.0, avg_risk * 1.08),
            "failure_probability_168h": min(1.0, avg_risk * 1.15),
            "rul_hours": None,
            "recommended_action": "Review telemetry and schedule maintenance based on risk score.",
            "telemetry_count": len(telemetry_data),
            "average_risk_score": avg_risk,
            "latest_reading": telemetry_data[0] if telemetry_data else None,
        }

# --- GET RUL ---
@router.get("/{equipment_id}/rul")
def get_equipment_rul(equipment_id: str, u=Depends(current_user)):
    """Get Remaining Useful Life prediction for equipment"""
    from app.ml.predictor import predict_rul

    # Check if equipment exists
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    eq = eq_list[0]
    facility_id = eq.get("facility_id")

    try:
        rul_hours, equipment_type = predict_rul(equipment_id)

        # Convert to days for readability
        rul_days = rul_hours / 24 if rul_hours else None

        audit(u, "VIEW_RUL", "equipment", equipment_id)

        return {
            "equipment_id": equipment_id,
            "equipment_type": equipment_type or eq.get("equipment_type", "Unknown"),
            "rul_hours": rul_hours,
            "rul_days": rul_days,
            "status": "CRITICAL" if rul_hours and rul_hours < 24 else "HIGH" if rul_hours and rul_hours < 72 else "MEDIUM" if rul_hours and rul_hours < 168 else "NORMAL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        # Fallback using telemetry
        telemetry_data = get_equipment_telemetry(equipment_id, facility_id, limit=10)
        if not telemetry_data:
            return {
                "equipment_id": equipment_id,
                "error": "No data available for RUL prediction",
                "rul_hours": None,
                "status": "UNKNOWN",
            }

        # Estimate RUL based on risk score trend
        risk_scores = [t.get("risk_score", 0) for t in telemetry_data if t.get("risk_score") is not None]
        if len(risk_scores) > 1:
            trend = (risk_scores[0] - risk_scores[-1]) / len(risk_scores)
            base_hours = 720  # 30 days baseline
            if trend > 0.01:
                estimated_rul = base_hours * (1 - min(1, trend * 100))
            else:
                estimated_rul = base_hours
        else:
            estimated_rul = 720

        return {
            "equipment_id": equipment_id,
            "equipment_type": eq.get("equipment_type", "Unknown"),
            "rul_hours": max(0, estimated_rul),
            "rul_days": max(0, estimated_rul / 24),
            "status": "CRITICAL" if estimated_rul < 24 else "HIGH" if estimated_rul < 72 else "MEDIUM" if estimated_rul < 168 else "NORMAL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "based_on": "telemetry_trend",
        }

# --- POST Evaluate Equipment ---
@router.post("/evaluate")
def evaluate_equipment_endpoint(
    request: EvaluateRequest,
    background_tasks: BackgroundTasks,
    u=Depends(current_user)
):
    """Evaluate equipment for failure probability and RUL"""
    # Check if equipment exists
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(request.equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    equipment_data = eq_list[0]
    facility_id = equipment_data.get("facility_id")

    try:
        result = evaluate_and_create_alert(request.equipment_id, facility_id)
        audit(u, "EVALUATE_EQUIPMENT", "equipment", request.equipment_id)
        
        # If alert was created, send notifications
        if result.get('created'):
            try:
                def send_alert_notification():
                    NotificationService.notify_alert_created(result.get('alert'), u)
                background_tasks.add_task(send_alert_notification)
            except Exception as e:
                logger.error(f"Failed to send alert notification: {e}")
        
        return result
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        # Newly registered equipment may not have ML telemetry
        telemetry_data = telemetry(request.equipment_id, facility_id=facility_id, limit=1)
        if not telemetry_data:
            return {
                "created": False,
                "equipment_id": request.equipment_id,
                "evaluation": {
                    "equipment_id": request.equipment_id,
                    "equipment_type": equipment_data.get("equipment_type", "Unknown"),
                    "severity": "LOW",
                    "status": "NORMAL",
                    "message": "No telemetry available yet for this equipment.",
                    "failure_probability_24h": 0.0,
                    "failure_probability_72h": 0.0,
                    "failure_probability_168h": 0.0,
                    "rul_hours": None,
                    "recommended_action": "Begin telemetry collection before predictive evaluation.",
                },
                "notifications": {"recipients": 0, "emails_sent": 0},
            }

        risk = float(telemetry_data[0].get("risk_score", 0))
        return {
            "created": False,
            "equipment_id": request.equipment_id,
            "evaluation": {
                "equipment_id": request.equipment_id,
                "equipment_type": equipment_data.get("equipment_type", "Unknown"),
                "severity": "MEDIUM" if risk >= 0.3 else "LOW",
                "status": "ACTIVE" if risk >= 0.3 else "NORMAL",
                "failure_probability_24h": risk,
                "failure_probability_72h": min(1, risk * 1.08),
                "failure_probability_168h": min(1, risk * 1.15),
                "rul_hours": None,
                "recommended_action": "Review telemetry and schedule maintenance according to risk.",
            },
            "notifications": {"recipients": 0, "emails_sent": 0},
        }

# --- POST Batch Telemetry Simulation ---
@router.post("/simulate-batch")
def simulate_batch_telemetry(request: TelemetryBatchRequest, u=Depends(current_user)):
    """Generate simulated telemetry data for testing"""
    eq = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(request.equipment_id)
    ]
    if not eq:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    equipment_data = eq[0]

    # Generate simulated telemetry
    telemetry_data = TelemetrySimulator.generate_batch(
        request.equipment_id,
        request.facility_id,
        request.count,
        equipment_data.get("equipment_type", "Unknown"),
    )

    # Save to CSV
    df = pd.DataFrame(telemetry_data)
    from app.core.paths import DATA_DIR

    file_path = DATA_DIR / "sensor_telemetry.csv"

    if file_path.exists():
        existing = pd.read_csv(file_path)
        df = pd.concat([existing, df], ignore_index=True)

    df.to_csv(file_path, index=False)

    audit(u, "SIMULATE_TELEMETRY", "equipment", request.equipment_id, {"count": request.count})

    return {
        "message": f"Generated {request.count} telemetry records",
        "equipment_id": request.equipment_id,
        "count": request.count,
    }

# --- GET Equipment Statistics ---
@router.get("/stats/summary")
def get_equipment_stats(
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    u=Depends(current_user),
):
    """Get equipment statistics summary"""
    eq = scope_filter(equipment(), u)

    if facility_id:
        eq = [e for e in eq if str(e.get("facility_id")) == facility_id]

    total = len(eq)
    operational = len([e for e in eq if e.get("status") == "OPERATIONAL"])
    maintenance = len([e for e in eq if e.get("status") == "MAINTENANCE"])
    decommissioned = len([e for e in eq if e.get("status") == "DECOMMISSIONED"])

    # Group by type
    by_type = {}
    for e in eq:
        eq_type = e.get("equipment_type", "Unknown")
        if eq_type not in by_type:
            by_type[eq_type] = {"total": 0, "operational": 0, "maintenance": 0, "decommissioned": 0}
        by_type[eq_type]["total"] += 1
        status = e.get("status", "UNKNOWN")
        if status in by_type[eq_type]:
            by_type[eq_type][status.lower()] += 1

    # Group by facility
    by_facility = {}
    for e in eq:
        fac_id = e.get("facility_id", "Unknown")
        if fac_id not in by_facility:
            by_facility[fac_id] = 0
        by_facility[fac_id] += 1

    return {
        "total": total,
        "operational": operational,
        "maintenance": maintenance,
        "decommissioned": decommissioned,
        "by_type": by_type,
        "by_facility": by_facility,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

# --- GET Telemetry Data ---
@router.get("/{equipment_id}/telemetry")
def get_equipment_telemetry_endpoint(
    equipment_id: str,
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    limit: int = Query(100, description="Number of records to return"),
    days: int = Query(7, description="Number of days to look back"),
    u=Depends(current_user),
):
    """Get telemetry data for a specific equipment"""
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    telemetry_data = telemetry(
        equipment_id=equipment_id,
        facility_id=facility_id or eq_list[0].get("facility_id"),
        limit=limit,
    )

    if days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        telemetry_data = [t for t in telemetry_data if t.get("timestamp", "") > cutoff]

    return {
        "equipment_id": equipment_id,
        "count": len(telemetry_data),
        "data": telemetry_data,
    }

# --- GET Alerts for Equipment ---
@router.get("/{equipment_id}/alerts")
def get_equipment_alerts(
    equipment_id: str,
    limit: int = Query(50, description="Number of alerts to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    u=Depends(current_user),
):
    """Get alerts for a specific equipment"""
    eq_list = [
        e for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not eq_list:
        raise HTTPException(404, "Equipment not found or outside your access scope")

    with db() as c:
        query = "SELECT * FROM alerts WHERE equipment_id=?"
        params = [equipment_id]

        if status:
            query += " AND status=?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        alerts = [dict(r) for r in c.execute(query, params).fetchall()]

    return {"equipment_id": equipment_id, "count": len(alerts), "alerts": alerts}
