from app.ml.feature_builder import build_failure_features, FAILURE_MODELS, build_rul_features, RUL_MODEL

def predict_failure(equipment_id, horizon):
    features, equipment_type = build_failure_features(equipment_id, horizon)
    probability = float(FAILURE_MODELS[int(str(horizon).replace('h',''))].predict_proba(features)[0][1])
    return probability, equipment_type

def predict_failure_24h(equipment_id): return predict_failure(equipment_id, '24h')
def predict_failure_72h(equipment_id): return predict_failure(equipment_id, '72h')
def predict_failure_168h(equipment_id): return predict_failure(equipment_id, '168h')

def predict_rul(equipment_id):
    features, equipment_type = build_rul_features(equipment_id)
    prediction = max(0.0, float(RUL_MODEL.predict(features)[0]))
    return prediction, equipment_type
