# API Keys and Configuration Constants
# Add your API keys here instead of using .env file

# OpenAI API Key for intelligent curation and summarization
OPENAI_API_KEY = "your-openai-api-key-here"

# Azure OpenAI Configuration (dummy values - replace with your actual Azure credentials)
AZURE_OPENAI_API_KEY = "your-azure-openai-api-key-here"
AZURE_OPENAI_ENDPOINT = "https://your-resource-name.openai.azure.com/"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o-mini"  # Your deployment name

# Tavily API Key for enhanced web search
TAVILY_API_KEY = "your-tavily-api-key-here"

# NewsAPI Key for pharmaceutical news
NEWSAPI_KEY = "your-newsapi-key-here"
EXA_API_KEY = "your-exa-api-key-here"

# PubMed Email (required for PubMed API)
PUBMED_EMAIL = "your-email@example.com"

# Flask Configuration
SECRET_KEY = "dev-secret-key-change-in-production"
FLASK_DEBUG = True

# Search Configuration
MAX_KEYWORDS = 100
MAX_RESULTS_PER_SOURCE = 50
DEFAULT_DATE_RANGE_DAYS = 7

# LLM Configuration
OPENAI_MODEL = "gpt-4o-mini"  # Main model for curation
DATE_EXTRACTION_MODEL = "gpt-3.5-turbo"  # Faster/cheaper model for date extraction
MAX_TOKENS = 3000  # Increased for larger batches (10 articles instead of 3)
TEMPERATURE = 0.0
