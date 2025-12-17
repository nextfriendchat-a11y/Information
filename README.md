# AI-Powered Public Information Search System

An intelligent system that crawls, indexes, and searches publicly available information using AI-powered natural language queries.

## Features

- **AI-Powered Search**: Uses GPT-4o-mini to understand natural language queries
- **Flexible Attribute Search**: Search by name, phone, address, institution, or any combination
- **Interactive Clarification**: AI asks follow-up questions when queries are ambiguous
- **Web Crawling**: Automatically crawls and indexes public data sources
- **Disambiguation**: Handles multiple matching records intelligently
- **Source Transparency**: All results include source URLs and timestamps

## Project Structure

```
AI_information_search/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables (create from .env.example)
├── crawler/              # Web crawling components
├── services/             # AI, search, and cache services
├── models/               # Data models
├── database/             # MongoDB connection
├── api/                  # API routes and schemas
└── static/               # Frontend files
```

## Setup

1. **Install Dependencies**

```bash
pip install -r requirements.txt
```

2. **Install Playwright Browsers**

```bash
playwright install chromium
```

3. **Configure Environment**

Create a `.env` file from `.env.example`:

```env
MONGODB_URI=mongodb+srv://anabia_db:anabia212@cluster0.nqzucks.mongodb.net/?appName=Cluster0
DATABASE_NAME=public_information
OPENAI_API_KEY=your_openai_api_key_here
CRAWL_INTERVAL_HOURS=24
CRAWL_DELAY_SECONDS=2
```

4. **Run the Application**

```bash
python app.py
```

Or using uvicorn directly:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

5. **Access the Application**

Open your browser and navigate to `http://localhost:8000`

## Usage

### Web Interface

Simply type your query in natural language:

- "Find Zoe Khan"
- "Whose number is 021-1234567?"
- "Show students from ABC Public School"
- "Find information about John Smith"

The AI will:
1. Understand your intent
2. Ask clarifying questions if needed
3. Search the database
4. Present results with source attribution

### API Endpoints

#### POST `/api/chat`
Main conversational endpoint for AI-powered search.

**Request:**
```json
{
  "query": "Find Zoe Khan",
  "conversation_history": []
}
```

**Response:**
```json
{
  "response": "I found 2 records...",
  "results": [...],
  "needs_clarification": false,
  "needs_disambiguation": true,
  "disambiguation_options": [...],
  "action": "search"
}
```

#### POST `/api/search`
Direct search endpoint (bypasses AI conversation).

#### GET `/api/status`
Get system status and statistics.

#### POST `/api/crawl/trigger`
Manually trigger a crawl job.

## Data Sources

The system crawls the following public data sources:

- Karachi Municipal Corporation Schools
- Pakistan Government Open Data
- POI Data Store
- HamariWeb Directories
- Yellow Pages Pakistan
- Board of Secondary Education Karachi
- Board of Intermediate Education Karachi
- Wikipedia - List of Schools in Karachi
- Various result and education portals

## Database Collections

- **public_records**: Stores all scraped public information
- **crawl_jobs**: Tracks crawl status and history
- **ai_cache**: Caches AI responses to reduce API costs

## Technologies

- **Backend**: FastAPI
- **Database**: MongoDB
- **AI**: OpenAI GPT-4o-mini
- **Web Scraping**: BeautifulSoup, Playwright
- **Frontend**: HTML, CSS, JavaScript

## Ethical Compliance

- Only crawls publicly accessible pages
- Respects robots.txt files
- Implements rate limiting and crawl delays
- No authentication bypassing
- No access to private or restricted data
- Source transparency for all results

## License

This project is for educational and research purposes only. Ensure compliance with website terms of service and applicable laws when crawling public data.

