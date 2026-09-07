from fastapi import APIRouter,Depends
from pydantic import BaseModel
from app.core.security import current_user
from app.core.audit import audit
from app.services.data_service import equipment,maintenance,failures,scope_filter
router=APIRouter(prefix='/chat',tags=['Operational Assistant'])
class Chat(BaseModel): message:str
@router.post('')
def chat(x:Chat,u=Depends(current_user)):
 msg=x.message.lower(); eq=scope_filter(equipment(),u); target=next((e for e in eq if str(e['equipment_id']).lower() in msg),None)
 if target:
  eid=str(target['equipment_id']); m=maintenance(eid,limit=1); f=failures(eid,limit=3)
  if 'last' in msg and ('maintenance' in msg or 'handled' in msg or 'service' in msg): ans=f"{eid} ({target['equipment_type']}) was last maintained on {m[0]['maintenance_date']} by {m[0]['technician']}." if m else f'No maintenance history is available for {eid}.'
  elif 'alert' in msg or 'resolve' in msg: ans=f"{eid} has {len(f)} recorded failure/alert events in the available history."; 
  else: ans=f"{eid} is a {target['equipment_type']} at {target['facility']}. I can help with maintenance history, alerts, recommendations and reports."
 else:
  ans=f"You currently have access to {len(eq)} equipment units. Try asking about a specific equipment ID, its last maintenance, alerts, or a report."
 audit(u,'CHAT_QUERY','assistant',details={'question':x.message}); return {'answer':ans,'scope':u['scope_id'] or 'national'}
