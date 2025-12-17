from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from api.schemas import ChatRequest, ChatResponse, SearchRequest, StatusResponse
from services.ai_service import AIService
from services.search_service import SearchService
from database.mongodb import get_collection
from crawler.scheduler import CrawlScheduler
from datetime import datetime

router = APIRouter()

# Lazy-loaded services
_ai_service = None
_search_service = None

def get_ai_service():
    """Get or create AI service instance"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service

def get_search_service():
    """Get or create search service instance"""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversational endpoint for AI-powered search
    
    Handles natural language queries, intent detection, and result formatting
    """
    try:
        ai_service = get_ai_service()
        # Process query with AI
        result = ai_service.process_query(
            request.query,
            conversation_context=request.conversation_history
        )
        
        return ChatResponse(
            response=result.get("response", "I'm sorry, I couldn't process that query."),
            results=result.get("results", []),
            needs_clarification=result.get("needs_clarification", False),
            needs_disambiguation=result.get("needs_disambiguation", False),
            disambiguation_options=result.get("disambiguation_options"),
            action=result.get("action", "search")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@router.post("/api/search")
async def search(request: SearchRequest):
    """
    Direct search endpoint (bypasses AI for programmatic access)
    """
    try:
        ai_service = get_ai_service()
        search_service = get_search_service()
        
        # Extract attributes using AI
        extraction = ai_service._extract_search_attributes(request.query)
        attributes = extraction.get("attributes", {})
        
        if not attributes:
            return JSONResponse({
                "error": "Could not extract search attributes from query",
                "results": []
            })
        
        # Perform search
        results = search_service.search_by_attributes(attributes, limit=request.limit)
        
        return JSONResponse({
            "query": request.query,
            "attributes": attributes,
            "results": results,
            "count": len(results)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing search: {str(e)}")


@router.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get system status and statistics"""
    try:
        public_records = get_collection("public_records")
        crawl_jobs = get_collection("crawl_jobs")
        
        total_records = public_records.count_documents({})
        total_jobs = crawl_jobs.count_documents({})
        
        # Get most recent crawl
        last_job = crawl_jobs.find_one(
            {"status": "completed"},
            sort=[("last_crawled", -1)]
        )
        
        last_crawl = None
        if last_job and last_job.get("last_crawled"):
            last_crawl_time = last_job["last_crawled"]
            if isinstance(last_crawl_time, datetime):
                last_crawl = last_crawl_time.isoformat()
            else:
                last_crawl = str(last_crawl_time)
        
        return StatusResponse(
            status="running",
            total_records=total_records,
            crawl_jobs=total_jobs,
            last_crawl=last_crawl
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@router.post("/api/crawl/trigger")
async def trigger_crawl(request: Request, urls: List[str] = None):
    """Manually trigger a crawl"""
    try:
        # Try to use scheduler from app state, otherwise create a temporary one
        scheduler = getattr(request.app.state, 'scheduler', None)
        if scheduler:
            scheduler.trigger_manual_crawl(urls)
        else:
            # Create temporary scheduler for manual trigger
            temp_scheduler = CrawlScheduler()
            temp_scheduler.trigger_manual_crawl(urls)
        
        return JSONResponse({
            "message": "Crawl triggered successfully",
            "urls": urls or "all seed URLs"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering crawl: {str(e)}")

