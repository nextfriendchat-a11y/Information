from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class PublicRecord(BaseModel):
    """Model for public information records"""
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    institution: Optional[str] = None
    organization: Optional[str] = None
    source_url: str
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CrawlJob(BaseModel):
    """Model for tracking crawl jobs"""
    url: str
    status: str = "pending"  # pending, running, completed, failed
    last_crawled: Optional[datetime] = None
    next_crawl: Optional[datetime] = None
    pages_crawled: int = 0
    error_message: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AICacheEntry(BaseModel):
    """Model for AI response caching"""
    query_hash: str
    response: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

