# app/api/routers/predictions.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.ml.schemas import EquipmentFeatures, RULRequest
from app.ml.predictor import (
    predict_failure_24h,
    predict_failure_72h,
    predict_failure_168h,
    predict_rul,
)
from app.core.security import current_user, require_roles, optional_user
from app.services.data_service import equipment, scope_filter, get_equipment_telemetry
from app.core.db import db
from app.core.audit import audit
from app.engines.alert_engine import (
    evaluate_equipment,
    determine_severity,
    build_recommendation,
)
from app.ml.risk_config import get_risk_config
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["ML Predictions"])


# --- Response Models ---
class FailurePredictionResponse(BaseModel):
    equipment_id: str
    equipment_type: str
    horizon: str
    failure_probability: float
    severity: str
    status: str
    recommendation: str
    timestamp: str
    has_telemetry: bool
    telemetry_count: int


class RULPredictionResponse(BaseModel):
    equipment_id: str
    equipment_type: str
    rul_hours: float
    rul_days: float
    severity: str
    status: str
    recommendation: str
    confidence_score: Optional[float] = None
    timestamp: str
    based_on: str  # 'ml_model' or 'telemetry_trend'


class BatchPredictionResponse(BaseModel):
    total: int
    predictions: List[Dict[str, Any]]
    timestamp: str
    summary: Dict[str, int]


# --- Helper Functions ---
def _check_equipment_access(equipment_id: str, u) -> Dict:
    """Check if user has access to equipment"""
    rows = [
        e
        for e in scope_filter(equipment(), u)
        if str(e.get("equipment_id")) == str(equipment_id)
    ]
    if not rows:
        raise HTTPException(404, "Equipment not found or outside your access scope")
    return rows[0]


def _get_prediction_severity(probability: float) -> Dict[str, str]:
    """Determine severity and status based on probability"""
    from app.ml.risk_config import (
        FAILURE_WARNING_THRESHOLD,
        FAILURE_HIGH_THRESHOLD,
        FAILURE_CRITICAL_THRESHOLD,
    )

    if probability >= FAILURE_CRITICAL_THRESHOLD:
        return {"severity": "CRITICAL", "status": "CRITICAL_RISK"}
    elif probability >= FAILURE_HIGH_THRESHOLD:
        return {"severity": "HIGH", "status": "HIGH_RISK"}
    elif probability >= FAILURE_WARNING_THRESHOLD:
        return {"severity": "MEDIUM", "status": "WARNING"}
    else:
        return {"severity": "LOW", "status": "NORMAL"}


def _get_rul_severity(rul_hours: float) -> Dict[str, str]:
    """Determine severity based on RUL hours"""
    from app.ml.risk_config import RUL_CRITICAL_HOURS, RUL_HIGH_HOURS, RUL_WARNING_HOURS

    if rul_hours <= RUL_CRITICAL_HOURS:
        return {"severity": "CRITICAL", "status": "IMMINENT_FAILURE"}
    elif rul_hours <= RUL_HIGH_HOURS:
        return {"severity": "HIGH", "status": "URGENT_MAINTENANCE"}
    elif rul_hours <= RUL_WARNING_HOURS:
        return {"severity": "MEDIUM", "status": "SCHEDULE_MAINTENANCE"}
    else:
        return {"severity": "LOW", "status": "NORMAL"}


# --- Individual Failure Prediction Endpoints ---
@router.post("/failure/24h", response_model=FailurePredictionResponse)
def predict_failure_24h_endpoint(data: EquipmentFeatures, u=Depends(optional_user)):
    """Predict failure probability within the next 24 hours"""
    equipment_data = _check_equipment_access(data.equipment_id, u)

    try:
        probability, equipment_type = predict_failure_24h(data.equipment_id)
        severity_info = _get_prediction_severity(probability)

        # Get telemetry info
        telemetry_data = get_equipment_telemetry(data.equipment_id, limit=1)

        # Build recommendation
        recommendation = build_recommendation(
            severity_info["severity"], probability, None
        )

        audit(
            u,
            "PREDICT_FAILURE_24H",
            "equipment",
            data.equipment_id,
            {"probability": probability, "severity": severity_info["severity"]},
        )

        return FailurePredictionResponse(
            equipment_id=data.equipment_id,
            equipment_type=equipment_type
            or equipment_data.get("equipment_type", "Unknown"),
            horizon="24h",
            failure_probability=round(probability, 4),
            severity=severity_info["severity"],
            status=severity_info["status"],
            recommendation=recommendation,
            timestamp=datetime.now(timezone.utc).isoformat(),
            has_telemetry=len(telemetry_data) > 0,
            telemetry_count=len(telemetry_data),
        )
    except Exception as e:
        logger.error(f"24h prediction failed for {data.equipment_id}: {e}")
        raise HTTPException(503, f"Prediction service unavailable: {str(e)}")


