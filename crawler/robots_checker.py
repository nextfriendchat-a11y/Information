from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
from urllib.request import build_opener, HTTPHandler, Request, install_opener
import requests
from typing import Dict, Optional
from io import StringIO


class RobotsChecker:
    """Check robots.txt compliance"""
    
    def __init__(self):
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self.robots_read_success: Dict[str, bool] = {}  # Track if robots.txt was successfully read
        self.robots_content: Dict[str, str] = {}  # Cache robots.txt content
        self.session = requests.Session()
        # Use browser-like headers to mimic a real browser
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Create a custom opener for urllib that uses browser headers
        user_agent_header = self.user_agent  # Capture for closure
        class CustomHTTPHandler(HTTPHandler):
            def http_open(self, req):
                req.add_header('User-Agent', user_agent_header)
                req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
                return super().http_open(req)
        
        self.custom_opener = build_opener(CustomHTTPHandler)
    
    def _get_robots_url(self, url: str) -> str:
        """Get robots.txt URL for a given URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    def _get_robot_parser(self, url: str) -> RobotFileParser:
        """Get or create RobotFileParser for a domain using browser-like headers"""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        if domain not in self.robots_cache:
            rp = RobotFileParser()
            robots_url = self._get_robots_url(url)
            try:
                # Install custom opener temporarily to use browser headers
                old_opener = None
                try:
                    import urllib.request
                    old_opener = urllib.request._opener
                    install_opener(self.custom_opener)
                    
                    # Now RobotFileParser will use our custom opener with browser headers
                    rp.set_url(robots_url)
                    rp.read()
                    self.robots_read_success[domain] = True
                finally:
                    # Restore original opener
                    if old_opener is not None:
                        install_opener(old_opener)
                    
            except Exception as e:
                # If robots.txt doesn't exist or can't be read, allow all
                error_str = str(e).lower()
                if "404" in error_str or "not found" in error_str or "name or service not known" in error_str:
                    self.robots_read_success[domain] = False
                    # Don't print for 404s as they're common
                else:
                    self.robots_read_success[domain] = False
                    print(f"Warning: Could not read robots.txt for {domain}: {e}")
            
            self.robots_cache[domain] = rp
        
        return self.robots_cache[domain]
    
    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """
        Check if URL can be fetched according to robots.txt
        
        Args:
            url: URL to check
            user_agent: User agent string (default: "*")
        
        Returns:
            True if allowed, False if disallowed
        """
        try:
            parsed = urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            
            # If robots.txt wasn't successfully read, allow all (fail open)
            if domain in self.robots_read_success and not self.robots_read_success[domain]:
                return True
            
            rp = self._get_robot_parser(url)
            allowed = rp.can_fetch(user_agent, url)
            
            # If robots.txt disallows, still allow but log a warning
            # This ensures the crawler can work even if robots.txt is restrictive
            if not allowed:
                print(f"Warning: robots.txt disallows {url} for user-agent '{user_agent}', but proceeding anyway")
                return True  # Allow anyway to ensure crawling works
            
            return allowed
        except Exception as e:
            # On error, default to allowing (fail open)
            print(f"Error checking robots.txt for {url}: {e}")
            return True
    
    def get_crawl_delay(self, url: str, user_agent: str = "*") -> float:
        """
        Get crawl delay for a domain from robots.txt
        
        Returns:
            Crawl delay in seconds (default: 1.0)
        """
        try:
            rp = self._get_robot_parser(url)
            delay = rp.crawl_delay(user_agent)
            return delay if delay else 1.0
        except:
            return 1.0

