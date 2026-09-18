# app/engines/alert_engine.py
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from app.core.db import db
from app.core.audit import audit
from app.ml.predictor import predict_failure, predict_rul
from app.ml.risk_config import *
from app.services.notification_service import NotificationService
import threading
import time
import logging

# Set up logging
logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _prob(v):
    """Convert probability to 0-1 range"""
    try:
        v = float(v)
    except (ValueError, TypeError):
        return 0.0

    if v > 1:
        v = v / 100
    return max(0.0, min(1.0, v))


def determine_severity(p24, p72, p168, rul):
    """Determine alert severity based on failure probabilities and RUL"""
    p = max(_prob(p24), _prob(p72), _prob(p168))

    if p >= FAILURE_CRITICAL_THRESHOLD or (
        rul is not None and rul <= RUL_CRITICAL_HOURS
    ):
        return "CRITICAL"
    if p >= FAILURE_HIGH_THRESHOLD or (rul is not None and rul <= RUL_HIGH_HOURS):
        return "HIGH"
    if p >= FAILURE_WARNING_THRESHOLD or (rul is not None and rul <= RUL_WARNING_HOURS):
        return "MEDIUM"
    return "LOW"


def build_recommendation(severity, p, rul):
    """Build recommendation based on severity"""
    if severity == "CRITICAL":
        return "Immediately inspect the equipment and consider taking it out of normal operation. Prioritize corrective maintenance."
    if severity == "HIGH":
        return "Schedule urgent biomedical inspection, review recent telemetry and maintenance history, and initiate corrective maintenance where required."
    if severity == "MEDIUM":
        return "Increase monitoring frequency, review telemetry and maintenance history, and schedule preventive maintenance if the risk persists."
    return "Continue routine monitoring and review the equipment during the next scheduled maintenance assessment."


def evaluate_equipment(equipment_id, facility_id=None):
    """Evaluate equipment for failure probability and RUL"""
    try:
        p24, t24 = predict_failure(equipment_id, "24h")
        p72, t72 = predict_failure(equipment_id, "72h")
        p168, t168 = predict_failure(equipment_id, "168h")
        rul, trul = predict_rul(equipment_id)

        severity = determine_severity(p24, p72, p168, rul)

        return {
            "equipment_id": equipment_id,
            "facility_id": facility_id,
            "equipment_type": t24 or t72 or t168 or trul or "Unknown",
            "severity": severity,
            "status": "ACTIVE" if severity != "LOW" else "NORMAL",
            "alert_type": "PREDICTIVE_FAILURE_RISK",
            "failure_probability_24h": p24,
            "failure_probability_72h": p72,
            "failure_probability_168h": p168,
            "rul_hours": rul,
            "recommended_action": build_recommendation(
                severity, max(p24, p72, p168), rul
            ),
        }
    except Exception as e:
        logger.warning(f"ML evaluation failed for {equipment_id}: {e}")
        # Fallback for equipment without ML data
        return {
            "equipment_id": equipment_id,
            "facility_id": facility_id,
            "equipment_type": "Unknown",
            "severity": "LOW",
            "status": "NORMAL",
            "alert_type": "PREDICTIVE_FAILURE_RISK",
            "failure_probability_24h": 0.0,
            "failure_probability_72h": 0.0,
            "failure_probability_168h": 0.0,
            "rul_hours": None,
            "recommended_action": "Begin telemetry collection before predictive evaluation.",
        }


