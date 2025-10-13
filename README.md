# Pharma News Research Agent

An AI-powered pharmaceutical news research application that aggregates and curates content from multiple sources including PubMed, Exa, and Tavily APIs.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy the example constants file and add your API keys:

```bash
cp constants.py.example constants.py
```

Edit `constants.py` and add your API keys:
- **OpenAI API Key** (Required for AI-powered curation)
- **Tavily API Key** (Optional for enhanced web search)
- **Exa API Key** (Optional for neural search)
- **NewsAPI Key** (Optional for pharmaceutical news)
- **PubMed Email** (Required for PubMed API access)

### 3. Run the Application

```bash
python run_pharma_search.py
```

The application will start on `http://127.0.0.1:5000`

## 📁 Project Structure

```
News-Agent/
├── medical_search_simple.py    # Main Flask web application
├── pharma_agent.py              # Primary agent implementation
├── multi_agent_pharma.py        # Multi-agent orchestrator
├── config.py                    # Configuration management
├── constants.py                 # API keys and settings (not in git)
├── constants.py.example         # Example configuration template
├── run_pharma_search.py         # Application launcher script
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## ✨ Features

- 🔍 **Multi-Source Search**: Aggregates from PubMed, Exa, and Tavily APIs
- 🤖 **AI-Powered Curation**: Uses OpenAI GPT for intelligent content analysis
- 🧠 **Smart Date Extraction**: Fast LLM extracts dates from URLs, content, and metadata for articles without publication dates
- 📊 **Multiple Search Strategies**: Standard, Title-based, and Co-occurrence modes
- 📅 **Date Filtering**: Default 7-day search range (configurable)
- 🎯 **Quick-fill Buttons**: Pre-populated keywords for common research topics
- 📥 **CSV Export**: Download results for further analysis
- 📁 **Batch Processing**: Upload CSV files for multi-section searches

## 📖 Usage

### Single Search

1. **Choose a quick-fill option** or enter custom keywords:
   - 🏥 Prostate Cancer & Urology (orgovyx, myfembree, OAB, etc.)
   - 🤖 AI in Pharma (AI, machine learning, RAG, LLM, etc.)

2. **Select date range** (default: last 7 days)

3. **Choose search type**:
   - **Standard**: Any keyword in article
   - **Title**: Keyword must be in title
   - **Co-occurrence**: 2+ keywords must appear together

4. **Click "Research Pharma Sources"** to start the search

### Multi-Section CSV Processing

Upload a CSV file with columns:
- `aliases` - Alternative names/keywords
- `keywords` - Main search terms
- `search_type` - standard/title/co-occurrence
- `subheader` - Section name
- `header` - Main header
- `user` - User identifier

## ⚙️ Configuration

Default settings in `constants.py`:

```python
# Search Configuration
DEFAULT_DATE_RANGE_DAYS = 7
MAX_KEYWORDS = 100
MAX_RESULTS_PER_SOURCE = 50

# LLM Configuration
OPENAI_MODEL = "gpt-4o-mini"  # Main model for curation
DATE_EXTRACTION_MODEL = "gpt-3.5-turbo"  # Fast model for date extraction
MAX_TOKENS = 3000
TEMPERATURE = 0.0
```

### Smart Date Extraction

Articles without publication dates are processed by a fast LLM (`gpt-3.5-turbo`) that:
- Analyzes URLs for date patterns (e.g., `/2024/03/15/`)
- Scans content for publication indicators
- Checks metadata and article text (up to 3000 characters)
- Extracts dates and validates them against your search range

**Benefits:**
- 📈 Captures more relevant articles (rescued by LLM)
- 💰 Cost-efficient (uses cheaper model for date extraction)
- 🎯 Only includes articles with dates within your specified range

## 🔑 API Keys

The application requires at least one of the following API configurations:

- **OpenAI** (Required): For AI-powered curation and summarization
- **PubMed Email** (Recommended): For accessing PubMed medical literature
- **Tavily** (Optional): For enhanced web search capabilities
- **Exa** (Optional): For neural search functionality
- **NewsAPI** (Optional): For pharmaceutical news articles

## 🧪 Tech Stack

- **Backend**: Python 3.7+, Flask
- **AI/ML**: OpenAI GPT-4o-mini
- **APIs**: PubMed, Exa, Tavily, NewsAPI
- **Data Processing**: Pandas-compatible CSV export

## 📝 Notes

- API keys are stored in `constants.py` (git-ignored for security)
- The application works with any combination of available APIs
- Without API keys, basic search functionality will be available
- Results are temporarily stored in memory for CSV export
- Default date range uses today as end date and 7 days prior as start date

## 🔒 Security

- Never commit `constants.py` to version control
- Use `constants.py.example` as a template
- Keep your API keys secure and private

## 📄 License

Private project - All rights reserved
