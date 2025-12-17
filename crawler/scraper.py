import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Browser, Playwright
import requests
from datetime import datetime
from database.mongodb import get_collection
import concurrent.futures
import threading


class WebScraper:
    """Scraper for extracting data from web pages"""
    
    def __init__(self, use_playwright: bool = True):
        self.use_playwright = use_playwright
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.collection = get_collection("public_records")
        self.session = requests.Session()
        # Use complete browser-like headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
        # Thread pool for running Playwright (to avoid asyncio conflicts)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
        self._playwright_lock = threading.Lock()
    
    def _init_playwright(self):
        """Initialize Playwright browser if not already done (thread-safe)"""
        with self._playwright_lock:
            if self.browser is None and self.use_playwright:
                try:
                    self.playwright = sync_playwright().start()
                    self.browser = self.playwright.chromium.launch(headless=True)
                except Exception as e:
                    print(f"Error initializing Playwright: {e}")
                    self.use_playwright = False
    
    def _close_playwright(self):
        """Close Playwright browser (thread-safe)"""
        with self._playwright_lock:
            if self.browser:
                try:
                    self.browser.close()
                    self.browser = None
                except:
                    pass
            if self.playwright:
                try:
                    self.playwright.stop()
                    self.playwright = None
                except:
                    pass
    
    def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def _fetch_with_playwright_sync(self, url: str) -> Optional[str]:
        """Synchronous Playwright fetch (runs in thread)"""
        try:
            # Initialize if needed
            if self.browser is None:
                self._init_playwright()
            
            if not self.browser:
                return None
                
            page = self.browser.new_page()
            # Set browser-like headers
            page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            # Navigate with longer timeout and wait for content
            page.goto(url, wait_until="networkidle", timeout=60000)
            # Wait a bit more for dynamic content
            page.wait_for_timeout(2000)
            content = page.content()
            page.close()
            return content
        except Exception as e:
            print(f"Error fetching with Playwright {url}: {e}")
            return None
    
    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """Fetch HTML content using Playwright for JavaScript-rendered pages (runs in thread pool)"""
        if not self.use_playwright:
            return None
        
        try:
            # Run Playwright in thread pool to avoid asyncio conflicts
            future = self.executor.submit(self._fetch_with_playwright_sync, url)
            return future.result(timeout=90)  # 90 second timeout
        except concurrent.futures.TimeoutError:
            print(f"Timeout fetching with Playwright {url}")
            return None
        except Exception as e:
            print(f"Error in Playwright thread for {url}: {e}")
            return None
    
    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """Extract clean text content from soup"""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator=" ", strip=True)
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract data from HTML tables"""
        records = []
        tables = soup.find_all("table")
        
        for table in tables:
            rows = table.find_all("tr")
            headers = []
            
            # Get headers from first row
            header_row = rows[0] if rows else None
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
            
            # Extract data rows
            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if cells:
                    record = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers) and headers[i]:
                            key = headers[i].lower().replace(" ", "_")
                            record[key] = cell
                    if record:
                        records.append(record)
        
        return records
    
    def _extract_lists(self, soup: BeautifulSoup) -> List[str]:
        """Extract data from HTML lists"""
        items = []
        for ul in soup.find_all(["ul", "ol"]):
            for li in ul.find_all("li", recursive=False):
                text = li.get_text(strip=True)
                if text:
                    items.append(text)
        return items
    
    def _extract_structured_data(self, soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
        """Extract structured data from page"""
        records = []
        
        # Extract from tables
        table_records = self._extract_tables(soup)
        for record in table_records:
            normalized = self._normalize_record(record, url)
            if normalized:
                records.append(normalized)
        
        # Extract from lists
        list_items = self._extract_lists(soup)
        for item in list_items:
            normalized = self._extract_info_from_text(item, url)
            if normalized:
                records.append(normalized)
        
        # Extract from paragraphs and divs with structured content
        content_divs = soup.find_all(["div", "article", "section"], class_=re.compile(r"(content|data|list|result)", re.I))
        for div in content_divs:
            text = div.get_text(separator=" ", strip=True)
            if text and len(text) > 20:  # Only process substantial content
                normalized = self._extract_info_from_text(text, url)
                if normalized:
                    records.append(normalized)
        
        # NEW: Extract from any div/span/p that contains phone numbers and names together
        # This catches phone numbers that might be in contact info sections
        all_elements = soup.find_all(["div", "span", "p", "td", "li"])
        for elem in all_elements:
            text = elem.get_text(separator=" ", strip=True)
            if text and len(text) < 500:  # Focus on smaller chunks
                # Check if this element contains both a name pattern and phone pattern
                phone_pattern = r'(\+?92[\s-]?[0-9]{2}[\s-]?[0-9]{7,9}|0[0-9]{2}[\s-]?[0-9]{7,9}|\+?[0-9]{10,13})'
                name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'
                
                if re.search(phone_pattern, text) and re.search(name_pattern, text):
                    normalized = self._extract_info_from_text(text, url)
                    if normalized and normalized.get("name") and normalized.get("phone"):
                        records.append(normalized)
        
        return records
    
    def _normalize_record(self, record: Dict[str, Any], source_url: str) -> Optional[Dict[str, Any]]:
        """Normalize a record to standard format"""
        normalized = {
            "source_url": source_url,
            "scraped_at": datetime.utcnow(),
            "metadata": {}
        }
        
        # Map common field names (expanded phone field mappings)
        field_mapping = {
            "name": ["name", "student_name", "person", "student", "candidate"],
            "phone": ["phone", "telephone", "contact", "phone_number", "mobile", "contact_number", "phone_no", "tel", "telephone_number", "cell", "cellphone", "number"],
            "address": ["address", "location", "area", "city"],
            "institution": ["institution", "school", "college", "university", "education"],
            "organization": ["organization", "company", "business", "org"]
        }
        
        record_lower = {k.lower(): v for k, v in record.items()}
        
        for standard_field, possible_names in field_mapping.items():
            for possible_name in possible_names:
                if possible_name in record_lower:
                    value = record_lower[possible_name]
                    if value and str(value).strip():
                        # For phone field, try to extract phone number from value if it contains other text
                        if standard_field == "phone":
                            phone_pattern = r'(\+?92[\s-]?[0-9]{2}[\s-]?[0-9]{7,9}|0[0-9]{2}[\s-]?[0-9]{7,9}|\+?[0-9]{10,13})'
                            phone_match = re.search(phone_pattern, str(value))
                            if phone_match:
                                normalized[standard_field] = phone_match.group(1).strip()
                            else:
                                normalized[standard_field] = str(value).strip()
                        else:
                            normalized[standard_field] = str(value).strip()
                        break
        
        # Also check all fields for phone numbers if not found yet
        if not normalized.get("phone"):
            phone_pattern = r'(\+?92[\s-]?[0-9]{2}[\s-]?[0-9]{7,9}|0[0-9]{2}[\s-]?[0-9]{7,9}|\+?[0-9]{10,13})'
            for key, value in record.items():
                if value:
                    phone_match = re.search(phone_pattern, str(value))
                    if phone_match:
                        normalized["phone"] = phone_match.group(1).strip()
                        break
        
        # Store any additional fields in metadata
        for key, value in record.items():
            key_lower = key.lower()
            if not any(key_lower in names for names in field_mapping.values()):
                normalized["metadata"][key] = value
        
        # Only return if at least one standard field is present
        if any(normalized.get(field) for field in ["name", "phone", "address", "institution", "organization"]):
            return normalized
        
        return None
    
    def _extract_info_from_text(self, text: str, source_url: str) -> Optional[Dict[str, Any]]:
        """Extract structured information from free text"""
        normalized = {
            "source_url": source_url,
            "scraped_at": datetime.utcnow(),
            "metadata": {}
        }
        
        # Extract phone numbers
        phone_pattern = r'(\+?92[\s-]?[0-9]{2}[\s-]?[0-9]{7,9}|0[0-9]{2}[\s-]?[0-9]{7,9})'
        phones = re.findall(phone_pattern, text)
        if phones:
            normalized["phone"] = phones[0].strip()
        
        # Extract names (capitalized words, 2-4 words)
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'
        names = re.findall(name_pattern, text)
        if names and len(names[0].split()) >= 2:
            normalized["name"] = names[0].strip()
        
        # Extract institutions (common patterns)
        institution_keywords = ["school", "college", "university", "academy", "institute"]
        for keyword in institution_keywords:
            pattern = rf'\b([A-Z][a-zA-Z\s]+{keyword}[a-zA-Z\s]*)\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                normalized["institution"] = matches[0].strip()
                break
        
        # Extract addresses (lines with common address words)
        address_pattern = r'([A-Z][a-zA-Z\s]+(?:Street|Road|Avenue|Lane|Area|Block|Sector|City)[a-zA-Z\s]*)'
        addresses = re.findall(address_pattern, text)
        if addresses:
            normalized["address"] = addresses[0].strip()
        
        # Only return if we extracted something useful
        if any(normalized.get(field) for field in ["name", "phone", "address", "institution"]):
            return normalized
        
        return None
    
    def scrape(self, url: str, use_js: bool = False) -> List[Dict[str, Any]]:
        """
        Scrape a single URL and extract structured data
        
        Args:
            url: URL to scrape
            use_js: Whether to use Playwright for JavaScript rendering
        
        Returns:
            List of extracted records
        """
        html_content = None
        
        if use_js and self.use_playwright:
            html_content = self._fetch_with_playwright(url)
        else:
            html_content = self._fetch_html(url)
        
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'lxml')
        records = self._extract_structured_data(soup, url)
        
        # Save to database
        for record in records:
            try:
                # Check for duplicates (same source_url and key fields)
                query = {"source_url": record["source_url"]}
                if record.get("name"):
                    query["name"] = record["name"]
                elif record.get("phone"):
                    query["phone"] = record["phone"]
                
                existing = self.collection.find_one(query)
                if not existing:
                    self.collection.insert_one(record)
            except Exception as e:
                print(f"Error saving record: {e}")
        
        return records
    
    def cleanup(self):
        """Cleanup resources"""
        self._close_playwright()
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
        self.session.close()

