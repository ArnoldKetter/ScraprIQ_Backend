from pydantic import BaseModel, Field
from typing import Optional, List

class LeadCreate(BaseModel):
    name: str
    job_title: str
    company: str
    inferred_email: str
    verified_status: str = "UNVERIFIED"
    verification_details: Optional[str] = None

class LeadResponse(LeadCreate):
    id: int

    class Config:
        from_attributes = True

# New model for batch scraping requests
class BatchScrapeRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, description="List of URLs to scrape.")