@router.post("/failure/72h", response_model=FailurePredictionResponse)
def predict_failure_72h_endpoint(data: EquipmentFeatures, u=Depends(optional_user)):
    """Predict failure probability within the next 72 hours"""
    equipment_data = _check_equipment_access(data.equipment_id, u)

    try:
        probability, equipment_type = predict_failure_72h(data.equipment_id)
        severity_info = _get_prediction_severity(probability)

        telemetry_data = get_equipment_telemetry(data.equipment_id, limit=1)

        recommendation = build_recommendation(
            severity_info["severity"], probability, None
        )

        audit(
            u,
            "PREDICT_FAILURE_72H",
            "equipment",
            data.equipment_id,
            {"probability": probability, "severity": severity_info["severity"]},
        )

        return FailurePredictionResponse(
            equipment_id=data.equipment_id,
            equipment_type=equipment_type
            or equipment_data.get("equipment_type", "Unknown"),
            horizon="72h",
            failure_probability=round(probability, 4),
            severity=severity_info["severity"],
            status=severity_info["status"],
            recommendation=recommendation,
            timestamp=datetime.now(timezone.utc).isoformat(),
            has_telemetry=len(telemetry_data) > 0,
            telemetry_count=len(telemetry_data),
        )
    except Exception as e:
        logger.error(f"72h prediction failed for {data.equipment_id}: {e}")
        raise HTTPException(503, f"Prediction service unavailable: {str(e)}")


@router.post("/failure/168h", response_model=FailurePredictionResponse)
def predict_failure_168h_endpoint(data: EquipmentFeatures, u=Depends(optional_user)):
    """Predict failure probability within the next 168 hours (7 days)"""
    equipment_data = _check_equipment_access(data.equipment_id, u)

    try:
        probability, equipment_type = predict_failure_168h(data.equipment_id)
        severity_info = _get_prediction_severity(probability)

        telemetry_data = get_equipment_telemetry(data.equipment_id, limit=1)

        recommendation = build_recommendation(
            severity_info["severity"], probability, None
        )

        audit(
            u,
            "PREDICT_FAILURE_168H",
            "equipment",
            data.equipment_id,
            {"probability": probability, "severity": severity_info["severity"]},
        )

        return FailurePredictionResponse(
            equipment_id=data.equipment_id,
            equipment_type=equipment_type
            or equipment_data.get("equipment_type", "Unknown"),
            horizon="168h",
            failure_probability=round(probability, 4),
            severity=severity_info["severity"],
            status=severity_info["status"],
            recommendation=recommendation,
            timestamp=datetime.now(timezone.utc).isoformat(),
            has_telemetry=len(telemetry_data) > 0,
            telemetry_count=len(telemetry_data),
        )
    except Exception as e:
        logger.error(f"168h prediction failed for {data.equipment_id}: {e}")
        raise HTTPException(503, f"Prediction service unavailable: {str(e)}")


