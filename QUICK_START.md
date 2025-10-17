# Quick Start Guide - OME Blueprint

## 🚀 Ready to Use in 3 Lines of Code

```python
from ome_blueprint import ome_blueprint
app.register_blueprint(ome_blueprint, url_prefix='/OME')
# Done! Access at /OME/
```

## 📦 What You Have

| File | Purpose |
|------|---------|
| `ome_blueprint.py` | Main blueprint - import this |
| `constants.py` | Your API keys (configured ✓) |
| `example_integration.py` | Working example |
| `test_blueprint.py` | Test it works |

## 🎯 Endpoints

- **`/OME/`** → Main interface
- **`/OME/search`** → Search API
- **`/OME/health`** → Status check

## ✅ Test It

```bash
python test_blueprint.py
```

## 🏃 Run Example

```bash
python example_integration.py
```

Visit: http://localhost:5000/OME/

## 📝 Full Example

```python
from flask import Flask
from ome_blueprint import ome_blueprint

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-key'
app.register_blueprint(ome_blueprint, url_prefix='/OME')

@app.route('/')
def home():
    return '<a href="/OME/">Pharma News Agent</a>'

if __name__ == '__main__':
    app.run(debug=True)
```

## 🔥 Features

- ✅ Multi-source pharma news (PubMed, Exa, Tavily, NewsAPI)
- ✅ AI-powered relevance scoring
- ✅ Auto-deduplication
- ✅ Date extraction with LLM
- ✅ CSV export
- ✅ Beautiful web UI

## 📚 More Info

- `README.md` - Full documentation
- `INTEGRATION_GUIDE.md` - Detailed integration
- `CHANGES_SUMMARY.txt` - What changed

---

**That's it!** 🎉 You're ready to go!

