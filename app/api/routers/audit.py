from fastapi import APIRouter,Depends
from app.core.db import db
from app.core.security import require_roles
router=APIRouter(prefix='/audit',tags=['Audit Trail'])
@router.get('')
def logs(u=Depends(require_roles('system_administrator','national_administrator','national_executive','facility_manager'))):
 with db() as c: rows=[dict(x) for x in c.execute('SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 1000')]
 if u['scope_type']!='national': rows=[x for x in rows if str(x.get('scope_id'))==str(u['scope_id'])]
 if u['role']=='facility_manager': rows=[x for x in rows if x.get('actor_role') not in ('system_administrator','national_administrator','national_executive')]
 return rows
