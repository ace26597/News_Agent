# OME Blueprint Integration Guide

## Overview

This project has been converted to a **Flask Blueprint** that can be easily integrated into any existing Flask application at the `/OME/` endpoint.

## What Changed

### Files Removed ❌
- All documentation `.md` files (10 files)
- `run_pharma_search.py` (old runner script)
- `medical_search_simple.py` (old standalone Flask app)
- `constants.py.example` (example file)

### Files Kept ✅
- `.gitignore` (as requested)
- `constants.py` (API keys and configuration - as requested)
- `config.py` (configuration loader)
- `multi_agent_pharma.py` (multi-agent workflow)
- `pharma_agent.py` (base pharma agent)
- `requirements.txt` (updated dependencies)

### Files Added ✨
- **`ome_blueprint.py`** - Main Flask blueprint (replaces `medical_search_simple.py`)
- `example_integration.py` - Shows how to integrate into your app
- `test_blueprint.py` - Tests blueprint functionality
- `README.md` - Updated documentation
- `INTEGRATION_GUIDE.md` - This file

## Quick Integration (3 Steps)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure API Keys

Make sure your `constants.py` has the required API keys:

```python
OPENAI_API_KEY = "your-key"
TAVILY_API_KEY = "your-key"
NEWSAPI_KEY = "your-key"
EXA_API_KEY = "your-key"
PUBMED_EMAIL = "your-email"
```

### Step 3: Add to Your Flask App

```python
from flask import Flask
from ome_blueprint import ome_blueprint

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'

# Register the OME blueprint
app.register_blueprint(ome_blueprint, url_prefix='/OME')

if __name__ == '__main__':
    app.run(debug=True)
```

That's it! The agent is now available at:
- **Main Interface**: `http://your-domain/OME/`
- **Search API**: `http://your-domain/OME/search`
- **Health Check**: `http://your-domain/OME/health`

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/OME/` | GET | Main search interface (HTML) |
| `/OME/search` | POST | Perform pharmaceutical news search |
| `/OME/health` | GET | Health check and API status |
| `/OME/download/<session_id>` | GET | Download results as CSV |
| `/OME/upload_csv` | POST | Batch processing via CSV |

## API Usage Example

```python
import requests

# Search for pharma news
response = requests.post('http://localhost:5000/OME/search', json={
    'keywords': 'prostate cancer, immunotherapy',
    'start_date': '2024-01-01',
    'end_date': '2024-12-31',
    'search_type': 'standard',
    'search_engines': ['pubmed', 'exa', 'tavily', 'newsapi']
})

data = response.json()
print(f"Found {len(data['results'])} articles")

for article in data['results']:
    print(f"- {article['title']}")
    print(f"  Relevance: {article['relevance_score']}/100")
    print(f"  Source: {article['source']}")
    print()
```

## Testing

Run the test to verify the blueprint works:

```bash
python test_blueprint.py
```

Expected output:
```
[SUCCESS] All expected routes are registered!
[SUCCESS] Blueprint integration successful!
```

## Running Example

Run the example integration:

```bash
python example_integration.py
```

Then visit:
- Main app: http://localhost:5000/
- OME Agent: http://localhost:5000/OME/

## Features

✅ Multi-source data collection (PubMed, Exa, Tavily, NewsAPI)  
✅ AI-powered relevance scoring with GPT-4  
✅ Automatic deduplication of articles  
✅ LLM-based date extraction  
✅ Real-time filtering and analytics  
✅ CSV export for batch processing  
✅ Beautiful web interface  

## Architecture

The blueprint uses a multi-agent architecture:

1. **Date Extraction Agent** - Extracts publication dates using LLM + regex
2. **Relevance Agent** - Scores articles for pharmaceutical relevance (0-100)
3. **Content Enhancement Agent** - Highlights keywords and generates summaries
4. **Deduplication Agent** - Removes near-duplicate articles based on title similarity

## File Structure

```
.
├── ome_blueprint.py          # Main Flask blueprint (MAIN FILE)
├── multi_agent_pharma.py     # Multi-agent AI workflow
├── pharma_agent.py           # Base pharma agent
├── config.py                 # Configuration loader
├── constants.py              # API keys (keep private!)
├── requirements.txt          # Dependencies
├── example_integration.py    # Integration example
├── test_blueprint.py         # Blueprint tests
├── README.md                 # Documentation
├── INTEGRATION_GUIDE.md      # This file
└── .gitignore                # Git ignore rules
```

## Important Notes

⚠️ **Security**: Never commit `constants.py` to version control (it's in `.gitignore`)  
⚠️ **API Keys**: Make sure all required API keys are configured  
⚠️ **Dependencies**: Install all requirements before running  

## Troubleshooting

### Blueprint not registering?
Make sure you import from `ome_blueprint`, not `medical_search_simple`

### API errors?
Check that your `constants.py` has valid API keys

### Routes not working?
Verify the `url_prefix='/OME'` is set when registering the blueprint

### Import errors?
Run `pip install -r requirements.txt`

## Next Steps

1. ✅ Test the blueprint: `python test_blueprint.py`
2. ✅ Run example: `python example_integration.py`
3. ✅ Integrate into your app
4. ✅ Access at `/OME/` endpoint

## Support

For issues or questions:
1. Check this guide
2. Review `example_integration.py`
3. Test with `test_blueprint.py`
4. Check your API keys in `constants.py`

---

**You're all set!** The Pharma News Research Agent is now available as a clean Flask blueprint at `/OME/`.

