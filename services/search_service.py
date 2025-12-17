from typing import List, Dict, Any, Optional
from datetime import datetime
from database.mongodb import get_collection


class SearchService:
    """Service for searching public records"""
    
    def __init__(self):
        self.collection = get_collection("public_records")
    
    def search(self, filters: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search public records with flexible attribute matching
        
        Args:
            filters: Dictionary of search criteria (name, phone, address, institution, etc.)
            limit: Maximum number of results to return
        
        Returns:
            List of matching records
        """
        # Build MongoDB query
        query = {}
        
        # Standard field search
        for key, value in filters.items():
            if value and value.strip():
                # Use case-insensitive partial matching
                query[key] = {"$regex": value, "$options": "i"}
        
        # Also search in metadata if we have search terms
        # This allows finding academic results, grades, scores, positions, etc.
        if filters:
            metadata_conditions = []
            for key, value in filters.items():
                if value and value.strip():
                    # Search in metadata fields (for academic results, grades, etc.)
                    metadata_conditions.append({
                        f"metadata.{key}": {"$regex": value, "$options": "i"}
                    })
                    # Also search in any metadata field for the value
                    metadata_conditions.append({
                        "metadata": {"$regex": value, "$options": "i"}
                    })
            
            # If we have metadata conditions, combine with OR
            if metadata_conditions:
                if query:
                    # Combine standard fields with metadata search using $or
                    query = {
                        "$or": [
                            query,
                            {"$or": metadata_conditions}
                        ]
                    }
                else:
                    # Only metadata search
                    query = {"$or": metadata_conditions}
        
        # Special handling for queries about positions, ranks, results, grades
        # If no filters but query seems to be about academic results, search metadata broadly
        if not query and any(term in str(filters).lower() for term in ["position", "rank", "result", "grade", "score", "board", "year"]):
            query = {
                "$or": [
                    {"metadata": {"$exists": True, "$ne": {}}},
                    {"institution": {"$exists": True}}
                ]
            }
        
        # Execute search
        cursor = self.collection.find(query).limit(limit)
        results = list(cursor)
        
        # Convert ObjectId to string and format dates
        for result in results:
            result["_id"] = str(result["_id"])
            if "scraped_at" in result and isinstance(result["scraped_at"], datetime):
                result["scraped_at"] = result["scraped_at"].isoformat()
        
        return results
    
    def search_by_attributes(self, attributes: Dict[str, str], limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search using extracted attributes from AI
        
        Args:
            attributes: Dictionary with keys like 'name', 'phone', 'address', 'institution'
            limit: Maximum number of results
        
        Returns:
            List of matching records
        """
        return self.search(attributes, limit)
    
    def get_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Get a single record by ID"""
        from bson import ObjectId
        try:
            result = self.collection.find_one({"_id": ObjectId(record_id)})
            if result:
                result["_id"] = str(result["_id"])
                if "scraped_at" in result and isinstance(result["scraped_at"], datetime):
                    result["scraped_at"] = result["scraped_at"].isoformat()
            return result
        except:
            return None
    
    def count_results(self, filters: Dict[str, Any]) -> int:
        """Count matching records"""
        query = {}
        for key, value in filters.items():
            if value and value.strip():
                query[key] = {"$regex": value, "$options": "i"}
        
        return self.collection.count_documents(query)

