"""
Helper script to create .env file from template
Run this if .env doesn't exist
"""
import os
from pathlib import Path

env_content = """MONGODB_URI=mongodb+srv://anabia_db:anabia212@cluster0.nqzucks.mongodb.net/?appName=Cluster0
DATABASE_NAME=public_information
OPENAI_API_KEY=your_openai_api_key_here
CRAWL_INTERVAL_HOURS=24
CRAWL_DELAY_SECONDS=2
"""

env_path = Path(".env")

if env_path.exists():
    print(".env file already exists. Skipping creation.")
else:
    with open(env_path, "w") as f:
        f.write(env_content)
    print(".env file created successfully!")
    print("Please update OPENAI_API_KEY with your actual API key.")