# --- Combined Prediction Endpoint ---
@router.post("/failure/all")
def predict_all_failures(data: EquipmentFeatures, u=Depends(optional_user)):
    """Get failure predictions for all horizons (24h, 72h, 168h)"""
    equipment_data = _check_equipment_access(data.equipment_id, u)

    result = {
        "equipment_id": data.equipment_id,
        "equipment_type": equipment_data.get("equipment_type", "Unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "predictions": {},
        "overall_severity": "LOW",
        "recommendation": "",
    }

    horizons = {
        "24h": predict_failure_24h,
        "72h": predict_failure_72h,
        "168h": predict_failure_168h,
    }

    probabilities = {}
    max_prob = 0

    for horizon, func in horizons.items():
        try:
            probability, _ = func(data.equipment_id)
            probabilities[horizon] = round(probability, 4)
            max_prob = max(max_prob, probability)

            severity_info = _get_prediction_severity(probability)
            result["predictions"][horizon] = {
                "probability": round(probability, 4),
                "severity": severity_info["severity"],
                "status": severity_info["status"],
            }
        except Exception as e:
            result["predictions"][horizon] = {"error": str(e), "probability": None}

    # Overall severity
    overall_severity_info = _get_prediction_severity(max_prob)
    result["overall_severity"] = overall_severity_info["severity"]
    result["overall_status"] = overall_severity_info["status"]
    result["max_probability"] = round(max_prob, 4)
    result["recommendation"] = build_recommendation(
        overall_severity_info["severity"], max_prob, None
    )

    audit(
        u,
        "PREDICT_ALL_FAILURES",
        "equipment",
        data.equipment_id,
        {
            "probabilities": probabilities,
            "max_probability": max_prob,
            "severity": overall_severity_info["severity"],
        },
    )

    return result


# --- RUL Prediction Endpoint ---
@router.post("/rul", response_model=RULPredictionResponse)
def predict_rul_endpoint(data: RULRequest, u=Depends(optional_user)):
    """Predict Remaining Useful Life (RUL) in hours"""
    equipment_data = _check_equipment_access(data.equipment_id, u)

    try:
        rul_hours, equipment_type = predict_rul(data.equipment_id)

        # Ensure non-negative
        rul_hours = max(0, rul_hours)
        rul_days = rul_hours / 24

        severity_info = _get_rul_severity(rul_hours)

        recommendation = build_recommendation(
            severity_info["severity"],
            0,  # Not using failure probability for RUL
            rul_hours,
        )

        audit(
            u,
            "PREDICT_RUL",
            "equipment",
            data.equipment_id,
            {
                "rul_hours": rul_hours,
                "rul_days": rul_days,
                "severity": severity_info["severity"],
            },
        )

        return RULPredictionResponse(
            equipment_id=data.equipment_id,
            equipment_type=equipment_type
            or equipment_data.get("equipment_type", "Unknown"),
            rul_hours=round(rul_hours, 2),
            rul_days=round(rul_days, 2),
            severity=severity_info["severity"],
            status=severity_info["status"],
            recommendation=recommendation,
            confidence_score=0.85,  # Placeholder - can be calculated from model
            timestamp=datetime.now(timezone.utc).isoformat(),
            based_on="ml_model",
        )
    except Exception as e:
        logger.error(f"RUL prediction failed for {data.equipment_id}: {e}")

        # Fallback: Estimate RUL from telemetry trend
        telemetry_data = get_equipment_telemetry(data.equipment_id, limit=50)
        if telemetry_data and len(telemetry_data) > 1:
            risk_scores = [
                t.get("risk_score", 0)
                for t in telemetry_data
                if t.get("risk_score") is not None
            ]
            if risk_scores:
                trend = (risk_scores[0] - risk_scores[-1]) / len(risk_scores)
                base_hours = 720  # 30 days baseline
                if trend > 0.01:
                    estimated_rul = base_hours * (1 - min(1, trend * 100))
                else:
                    estimated_rul = base_hours
                estimated_rul = max(0, estimated_rul)

                severity_info = _get_rul_severity(estimated_rul)
                recommendation = build_recommendation(
                    severity_info["severity"], 0, estimated_rul
                )

                return RULPredictionResponse(
                    equipment_id=data.equipment_id,
                    equipment_type=equipment_data.get("equipment_type", "Unknown"),
                    rul_hours=round(estimated_rul, 2),
                    rul_days=round(estimated_rul / 24, 2),
                    severity=severity_info["severity"],
                    status=severity_info["status"],
                    recommendation=recommendation,
                    confidence_score=0.5,  # Lower confidence for trend-based estimate
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    based_on="telemetry_trend",
                )

        raise HTTPException(503, f"RUL prediction service unavailable: {str(e)}")


# --- Batch Predictions ---
@router.post("/failure/batch")
def predict_batch_failures(
    equipment_ids: List[str] = Query(..., description="List of equipment IDs"),
    horizon: str = Query("24h", description="Prediction horizon: 24h, 72h, 168h"),
    u=Depends(
        require_roles(
            "system_administrator", "national_administrator", "facility_manager"
        )
    ),
):
    """Get failure predictions for multiple equipment at once"""
    horizon_map = {
        "24h": predict_failure_24h,
        "72h": predict_failure_72h,
        "168h": predict_failure_168h,
    }

    if horizon not in horizon_map:
        raise HTTPException(
            400, f'Invalid horizon. Must be one of: {", ".join(horizon_map.keys())}'
        )

    results = []
    summary = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "ERROR": 0}

    for eq_id in equipment_ids:
        try:
            # Check access
            equipment_data = _check_equipment_access(eq_id, u)

            # Get prediction
            probability, equipment_type = horizon_map[horizon](eq_id)
            severity_info = _get_prediction_severity(probability)

            results.append(
                {
                    "equipment_id": eq_id,
                    "equipment_type": equipment_type
                    or equipment_data.get("equipment_type", "Unknown"),
                    "probability": round(probability, 4),
                    "severity": severity_info["severity"],
                    "status": severity_info["status"],
                }
            )

            summary[severity_info["severity"]] = (
                summary.get(severity_info["severity"], 0) + 1
            )

        except Exception as e:
            logger.error(f"Batch prediction failed for {eq_id}: {e}")
            results.append(
                {"equipment_id": eq_id, "error": str(e), "severity": "ERROR"}
            )
            summary["ERROR"] += 1

    audit(
        u,
        "PREDICT_BATCH_FAILURES",
        "prediction",
        details={
            "horizon": horizon,
            "total": len(equipment_ids),
            "successful": len(results) - summary["ERROR"],
            "summary": summary,
        },
    )

    return {
        "total": len(equipment_ids),
        "predictions": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "horizon": horizon,
        "summary": summary,
    }


