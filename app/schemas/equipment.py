from pydantic import BaseModel
class EquipmentCreate(BaseModel):
    equipment_id:str; facility_id:str; equipment_type:str; manufacturer:str|None=None; model:str|None=None; serial_number:str|None=None; status:str='OPERATIONAL'; installation_date:str|None=None
