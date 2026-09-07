from fastapi import APIRouter,Depends,HTTPException
from app.ml.schemas import RULRequest
from app.ml.predictor import predict_rul
from app.core.security import current_user
from app.services.data_service import equipment,scope_filter
from app.ml.risk_config import RUL_ALERT_THRESHOLD_HOURS
router=APIRouter(tags=['ML RUL Prediction'])
@router.post('/predict/rul')
def rul(data:RULRequest,u=Depends(current_user)):
    rows=[e for e in scope_filter(equipment(),u) if str(e.get('equipment_id'))==str(data.equipment_id)]
    if not rows: raise HTTPException(404,'Equipment not found or outside your access scope')
    try:
        hours,t=predict_rul(data.equipment_id); return {'equipment_id':data.equipment_id,'equipment_type':t or rows[0].get('equipment_type'),'rul_hours':hours,'alert_threshold_hours':RUL_ALERT_THRESHOLD_HOURS}
    except Exception as exc: raise HTTPException(503,str(exc))
