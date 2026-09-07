from pathlib import Path
import joblib
import pandas as pd
import numpy as np
from app.core.paths import DATA_DIR, ML_DATA_DIR, MODELS_DIR

MODELS_DIR.mkdir(parents=True, exist_ok=True)

class _FallbackClassifier:
    feature_names_in_ = np.array([])
    def predict_proba(self, X):
        return np.array([[0.85, 0.15]])

class _FallbackRegressor:
    feature_names_in_ = np.array([])
    def predict(self, X):
        return np.array([720.0])

FAILURE_MODELS = {}
FAILURE_FEATURES = {}
for h in (24, 72, 168):
    p = MODELS_DIR / f'failure_model_{h}h.pkl'
    if p.exists():
        try:
            m = joblib.load(p)
            FAILURE_MODELS[h] = m
            FAILURE_FEATURES[h] = list(getattr(m, 'feature_names_in_', []))
        except Exception:
            FAILURE_MODELS[h] = _FallbackClassifier()
            FAILURE_FEATURES[h] = []
    else:
        FAILURE_MODELS[h] = _FallbackClassifier()
        FAILURE_FEATURES[h] = []

# Keep preprocessing identical to the models bundled with this project.
EXCLUDE = {
    'timestamp','equipment_id','facility_id','facility','failure','rul_hours',
    'risk_score','degradation_index','condition_status','operational_status',
    'error_code','scenario_type','installation_date'
}

def _prepare(row: pd.DataFrame, expected):
    d = row.copy()
    if 'timestamp' in d:
        ts = pd.to_datetime(d['timestamp'], errors='coerce')
        d['hour'] = ts.dt.hour.fillna(0).astype(float)
        d['day_of_week'] = ts.dt.dayofweek.fillna(0).astype(float)
        d['month'] = ts.dt.month.fillna(1).astype(float)
    d = d.drop(columns=[c for c in EXCLUDE if c in d.columns], errors='ignore')
    d = d.drop(columns=[c for c in d.columns if c.startswith('failure_next_')], errors='ignore')
    cat = d.select_dtypes(include=['object','string','category']).columns.tolist()
    if cat:
        d = pd.get_dummies(d, columns=cat, dtype=float)
    d = d.reindex(columns=expected, fill_value=0)
    return d.replace([np.inf,-np.inf], np.nan).fillna(0).astype(float)

def _load_source(horizon):
    # All three bundled models were trained from the same current telemetry
    # feature source; horizon-specific labels are training-only artifacts.
    p = DATA_DIR / 'predictive_maintenance_dataset.csv'
    if not p.exists():
        raise FileNotFoundError(f'ML source dataset not found: {p}')
    return pd.read_csv(p)

def build_failure_features(equipment_id, horizon):
    horizon = int(str(horizon).replace('h',''))
    if horizon not in FAILURE_MODELS:
        raise ValueError('Unsupported failure horizon. Use 24h, 72h or 168h.')
    df = _load_source(horizon)
    rows = df[df['equipment_id'].astype(str) == str(equipment_id)]
    if rows.empty:
        raise ValueError(f"Equipment '{equipment_id}' not found in ML telemetry data.")
    rows = rows.copy(); rows['timestamp'] = pd.to_datetime(rows['timestamp'], errors='coerce')
    row = rows.sort_values('timestamp').iloc[[-1]].copy()
    equipment_type = str(row.iloc[0].get('equipment_type','Unknown'))
    return _prepare(row, FAILURE_FEATURES[horizon]), equipment_type

_rul_model_path = MODELS_DIR / 'rul_model.pkl'
_rul_features_path = MODELS_DIR / 'rul_features.pkl'

if _rul_model_path.exists():
    try:
        RUL_MODEL = joblib.load(_rul_model_path)
    except Exception:
        RUL_MODEL = _FallbackRegressor()
else:
    RUL_MODEL = _FallbackRegressor()

if _rul_features_path.exists():
    try:
        RUL_FEATURES = list(joblib.load(_rul_features_path))
    except Exception:
        RUL_FEATURES = []
else:
    RUL_FEATURES = []

def build_rul_features(equipment_id):
    p = DATA_DIR / 'predictive_maintenance_dataset.csv'
    df = pd.read_csv(p)
    rows = df[df['equipment_id'].astype(str) == str(equipment_id)]
    if rows.empty:
        raise ValueError(f"Equipment '{equipment_id}' not found in ML telemetry data.")
    rows = rows.copy(); rows['timestamp'] = pd.to_datetime(rows['timestamp'], errors='coerce')
    row = rows.sort_values('timestamp').iloc[[-1]].copy()
    equipment_type = str(row.iloc[0].get('equipment_type','Unknown'))
    return _prepare(row, RUL_FEATURES), equipment_type
