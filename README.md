# Pharma News Research Agent - Flask Blueprint

https://www.mermaidchart.com/app/projects/aafc7971-6213-42b5-8d9b-68bc066e3d3a/diagrams/77269448-8b76-476c-a55a-660e8871b315/share/invite/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb2N1bWVudElEIjoiNzcyNjk0NDgtOGI3Ni00NzZjLWE1NWEtNjYwZTg4NzFiMzE1IiwiYWNjZXNzIjoiRWRpdCIsImlhdCI6MTc2MTE3MjQ4N30.fk8Ra-v4EoC2eB2Y1cVVwN4RDykIS19-S5C__jF9DDQ 

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

