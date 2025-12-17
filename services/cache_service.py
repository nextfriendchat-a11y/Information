import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from database.mongodb import get_collection


class CacheService:
    """Service for caching AI responses"""
    
    def __init__(self, ttl_hours: int = 24):
        self._collection = None
        self.ttl_hours = ttl_hours
    
    @property
    def collection(self):
        """Lazy-load collection on first access"""
        if self._collection is None:
            self._collection = get_collection("ai_cache")
        return self._collection
    
    def _hash_query(self, query: str, context: Optional[Dict] = None) -> str:
        """Generate hash for query and context"""
        cache_key = {
            "query": query.lower().strip(),
            "context": context or {}
        }
        cache_str = json.dumps(cache_key, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()
    
    def get(self, query: str, context: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired"""
        query_hash = self._hash_query(query, context)
        cache_entry = self.collection.find_one({"query_hash": query_hash})
        
        if cache_entry:
            expires_at = cache_entry.get("expires_at")
            if expires_at and datetime.utcnow() < expires_at:
                return cache_entry.get("response")
            else:
                # Remove expired entry
                self.collection.delete_one({"query_hash": query_hash})
        
        return None
    
    def set(self, query: str, response: Dict[str, Any], context: Optional[Dict] = None):
        """Cache a response"""
        query_hash = self._hash_query(query, context)
        expires_at = datetime.utcnow() + timedelta(hours=self.ttl_hours)
        
        self.collection.update_one(
            {"query_hash": query_hash},
            {
                "$set": {
                    "query_hash": query_hash,
                    "response": response,
                    "created_at": datetime.utcnow(),
                    "expires_at": expires_at
                }
            },
            upsert=True
        )

