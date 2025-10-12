# Pharma News Research Agent

An AI-powered pharmaceutical news research application with intelligent curation and multi-source data collection.

## Features

- 🔍 **Multi-Source Search**: Integrates PubMed, Exa, and Tavily APIs for comprehensive research
- 🤖 **AI-Powered Curation**: Uses OpenAI GPT for intelligent content analysis and relevance scoring
- 📊 **Multiple Search Strategies**: Standard, Title-based, and Co-occurrence search modes
- 📅 **Date Filtering**: Default 7-day search range (configurable)
- 🎯 **Pre-filled Keywords**: Quick-fill buttons for common research topics
- 📁 **CSV Processing**: Batch processing support for multiple sections
- 📥 **Export to CSV**: Download results for further analysis

## Quick Start

1. **Set up API keys** in `constants.py`:
   - OpenAI API Key (for intelligent curation)
   - Tavily API Key (for enhanced web search)
   - Exa API Key (for neural search)
   - NewsAPI Key (for pharmaceutical news)
   - PubMed Email (for PubMed API access)

2. **Run the application**:
   ```bash
   python run_pharma_search.py
   ```

3. **Access the web interface** at `http://127.0.0.1:5000`

## Project Structure

```
News-Agent/
├── medical_search_simple.py  # Flask application & UI
├── pharma_agent.py           # Agentic workflow orchestrator
├── config.py                 # Configuration management
├── constants.py              # API keys and settings
├── run_pharma_search.py      # Application launcher
└── README.md                 # This file
```

## Usage

### Single Search
1. Use the quick-fill buttons to populate common keywords:
   - 🏥 **Prostate Cancer & Urology**: Pre-fills keywords for prostate cancer, orgovyx, myfembree, OAB, etc.
   - 🤖 **AI in Pharma**: Pre-fills keywords for AI, machine learning, RAG, LLM, etc.

2. Or enter your own keywords (comma-separated)

3. Select date range (defaults to last 7 days)

4. Choose search type:
   - **Standard**: Any keyword in article
   - **Title**: Keyword must be in article title
   - **Co-occurrence**: 2+ keywords must appear together

5. Click "Research Pharma Sources" to start the search

### Multi-Section CSV Processing
Upload a CSV file with columns: `aliases`, `keywords`, `search_type`, `subheader`, `header`, `user`

## Default Settings

- **Date Range**: Last 7 days (today as end date, today-7 days as start date)
- **Search Engines**: PubMed, Exa, and Tavily (all enabled by default)
- **Max Keywords**: 100 per search
- **Max Results**: 50 per source

## Features in Detail

### Autofill Buttons
The UI includes quick-fill buttons that automatically populate:
- Keywords relevant to the research topic
- Alert and section names
- Date range (last 7 days)

### Agentic Workflow
The application uses an intelligent multi-step workflow:
1. Data Collection from multiple sources
2. Data Validation & Filtering
3. Intelligent Curation with LLM
4. Relevance Scoring & Ranking
5. Content Enhancement & Highlighting
6. Result Aggregation & Formatting

### API Integration
- **PubMed**: Medical literature and clinical trials
- **Exa**: Neural search for web content
- **Tavily**: Enhanced web search
- **OpenAI**: GPT-powered curation and summarization

## Requirements

- Python 3.7+
- Flask
- Requests
- OpenAI Python SDK
- Tavily Python SDK (optional)
- Exa Python SDK (optional)

## Notes

- All API keys are configured in `constants.py`
- The application will work with any combination of available APIs
- Without API keys, the application will use basic search functionality
- Results are temporarily stored in memory for CSV export

## License

Private project - All rights reserved