# --- Batch RUL Predictions ---
@router.post("/rul/batch")
def predict_batch_rul(
    equipment_ids: List[str] = Query(..., description="List of equipment IDs"),
    u=Depends(
        require_roles(
            "system_administrator", "national_administrator", "facility_manager"
        )
    ),
):
    """Get RUL predictions for multiple equipment at once"""
    results = []
    summary = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "ERROR": 0}

    for eq_id in equipment_ids:
        try:
            equipment_data = _check_equipment_access(eq_id, u)

            rul_hours, equipment_type = predict_rul(eq_id)
            rul_hours = max(0, rul_hours)

            severity_info = _get_rul_severity(rul_hours)

            results.append(
                {
                    "equipment_id": eq_id,
                    "equipment_type": equipment_type
                    or equipment_data.get("equipment_type", "Unknown"),
                    "rul_hours": round(rul_hours, 2),
                    "rul_days": round(rul_hours / 24, 2),
                    "severity": severity_info["severity"],
                    "status": severity_info["status"],
                }
            )

            summary[severity_info["severity"]] = (
                summary.get(severity_info["severity"], 0) + 1
            )

        except Exception as e:
            logger.error(f"Batch RUL prediction failed for {eq_id}: {e}")
            results.append(
                {"equipment_id": eq_id, "error": str(e), "severity": "ERROR"}
            )
            summary["ERROR"] += 1

    audit(
        u,
        "PREDICT_BATCH_RUL",
        "prediction",
        details={
            "total": len(equipment_ids),
            "successful": len(results) - summary["ERROR"],
            "summary": summary,
        },
    )

    return {
        "total": len(equipment_ids),
        "predictions": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }


# --- Get Risk Configuration ---
@router.get("/config")
def get_risk_configuration(u=Depends(optional_user)):
    """Get current risk threshold configuration"""
    from app.ml.risk_config import get_risk_config

    return {
        "config": get_risk_config(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# --- Get Prediction History ---
@router.get("/history/{equipment_id}")
def get_prediction_history(
    equipment_id: str,
    limit: int = Query(50, description="Number of records to return"),
    u=Depends(optional_user),
):
    """Get historical prediction results for equipment"""
    _check_equipment_access(equipment_id, u)

    with db() as c:
        # Get alerts (which contain prediction results)
        alerts = c.execute(
            """
            SELECT id, severity, title, message, recommendation, 
                   created_at, status, source
            FROM alerts 
            WHERE equipment_id = ? AND source = 'SYSTEM'
            ORDER BY created_at DESC LIMIT ?
        """,
            (equipment_id, limit),
        ).fetchall()

        return {
            "equipment_id": equipment_id,
            "history": [dict(a) for a in alerts],
            "count": len(alerts),
        }


# --- Health Check for ML Service ---
@router.get("/health")
def ml_health_check(u=Depends(optional_user)):
    """Check ML service health and model availability"""
    models_status = {"24h": False, "72h": False, "168h": False, "rul": False}

    try:
        # Test each model with a sample prediction
        from app.ml.predictor import (
            predict_failure_24h,
            predict_failure_72h,
            predict_failure_168h,
            predict_rul,
        )

        # Get any equipment ID
        eq_list = equipment()
        if eq_list:
            test_id = eq_list[0].get("equipment_id")
            if test_id:
                try:
                    predict_failure_24h(test_id)
                    models_status["24h"] = True
                except:
                    pass
                try:
                    predict_failure_72h(test_id)
                    models_status["72h"] = True
                except:
                    pass
                try:
                    predict_failure_168h(test_id)
                    models_status["168h"] = True
                except:
                    pass
                try:
                    predict_rul(test_id)
                    models_status["rul"] = True
                except:
                    pass

    except Exception as e:
        logger.error(f"ML health check failed: {e}")
        return {
            "status": "degraded",
            "models": models_status,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    all_available = all(models_status.values())

    return {
        "status": "healthy" if all_available else "degraded",
        "models": models_status,
        "all_available": all_available,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
