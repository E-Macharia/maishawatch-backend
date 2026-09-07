from fastapi import APIRouter,Depends,HTTPException
from app.ml.schemas import EquipmentFeatures
from app.ml.predictor import predict_failure_24h,predict_failure_72h,predict_failure_168h
from app.core.security import current_user
from app.services.data_service import equipment,scope_filter
router=APIRouter(tags=['ML Failure Prediction'])

def _check(data,u):
    rows=[e for e in scope_filter(equipment(),u) if str(e.get('equipment_id'))==str(data.equipment_id)]
    if not rows: raise HTTPException(404,'Equipment not found or outside your access scope')
    return rows[0]
@router.post('/predict/failure/24h')
def failure_24h(data:EquipmentFeatures,u=Depends(current_user)):
    e=_check(data,u)
    try: p,t=predict_failure_24h(data.equipment_id); return {'equipment_id':data.equipment_id,'equipment_type':t or e.get('equipment_type'),'horizon':'24h','failure_probability':p}
    except Exception as exc: raise HTTPException(503,str(exc))
@router.post('/predict/failure/72h')
def failure_72h(data:EquipmentFeatures,u=Depends(current_user)):
    e=_check(data,u)
    try: p,t=predict_failure_72h(data.equipment_id); return {'equipment_id':data.equipment_id,'equipment_type':t or e.get('equipment_type'),'horizon':'72h','failure_probability':p}
    except Exception as exc: raise HTTPException(503,str(exc))
@router.post('/predict/failure/168h')
def failure_168h(data:EquipmentFeatures,u=Depends(current_user)):
    e=_check(data,u)
    try: p,t=predict_failure_168h(data.equipment_id); return {'equipment_id':data.equipment_id,'equipment_type':t or e.get('equipment_type'),'horizon':'168h','failure_probability':p}
    except Exception as exc: raise HTTPException(503,str(exc))