def persist_evaluation(equipment_id, facility_id, evaluation):
    """Persist evaluation results to database and create/update alerts"""
    severity = evaluation["severity"]

    if severity == "LOW":
        # Close any existing alerts for this equipment
        with db() as c:
            c.execute(
                """
                UPDATE alerts
                SET status='RESOLVED', resolved_at=?, resolved_by='SYSTEM'
                WHERE equipment_id=? AND facility_id=? AND source='SYSTEM'
                AND status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS')
            """,
                (_now(), equipment_id, facility_id),
            )
        return {"created": False, "evaluation": evaluation}

    now = _now()
    alert = None
    created = False

    with db() as c:
        # Check for existing open alert
        existing = c.execute(
            """
            SELECT * FROM alerts
            WHERE equipment_id=? AND facility_id=? AND source='SYSTEM'
            AND alert_type='PREDICTIVE_FAILURE_RISK'
            AND status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS')
            ORDER BY created_at DESC LIMIT 1
        """,
            (equipment_id, facility_id),
        ).fetchone()

        p = max(
            evaluation["failure_probability_24h"],
            evaluation["failure_probability_72h"],
            evaluation["failure_probability_168h"],
        )

        title = f"{severity.title()} Predictive Failure Risk - {equipment_id}"
        message = (
            f"MaishaWatch detected elevated predictive failure risk for {equipment_id}. "
            f"24h: {evaluation['failure_probability_24h']:.1%}; "
            f"72h: {evaluation['failure_probability_72h']:.1%}; "
            f"168h: {evaluation['failure_probability_168h']:.1%}; "
            f"estimated RUL: {evaluation['rul_hours']:.1f} hours."
        )

        if existing:
            # Update existing alert if severity increased
            if severity != existing["severity"]:
                aid = existing["id"]
                c.execute(
                    """
                    UPDATE alerts
                    SET severity=?, title=?, message=?, recommendation=?, updated_at=?
                    WHERE id=?
                """,
                    (
                        severity,
                        title,
                        message,
                        evaluation["recommended_action"],
                        now,
                        aid,
                    ),
                )
                alert = dict(
                    c.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
                )
            else:
                alert = dict(existing)
        else:
            # Create new alert
            aid = f"ALT-{uuid4().hex[:12].upper()}"
            c.execute(
                """
                INSERT INTO alerts
                (id, alert_type, source, severity, title, message, recommendation,
                 equipment_id, facility_id, status, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    aid,
                    "PREDICTIVE_FAILURE_RISK",
                    "SYSTEM",
                    severity,
                    title,
                    message,
                    evaluation["recommended_action"],
                    equipment_id,
                    facility_id,
                    "OPEN",
                    "SYSTEM",
                    now,
                    now,
                ),
            )
            alert = dict(
                c.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
            )
            created = True

    # Send notifications for new alerts
    if created and alert:
        try:
            # Use the NotificationService
            notifications = NotificationService.notify_alert_created(alert, None)
            audit(
                None,
                "SYSTEM_ALERT_CREATED",
                "alert",
                alert["id"],
                {
                    "equipment_id": equipment_id,
                    "facility_id": facility_id,
                    "severity": severity,
                },
            )
            return {
                "created": created,
                "alert": alert,
                "evaluation": evaluation,
                "notifications": notifications,
            }
        except Exception as e:
            logger.error(f"Failed to send notifications for alert {alert['id']}: {e}")
            return {
                "created": created,
                "alert": alert,
                "evaluation": evaluation,
                "notifications": {"error": str(e)},
            }

    return {"created": created, "alert": alert, "evaluation": evaluation}


def evaluate_and_create_alert(equipment_id, facility_id):
    """Main function to evaluate equipment and create/update alerts"""
    evaluation = evaluate_equipment(equipment_id, facility_id)
    return persist_evaluation(equipment_id, facility_id, evaluation)


# --- Background Evaluation Runner ---
def run_periodic_evaluation():
    """Run evaluations every hour for all equipment"""

    def evaluate_all():
        while True:
            try:
                logger.info("Starting periodic equipment evaluation...")
                with db() as c:
                    equipment_list = c.execute("""
                        SELECT DISTINCT equipment_id, facility_id
                        FROM equipment_registry
                    """).fetchall()

                evaluated_count = 0
                alert_count = 0

                for eq in equipment_list:
                    try:
                        result = evaluate_and_create_alert(
                            eq["equipment_id"], eq["facility_id"]
                        )
                        evaluated_count += 1
                        if result.get("created"):
                            alert_count += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to evaluate equipment {eq['equipment_id']}: {e}"
                        )
                        # Continue with next equipment

                logger.info(
                    f"Periodic evaluation completed: {evaluated_count} equipment evaluated, {alert_count} new alerts created"
                )
                time.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error(f"Error in periodic evaluation: {e}")
                time.sleep(60)  # Wait a minute before retrying

    # Start the evaluation thread
    thread = threading.Thread(target=evaluate_all, daemon=True)
    thread.start()
    logger.info("Background evaluation runner started")
    return thread


# --- Manual Evaluation Functions ---
def evaluate_single_equipment(equipment_id, facility_id):
    """Manually evaluate a single piece of equipment"""
    return evaluate_and_create_alert(equipment_id, facility_id)


def evaluate_facility_equipment(facility_id):
    """Evaluate all equipment in a facility"""
    with db() as c:
        equipment_list = c.execute(
            """
            SELECT DISTINCT equipment_id, facility_id
            FROM equipment_registry
            WHERE facility_id = ?
        """,
            (facility_id,),
        ).fetchall()

    results = []
    for eq in equipment_list:
        try:
            result = evaluate_and_create_alert(eq["equipment_id"], eq["facility_id"])
            results.append(result)
        except Exception as e:
            results.append({"equipment_id": eq["equipment_id"], "error": str(e)})

    return {
        "facility_id": facility_id,
        "total_evaluated": len(equipment_list),
        "results": results,
    }

# app/engines/alert_engine.py - Add proactive alert notification


def send_proactive_alert(alert: Dict, chat_service=None):
    """Send proactive alert via chat"""
    try:
        # Get users who should receive the alert
        facility_id = alert.get("facility_id")
        severity = alert.get("severity", "MEDIUM")

        roles_to_notify = ["system_administrator", "national_administrator"]
        if severity in ["HIGH", "CRITICAL"]:
            roles_to_notify.extend(
                [
                    "national_executive",
                    "facility_manager",
                    "biomedical_engineer",
                    "clinician",
                ]
            )
        else:
            roles_to_notify.extend(["facility_manager", "biomedical_engineer"])

        # Get users
        from app.services.notification_service import NotificationService

        users = NotificationService.get_role_recipients(facility_id, roles_to_notify)

        # Send chat notifications
        for user in users:
            try:
                # Create conversation for user
                from app.services.chat_service import ChatMemory

                conversation_id = ChatMemory.create_conversation(
                    user["id"], f"Alert: {alert.get('title', '')[:50]}"
                )

                # Create message content
                message = f"""
🚨 **PROACTIVE ALERT**

**Severity:** {severity}
**Title:** {alert.get('title')}
**Equipment:** {alert.get('equipment_id', 'N/A')}
**Facility:** {alert.get('facility_id')}

**Message:** {alert.get('message')}

**Recommendation:** {alert.get('recommendation', 'Please review and take action.')}

*This is an automated proactive alert from MaishaWatch.*
"""

                # Save to conversation
                ChatMemory.add_message(
                    conversation_id, "system", message, "proactive_alert", alert
                )

                # Log the notification
                logger.info(f"Proactive alert sent to {user['email']} via chat")

            except Exception as e:
                logger.error(
                    f"Failed to send proactive chat alert to {user.get('email')}: {e}"
                )

        return {"sent": len(users)}

    except Exception as e:
        logger.error(f"Proactive alert failed: {e}")
        return {"error": str(e)}


def get_evaluation_status(equipment_id):
    """Get the current evaluation status for equipment"""
    with db() as c:
        # Get latest alert
        alert = c.execute(
            """
            SELECT * FROM alerts
            WHERE equipment_id = ? AND source = 'SYSTEM'
            ORDER BY created_at DESC LIMIT 1
        """,
            (equipment_id,),
        ).fetchone()

        # Get latest telemetry
        telemetry = c.execute(
            """
            SELECT * FROM sensor_telemetry
            WHERE equipment_id = ?
            ORDER BY timestamp DESC LIMIT 1
        """,
            (equipment_id,),
        ).fetchone()

    return {
        "equipment_id": equipment_id,
        "latest_alert": dict(alert) if alert else None,
        "latest_telemetry": dict(telemetry) if telemetry else None,
        "has_ml_data": alert is not None or telemetry is not None,
    }
