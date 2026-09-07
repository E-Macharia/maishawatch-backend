import os
FAILURE_WARNING_THRESHOLD=float(os.getenv('FAILURE_WARNING_THRESHOLD','0.30'))
FAILURE_HIGH_THRESHOLD=float(os.getenv('FAILURE_HIGH_THRESHOLD','0.60'))
FAILURE_CRITICAL_THRESHOLD=float(os.getenv('FAILURE_CRITICAL_THRESHOLD','0.80'))
RUL_WARNING_HOURS=float(os.getenv('RUL_WARNING_HOURS','30'))
RUL_HIGH_HOURS=float(os.getenv('RUL_HIGH_HOURS','15'))
RUL_CRITICAL_HOURS=float(os.getenv('RUL_CRITICAL_HOURS','8'))
RUL_MEDIUM_HOURS=float(os.getenv('RUL_MEDIUM_HOURS','168'))
RUL_ALERT_THRESHOLD_HOURS=float(os.getenv('RUL_ALERT_THRESHOLD_HOURS',str(RUL_HIGH_HOURS)))

def get_risk_config():
    return {'failure_probability_warning':FAILURE_WARNING_THRESHOLD,'failure_probability_high':FAILURE_HIGH_THRESHOLD,'failure_probability_critical':FAILURE_CRITICAL_THRESHOLD,'rul_warning_hours':RUL_WARNING_HOURS,'rul_high_hours':RUL_HIGH_HOURS,'rul_critical_hours':RUL_CRITICAL_HOURS,'rul_medium_hours':RUL_MEDIUM_HOURS,'rul_alert_threshold_hours':RUL_ALERT_THRESHOLD_HOURS}
