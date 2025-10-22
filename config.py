"""
Configuration for Pharma News Research Agent
Handles API keys and settings for real data integration
"""

import os
import sys
from openai import AzureOpenAI, OpenAI

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
    EXA_API_KEY = getattr(constants, 'EXA_API_KEY', None) if constants else None
    PUBMED_EMAIL = getattr(constants, 'PUBMED_EMAIL', None) if constants else None
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY = getattr(constants, 'AZURE_OPENAI_API_KEY', None) if constants else None
    AZURE_OPENAI_ENDPOINT = getattr(constants, 'AZURE_OPENAI_ENDPOINT', None) if constants else None
    AZURE_OPENAI_API_VERSION = getattr(constants, 'AZURE_OPENAI_API_VERSION', "2024-02-15-preview") if constants else "2024-02-15-preview"
    AZURE_OPENAI_DEPLOYMENT_NAME = getattr(constants, 'AZURE_OPENAI_DEPLOYMENT_NAME', "gpt-4o-mini") if constants else "gpt-4o-mini"
    
    # Search settings
    MAX_KEYWORDS = getattr(constants, 'MAX_KEYWORDS', 100) if constants else 100
    MAX_RESULTS_PER_SOURCE = getattr(constants, 'MAX_RESULTS_PER_SOURCE', 50) if constants else 50
    DEFAULT_DATE_RANGE_DAYS = getattr(constants, 'DEFAULT_DATE_RANGE_DAYS', 7) if constants else 7
    
    # LLM settings for curation
    OPENAI_MODEL = getattr(constants, 'OPENAI_MODEL', "gpt-4o-mini") if constants else "gpt-4o-mini"
    DATE_EXTRACTION_MODEL = getattr(constants, 'DATE_EXTRACTION_MODEL', "gpt-3.5-turbo") if constants else "gpt-3.5-turbo"
    MAX_TOKENS = getattr(constants, 'MAX_TOKENS', 1000) if constants else 1000
    TEMPERATURE = getattr(constants, 'TEMPERATURE', 0.0) if constants else 0.0
    
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
        if not cls.EXA_API_KEY:
            missing_keys.append('EXA_API_KEY')
        
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
            'azure_openai_configured': bool(cls.AZURE_OPENAI_API_KEY and cls.AZURE_OPENAI_ENDPOINT),
            'tavily_configured': bool(cls.TAVILY_API_KEY),
            'exa_configured': bool(cls.EXA_API_KEY),
            'newsapi_configured': bool(cls.NEWSAPI_KEY),
            'pubmed_configured': bool(cls.PUBMED_EMAIL)
        }
    
    @classmethod
    def should_use_azure_openai(cls):
        """Determine if Azure OpenAI should be used based on available credentials"""
        return bool(cls.AZURE_OPENAI_API_KEY and cls.AZURE_OPENAI_ENDPOINT)
    
    @classmethod
    def get_openai_client_config(cls):
        """Get OpenAI client configuration (Azure or direct OpenAI)"""
        if cls.should_use_azure_openai():
            return {
                'type': 'azure',
                'api_key': cls.AZURE_OPENAI_API_KEY,
                'azure_endpoint': cls.AZURE_OPENAI_ENDPOINT,
                'api_version': cls.AZURE_OPENAI_API_VERSION,
                'azure_deployment': cls.AZURE_OPENAI_DEPLOYMENT_NAME
            }
        elif cls.OPENAI_API_KEY:
            return {
                'type': 'openai',
                'api_key': cls.OPENAI_API_KEY
            }
        else:
            return None
    
    @classmethod
    def get_model_name(cls, model_type='main'):
        """Get the correct model name based on client type"""
        if cls.should_use_azure_openai():
            # For Azure OpenAI, use the deployment name
            return cls.AZURE_OPENAI_DEPLOYMENT_NAME
        else:
            # For direct OpenAI, use the configured model names
            if model_type == 'date_extraction':
                return cls.DATE_EXTRACTION_MODEL
            else:
                return cls.OPENAI_MODEL

def create_openai_client(config: 'Config'):
    """
    Create appropriate OpenAI client based on configuration.
    Returns Azure OpenAI client if Azure credentials are available,
    otherwise returns direct OpenAI client.
    
    Args:
        config: Config instance with API credentials
        
    Returns:
        OpenAI client (AzureOpenAI or OpenAI)
        
    Raises:
        ValueError: If no valid OpenAI credentials are found
    """
    client_config = config.get_openai_client_config()
    
    if not client_config:
        raise ValueError("No valid OpenAI credentials found. Please configure either OPENAI_API_KEY or Azure OpenAI credentials.")
    
    if client_config['type'] == 'azure':
        print("Using Azure OpenAI client")
        return AzureOpenAI(
            api_key=client_config['api_key'],
            azure_endpoint=client_config['azure_endpoint'],
            api_version=client_config['api_version']
        )
    else:
        print("Using direct OpenAI client")
        return OpenAI(api_key=client_config['api_key'])
