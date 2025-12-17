import time
from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
from database.mongodb import get_collection
from crawler.scraper import WebScraper
from crawler.robots_checker import RobotsChecker
import os
from dotenv import load_dotenv

load_dotenv()


class WebCrawler:
    """Main web crawler that orchestrates crawling and scraping"""
    
    def __init__(self):
        self.scraper = WebScraper()
        self.robots_checker = RobotsChecker()
        self.visited_urls: Set[str] = set()
        self.crawl_jobs_collection = get_collection("crawl_jobs")
        self.crawl_delay = float(os.getenv("CRAWL_DELAY_SECONDS", "2"))
        # Use a complete browser-like user agent
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def _is_valid_url(self, url: str, base_domain: str) -> bool:
        """Check if URL is valid and within allowed domain"""
        try:
            parsed = urlparse(url)
            base_parsed = urlparse(base_domain)
            
            # Must be http or https
            if parsed.scheme not in ["http", "https"]:
                return False
            
            # Must be same domain
            if parsed.netloc != base_parsed.netloc:
                return False
            
            # Avoid common non-content URLs
            excluded_patterns = [
                "/login", "/signin", "/register", "/signup",
                "/logout", "/admin", "/api/", ".pdf", ".doc", ".zip",
                "mailto:", "tel:", "javascript:"
            ]
            
            for pattern in excluded_patterns:
                if pattern in url.lower():
                    return False
            
            return True
        except:
            return False
    
    def _extract_links(self, html_content: str, base_url: str) -> List[str]:
        """Extract all links from HTML content"""
        from bs4 import BeautifulSoup
        
        links = []
        soup = BeautifulSoup(html_content, 'lxml')
        base_domain = urlparse(base_url).netloc
        
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            absolute_url = urljoin(base_url, href)
            
            # Remove fragments
            absolute_url = absolute_url.split("#")[0]
            
            if self._is_valid_url(absolute_url, f"https://{base_domain}"):
                links.append(absolute_url)
        
        return links
    
    def _update_crawl_job(self, url: str, status: str, pages_crawled: int = 0, error: Optional[str] = None):
        """Update crawl job status in database"""
        self.crawl_jobs_collection.update_one(
            {"url": url},
            {
                "$set": {
                    "url": url,
                    "status": status,
                    "last_crawled": datetime.utcnow(),
                    "pages_crawled": pages_crawled,
                    "error_message": error
                }
            },
            upsert=True
        )
    
    def crawl_url(self, url: str, max_depth: int = 3, current_depth: int = 0) -> int:
        """
        Crawl a URL and its linked pages
        
        Args:
            url: Starting URL
            max_depth: Maximum depth to crawl
            current_depth: Current depth level
        
        Returns:
            Number of pages crawled
        """
        if current_depth > max_depth:
            return 0
        
        if url in self.visited_urls:
            return 0
        
        # Check robots.txt
        if not self.robots_checker.can_fetch(url, self.user_agent):
            print(f"Robots.txt disallows: {url}")
            return 0
        
        # Get crawl delay
        delay = self.robots_checker.get_crawl_delay(url, self.user_agent)
        time.sleep(max(delay, self.crawl_delay))
        
        self.visited_urls.add(url)
        pages_crawled = 0
        
        try:
            print(f"Crawling: {url} (depth: {current_depth})")
            self._update_crawl_job(url, "running", pages_crawled)
            
            # Try to scrape with JS first (for dynamic content), fallback to regular fetch
            use_js = current_depth <= 1  # Use JS for seed pages and first level
            
            # Scrape the page
            records = self.scraper.scrape(url, use_js=use_js)
            pages_crawled = 1
            
            print(f"  Extracted {len(records)} records from {url}")
            
            # Get HTML to extract links (only if not at max depth)
            if current_depth < max_depth:
                # Try Playwright first, fallback to regular fetch if it fails
                html_content = None
                if use_js:
                    html_content = self.scraper._fetch_with_playwright(url)
                
                # Fallback to regular fetch if Playwright failed or wasn't used
                if not html_content:
                    html_content = self.scraper._fetch_html(url)
                
                if html_content:
                    links = self._extract_links(html_content, url)
                    print(f"  Found {len(links)} links on {url}")
                    
                    # Crawl linked pages (increase limit for deeper crawling)
                    link_limit = 100 if current_depth == 0 else 50
                    for link in links[:link_limit]:
                        if link not in self.visited_urls:
                            pages_crawled += self.crawl_url(link, max_depth, current_depth + 1)
                else:
                    print(f"  Warning: Could not fetch HTML content from {url} for link extraction")
            
            self._update_crawl_job(url, "completed", pages_crawled)
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error crawling {url}: {error_msg}")
            self._update_crawl_job(url, "failed", pages_crawled, error_msg)
        
        return pages_crawled
    
    def crawl_seed_urls(self, seed_urls: List[str], max_depth: int = 3):  # Increased default depth
        """
        Crawl multiple seed URLs
        
        Args:
            seed_urls: List of starting URLs
            max_depth: Maximum crawl depth per seed (default: 3)
        """
        total_pages = 0
        for seed_url in seed_urls:
            print(f"\nStarting crawl for: {seed_url}")
            pages = self.crawl_url(seed_url, max_depth=max_depth)
            total_pages += pages
            print(f"Completed: {seed_url} - {pages} pages crawled")
        
        print(f"\nTotal pages crawled: {total_pages}")
        return total_pages
    
    def cleanup(self):
        """Cleanup resources"""
        self.scraper.cleanup()

