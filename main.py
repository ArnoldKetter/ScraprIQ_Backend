from fastapi import FastAPI

# Initialize the FastAPI application
app = FastAPI(
    title="ScraprIQ Backend API",
    description="API for lead scraping and verification for OutBound IQ.",
    version="0.1.0"
)

@app.get("/")
async def read_root():
    """
    Root endpoint to confirm API is running.
    """
    return {"message": "ScraprIQ API is running!"}

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok", "service": "ScraprIQ Backend"}

# You can add more endpoints here later for scraping, verification, etc.