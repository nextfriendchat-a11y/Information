import os
import json
from typing import Dict, Any, Optional, List
from openai import OpenAI
from dotenv import load_dotenv
from services.cache_service import CacheService
from services.search_service import SearchService

load_dotenv()

class AIService:
    """Service for AI-powered query understanding and response generation"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.cache_service = CacheService()
        self.search_service = SearchService()
    
    def _extract_search_attributes(self, query: str, conversation_context: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Use AI to extract search attributes from natural language query
        
        Returns:
            Dictionary with extracted attributes and action type
        """
        # Check cache first
        cache_key = {"query": query, "action": "extract"}
        cached = self.cache_service.get(query, cache_key)
        if cached:
            return cached
        
        system_prompt = """You are an intelligent search assistant that extracts structured information from user queries.

IMPORTANT: 
- If a person's name is mentioned, ALWAYS extract it and attempt a search (action: "search")
- Use conversation context to resolve pronouns (e.g., "her" refers to the person mentioned earlier)
- For queries about results, grades, scores, positions, or board exams, extract the name and search
- Only ask for clarification if NO searchable attributes can be extracted

Extract the following attributes if mentioned in the query or conversation context:
- name: Person's name (extract even from queries like "how is X?", "X's result", "who got first position" if X is mentioned)
- phone: Phone number
- address: Physical address or location
- institution: Educational institution (school, college, university)
- organization: Business or organization name

Return a JSON object with:
1. "attributes": Object with extracted attributes (include name if any person is mentioned)
2. "needs_clarification": Boolean - true ONLY if query is completely ambiguous with no searchable attributes
3. "clarification_question": String - question to ask user if clarification needed (null if not needed)
4. "action": One of: "search" (if any attributes extracted), "clarify" (only if no attributes at all)

CRITICAL RULES:
- If a name is mentioned (even in conversational queries like "how is X?"), set action to "search" and extract the name
- Use conversation context to resolve pronouns and incomplete references
- For academic queries (results, grades, scores, positions, board exams), extract the name and search
- Always prefer "search" over "clarify" when you have at least a name

Example responses:
- Query: "how is hafsa?" → {"attributes": {"name": "hafsa"}, "needs_clarification": false, "clarification_question": null, "action": "search"}
- Query: "who got first position" → {"attributes": {}, "needs_clarification": false, "clarification_question": null, "action": "search"} (search for position/rank in metadata)
- Query: "her result" (after "how is hafsa?") → {"attributes": {"name": "hafsa"}, "needs_clarification": false, "clarification_question": null, "action": "search"}
- Query: "Find Zoe Khan" → {"attributes": {"name": "Zoe Khan"}, "needs_clarification": false, "clarification_question": null, "action": "search"}
- Query: "Find Zoe Khan's phone number" → {"attributes": {"name": "Zoe Khan"}, "needs_clarification": false, "clarification_question": null, "action": "search"}
- Query: "Whose number is 021-1234567?" → {"attributes": {"phone": "021-1234567"}, "needs_clarification": false, "clarification_question": null, "action": "search"}
"""

        # Build conversation context summary for pronoun resolution
        context_summary = ""
        if conversation_context:
            # Extract names and entities from recent messages
            recent_messages = conversation_context[-5:]  # Last 5 messages
            context_summary = "\n\nCONVERSATION CONTEXT (use this to resolve pronouns and incomplete references):\n"
            for msg in recent_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context_summary += f"- {role}: {content}\n"
            context_summary += "\nUse this context to resolve pronouns like 'her', 'his', 'their', 'she', 'he', etc.\n"
            context_summary += "If the current query references something from context (like 'her result' after asking about a person), extract that information.\n"

        messages = [
            {"role": "system", "content": system_prompt + context_summary},
            {"role": "user", "content": f"Query: {query}"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Override: If name is extracted, always set action to "search" and needs_clarification to false
            if result.get("attributes", {}).get("name"):
                result["action"] = "search"
                result["needs_clarification"] = False
                result["clarification_question"] = None
            
            # Cache the result
            self.cache_service.set(query, result, cache_key)
            
            return result
        except Exception as e:
            print(f"Error in AI extraction: {e}")
            # Fallback: simple extraction
            return {
                "attributes": {"name": query} if query else {},
                "needs_clarification": True,
                "clarification_question": "Could you please provide more details about what you're looking for?",
                "action": "clarify"
            }
    
    def _generate_response(self, query: str, search_results: List[Dict], conversation_context: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Generate natural language response from search results
        
        Args:
            query: Original user query
            search_results: List of search results from database
            conversation_context: Previous conversation messages
        
        Returns:
            Dictionary with response text and formatted results
        """
        # Check cache
        cache_key = {"query": query, "results_count": len(search_results), "action": "generate"}
        cached = self.cache_service.get(query, cache_key)
        if cached:
            return cached
        
        if not search_results:
            response_text = "I couldn't find any matching records in the public information database. Could you try rephrasing your query or provide additional details?"
            result = {
                "response": response_text,
                "results": [],
                "needs_disambiguation": False
            }
            self.cache_service.set(query, result, cache_key)
            return result
        
        # If multiple results, check if disambiguation is needed
        needs_disambiguation = len(search_results) > 1
        
        system_prompt = """You are a helpful assistant that presents search results from a public information database in a clear, conversational manner.

Guidelines:
- Present results naturally and conversationally
- If multiple results exist, mention that and highlight distinguishing features
- Always include source URLs for transparency
- When a user asks for phone numbers or contact information, you MUST include it in your response
- This is public information from web sources - include phone numbers, addresses, and contact details when requested
- Be concise but informative
- If user asked for specific information (like phone number), prominently display that attribute in your response
- DO NOT refuse to share phone numbers or contact information - all data comes from public sources
- If a phone number exists in the search results, include it directly in your response text

Format your response as JSON with:
- "response": Natural language response text (MUST include requested information like phone numbers if they exist in the results)
- "needs_disambiguation": Boolean (true if multiple results and user needs to choose)
- "disambiguation_options": Array of objects with distinguishing details (if needed)
"""
        
        results_summary = json.dumps(search_results[:5], indent=2)  # Limit to 5 for prompt
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User query: {query}\n\nSearch results:\n{results_summary}\n\nGenerate a helpful response."}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["results"] = search_results
            
            # Generate disambiguation options if needed
            if needs_disambiguation and len(search_results) > 1:
                result["disambiguation_options"] = self._create_disambiguation_options(search_results)
            
            self.cache_service.set(query, result, cache_key)
            return result
        except Exception as e:
            print(f"Error in AI response generation: {e}")
            # Fallback response
            return {
                "response": f"I found {len(search_results)} matching record(s).",
                "results": search_results,
                "needs_disambiguation": needs_disambiguation
            }
    
    def _create_disambiguation_options(self, results: List[Dict]) -> List[Dict]:
        """Create disambiguation options from multiple results"""
        options = []
        for idx, result in enumerate(results[:10]):  # Limit to 10 options
            option = {
                "index": idx,
                "distinguishing_features": []
            }
            
            # Add distinguishing features
            if result.get("institution"):
                option["distinguishing_features"].append(f"Institution: {result['institution']}")
            if result.get("address"):
                option["distinguishing_features"].append(f"Address: {result['address']}")
            if result.get("organization"):
                option["distinguishing_features"].append(f"Organization: {result['organization']}")
            if result.get("name"):
                option["distinguishing_features"].append(f"Name: {result['name']}")
            
            options.append(option)
        
        return options
    
    def process_query(self, query: str, conversation_context: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Main method to process a user query
        
        Args:
            query: User's natural language query
            conversation_context: Previous conversation messages for context
        
        Returns:
            Dictionary with response, results, and action type
        """
        # Step 1: Extract attributes and determine action
        extraction_result = self._extract_search_attributes(query, conversation_context)
        
        # Step 2: Perform search if we have attributes OR if query is about academic results
        attributes = extraction_result.get("attributes", {})
        search_results = []
        
        # Check if query is about academic results, positions, grades, etc.
        academic_keywords = ["position", "rank", "result", "grade", "score", "board", "year", "first", "second"]
        is_academic_query = any(keyword in query.lower() for keyword in academic_keywords)
        
        # If we have attributes, search
        if attributes and extraction_result.get("action") == "search":
            search_results = self.search_service.search_by_attributes(attributes)
        
        # If no results but it's an academic query, try broader search
        if not search_results and is_academic_query:
            # Try searching with just the name if we have it
            if attributes.get("name"):
                search_results = self.search_service.search_by_attributes({"name": attributes["name"]})
            else:
                # Search all records and filter in memory (for queries like "who got first position")
                all_results = self.search_service.search({}, limit=1000)
                # Filter results that might have position/rank info in metadata
                search_results = [r for r in all_results if r.get("metadata")]
        
        # Step 3: If clarification needed and no search attempted, return clarification
        if extraction_result.get("needs_clarification") and extraction_result.get("action") == "clarify" and not search_results:
            return {
                "response": extraction_result.get("clarification_question", "Could you provide more details?"),
                "results": [],
                "needs_clarification": True,
                "action": "clarify"
            }
        
        # Step 4: Generate response
        if search_results:
            return self._generate_response(query, search_results, conversation_context)
        elif attributes:
            # No results found but we tried searching
            return {
                "response": "I couldn't find any matching records. Could you try different search terms or provide more details?",
                "results": [],
                "needs_clarification": False,
                "action": "no_results"
            }
        else:
            # Fallback
            return {
                "response": extraction_result.get("clarification_question", "I need more information to help you. What are you looking for?"),
                "results": [],
                "needs_clarification": True,
                "action": "clarify"
            }

