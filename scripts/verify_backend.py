from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ml.predictor import predict_failure_24h, predict_failure_72h, predict_failure_168h, predict_rul
from app.services.data_service import equipment
from app.engines.alert_engine import evaluate_and_create_alert
from app.core.db import db

root=Path(__file__).resolve().parents[1]
required=[root/'models/failure_model_24h.pkl',root/'models/failure_model_72h.pkl',root/'models/failure_model_168h.pkl',root/'models/rul_model.pkl',root/'data/predictive_maintenance_dataset.csv']
for p in required:
    assert p.exists(), f'Missing {p}'
row=equipment()[0]; eid=str(row['equipment_id']); fid=str(row['facility_id'])
for fn in (predict_failure_24h,predict_failure_72h,predict_failure_168h):
    value,_=fn(eid); assert 0<=value<=1
rul,_=predict_rul(eid); assert rul>=0
result=evaluate_and_create_alert(eid,fid)
assert 'created' in result
with db() as c:
    c.execute("DELETE FROM alerts WHERE equipment_id=?",(eid,))
print('ML verification: PASS')
print('Equipment:',eid,'Facility:',fid,'RUL:',round(rul,2))
