import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from api.routes import router
from database.mongodb import get_database
from crawler.scheduler import CrawlScheduler
import atexit
import asyncio

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="AI Public Information Search System",
    description="AI-powered public information search with web crawling",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(router)

# Initialize database connection
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("Initializing database connection...")
    db = get_database()
    print(f"Connected to database: {db.name}")
    
    # Initialize and start crawler scheduler
    # Note: Initial crawl is disabled - data is already in DB, cron job will handle crawling
    print("Starting crawler scheduler...")
    scheduler = CrawlScheduler()
    
    # Start scheduler without initial crawl (data already in DB)
    scheduler.start(run_initial_crawl=False)
    
    # Store scheduler in app state for cleanup
    app.state.scheduler = scheduler
    print("Application started successfully!")
    print("Scheduler is ready for cron jobs. Use /api/crawl/trigger to manually trigger crawls.")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if hasattr(app.state, 'scheduler'):
        print("Stopping crawler scheduler...")
        app.state.scheduler.stop()
    print("Application shutdown complete.")

# Root route - serve frontend
@app.get("/")
async def read_root():
    """Serve the main frontend page"""
    return FileResponse("static/index.html")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

