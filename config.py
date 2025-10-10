"""
Configuration for Pharma News Research Agent
Handles API keys and settings for real data integration
"""

import os
import sys

# Import constants instead of using dotenv
try:
    import constants
    CONSTANTS_LOADED = True
except ImportError:
    print("Warning: constants.py not found. Using default configuration.")
    print("Create constants.py with your API keys for enhanced functionality")
    CONSTANTS_LOADED = False
    constants = None

class Config:
    """Configuration class for the Pharma News Research Agent"""
    
    # Flask settings
    SECRET_KEY = getattr(constants, 'SECRET_KEY', 'dev-secret-key-change-in-production') if constants else 'dev-secret-key-change-in-production'
    DEBUG = getattr(constants, 'FLASK_DEBUG', True) if constants else True
    
    # API Keys - Required for real data
    OPENAI_API_KEY = getattr(constants, 'OPENAI_API_KEY', None) if constants else None
    TAVILY_API_KEY = getattr(constants, 'TAVILY_API_KEY', None) if constants else None
    NEWSAPI_KEY = getattr(constants, 'NEWSAPI_KEY', None) if constants else None
    PUBMED_EMAIL = getattr(constants, 'PUBMED_EMAIL', None) if constants else None
    
    # Search settings
    MAX_KEYWORDS = getattr(constants, 'MAX_KEYWORDS', 100) if constants else 100
    MAX_RESULTS_PER_SOURCE = getattr(constants, 'MAX_RESULTS_PER_SOURCE', 50) if constants else 50
    DEFAULT_DATE_RANGE_DAYS = getattr(constants, 'DEFAULT_DATE_RANGE_DAYS', 7) if constants else 7
    
    # LLM settings for curation
    OPENAI_MODEL = getattr(constants, 'OPENAI_MODEL', "gpt-3.5-turbo") if constants else "gpt-3.5-turbo"
    MAX_TOKENS = getattr(constants, 'MAX_TOKENS', 1000) if constants else 1000
    TEMPERATURE = getattr(constants, 'TEMPERATURE', 0.3) if constants else 0.3
    
    # API rate limits and timeouts
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        missing_keys = []
        
        # Check for at least one API key
        if not cls.OPENAI_API_KEY:
            missing_keys.append('OPENAI_API_KEY')
        if not cls.TAVILY_API_KEY:
            missing_keys.append('TAVILY_API_KEY')
        if not cls.NEWSAPI_KEY:
            missing_keys.append('NEWSAPI_KEY')
        
        if missing_keys:
            print(f"Warning: Missing API keys: {', '.join(missing_keys)}")
            print("Some features may not work without proper API keys")
            print("Add them to your constants.py file:")
            for key in missing_keys:
                print(f"   {key} = 'your_api_key_here'")
            return False
        
        return True
    
    @classmethod
    def get_api_status(cls):
        """Get status of API configurations"""
        return {
            'openai_configured': bool(cls.OPENAI_API_KEY),
            'tavily_configured': bool(cls.TAVILY_API_KEY),
            'newsapi_configured': bool(cls.NEWSAPI_KEY),
            'pubmed_configured': bool(cls.PUBMED_EMAIL)
        }
