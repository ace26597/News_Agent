# Pharma News Research Agent - Flask Blueprint

AI-powered pharmaceutical news research with multi-source data collection.

## Quick Start

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configure API Keys
Edit `constants.py` with your API keys:
```python
OPENAI_API_KEY = "your-key"
TAVILY_API_KEY = "your-key"
NEWSAPI_KEY = "your-key"
EXA_API_KEY = "your-key"
PUBMED_EMAIL = "your-email"
```

### Integration
```python
from flask import Flask
from ome_blueprint import ome_blueprint

app = Flask(__name__)
app.register_blueprint(ome_blueprint, url_prefix='/OME')

if __name__ == '__main__':
    app.run(debug=True)
```

### Run the App
```bash
python -c "from flask import Flask; from ome_blueprint import ome_blueprint; app = Flask(__name__); app.register_blueprint(ome_blueprint, url_prefix='/OME'); app.run(debug=True)"
```

Visit: http://localhost:5000/OME/

## Features

- 🔬 Multi-source pharma news (PubMed, Exa, Tavily, NewsAPI)
- 🤖 AI-powered relevance scoring
- 🔄 Auto-deduplication
- 📅 LLM date extraction
- 📥 HTML export for email
- 💾 CSV export

## Endpoints

- `GET /OME/` - Main interface
- `POST /OME/search` - Search API
- `GET /OME/export_html/<session_id>` - Export as HTML
- `GET /OME/download/<session_id>` - Download CSV
- `GET /OME/health` - Health check

## Files

- `ome_blueprint.py` - Main Flask blueprint
- `multi_agent_pharma.py` - Multi-agent AI workflow
- `pharma_agent.py` - Base pharma agent
- `config.py` - Configuration loader
- `constants.py` - API keys

## License

MIT

