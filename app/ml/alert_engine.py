from app.engines.alert_engine import determine_severity, build_recommendation

def classify_alert(failure_probability, rul_hours=None):
    severity = determine_severity(failure_probability, rul_hours)
    return {'severity': severity, 'recommendation': build_recommendation(severity, failure_probability, rul_hours)}
