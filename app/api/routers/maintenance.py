from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.db import db
from app.core.security import current_user, require_roles
from app.core.audit import audit
from app.services.data_service import maintenance, equipment, scope_filter

router=APIRouter(prefix='/maintenance',tags=['Maintenance'])
class WorkOrderCreate(BaseModel):
    equipment_id:str; priority:str='MEDIUM'; title:str; description:str|None=None; assigned_to:str|None=None; scheduled_at:str|None=None
class WorkOrderUpdate(BaseModel):
    status:str|None=None; assigned_to:str|None=None; priority:str|None=None; resolution:str|None=None; completed_at:str|None=None

@router.get('')
def list_work_orders(u=Depends(current_user)):
    with db() as c: rows=[dict(r) for r in c.execute('SELECT * FROM maintenance_work_orders ORDER BY created_at DESC').fetchall()]
    return rows if str(u['scope_type'])=='national' else [r for r in rows if str(r.get('facility_id'))==str(u['scope_id'])]

@router.get('/history/{equipment_id}')
def history(equipment_id:str,u=Depends(current_user)):
    eq=[x for x in scope_filter(equipment(),u) if str(x.get('equipment_id'))==str(equipment_id)]
    if not eq: raise HTTPException(404,'Equipment not found or outside your access scope')
    rows=maintenance(equipment_id,facility_id=eq[0].get('facility_id')); audit(u,'VIEW_MAINTENANCE_HISTORY','equipment',equipment_id); return rows

@router.post('/work-orders',status_code=201)
def create_work_order(x:WorkOrderCreate,u=Depends(require_roles('system_administrator','national_administrator','facility_manager','biomedical_engineer','maintenance_technician'))):
    eq=[e for e in scope_filter(equipment(),u) if str(e.get('equipment_id'))==str(x.equipment_id)]
    if not eq: raise HTTPException(404,'Equipment not found or outside your access scope')
    now=datetime.now(timezone.utc).isoformat(); wid='WO-'+uuid4().hex[:8].upper(); fid=str(eq[0].get('facility_id'))
    with db() as c:
        c.execute('''INSERT INTO maintenance_work_orders (id,equipment_id,facility_id,assigned_to,priority,status,title,description,scheduled_at,completed_at,resolution,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(wid,x.equipment_id,fid,x.assigned_to,x.priority,'OPEN',x.title,x.description,x.scheduled_at,None,None,u['id'],now,now))
        row=dict(c.execute('SELECT * FROM maintenance_work_orders WHERE id=?',(wid,)).fetchone())
    audit(u,'CREATE_WORK_ORDER','maintenance',wid,{'equipment_id':x.equipment_id},fid); return row

@router.patch('/work-orders/{work_order_id}')
def update_work_order(work_order_id:str,x:WorkOrderUpdate,u=Depends(require_roles('system_administrator','national_administrator','facility_manager','biomedical_engineer','maintenance_technician'))):
    data=x.model_dump(exclude_none=True)
    if not data: raise HTTPException(400,'No changes supplied')
    data['updated_at']=datetime.now(timezone.utc).isoformat()
    with db() as c:
        row=c.execute('SELECT * FROM maintenance_work_orders WHERE id=?',(work_order_id,)).fetchone()
        if not row: raise HTTPException(404,'Work order not found')
        if str(u['scope_type'])!='national' and str(row['facility_id'])!=str(u['scope_id']): raise HTTPException(403,'Work order is outside your access scope')
        sets=', '.join(f'{k}=?' for k in data); c.execute(f'UPDATE maintenance_work_orders SET {sets} WHERE id=?',[*data.values(),work_order_id]); updated=dict(c.execute('SELECT * FROM maintenance_work_orders WHERE id=?',(work_order_id,)).fetchone())
    audit(u,'UPDATE_WORK_ORDER','maintenance',work_order_id,data,str(updated['facility_id'])); return updated
