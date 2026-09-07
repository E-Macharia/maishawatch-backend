from app.ml.recommendation_engine import recommendation_for_role

def get_recommendation(role, severity, base_recommendation):
    return recommendation_for_role(role, severity, base_recommendation)
