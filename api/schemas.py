from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    query: str
    conversation_history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    """Response schema for chat endpoint"""
    response: str
    results: List[Dict[str, Any]] = []
    needs_clarification: bool = False
    needs_disambiguation: bool = False
    disambiguation_options: Optional[List[Dict[str, Any]]] = None
    action: str


class SearchRequest(BaseModel):
    """Request schema for search endpoint"""
    query: str
    limit: int = 50


class StatusResponse(BaseModel):
    """Response schema for status endpoint"""
    status: str
    total_records: int
    crawl_jobs: int
    last_crawl: Optional[str] = None

