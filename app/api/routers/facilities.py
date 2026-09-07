from fastapi import APIRouter,Depends,Query,HTTPException
from pydantic import BaseModel
from datetime import datetime,timezone
from app.core.db import db
from app.core.security import current_user,require_roles
from app.core.audit import audit
from app.services.data_service import facilities,equipment,scope_filter
router=APIRouter(prefix='/facilities',tags=['Hospital Management'])
class HospitalCreate(BaseModel): facility_id:str; facility_name:str; county:str; keph_level:str|None=None; status:str='ACTIVE'
@router.get('')
def get_facilities(name:str|None=None,county:str|None=None,equipment_type:str|None=None,status:str|None=None,keph_level:str|None=None,u=Depends(current_user)):
 rows=scope_filter(facilities(),u)
 if name: rows=[r for r in rows if name.lower() in str(r.get('facility_name', r.get('facility', ''))).lower()]
 if county: rows=[r for r in rows if str(r['county']).lower()==county.lower()]
 if keph_level: rows=[r for r in rows if str(r['keph_level']).lower()==keph_level.lower()]
 if equipment_type:
  rows=[r for r in rows if equipment_type.lower() in str(r.get('equipment_types','')).lower()]
 if status:
  # Status is derived from equipment/operational records in the source data; expose filter compatibility.
  if status.upper()=='ACTIVE': rows=rows
 audit(u,'VIEW_FACILITIES','facility',details={'filters':{'name':name,'county':county,'equipment_type':equipment_type,'status':status,'keph_level':keph_level}})
 return rows
@router.post('')
def create_hospital(x:HospitalCreate,u=Depends(require_roles('system_administrator','national_administrator'))):
 if u['scope_type']!='national': raise HTTPException(403,'Only national administrators can register hospitals')
 now=datetime.now(timezone.utc).isoformat()
 with db() as c:
  try: c.execute('INSERT INTO hospitals VALUES(?,?,?,?,?,?,?)',(x.facility_id,x.facility_name,x.county,x.keph_level,x.status,now,u['id']))
  except Exception: raise HTTPException(409,'Hospital ID already registered')
 audit(u,'CREATE_HOSPITAL','facility',x.facility_id,{'name':x.facility_name,'county':x.county},None)
 return {'facility_id':x.facility_id,'message':'Hospital registered'}
