from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from typing import List
from fastapi.middleware.cors import CORSMiddleware  # Import CORS middleware

# Import newly created modules
from app.scrapers import scrape_company_team_page
from app.models import LeadCreate, LeadResponse, BatchScrapeRequest # Import Pydantic models



# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./test.db"
    print("WARNING: DATABASE_URL not found in environment. Using SQLite for local development.")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

Base = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Database Model (Lead) ---
class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    job_title = Column(String, nullable=False)
    company = Column(String, index=True, nullable=False)
    inferred_email = Column(String, unique=True, index=True, nullable=False)
    verified_status = Column(String, default="UNVERIFIED")
    verification_details = Column(String, nullable=True)


# --- FastAPI Application Setup ---

app = FastAPI(
    title="ScraprIQ Backend API",
    description="API for lead scraping and verification for OutBound IQ.",
    version="0.1.0" # testing git
)

# Configure CORS middleware
origins = [
    "http://localhost:3000",  # For local Next.js development
    "https://scrapr-iq-frontend.vercel.app",  # Production Vercel frontend domain (no trailing slash)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
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


# Original single URL scrape endpoint
@app.post("/scrape-leads/", response_model=List[LeadResponse])
async def scrape_and_store_leads(
    target_url: str,
    db: Session = Depends(get_db)
):
    """
    Scrapes a single target URL for employee leads and stores them in the database.
    """
    print(f"Attempting to scrape: {target_url}")
    scraped_data = scrape_company_team_page(target_url)

    if not scraped_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No leads found or scraping failed for the provided URL.")

    stored_leads = []
    for lead_dict in scraped_data:
        try:
            lead_in = LeadCreate(**lead_dict)
            existing_lead = db.query(Lead).filter(Lead.inferred_email == lead_in.inferred_email).first()
            if existing_lead:
                print(f"Skipping duplicate lead: {lead_in.inferred_email}")
                stored_leads.append(existing_lead)
                continue

            db_lead = Lead(**lead_in.model_dump())
            db.add(db_lead)
            db.commit()
            db.refresh(db_lead)
            stored_leads.append(db_lead)
        except Exception as e:
            db.rollback()
            print(f"Error storing lead {lead_dict.get('inferred_email', 'N/A')}: {e}")

    if not stored_leads:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="No leads could be stored in the database after scraping.")

    return [LeadResponse.model_validate(lead) for lead in stored_leads]

# NEW BATCH SCRAPE ENDPOINT
@app.post("/batch-scrape-leads/", response_model=List[LeadResponse])
async def batch_scrape_and_store_leads(
    request: BatchScrapeRequest, # Accepts a Pydantic model with a list of URLs
    db: Session = Depends(get_db)
):
    """
    Scrapes multiple target URLs for employee leads and stores them in the database.
    """
    all_stored_leads = []

    for url in request.urls:
        print(f"Attempting to batch scrape: {url}")
        try:
            scraped_data = scrape_company_team_page(url)
            if not scraped_data:
                print(f"No leads found or scraping failed for {url}.")
                continue # Continue to next URL if no leads found

            for lead_dict in scraped_data:
                try:
                    lead_in = LeadCreate(**lead_dict)
                    existing_lead = db.query(Lead).filter(Lead.inferred_email == lead_in.inferred_email).first()
                    if existing_lead:
                        print(f"Skipping duplicate lead: {lead_in.inferred_email}")
                        all_stored_leads.append(existing_lead)
                        continue

                    db_lead = Lead(**lead_in.model_dump())
                    db.add(db_lead)
                    db.commit()
                    db.refresh(db_lead)
                    all_stored_leads.append(db_lead)
                except Exception as e:
                    db.rollback()
                    print(f"Error storing lead from {url} ({lead_dict.get('inferred_email', 'N/A')}): {e}")
        except Exception as e:
            print(f"An error occurred while processing URL {url}: {e}")
            # Log the error but continue with other URLs in the batch

    if not all_stored_leads and request.urls: # If no leads stored but URLs were provided
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT, # No Content
                            detail="Processed all URLs but no leads were stored or found.")
    elif not all_stored_leads: # No URLs provided or genuinely no leads
         return [] # Return empty list if no leads found at all


    return [LeadResponse.model_validate(lead) for lead in all_stored_leads]

# Main ScraprIQ Endpoint
@app.post("/scrapr-iq/", response_model=List[LeadResponse], status_code=status.HTTP_200_OK)
async def scrapr_iq_scrape_company(
    target_url: str,
    db: Session = Depends(get_db)
):
    """
    ScraprIQ: Takes a company's 'About Us' or 'Team' page URL,
    scrapes for employee names and job titles, infers email addresses,
    verifies them using Hunter.io, and stores the leads.
    Returns a list of structured leads.
    """
    if not target_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A target_url must be provided for scraping."
        )

    print(f"ScraprIQ initiated for: {target_url}")
    scraped_data = scrape_company_team_page(target_url)

    if not scraped_data:
        # Return 200 OK with empty list if no leads found (as per typical API design for "no results")
        # Or raise 404 if "no leads found" is considered an error state for this specific endpoint
        # For MVP, returning an empty list for no leads is often better than a 404, but the choice depends on consumer expectations.
        # Let's stick with returning an empty list and 200 OK for now, to differentiate from scraping errors.
        print(f"No leads found or scraping failed for {target_url}. Returning empty list.")
        return [] # Return empty list if no leads found

    stored_leads = []
    for lead_dict in scraped_data:
        try:
            lead_in = LeadCreate(**lead_dict)
            existing_lead = db.query(Lead).filter(Lead.inferred_email == lead_in.inferred_email).first()
            if existing_lead:
                # Update existing lead if verification details have changed? Or just skip?
                # For now, just skip to avoid duplicates, but consider update logic later if needed.
                print(f"Skipping duplicate lead: {lead_in.inferred_email}")
                stored_leads.append(existing_lead)
                continue

            db_lead = Lead(**lead_in.model_dump())
            db.add(db_lead)
            db.commit()
            db.refresh(db_lead)
            stored_leads.append(db_lead)
        except Exception as e:
            db.rollback()
            print(f"Error storing lead from {target_url} ({lead_dict.get('inferred_email', 'N/A')}): {e}")

    if not stored_leads and scraped_data:
        # This indicates leads were scraped but none could be stored (e.g., all were duplicates)
        # This might be an acceptable outcome, so still return 200 OK with the leads that were identified.
        # If all were duplicates and no new ones were added, all_stored_leads will contain the existing ones.
        # Adjusting to return `all_stored_leads` which will contain both new and existing leads.
        # This logic should be robust.
        return [LeadResponse.model_validate(lead) for lead in stored_leads]
    elif not stored_leads:
        # If no leads were scraped AND none were stored (e.g., input was bad, or site returned no data)
        return [] # Return empty list as per the `if not scraped_data` block

    return [LeadResponse.model_validate(lead) for lead in stored_leads]

# Endpoint to retrieve all leads
@app.get("/leads/", response_model=List[LeadResponse])
async def get_all_leads(db: Session = Depends(get_db)):
    """
    Retrieves all leads from the database.
    """
    leads = db.query(Lead).all()
    return [LeadResponse.model_validate(lead) for lead in leads]