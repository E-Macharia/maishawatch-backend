from pydantic import BaseModel, Field

class EquipmentFeatures(BaseModel):
    equipment_id: str = Field(min_length=1)

class RULRequest(BaseModel):
    equipment_id: str = Field(min_length=1)
