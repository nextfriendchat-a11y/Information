from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://anabia_db:anabia212@cluster0.nqzucks.mongodb.net/?appName=Cluster0")
DATABASE_NAME = os.getenv("DATABASE_NAME", "public_information")

_client: MongoClient = None
_database: Database = None
_indexes_created = False


def get_client() -> MongoClient:
    """Get or create MongoDB client"""
    global _client
    if _client is None:
        try:
            # For mongodb+srv://, TLS is automatically enabled
            # Only use tls_* parameters, not ssl_* parameters
            _client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=30000,  # 30 second timeout
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                tlsAllowInvalidCertificates=True,  # For development/testing
                retryWrites=True,
                retryReads=True
            )
            # Test connection with longer timeout
            _client.admin.command('ping')
            logger.info("MongoDB connection established")
        except ServerSelectionTimeoutError as e:
            error_msg = str(e)
            logger.error("=" * 60)
            logger.error("MONGODB CONNECTION FAILED")
            logger.error("=" * 60)
            if "SSL" in error_msg or "TLS" in error_msg:
                logger.error("SSL/TLS Error detected. Possible solutions:")
                logger.error("1. Check MongoDB Atlas Network Access - whitelist your IP")
                logger.error("2. Verify your internet connection")
                logger.error("3. Check firewall/antivirus settings")
            else:
                logger.error("Connection timeout. Check:")
                logger.error("1. MongoDB Atlas cluster status")
                logger.error("2. Your IP is whitelisted in Network Access")
                logger.error("3. Network connectivity")
            logger.error("=" * 60)
            raise
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            raise
    return _client


def get_database() -> Database:
    """Get or create database connection"""
    global _database
    if _database is None:
        client = get_client()
        _database = client[DATABASE_NAME]
        # Create indexes (non-blocking, with error handling)
        _create_indexes_safe()
    return _database


def _create_indexes_safe():
    """Create necessary indexes for collections with error handling"""
    global _indexes_created
    if _indexes_created:
        return
    
    try:
        db = get_database()
        
        # Indexes for public_records
        public_records = db.public_records
        try:
            public_records.create_index("name", background=True)
            public_records.create_index("phone", background=True)
            public_records.create_index("institution", background=True)
            public_records.create_index("address", background=True)
            public_records.create_index("organization", background=True)
        except OperationFailure as e:
            logger.warning(f"Some indexes may already exist: {e}")
        
        # Indexes for crawl_jobs
        crawl_jobs = db.crawl_jobs
        try:
            crawl_jobs.create_index("url", unique=True, background=True)
            crawl_jobs.create_index("status", background=True)
            crawl_jobs.create_index("next_crawl", background=True)
        except OperationFailure as e:
            logger.warning(f"Some indexes may already exist: {e}")
        
        # Indexes for ai_cache
        ai_cache = db.ai_cache
        try:
            ai_cache.create_index("query_hash", unique=True, background=True)
            ai_cache.create_index("expires_at", expireAfterSeconds=0, background=True)
        except OperationFailure as e:
            logger.warning(f"Some indexes may already exist: {e}")
        
        _indexes_created = True
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        # Don't raise - allow app to continue without indexes
        # Indexes can be created later


def get_collection(collection_name: str) -> Collection:
    """Get a specific collection from the database"""
    db = get_database()
    return db[collection_name]

