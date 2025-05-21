from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from typing import List

# Import newly created modules
from app.scrapers import scrape_company_team_page
from app.models import LeadCreate, LeadResponse # Import Pydantic models


# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback for local development if DATABASE_URL not set in env
    DATABASE_URL = "sqlite:///./test.db"
    print("WARNING: DATABASE_URL not found in environment. Using SQLite for local development.")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

Base = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Database Model (Lead - defined here for SQLAlchemy's Base) ---
class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    job_title = Column(String, nullable=False)
    company = Column(String, index=True, nullable=False)
    inferred_email = Column(String, unique=True, index=True, nullable=False) # Email should be unique
    verified_status = Column(String, default="UNVERIFIED")
    verification_details = Column(String, nullable=True)

# --- FastAPI Application Setup ---
app = FastAPI(
    title="ScraprIQ Backend API",
    description="API for lead scraping and verification for OutBound IQ.",
    version="0.1.0"
)

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def read_root():
    """
    Root endpoint to confirm API is running.
    """
    return {"message": "ScraprIQ API is running!"}

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint. Attempts to connect to DB.
    """
    try:
        db.connection()
        return {"status": "ok", "service": "ScraprIQ Backend", "db_connected": True}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Database connection failed: {e}")

@app.post("/create-tables")
async def create_db_tables():
    """
    Endpoint to create database tables.
    ONLY CALL THIS ONCE for initial setup, or after dropping tables.
    """
    try:
        Base.metadata.create_all(bind=engine)
        return {"message": "Database tables created successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create tables: {e}")

@app.post("/scrape-leads/", response_model=List[LeadResponse])
async def scrape_and_store_leads(
    target_url: str,
    db: Session = Depends(get_db)
):
    """
    Scrapes a target URL for employee leads and stores them in the database.
    """
    print(f"Attempting to scrape: {target_url}")
    scraped_data = scrape_company_team_page(target_url)

    if not scraped_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No leads found or scraping failed for the provided URL.")

    stored_leads = []
    for lead_dict in scraped_data:
        try:
            # Use LeadCreate Pydantic model for validation
            lead_in = LeadCreate(**lead_dict)

            # Check for existing lead by inferred_email to avoid duplicates
            existing_lead = db.query(Lead).filter(Lead.inferred_email == lead_in.inferred_email).first()
            if existing_lead:
                print(f"Skipping duplicate lead: {lead_in.inferred_email}")
                # Optionally update existing lead or return existing one
                stored_leads.append(existing_lead)
                continue

            # Create new Lead ORM object
            db_lead = Lead(**lead_in.model_dump()) # Use model_dump() for Pydantic v2+

            db.add(db_lead)
            db.commit()
            db.refresh(db_lead) # Refresh to get the generated ID
            stored_leads.append(db_lead)
        except Exception as e:
            db.rollback() # Rollback if any error occurs during add/commit
            print(f"Error storing lead {lead_dict.get('inferred_email', 'N/A')}: {e}")
            # Log the error but don't stop the whole process for one bad lead
            # You might want to return 200 with a list of successful/failed leads
            # For MVP, we'll just skip problematic ones and print.

    if not stored_leads:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="No leads could be stored in the database after scraping.")

    # Convert ORM objects to Pydantic response models
    return [LeadResponse.model_validate(lead) for lead in stored_leads]


# Optional: Endpoint to retrieve all leads
@app.get("/leads/", response_model=List[LeadResponse])
async def get_all_leads(db: Session = Depends(get_db)):
    """
    Retrieves all leads from the database.
    """
    leads = db.query(Lead).all()
    return [LeadResponse.model_validate(lead) for lead in leads]