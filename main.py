from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

# --- Database Configuration ---
# Get database URL from environment variable. Render will provide this.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback for local development if DATABASE_URL not set in env
    # Replace with your local PostgreSQL connection string if you have one
    # For simple local testing without a local PG, you can use SQLite temporarily.
    # This will be replaced by Render's PostgreSQL for deployment.
    DATABASE_URL = "sqlite:///./test.db" # Using SQLite for local dev fallback
    print("WARNING: DATABASE_URL not found in environment. Using SQLite for local development.")


# SQLAlchemy Engine: responsible for connecting to the database
# For SQLite, connect_args are needed for multi-threading
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Base class for declarative models
Base = declarative_base()

# SessionLocal: each instance of SessionLocal will be a database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Database Model (Lead) ---
class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    job_title = Column(String)
    company = Column(String, index=True)
    inferred_email = Column(String, unique=True, index=True)
    verified_status = Column(String, default="UNVERIFIED") # e.g., VERIFIED, INVALID, UNVERIFIED
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
        db.connection() # Try to get a connection to the DB
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

# You can add more endpoints here later for scraping, verification, etc.