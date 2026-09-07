from fastapi import APIRouter,Depends
from app.core.security import current_user
from app.ml.recommendation_engine import ROLE_RECOMMENDATIONS
router=APIRouter(prefix='/recommendations',tags=['Recommendations'])
@router.get('')
def recommendations(u=Depends(current_user)):
    return {'role':u['role'],'recommendation':ROLE_RECOMMENDATIONS.get(u['role'],'Follow the applicable facility procedure.')}
