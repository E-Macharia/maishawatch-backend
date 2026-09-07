from dataclasses import dataclass, field
from typing import List


@dataclass
class AlertConfig:
    """
    Configurable Alert Engine thresholds.

    These values can later be moved into a database/settings table.
    """

    # Failure probability thresholds
    failure_warning: float = 0.30
    failure_high: float = 0.60
    failure_critical: float = 0.80

    # RUL thresholds in hours
    rul_warning_hours: float = 30.0
    rul_high_hours: float = 15.0
    rul_critical_hours: float = 8.0

    # Usage discrepancy
    usage_discrepancy_warning: float = 0.30
    usage_discrepancy_high: float = 0.50

    # Historical failure count
    previous_failures_warning: int = 1
    previous_failures_high: int = 3

    # Risk score
    risk_warning: float = 0.50
    risk_high: float = 0.70
    risk_critical: float = 0.80


@dataclass
class AlertResult:
    severity: str
    reasons: List[str] = field(default_factory=list)
    recommended_action: str = "Continue routine monitoring"
    weighted_failure_risk: float = 0.0


def evaluate_alert(
    failure_24h: float,
    failure_72h: float,
    failure_168h: float,
    rul_hours: float,
    risk_score: float = 0.0,
    previous_failures: int = 0,
    maintenance_overdue: bool = False,
    anomaly_detected: bool = False,
    usage_discrepancy_pct: float = 0.0,
    operational_status: str = "Normal",
    config: AlertConfig | None = None,
) -> AlertResult:

    if config is None:
        config = AlertConfig()

    # ---------------------------------------------------------
    # Normalize values
    # ---------------------------------------------------------

    failure_24h = float(failure_24h or 0)
    failure_72h = float(failure_72h or 0)
    failure_168h = float(failure_168h or 0)
    rul_hours = float(rul_hours or 0)
    risk_score = float(risk_score or 0)
    usage_discrepancy_pct = float(
        usage_discrepancy_pct or 0
    )

    previous_failures = int(
        previous_failures or 0
    )

    reasons = []

    severity_score = 0

    # =========================================================
    # FAILURE PROBABILITY
    # =========================================================

    # 24-hour failure
    if failure_24h >= config.failure_critical:
        severity_score = max(severity_score, 4)

        reasons.append(
            "24-hour failure probability is critically high."
        )

    elif failure_24h >= config.failure_high:
        severity_score = max(severity_score, 3)

        reasons.append(
            "24-hour failure probability is high."
        )

    elif failure_24h >= config.failure_warning:
        severity_score = max(severity_score, 2)

        reasons.append(
            "24-hour failure probability is elevated."
        )

    # 72-hour failure
    if failure_72h >= config.failure_critical:
        severity_score = max(severity_score, 4)

        reasons.append(
            "72-hour failure probability is critically high."
        )

    elif failure_72h >= config.failure_high:
        severity_score = max(severity_score, 3)

        reasons.append(
            "72-hour failure probability is high."
        )

    elif failure_72h >= config.failure_warning:
        severity_score = max(severity_score, 2)

        reasons.append(
            "72-hour failure probability is elevated."
        )

    # 168-hour failure
    if failure_168h >= config.failure_critical:
        severity_score = max(severity_score, 4)

        reasons.append(
            "168-hour failure probability is critically high."
        )

    elif failure_168h >= config.failure_high:
        severity_score = max(severity_score, 3)

        reasons.append(
            "168-hour failure probability is high."
        )

    elif failure_168h >= config.failure_warning:
        severity_score = max(severity_score, 2)

        reasons.append(
            "168-hour failure probability is elevated."
        )

    # =========================================================
    # RUL
    # =========================================================

    if rul_hours <= config.rul_critical_hours:

        severity_score = max(
            severity_score,
            4
        )

        reasons.append(
            "Remaining useful life is below the critical threshold."
        )

    elif rul_hours <= config.rul_high_hours:

        severity_score = max(
            severity_score,
            3
        )

        reasons.append(
            "Remaining useful life is below the high-risk threshold."
        )

    elif rul_hours <= config.rul_warning_hours:

        severity_score = max(
            severity_score,
            2
        )

        reasons.append(
            "Remaining useful life is approaching the maintenance threshold."
        )

    # =========================================================
    # CURRENT RISK SCORE
    # =========================================================

    if risk_score >= config.risk_critical:

        severity_score = max(
            severity_score,
            4
        )

        reasons.append(
            "Current equipment risk score is critically high."
        )

    elif risk_score >= config.risk_high:

        severity_score = max(
            severity_score,
            3
        )

        reasons.append(
            "Current equipment risk score is high."
        )

    elif risk_score >= config.risk_warning:

        severity_score = max(
            severity_score,
            2
        )

        reasons.append(
            "Current equipment risk score is elevated."
        )

    # =========================================================
    # HISTORICAL FAILURES
    # =========================================================

    if previous_failures >= config.previous_failures_high:

        severity_score = max(
            severity_score,
            3
        )

        reasons.append(
            f"Equipment has {previous_failures} previously recorded failures."
        )

    elif previous_failures >= config.previous_failures_warning:

        severity_score = max(
            severity_score,
            2
        )

        reasons.append(
            f"Equipment has {previous_failures} previously recorded failure."
        )

    # =========================================================
    # MAINTENANCE
    # =========================================================

    if maintenance_overdue:

        severity_score = max(
            severity_score,
            3
        )

        reasons.append(
            "Equipment maintenance is overdue."
        )

    # =========================================================
    # ANOMALY
    # =========================================================

    if anomaly_detected:

        severity_score = max(
            severity_score,
            3
        )

        reasons.append(
            "Anomaly detected in equipment operation."
        )

    # =========================================================
    # USAGE DISCREPANCY
    # =========================================================

    if usage_discrepancy_pct >= config.usage_discrepancy_high:

        severity_score = max(
            severity_score,
            3
        )

        reasons.append(
            "Large usage-reporting discrepancy detected."
        )

    elif usage_discrepancy_pct >= config.usage_discrepancy_warning:

        severity_score = max(
            severity_score,
            2
        )

        reasons.append(
            "Usage-reporting discrepancy detected."
        )

    # =========================================================
    # OPERATIONAL STATUS
    # =========================================================

    status = str(
        operational_status or ""
    ).lower()

    if status in {
        "failed",
        "critical"
    }:

        severity_score = max(
            severity_score,
            4
        )

        reasons.append(
            "Equipment operational status is critical or failed."
        )

    elif status in {
        "degraded",
        "warning"
    }:

        severity_score = max(
            severity_score,
            3
        )

        reasons.append(
            "Equipment operational status indicates degradation."
        )

    # =========================================================
    # WEIGHTED FAILURE RISK
    # =========================================================

    weighted_failure_risk = (
        failure_24h * 0.50
        + failure_72h * 0.30
        + failure_168h * 0.20
    )

    weighted_failure_risk = round(
        weighted_failure_risk,
        6
    )

    # =========================================================
    # FINAL SEVERITY
    # =========================================================

    if severity_score >= 4:

        severity = "CRITICAL"

        action = (
            "Immediate inspection and maintenance required."
        )

    elif severity_score == 3:

        severity = "HIGH"

        action = (
            "Prioritize equipment inspection and maintenance."
        )

    elif severity_score == 2:

        severity = "WARNING"

        action = (
            "Schedule inspection and increase monitoring."
        )

    else:

        severity = "NORMAL"

        action = (
            "Continue routine monitoring."
        )

    # =========================================================
    # FALLBACK REASON
    # =========================================================

    if not reasons:

        reasons.append(
            "No significant risk indicators detected."
        )

    return AlertResult(
        severity=severity,
        reasons=reasons,
        recommended_action=action,
        weighted_failure_risk=weighted_failure_risk,
    )