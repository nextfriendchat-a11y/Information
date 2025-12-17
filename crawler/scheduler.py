import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from typing import List
from crawler.crawler import WebCrawler
from database.mongodb import get_collection
from dotenv import load_dotenv

load_dotenv()


class CrawlScheduler:
    """Scheduler for periodic web crawling"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.crawl_jobs_collection = get_collection("crawl_jobs")
        self.crawl_interval_hours = int(os.getenv("CRAWL_INTERVAL_HOURS", "24"))
        
        # Seed URLs from the project requirements
        self.seed_urls = [
  
            "https://www.biek.edu.pk/default.asp"
           
        ]
    
    def _crawl_job(self, force_all: bool = False):
        """
        Job function to run crawler
        
        Args:
            force_all: If True, crawl all URLs regardless of last crawl time (for startup)
        """
        print(f"\n{'='*50}")
        print(f"Scheduled crawl started at {datetime.utcnow()}")
        if force_all:
            print("FORCE MODE: Crawling all URLs regardless of last crawl time")
        print(f"{'='*50}\n")
        
        try:
            # Check which URLs need crawling
            urls_to_crawl = []
            for seed_url in self.seed_urls:
                if force_all:
                    # Force mode: always crawl all URLs
                    urls_to_crawl.append(seed_url)
                else:
                    # Normal mode: check if URL needs crawling based on interval
                    job = self.crawl_jobs_collection.find_one({"url": seed_url})
                    
                    if not job:
                        # Never crawled
                        urls_to_crawl.append(seed_url)
                    else:
                        last_crawled = job.get("last_crawled")
                        if last_crawled:
                            last_crawled = last_crawled if isinstance(last_crawled, datetime) else datetime.fromisoformat(str(last_crawled))
                            hours_since_crawl = (datetime.utcnow() - last_crawled).total_seconds() / 3600
                            
                            if hours_since_crawl >= self.crawl_interval_hours:
                                urls_to_crawl.append(seed_url)
                        else:
                            urls_to_crawl.append(seed_url)
            
            if urls_to_crawl:
                print(f"Crawling {len(urls_to_crawl)} URL(s)...")
                # Create new crawler instance for this run
                crawler = WebCrawler()
                crawler.crawl_seed_urls(urls_to_crawl, max_depth=3)
                crawler.cleanup()
                print(f"Completed crawling {len(urls_to_crawl)} URL(s)")
            else:
                print("No URLs need crawling at this time.")
        
        except Exception as e:
            print(f"Error in scheduled crawl: {e}")
            import traceback
            traceback.print_exc()
    
    def start(self, run_initial_crawl: bool = False):
        """
        Start the scheduler
        
        Args:
            run_initial_crawl: If True, run initial crawl on startup (default: False)
                              Set to False since data is already in DB and cron job will handle crawling
        """
        # Schedule crawl job to run at intervals (normal mode - respects crawl interval)
        self.scheduler.add_job(
            func=self._crawl_job,
            args=[False],  # Normal mode - check crawl interval
            trigger=IntervalTrigger(hours=self.crawl_interval_hours),
            id='crawl_job',
            name='Periodic web crawl',
            replace_existing=True
        )
        
        self.scheduler.start()
        print(f"Scheduler started. Crawls will run every {self.crawl_interval_hours} hours.")
        
        # Only run initial crawl if explicitly requested
        # Disabled by default since data is already in DB and cron job will handle crawling
        if run_initial_crawl:
            print("Running initial crawl on startup (FORCE MODE - all URLs)...")
            self._crawl_job(force_all=True)
        else:
            print("Skipping initial crawl on startup. Data is already in database.")
            print("Use /api/crawl/trigger endpoint or cron job to trigger crawls manually.")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
    
    def trigger_manual_crawl(self, urls: List[str] = None, force_all: bool = True):
        """
        Manually trigger a crawl
        
        Args:
            urls: Specific URLs to crawl (None = all seed URLs)
            force_all: If True, crawl regardless of last crawl time
        """
        if urls:
            # Crawl specific URLs
            crawler = WebCrawler()
            crawler.crawl_seed_urls(urls, max_depth=3)
            crawler.cleanup()
        else:
            # Use the crawl job method with force_all
            self._crawl_job(force_all=force_all)

