from pydantic import BaseModel, Field
from typing import Optional

class LeadCreate(BaseModel):
    name: str
    job_title: str
    company: str
    inferred_email: str
    verified_status: str = "UNVERIFIED" # Default status
    verification_details: Optional[str] = None # Optional details

class LeadResponse(LeadCreate):
    id: int

    class Config:
        from_attributes = True # Was orm_mode = True in older Pydantic