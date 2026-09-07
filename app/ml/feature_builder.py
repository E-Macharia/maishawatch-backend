from pathlib import Path
import joblib
import pandas as pd
import numpy as np
from app.core.paths import DATA_DIR, ML_DATA_DIR, MODELS_DIR

FAILURE_MODELS = {
    h: joblib.load(MODELS_DIR / f'failure_model_{h}h.pkl') for h in (24,72,168)
}
FAILURE_FEATURES = {h: list(m.feature_names_in_) for h,m in FAILURE_MODELS.items()}

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

RUL_MODEL = joblib.load(MODELS_DIR / 'rul_model.pkl')
RUL_FEATURES = list(joblib.load(MODELS_DIR / 'rul_features.pkl'))

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
