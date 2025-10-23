"""
Pharma News Research Agent - Flask Blueprint
Real API integration with agentic workflow for pharmaceutical news research

This blueprint can be integrated into any Flask application at the /OME/ endpoint.

Usage:
    from ome_blueprint import ome_blueprint
    
    app = Flask(__name__)
    app.register_blueprint(ome_blueprint, url_prefix='/OME')
"""

import json
import csv
import io
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from pathlib import Path
from flask import Blueprint, render_template_string, request, jsonify, send_file

# Import our agentic workflow
try:
    from multi_agent_pharma import MultiAgentPharmaAgent
    from config import Config
    AGENT_AVAILABLE = True
    MULTI_AGENT_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Multi-agent workflow not available: {e}")
    print("INFO: Trying fallback to basic pharma agent...")
    try:
        from pharma_agent import PharmaNewsAgent
        from config import Config
        AGENT_AVAILABLE = True
        MULTI_AGENT_AVAILABLE = False
    except ImportError as e2:
        print(f"WARNING: Basic agentic workflow also not available: {e2}")
        print("INFO: Falling back to basic search functionality")
        AGENT_AVAILABLE = False
        MULTI_AGENT_AVAILABLE = False
    else:
        MULTI_AGENT_AVAILABLE = False
else:
    MULTI_AGENT_AVAILABLE = True

# Configuration
if not AGENT_AVAILABLE:
    class Config:
        MAX_KEYWORDS = 100
        MAX_RESULTS_PER_SOURCE = 50

# Create Blueprint instead of Flask app
ome_blueprint = Blueprint('ome', __name__)

# Initialize Pharma News Agent (if available)
pharma_agent = None
if AGENT_AVAILABLE:
    try:
        if MULTI_AGENT_AVAILABLE:
            pharma_agent = MultiAgentPharmaAgent(Config())
            print("Multi-Agent Pharma Agent initialized successfully")
        else:
            pharma_agent = PharmaNewsAgent()
            print("Basic Pharma News Agent initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Pharma News Agent: {e}")
        AGENT_AVAILABLE = False

# In-memory storage for search results
search_results_store = {}

# In-memory storage for CSV uploads and multi-section processing
csv_uploads_store = {}
multi_section_results = {}

# File system storage for batch processing results
BATCH_RESULTS_DIR = Path("batch_results")
BATCH_RESULTS_DIR.mkdir(exist_ok=True)

def save_batch_result_html(user: str, alert_data: Dict[str, Any], results: List[Dict[str, Any]], timestamp: datetime) -> str:
    """Save HTML result for a single alert processing"""
    try:
        # Create user-specific directory
        user_dir = BATCH_RESULTS_DIR / user
        user_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{alert_data['header'].replace(' ', '_')[:30]}.html"
        filepath = user_dir / filename
        
        # Generate HTML content for this single alert
        html_content = generate_single_alert_html(alert_data, results, timestamp)
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Also save metadata
        metadata_file = user_dir / f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{alert_data['header'].replace(' ', '_')[:30]}_metadata.json"
        metadata = {
            'user': user,
            'alert_data': alert_data,
            'results_count': len(results),
            'timestamp': timestamp.isoformat(),
            'html_file': filename
        }
        
        # Generate hash for URL sharing
        metadata['hash'] = generate_result_hash(metadata)
        metadata['share_url'] = f"#{metadata['hash']}"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        return str(filepath)
        
    except Exception as e:
        print(f"Error saving batch result HTML: {e}")
        return None

def generate_single_alert_html(alert_data: Dict[str, Any], results: List[Dict[str, Any]], timestamp: datetime) -> str:
    """Generate HTML content for a single alert processing result"""
    
    # Create table of contents
    toc_items = []
    for i, result in enumerate(results, 1):
        title = result.get('title', f'Article {i}')
        relevance_score = result.get('relevance_score', 0)
        source = result.get('source', 'Unknown')
        date_str = 'No date'
        if result.get('date'):
            try:
                date_obj = datetime.fromisoformat(result['date'].replace('Z', '+00:00'))
                date_str = date_obj.strftime('%b %d, %Y')
            except:
                date_str = str(result.get('date', 'No date'))
        
        toc_items.append(f'''
            <tr style="border-bottom: 1px solid #e0e0e0;">
                <td style="padding: 12px 8px; font-size: 14px;">
                    <a href="#article-{i}" style="color: #3498db; text-decoration: none; font-weight: 500;">
                        {i}. {title[:80]}{'...' if len(title) > 80 else ''}
                    </a>
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 13px;">
                    <span style="background: {'#27ae60' if relevance_score >= 80 else '#f39c12' if relevance_score >= 60 else '#95a5a6'}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">
                        {relevance_score}/100
                    </span>
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 12px; color: #7f8c8d;">
                    {source}
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 12px; color: #7f8c8d;">
                    {date_str}
                </td>
            </tr>''')
    
    # Generate HTML
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alert Processing Result - {alert_data['header']}</title>
    <style>
        .toc-link {{ scroll-behavior: smooth; }}
        .article-section {{ scroll-margin-top: 20px; }}
        .keyword-highlight {{ 
            background: #fff3cd; 
            padding: 1px 3px; 
            border-radius: 2px; 
            font-weight: 600; 
            display: inline;
        }}
    </style>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
    
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">🔬 Alert Processing Result</h1>
        <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">{alert_data['header']}</p>
    </div>
    
    <!-- Alert Summary -->
    <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #667eea;">
        <h2 style="margin-top: 0; color: #2c3e50; font-size: 20px;">📊 Alert Details</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; font-weight: bold; color: #555;">Alert Title:</td>
                <td style="padding: 8px; color: #333;">{alert_data['header']}</td>
            </tr>
            <tr style="background: #f8f9fa;">
                <td style="padding: 8px; font-weight: bold; color: #555;">Subheader:</td>
                <td style="padding: 8px; color: #333;">{alert_data['subheader']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold; color: #555;">Keywords:</td>
                <td style="padding: 8px; color: #333;">{', '.join(alert_data.get('keywords', []))}</td>
            </tr>
            <tr style="background: #f8f9fa;">
                <td style="padding: 8px; font-weight: bold; color: #555;">Results Found:</td>
                <td style="padding: 8px; color: #333;"><strong>{len(results)} articles</strong></td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold; color: #555;">Processed:</td>
                <td style="padding: 8px; color: #333;">{timestamp.strftime('%B %d, %Y at %I:%M %p')}</td>
            </tr>
        </table>
    </div>
    
    <!-- Table of Contents -->
    <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #e74c3c;">
        <h2 style="margin-top: 0; color: #2c3e50; font-size: 20px;">📋 Table of Contents</h2>
        <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 15px;">Click on any title to jump directly to that article</p>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #e0e0e0;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0;">Article Title</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 80px;">Score</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 100px;">Source</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 100px;">Date</th>
                </tr>
            </thead>
            <tbody>{"".join(toc_items)}
            </tbody>
        </table>
    </div>
    
    <!-- Results -->
    <div style="margin-bottom: 30px;">
        <h2 style="color: #2c3e50; font-size: 20px; margin-bottom: 20px;">📄 Detailed Results (sorted by relevance)</h2>'''
    
    # Add each result
    for i, result in enumerate(results, 1):
        relevance_score = result.get('relevance_score', 0)
        
        # Score color
        if relevance_score >= 80:
            score_color = '#27ae60'  # Green
        elif relevance_score >= 60:
            score_color = '#f39c12'  # Orange
        else:
            score_color = '#95a5a6'  # Gray
        
        # Format date
        date_str = 'No date'
        if result.get('date'):
            try:
                date_obj = datetime.fromisoformat(result['date'].replace('Z', '+00:00'))
                date_str = date_obj.strftime('%B %d, %Y')
            except:
                date_str = str(result.get('date', 'No date'))
        
        html_content += f'''
        <!-- Result {i} -->
        <div id="article-{i}" class="article-section" style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid {score_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            
            <!-- Title and Score -->
            <div style="margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #2c3e50;">
                    <a href="{result.get('url', '#')}" style="color: #3498db; text-decoration: none;">{i}. {result.get('title', 'No title')}</a>
                </h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <span style="background: {score_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                        Relevance: {relevance_score}/100
                    </span>
                    <span style="background: #e74c3c; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px;">
                        {result.get('article_type', 'unknown').title()}
                    </span>
                    <span style="color: #7f8c8d; font-size: 13px;">
                        📅 {date_str}
                    </span>
                    <span style="color: #7f8c8d; font-size: 13px;">
                        📰 {result.get('source', 'Unknown')}
                    </span>
                </div>
            </div>
            
            <!-- Summary -->
            <div style="margin-bottom: 15px; padding: 15px; background: #f8f9fa; border-radius: 6px; font-size: 14px; line-height: 1.6;">
                {result.get('highlighted_content', result.get('summary', result.get('content', 'No summary available')[:300] + '...'))}
            </div>
            
            <!-- Why Relevant -->
            {f"""<div style="margin-bottom: 12px; padding: 12px; background: #d4edda; border-left: 3px solid #28a745; border-radius: 4px; font-size: 13px;">
                <strong style="color: #155724;">Why it's relevant:</strong><br/>
                {result.get('relevance_reason', 'No reason provided')}
            </div>""" if result.get('relevance_reason') else ''}
            
            <!-- Keywords -->
            {f"""<div style="margin-bottom: 12px;">
                <strong style="font-size: 13px; color: #555;">Keywords found:</strong><br/>
                <div style="margin-top: 6px;">
                    {''.join([f'<span style="background: #3498db; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-right: 6px; margin-bottom: 6px; display: inline-block;">{kw}</span>' for kw in result.get('mentioned_keywords', [])])}
                </div>
            </div>""" if result.get('mentioned_keywords') else ''}
            
            <!-- Pertinent Keywords -->
            {f"""<div style="margin-bottom: 12px;">
                <strong style="font-size: 13px; color: #555;">Related terms:</strong><br/>
                <div style="margin-top: 6px;">
                    {''.join([f'<span style="background: #e67e22; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-right: 6px; margin-bottom: 6px; display: inline-block;">{kw}</span>' for kw in result.get('pertinent_keywords', [])])}
                </div>
            </div>""" if result.get('pertinent_keywords') else ''}
            
            <!-- Clinical Significance -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #fff3cd; border-left: 3px solid #ffc107; border-radius: 4px; font-size: 13px;">
                <strong style="color: #856404;">Clinical Significance:</strong><br/>
                {result.get('clinical_significance')}
            </div>""" if result.get('clinical_significance') and result.get('clinical_significance') != 'None' else ''}
            
            <!-- Regulatory Impact -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #d1ecf1; border-left: 3px solid #17a2b8; border-radius: 4px; font-size: 13px;">
                <strong style="color: #0c5460;">Regulatory Impact:</strong><br/>
                {result.get('regulatory_impact')}
            </div>""" if result.get('regulatory_impact') and result.get('regulatory_impact') != 'None' else ''}
            
            <!-- Market Impact -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #d4edda; border-left: 3px solid #28a745; border-radius: 4px; font-size: 13px;">
                <strong style="color: #155724;">Market Impact:</strong><br/>
                {result.get('market_impact')}
            </div>""" if result.get('market_impact') and result.get('market_impact') != 'None' else ''}
            
            <!-- Link -->
            <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;">
                <a href="{result.get('url', '#')}" style="color: #3498db; text-decoration: none; font-size: 13px;">
                    🔗 View Full Article →
                </a>
            </div>
            
        </div>'''
    
    # Footer
    html_content += '''
    </div>
    
    <!-- Footer -->
    <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px; border-top: 2px solid #e0e0e0; margin-top: 30px;">
        <p style="margin: 5px 0;">Generated by <strong>Pharma News Research Agent</strong></p>
        <p style="margin: 5px 0;">AI-powered pharmaceutical news analysis with multi-source data collection</p>
        <p style="margin: 5px 0;">Powered by GPT-4, PubMed, Exa, Tavily, and NewsAPI</p>
    </div>
    
</body>
</html>'''
    
    return html_content

def get_global_history() -> List[Dict[str, Any]]:
    """Get all recent alerts processed (both batch and single search)"""
    try:
        history = []
        
        # Get batch processing history from file system
        if BATCH_RESULTS_DIR.exists():
            for user_dir in BATCH_RESULTS_DIR.iterdir():
                if user_dir.is_dir():
                    for metadata_file in user_dir.glob("*_metadata.json"):
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                                # Add type and hash for URL sharing
                                metadata['type'] = 'batch'
                                metadata['hash'] = generate_result_hash(metadata)
                                metadata['share_url'] = f"#{metadata['hash']}"
                                history.append(metadata)
                        except Exception as e:
                            print(f"Error reading metadata file {metadata_file}: {e}")
        
        # Get single search history from search_results_store
        for session_id, data in search_results_store.items():
            if session_id.startswith('search_') and 'metadata' in data:
                metadata = data['metadata'].copy()
                metadata['type'] = 'single'
                metadata['session_id'] = session_id
                metadata['results_count'] = len(data.get('results', []))
                metadata['hash'] = generate_result_hash(metadata)
                metadata['share_url'] = f"#{metadata['hash']}"
                history.append(metadata)
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Limit to last 50 entries
        return history[:50]
        
    except Exception as e:
        print(f"Error getting global history: {e}")
        return []

def generate_result_hash(metadata: Dict[str, Any]) -> str:
    """Generate a unique hash for result sharing"""
    import hashlib
    
    # Create a unique identifier from metadata
    hash_string = f"{metadata.get('timestamp', '')}_{metadata.get('type', '')}_{metadata.get('user', '')}_{metadata.get('session_id', '')}"
    return hashlib.md5(hash_string.encode()).hexdigest()[:12]

def get_result_by_hash(hash_id: str) -> Optional[Dict[str, Any]]:
    """Get result by hash ID for URL sharing"""
    try:
        # Check batch results
        if BATCH_RESULTS_DIR.exists():
            for user_dir in BATCH_RESULTS_DIR.iterdir():
                if user_dir.is_dir():
                    for metadata_file in user_dir.glob("*_metadata.json"):
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                                metadata['type'] = 'batch'
                                metadata['hash'] = generate_result_hash(metadata)
                                if metadata['hash'] == hash_id:
                                    return metadata
                        except Exception as e:
                            continue
        
        # Check single search results
        for session_id, data in search_results_store.items():
            if session_id.startswith('search_') and 'metadata' in data:
                metadata = data['metadata'].copy()
                metadata['type'] = 'single'
                metadata['session_id'] = session_id
                metadata['hash'] = generate_result_hash(metadata)
                if metadata['hash'] == hash_id:
                    return metadata
        
        return None
        
    except Exception as e:
        print(f"Error getting result by hash: {e}")
        return None

def get_user_batch_history(user: str) -> List[Dict[str, Any]]:
    """Get batch processing history for a user (legacy function)"""
    try:
        user_dir = BATCH_RESULTS_DIR / user
        if not user_dir.exists():
            return []
        
        history = []
        for metadata_file in user_dir.glob("*_metadata.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    history.append(metadata)
            except Exception as e:
                print(f"Error reading metadata file {metadata_file}: {e}")
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return history
        
    except Exception as e:
        print(f"Error getting user batch history: {e}")
        return []

def search_pubmed(keywords: List[str], max_results: int = 20, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
    """Search PubMed using Entrez API with date filtering"""
    try:
        # Create query with pharma-specific terms
        query_parts = []
        for keyword in keywords:
            # Search in title, abstract, and MeSH terms for better pharma coverage
            query_parts.append(f'("{keyword}"[Title/Abstract] OR "{keyword}"[MeSH Terms])')
        
        query = " OR ".join(query_parts)
        
        # Add date range if provided
        if start_date and end_date:
            date_query = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
            query = f"({query}) AND {date_query}"
        
        # Search PubMed
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json',
            'sort': 'relevance'
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        pmids = data.get('esearchresult', {}).get('idlist', [])
        
        if not pmids:
            return []
        
        # Fetch details
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'retmode': 'xml'
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse XML (simplified)
        results = []
        xml_content = response.text
        
        # Extract titles
        titles = re.findall(r'<ArticleTitle>(.*?)</ArticleTitle>', xml_content)
        abstracts = re.findall(r'<AbstractText.*?>(.*?)</AbstractText>', xml_content)
        pmids_found = re.findall(r'<PMID.*?>(.*?)</PMID>', xml_content)
        
        for i, pmid in enumerate(pmids_found[:max_results]):
            title = titles[i] if i < len(titles) else "No title"
            abstract = abstracts[i] if i < len(abstracts) else "No abstract"
            
            result = {
                'title': title,
                'content': abstract,
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
                'date': datetime.now().isoformat(),
                'source': 'PubMed'
            }
            results.append(result)
        
        return results
        
    except Exception as e:
        print(f"PubMed search error: {str(e)}")
        return []

def search_newsapi(keywords: List[str], max_results: int = 20) -> List[Dict[str, Any]]:
    """Search NewsAPI for news articles - requires API key configuration"""
    print("NewsAPI search requires API key configuration")
    return []

def search_all_sources(keywords: List[str], max_results: int = 50, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
    """Search across all available sources with date filtering"""
    all_results = []
    
    # Search each source
    sources = [
        lambda: search_pubmed(keywords, max_results // 2, start_date, end_date),
        lambda: search_newsapi(keywords, max_results // 2)
    ]
    
    for search_func in sources:
        try:
            results = search_func()
            all_results.extend(results)
            print(f"Found {len(results)} results from {search_func.__name__}")
        except Exception as e:
            print(f"Error in {search_func.__name__}: {str(e)}")
            continue
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_results = []
    for result in all_results:
        if result['url'] not in seen_urls:
            seen_urls.add(result['url'])
            unique_results.append(result)
    
    print(f"Total unique results: {len(unique_results)}")
    return unique_results

def filter_results(results: List[Dict[str, Any]], keywords: List[str], search_type: str) -> List[Dict[str, Any]]:
    """Filter results based on search type"""
    filtered_results = []
    keywords_lower = [kw.lower() for kw in keywords]
    
    for result in results:
        title = result.get('title', '').lower()
        content = result.get('content', '').lower()
        
        if search_type == 'standard':
            # Any keyword in title or content
            if any(kw in title or kw in content for kw in keywords_lower):
                filtered_results.append(result)
        
        elif search_type == 'title':
            # Any keyword in title
            if any(kw in title for kw in keywords_lower):
                filtered_results.append(result)
        
        elif search_type == 'co-occurrence':
            # 2 or more keywords in content
            keyword_count = sum(1 for kw in keywords_lower if kw in content)
            if keyword_count >= 2:
                filtered_results.append(result)
    
    return filtered_results

def calculate_relevance_score(result: Dict[str, Any], keywords: List[str]) -> int:
    """Calculate enhanced relevance score for pharma content"""
    text = (result['title'] + " " + result['content']).lower()
    keywords_lower = [kw.lower() for kw in keywords]
    
    # Count keyword occurrences
    keyword_count = sum(1 for keyword in keywords_lower if keyword in text)
    
    # Bonus points for pharma-specific terms
    pharma_terms = ['clinical trial', 'fda', 'approval', 'drug', 'pharmaceutical', 'therapeutic', 'dosage', 'efficacy', 'safety', 'regulatory']
    pharma_bonus = sum(1 for term in pharma_terms if term in text)
    
    # Base score calculation
    if keyword_count == 0:
        base_score = 10
    elif keyword_count == 1:
        base_score = 40
    elif keyword_count == 2:
        base_score = 60
    elif keyword_count >= 3:
        base_score = 80
    else:
        base_score = 30
    
    # Add pharma bonus (max 20 points)
    pharma_bonus_score = min(20, pharma_bonus * 3)
    
    # Title bonus (keywords in title are more important)
    title_text = result.get('title', '').lower()
    title_keyword_count = sum(1 for kw in keywords_lower if kw in title_text)
    title_bonus = min(15, title_keyword_count * 5)
    
    final_score = min(100, base_score + pharma_bonus_score + title_bonus)
    
    return final_score

def highlight_keywords(text: str, keywords: List[str]) -> str:
    """Highlight keywords in text"""
    highlighted_text = text
    
    for keyword in keywords:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        highlighted_text = pattern.sub(
            f'<mark style="background-color: yellow; font-weight: bold;">{keyword}</mark>',
            highlighted_text
        )
    
    return highlighted_text

def process_csv_upload(csv_content: str) -> Dict[str, Any]:
    """Process uploaded CSV file and extract sections for multi-section processing"""
    try:
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        sections = []
        users = set()
        user_email_alerts = {}  # Track which users have email alerts enabled
        
        for row in csv_reader:
            # Extract required columns
            aliases = row.get('aliases', '').strip()
            keywords = row.get('keyword', '').strip()  # Note: using 'keyword' as shown in demo
            search_type = row.get('search_type', 'standard').strip()
            subheader = row.get('subheader', '').strip()
            header = row.get('alert_title', '').strip()  # Using alert_title as header
            user = row.get('user', '').strip()
            email_alert = row.get('email_alert', '').strip().lower()
            
            # Track users and their email alert preferences
            if user:
                users.add(user)
                if user not in user_email_alerts:
                    user_email_alerts[user] = []
                
                # Only add rows with email_alert = 'yes'
                if email_alert == 'yes':
                    user_email_alerts[user].append({
                        'aliases': aliases,
                        'keywords': keywords,
                        'search_type': search_type,
                        'subheader': subheader,
                        'header': header,
                        'user': user,
                        'email_alert': email_alert,
                        'email_subject': row.get('email_subject', '').strip(),
                        'source_select': row.get('source_select', 'all').strip(),
                        'filter_type': row.get('filter_type', '').strip(),
                        'include_links': row.get('include_links', '').strip()
                    })
        
        # Process each user's email alert rows
        for user, alert_rows in user_email_alerts.items():
            for alert_row in alert_rows:
                # Combine aliases and keywords, make unique
                all_keywords = []
                if alert_row['aliases']:
                    all_keywords.extend([alias.strip() for alias in alert_row['aliases'].split(',') if alias.strip()])
                if alert_row['keywords']:
                    all_keywords.extend([kw.strip() for kw in alert_row['keywords'].split(',') if kw.strip()])
                
                # Remove duplicates and empty strings
                unique_keywords = list(dict.fromkeys([kw for kw in all_keywords if kw]))
                
                if unique_keywords:  # Only add if we have keywords
                    section = {
                        'aliases': alert_row['aliases'],
                        'keywords': alert_row['keywords'],
                        'combined_keywords': unique_keywords,
                        'search_type': alert_row['search_type'],
                        'subheader': alert_row['subheader'],
                        'header': alert_row['header'],
                        'user': alert_row['user'],
                        'email_alert': alert_row['email_alert'],
                        'email_subject': alert_row['email_subject'],
                        'source_select': alert_row['source_select'],
                        'filter_type': alert_row['filter_type'],
                        'include_links': alert_row['include_links'],
                        'section_id': f"{alert_row['user']}_{alert_row['header']}_{alert_row['subheader']}".replace(' ', '_').replace('/', '_')
                    }
                    sections.append(section)
        
        return {
            'success': True,
            'sections': sections,
            'users': list(users),
            'user_email_alerts': user_email_alerts,
            'total_sections': len(sections),
            'users_with_alerts': len([u for u, alerts in user_email_alerts.items() if alerts])
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'CSV processing failed: {str(e)}',
            'sections': [],
            'users': [],
            'user_email_alerts': {},
            'total_sections': 0,
            'users_with_alerts': 0
        }

def process_user_alerts(user_email_alerts: Dict[str, List[Dict[str, Any]]], selected_user: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Process alerts for a specific user with email_alert = 'yes' and relevance score > 65"""
    try:
        if selected_user not in user_email_alerts:
            return {
                'success': False,
                'error': f'User {selected_user} not found in uploaded data',
                'results': []
            }
        
        user_alert_rows = user_email_alerts[selected_user]
        if not user_alert_rows:
            return {
                'success': False,
                'error': f'No email alerts found for user {selected_user}',
                'results': []
            }
        
        print(f"Processing {len(user_alert_rows)} alerts for user: {selected_user}")
        
        all_results = []
        processed_alerts = []
        
        for alert_row in user_alert_rows:
            # Combine aliases and keywords, make unique
            all_keywords = []
            if alert_row['aliases']:
                all_keywords.extend([alias.strip() for alias in alert_row['aliases'].split(',') if alias.strip()])
            if alert_row['keywords']:
                all_keywords.extend([kw.strip() for kw in alert_row['keywords'].split(',') if kw.strip()])
            
            # Remove duplicates and empty strings
            unique_keywords = list(dict.fromkeys([kw for kw in all_keywords if kw]))
            
            if not unique_keywords:
                continue
                
            print(f"Processing alert: {alert_row['header']} - {alert_row['subheader']}")
            print(f"Keywords: {unique_keywords}")
            
            # Use agentic workflow if available
            if AGENT_AVAILABLE and pharma_agent:
                import asyncio
                workflow_result = asyncio.run(pharma_agent.execute_workflow(
                    keywords=unique_keywords,
                    start_date=start_date,
                    end_date=end_date,
                    search_type=alert_row['search_type'],
                    alert_title=alert_row['header'],
                    alert_header=alert_row['subheader']
                ))
                
                if workflow_result['success']:
                    # Use all LLM-scored results (no hardcoded filtering)
                    filtered_results = []
                    for result in workflow_result['results']:
                        # Add alert context to result
                        result['alert_context'] = {
                            'user': alert_row['user'],
                            'alert_title': alert_row['header'],
                            'subheader': alert_row['subheader'],
                            'email_subject': alert_row['email_subject'],
                            'search_type': alert_row['search_type'],
                            'source_select': alert_row['source_select'],
                            'filter_type': alert_row['filter_type'],
                            'include_links': alert_row['include_links']
                        }
                        filtered_results.append(result)
                    
                    if filtered_results:
                        all_results.extend(filtered_results)
                        processed_alerts.append({
                            'alert_title': alert_row['header'],
                            'subheader': alert_row['subheader'],
                            'keywords': unique_keywords,
                            'results_count': len(filtered_results),
                            'email_subject': alert_row['email_subject']
                        })
                        
                        # Save HTML result for this alert
                        alert_data = {
                            'header': alert_row['header'],
                            'subheader': alert_row['subheader'],
                            'keywords': unique_keywords,
                            'user': selected_user
                        }
                        timestamp = datetime.now()
                        html_file = save_batch_result_html(selected_user, alert_data, filtered_results, timestamp)
                        if html_file:
                            print(f"Saved HTML result for alert '{alert_row['header']}': {html_file}")
                else:
                    print(f"Workflow failed for alert: {alert_row['header']}")
            else:
                # Fallback to basic search
                raw_results = search_all_sources(unique_keywords, Config.MAX_RESULTS_PER_SOURCE, start_date, end_date)
                filtered_results = filter_results(raw_results, unique_keywords, alert_row['search_type'])
                
                # Calculate relevance scores and filter by > 65
                high_relevance_results = []
                for result in filtered_results:
                    relevance_score = calculate_relevance_score(result, unique_keywords)
                    if relevance_score > 65:
                        result['relevance_score'] = relevance_score
                        result['alert_context'] = {
                            'user': alert_row['user'],
                            'alert_title': alert_row['header'],
                            'subheader': alert_row['subheader'],
                            'email_subject': alert_row['email_subject'],
                            'search_type': alert_row['search_type'],
                            'source_select': alert_row['source_select'],
                            'filter_type': alert_row['filter_type'],
                            'include_links': alert_row['include_links']
                        }
                        high_relevance_results.append(result)
                
                if high_relevance_results:
                    all_results.extend(high_relevance_results)
                    processed_alerts.append({
                        'alert_title': alert_row['header'],
                        'subheader': alert_row['subheader'],
                        'keywords': unique_keywords,
                        'results_count': len(high_relevance_results),
                        'email_subject': alert_row['email_subject']
                    })
                    
                    # Save HTML result for this alert
                    alert_data = {
                        'header': alert_row['header'],
                        'subheader': alert_row['subheader'],
                        'keywords': unique_keywords,
                        'user': selected_user
                    }
                    timestamp = datetime.now()
                    html_file = save_batch_result_html(selected_user, alert_data, high_relevance_results, timestamp)
                    if html_file:
                        print(f"Saved HTML result for alert '{alert_row['header']}': {html_file}")
        
        # Sort all results by relevance score
        all_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return {
            'success': True,
            'user': selected_user,
            'results': all_results,
            'processed_alerts': processed_alerts,
            'total_alerts': len(user_alert_rows),
            'successful_alerts': len(processed_alerts),
            'total_results': len(all_results)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Alert processing failed: {str(e)}',
            'results': []
        }

def process_multi_section_search(sections: List[Dict[str, Any]], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Process multiple sections with the same data and generate results for each"""
    try:
        section_results = {}
        
        for section in sections:
            section_id = section['section_id']
            keywords = section['combined_keywords']
            search_type = section['search_type']
            
            print(f"Processing section: {section['header']} - {section['subheader']} for user: {section['user']}")
            print(f"Keywords: {keywords}")
            
            # Use agentic workflow if available
            if AGENT_AVAILABLE and pharma_agent:
                import asyncio
                workflow_result = asyncio.run(pharma_agent.execute_workflow(
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    search_type=search_type,
                    alert_title=section['header'],
                    alert_header=section['subheader']
                ))
                
                if workflow_result['success']:
                    # Add section context to results
                    processed_results = workflow_result['results']
                    for result in processed_results:
                        result['section_context'] = {
                            'header': section['header'],
                            'subheader': section['subheader'],
                            'user': section['user'],
                            'aliases': section['aliases'],
                            'original_keywords': section['keywords']
                        }
                    
                    section_results[section_id] = {
                        'success': True,
                        'section_info': {
                            'header': section['header'],
                            'subheader': section['subheader'],
                            'user': section['user'],
                            'aliases': section['aliases'],
                            'keywords': section['keywords'],
                            'combined_keywords': keywords,
                            'search_type': search_type
                        },
                        'results': processed_results,
                        'results_by_source': workflow_result.get('results_by_source', {}),
                        'total_found': workflow_result.get('total_found', 0),
                        'total_filtered': workflow_result.get('total_filtered', 0),
                        'total_processed': workflow_result.get('total_processed', 0)
                    }
                else:
                    section_results[section_id] = {
                        'success': False,
                        'error': workflow_result.get('error', 'Unknown error'),
                        'section_info': section
                    }
            else:
                # Fallback to basic search
                raw_results = search_all_sources(keywords, Config.MAX_RESULTS_PER_SOURCE, start_date, end_date)
                filtered_results = filter_results(raw_results, keywords, search_type)
                
                processed_results = []
                for i, result in enumerate(filtered_results):
                    relevance_score = calculate_relevance_score(result, keywords)
                    summary = result['content'][:200] + "..." if len(result['content']) > 200 else result['content']
                    highlighted_summary = highlight_keywords(summary, keywords)
                    
                    processed_result = result.copy()
                    processed_result.update({
                        'rank': i + 1,
                        'relevance_score': relevance_score,
                        'summary': summary,
                        'highlighted_summary': highlighted_summary,
                        'section_context': {
                            'header': section['header'],
                            'subheader': section['subheader'],
                            'user': section['user'],
                            'aliases': section['aliases'],
                            'original_keywords': section['keywords']
                        }
                    })
                    processed_results.append(processed_result)
                
                processed_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
                
                section_results[section_id] = {
                    'success': True,
                    'section_info': section,
                    'results': processed_results,
                    'total_found': len(raw_results),
                    'total_filtered': len(filtered_results),
                    'total_processed': len(processed_results)
                }
        
        return {
            'success': True,
            'section_results': section_results,
            'total_sections': len(sections),
            'successful_sections': len([r for r in section_results.values() if r['success']])
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Multi-section processing failed: {str(e)}',
            'section_results': {},
            'total_sections': 0,
            'successful_sections': 0
        }

# HTML Template (same as before, embedded in blueprint)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pharma News Research Agent</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            line-height: 1.6;
            height: 100vh;
            overflow: hidden;
        }

        /* Header */
        .header {
            background: #2c3e50;
            color: white;
            padding: 15px 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 22px;
            margin: 0;
        }

        .header p {
            font-size: 13px;
            margin: 5px 0 0 0;
            opacity: 0.9;
        }

        /* Main Layout */
        .main-layout {
            display: grid;
            grid-template-columns: 220px 1fr 280px;
            height: calc(100vh - 80px);
            gap: 0;
        }

        /* Left Sidebar */
        .left-sidebar {
            background: #34495e;
            color: white;
            padding: 20px;
            overflow-y: auto;
        }

        .sidebar-section {
            margin-bottom: 25px;
        }

        .sidebar-section h3 {
            font-size: 14px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-item {
            padding: 8px 0;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
        }

        .stat-value {
            font-weight: bold;
            color: #3498db;
        }

        .checkbox-group {
            margin: 10px 0;
        }

        .checkbox-group label {
            display: block;
            margin: 8px 0;
            font-size: 13px;
            cursor: pointer;
        }

        .checkbox-group input[type="checkbox"] {
            margin-right: 8px;
        }

        /* Main Content Area */
        .main-content {
            background: white;
            overflow-y: auto;
            padding: 20px;
        }

        /* Tabs */
        .tabs {
            display: flex;
            border-bottom: 2px solid #e0e0e0;
            margin-bottom: 20px;
        }

        .tab {
            padding: 12px 24px;
            cursor: pointer;
            border: none;
            background: none;
            font-size: 14px;
            font-weight: 600;
            color: #7f8c8d;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
        }

        .tab:hover {
            color: #2c3e50;
            background: #f8f9fa;
        }

        .tab.active {
            color: #2c3e50;
            border-bottom-color: #3498db;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* Form Styles */
        .form-group {
            margin-bottom: 18px;
        }

        .form-group label {
            display: block;
            margin-bottom: 6px;
            font-weight: 600;
            font-size: 13px;
            color: #2c3e50;
        }

        .form-group input,
        .form-group textarea,
        .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            font-family: inherit;
        }

        .form-group textarea {
            resize: vertical;
            min-height: 80px;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        /* Buttons */
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }

        .btn-primary {
            background: #3498db;
            color: white;
        }

        .btn-primary:hover {
            background: #2980b9;
        }

        .btn-primary:disabled {
            background: #95a5a6;
            cursor: not-allowed;
        }

        .btn-success {
            background: #27ae60;
            color: white;
        }

        .btn-success:hover {
            background: #229954;
        }

        .btn-group {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }

        .btn-group .btn {
            flex: 1;
        }

        /* Right Sidebar - Activity Panel */
        .right-sidebar {
            background: #ecf0f1;
            padding: 20px;
            overflow-y: auto;
            border-left: 1px solid #bdc3c7;
        }

        .activity-header {
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #3498db;
            text-transform: uppercase;
            color: #2c3e50;
        }

        .activity-log {
            font-size: 12px;
        }

        .activity-item {
            padding: 10px;
            margin-bottom: 8px;
            background: white;
            border-radius: 4px;
            border-left: 3px solid #95a5a6;
        }

        .activity-item.info {
            border-left-color: #3498db;
        }

        .activity-item.success {
            border-left-color: #27ae60;
        }

        .activity-item.warning {
            border-left-color: #f39c12;
        }

        .activity-item.error {
            border-left-color: #e74c3c;
        }

        .activity-time {
            font-size: 10px;
            color: #7f8c8d;
            margin-bottom: 4px;
        }

        .activity-message {
            color: #2c3e50;
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
        }

        .status-idle {
            background: #95a5a6;
        }

        .status-processing {
            background: #3498db;
        }

        .status-success {
            background: #27ae60;
        }

        .status-error {
            background: #e74c3c;
        }

        /* Results */
        .results-container {
            margin-top: 20px;
        }

        .result-card {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 15px;
            background: white;
        }

        .result-card:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .enhanced-result {
            border-left: 4px solid #3498db;
        }

        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }

        .result-scores {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .badge-type {
            background: #e74c3c;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            text-transform: capitalize;
        }

        .result-relevance {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            font-size: 14px;
            border-left: 3px solid #28a745;
        }

        .result-keywords {
            margin: 10px 0;
        }

        .keyword-tag {
            background: #3498db;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            margin-right: 5px;
            margin-bottom: 5px;
            display: inline-block;
        }

        .keyword-tag.pertinent {
            background: #e67e22;
            color: white;
        }

        .result-pertinent-keywords {
            margin: 10px 0;
        }

        .result-significance,
        .result-regulatory,
        .result-market {
            background: #fff3cd;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 8px 0;
            font-size: 13px;
            border-left: 3px solid #ffc107;
        }

        .result-regulatory {
            background: #d1ecf1;
            border-left-color: #17a2b8;
        }

        .result-market {
            background: #d4edda;
            border-left-color: #28a745;
        }

        .keyword-highlight {
            background: #fff3cd;
            padding: 1px 3px;
            border-radius: 2px;
            font-weight: 600;
        }

        .result-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 8px;
            color: #2c3e50;
        }

        .result-title a {
            color: #3498db;
            text-decoration: none;
        }

        .result-title a:hover {
            text-decoration: underline;
        }

        .result-summary {
            font-size: 13px;
            color: #555;
            margin-bottom: 10px;
            line-height: 1.6;
        }

        .result-meta {
            font-size: 12px;
            color: #7f8c8d;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }

        .result-meta span {
            display: inline-block;
        }

        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
        }

        .badge-score {
            background: #3498db;
            color: white;
        }

        .badge-source {
            background: #95a5a6;
            color: white;
        }

        /* Loading State */
        .loading-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 9999;
            justify-content: center;
            align-items: center;
        }

        .loading-overlay.active {
            display: flex;
        }

        .loading-content {
            background: white;
            padding: 30px;
            border-radius: 8px;
            text-align: center;
            max-width: 500px;
        }

        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: #ecf0f1;
            border-radius: 3px;
            overflow: hidden;
            margin: 15px 0;
        }

        .progress-fill {
            height: 100%;
            background: #3498db;
            width: 0%;
            transition: width 0.3s;
        }

        /* Alert Messages */
        .alert {
            padding: 12px 15px;
            border-radius: 4px;
            margin-bottom: 15px;
            font-size: 13px;
        }

        .alert-success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }

        .alert-error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }

        .alert-info {
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
        }

        /* CSV Upload Area */
        .upload-area {
            border: 2px dashed #bdc3c7;
            border-radius: 4px;
            padding: 30px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
        }

        .upload-area:hover {
            border-color: #3498db;
            background: #f8f9fa;
        }

        .upload-area.dragover {
            border-color: #27ae60;
            background: #d5f4e6;
        }

        /* Scrollbar Styling */
        ::-webkit-scrollbar {
            width: 8px;
        }

        ::-webkit-scrollbar-track {
            background: #f1f1f1;
        }

        ::-webkit-scrollbar-thumb {
            background: #bdc3c7;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #95a5a6;
        }

        /* No Results */
        .no-results {
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
        }

        .no-results-icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <h1>🔬 Pharma News Research Agent</h1>
        <p>AI-powered pharmaceutical news research with multi-source data collection</p>
    </div>

    <!-- Main Layout -->
    <div class="main-layout">
        <!-- Left Sidebar -->
        <div class="left-sidebar">
            <div class="sidebar-section">
                <h3>Session Stats</h3>
                <div class="stat-item">
                    <span>Total Searches:</span>
                    <span class="stat-value" id="stat-searches">0</span>
                </div>
                <div class="stat-item">
                    <span>Results Found:</span>
                    <span class="stat-value" id="stat-results">0</span>
                </div>
                <div class="stat-item">
                    <span>Sources Used:</span>
                    <span class="stat-value" id="stat-sources">0</span>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Search Engines</h3>
                <div class="checkbox-group">
                    <label>
                        <input type="checkbox" id="engine-pubmed" checked>
                        PubMed (Medical)
                    </label>
                    <label>
                        <input type="checkbox" id="engine-exa" checked>
                        Exa (Neural Search)
                    </label>
                    <label>
                        <input type="checkbox" id="engine-tavily" checked>
                        Tavily (Web Search)
                    </label>
                    <label>
                        <input type="checkbox" id="engine-newsapi" checked>
                        NewsAPI (News)
                    </label>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>API Status</h3>
                <div class="stat-item">
                    <span>OpenAI:</span>
                    <span id="api-openai">...</span>
                </div>
                <div class="stat-item">
                    <span>Tavily:</span>
                    <span id="api-tavily">...</span>
                </div>
                <div class="stat-item">
                    <span>Exa:</span>
                    <span id="api-exa">...</span>
                </div>
                <div class="stat-item">
                    <span>NewsAPI:</span>
                    <span id="api-newsapi">...</span>
                </div>
            </div>

            <!-- Data Collection Stats -->
            <div class="sidebar-section" id="collection-stats" style="display:none;">
                <h3>📥 Data Collection</h3>
                <div class="stat-item">
                    <span>Total Collected:</span>
                    <span class="stat-value" id="stat-collected">0</span>
                </div>
                <div class="stat-item">
                    <span>Sources Used:</span>
                    <span class="stat-value" id="stat-sources-list">-</span>
                </div>
            </div>

            <!-- Deduplication Stats -->
            <div class="sidebar-section" id="dedup-stats" style="display:none;">
                <h3>🔄 Deduplication</h3>
                <div class="stat-item">
                    <span>Duplicates Removed:</span>
                    <span class="stat-value" id="stat-duplicates">0</span>
                </div>
                <div class="stat-item">
                    <span>Unique Articles:</span>
                    <span class="stat-value" id="stat-unique">0</span>
                </div>
                <div class="stat-item">
                    <span>Duplicate Groups:</span>
                    <span class="stat-value" id="stat-dup-groups">0</span>
                </div>
            </div>

            <!-- Date Extraction Stats -->
            <div class="sidebar-section" id="date-stats" style="display:none;">
                <h3>📅 Date Extraction</h3>
                <div class="stat-item">
                    <span>With Dates:</span>
                    <span class="stat-value" id="stat-with-dates">0</span>
                </div>
                <div class="stat-item">
                    <span>Without Dates:</span>
                    <span class="stat-value" id="stat-without-dates">0</span>
                </div>
                <div class="stat-item">
                    <span>LLM Extracted:</span>
                    <span class="stat-value" id="stat-extracted-dates">0</span>
                </div>
            </div>

            <!-- Date Filtering Stats -->
            <div class="sidebar-section" id="filter-stats" style="display:none;">
                <h3>🗓️ Date Filtering</h3>
                <div class="stat-item">
                    <span>In Range:</span>
                    <span class="stat-value" id="stat-in-range">0</span>
                </div>
                <div class="stat-item">
                    <span>Out of Range:</span>
                    <span class="stat-value" id="stat-out-range">0</span>
                </div>
                <div class="stat-item">
                    <span>LLM Rescued:</span>
                    <span class="stat-value" id="stat-llm-rescued">0</span>
                </div>
            </div>

            <!-- Relevance Analysis Stats -->
            <div class="sidebar-section" id="relevance-stats" style="display:none;">
                <h3>🎯 Relevance Analysis</h3>
                <div class="stat-item">
                    <span>Analyzed:</span>
                    <span class="stat-value" id="stat-analyzed">0</span>
                </div>
                <div class="stat-item">
                    <span>Kept (≥ score):</span>
                    <span class="stat-value" id="stat-kept">0</span>
                </div>
                <div class="stat-item">
                    <span>Filtered:</span>
                    <span class="stat-value" id="stat-filtered">0</span>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <!-- Tabs -->
            <div class="tabs">
                <button class="tab active" data-tab="single">Single Search</button>
                <button class="tab" data-tab="batch">Batch Processing</button>
                <button class="tab" data-tab="results">Results History</button>
            </div>

            <!-- Single Search Tab -->
            <div class="tab-content active" id="tab-single">
                <div class="btn-group">
                    <button class="btn btn-success" onclick="quickFill('prostate')">
                        🏥 Prostate Cancer
                    </button>
                    <button class="btn btn-success" onclick="quickFill('ai')">
                        🤖 AI in Pharma
                    </button>
                </div>

                <form id="search-form" onsubmit="performSearch(event)">
                    <div class="form-group">
                        <label>Keywords (comma-separated)</label>
                        <textarea id="keywords" placeholder="e.g., prostate cancer, orgovyx, immunotherapy" required></textarea>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label>Start Date</label>
                            <input type="date" id="start-date" required>
                        </div>
                        <div class="form-group">
                            <label>End Date</label>
                            <input type="date" id="end-date" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>Search Type</label>
                        <select id="search-type">
                            <option value="standard">Standard (any keyword)</option>
                            <option value="title">Title Only</option>
                            <option value="co-occurrence">Co-occurrence (2+ keywords)</option>
                        </select>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label>Alert Name (optional)</label>
                            <input type="text" id="alert-name" placeholder="My Research Alert">
                        </div>
                        <div class="form-group">
                            <label>Section Name (optional)</label>
                            <input type="text" id="section-name" placeholder="Clinical Trials">
                        </div>
                    </div>

                    <button type="submit" class="btn btn-primary" id="search-btn">
                        🔍 Start Research
                    </button>
                </form>

                <div id="results-area" class="results-container"></div>
            </div>

            <!-- Batch Processing Tab -->
            <div class="tab-content" id="tab-batch">
                <div class="alert alert-info">
                    Upload a CSV file with columns: keyword, aliases, search_type, subheader, alert_title, user, email_alert, email_subject, source_select, filter_type, include_links
                </div>

                <div class="upload-area" id="upload-area">
                    <div style="font-size: 48px; margin-bottom: 10px;">📄</div>
                    <p><strong>Click to upload</strong> or drag and drop</p>
                    <p style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">CSV files only</p>
                    <input type="file" id="csv-file" accept=".csv" style="display: none;">
                </div>

                <!-- User Selection Section (hidden initially) -->
                <div id="user-selection-section" style="display: none; margin-top: 20px;">
                    <div class="form-group">
                        <label>Select User to Process Alerts</label>
                        <select id="user-select" class="form-group select">
                            <option value="">Choose a user...</option>
                        </select>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label>Start Date</label>
                            <input type="date" id="batch-start-date">
                        </div>
                        <div class="form-group">
                            <label>End Date</label>
                            <input type="date" id="batch-end-date">
                        </div>
                    </div>
                    
                    <button class="btn btn-primary" id="process-alerts-btn" disabled>
                        🔍 Process User Alerts
                    </button>
                </div>

                <div id="batch-results" style="margin-top: 20px;"></div>
            </div>

            <!-- Results History Tab -->
            <div class="tab-content" id="tab-results">
                <div class="alert alert-info">
                    <h3>📚 Recent Alerts History</h3>
                    <p>View and access all recent alerts processed (both batch and single search)</p>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <button onclick="loadGlobalHistory()" class="btn btn-primary" style="margin-right: 10px;">
                        🔄 Refresh History
                    </button>
                    <span id="history-loading" style="display: none; color: #7f8c8d;">Loading...</span>
                </div>
                
                <div id="global-history-container"></div>
            </div>
        </div>

        <!-- Right Sidebar - Filters & Activity Panel -->
        <div class="right-sidebar">
            <!-- Relevance Score Filter -->
            <div class="sidebar-section" id="relevance-filter-section" style="display:none;">
                <h3>🎚️ Relevance Filter</h3>
                <div style="margin-bottom: 10px;">
                    <label style="font-size: 12px; color: #7f8c8d;">Min Score: <span id="slider-value">65</span></label>
                    <input type="range" id="relevance-slider" min="0" max="100" value="65" 
                           style="width: 100%; margin-top: 5px;">
                </div>
                <div class="stat-item">
                    <span>Shown:</span>
                    <span class="stat-value" id="stat-shown-count">0</span>
                </div>
                <div class="stat-item">
                    <span>Hidden:</span>
                    <span class="stat-value" id="stat-hidden-count">0</span>
                </div>
            </div>

            <!-- Source Breakdown -->
            <div class="sidebar-section" id="source-breakdown" style="display:none;">
                <h3>📊 Source Breakdown</h3>
                <div id="source-stats-container">
                    <!-- Will be populated dynamically -->
                </div>
            </div>

            <div class="activity-header">
                <span class="status-indicator status-idle" id="status-indicator"></span>
                Live Activity
            </div>
            <div class="activity-log" id="activity-log">
                <div class="activity-item info">
                    <div class="activity-time" id="current-time"></div>
                    <div class="activity-message">System ready. Waiting for search...</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Loading Overlay -->
    <div class="loading-overlay" id="loading-overlay">
        <div class="loading-content">
            <div class="spinner"></div>
            <h3 id="loading-title">Processing Search...</h3>
            <p id="loading-message">Collecting data from multiple sources</p>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill"></div>
            </div>
            <p style="font-size: 12px; color: #7f8c8d; margin-top: 10px;" id="progress-text">0% complete</p>
        </div>
    </div>

    <script>
        // Get the base URL for this blueprint
        const BASE_URL = window.location.pathname.replace(/\/$/, '');
        
        // Initialize
        let searchCount = 0;
        let totalResults = 0;
        let sourcesUsed = new Set();

        // Update current time
        function updateTime() {
            const now = new Date();
            document.getElementById('current-time').textContent = now.toLocaleTimeString();
        }
        setInterval(updateTime, 1000);
        updateTime();

        // Set default dates (last 7 days)
        const today = new Date();
        const sevenDaysAgo = new Date(today);
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
        document.getElementById('end-date').valueAsDate = today;
        document.getElementById('start-date').valueAsDate = sevenDaysAgo;

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                // Remove active from all tabs
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                
                // Add active to clicked tab
                tab.classList.add('active');
                document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
                
                // Load history when results tab is clicked
                if (tab.dataset.tab === 'results') {
                    loadHistoryUsers();
                }
            });
        });

        // Global History functionality
        async function loadGlobalHistory() {
            try {
                document.getElementById('history-loading').style.display = 'inline';
                addActivity('Loading global history...', 'info');
                
                const response = await fetch(`${BASE_URL}/global_history`);
                const data = await response.json();
                
                if (data.success) {
                    displayGlobalHistory(data.history);
                    addActivity(`Loaded ${data.total_entries} history entries`, 'success');
                } else {
                    addActivity(`Error loading history: ${data.error}`, 'error');
                    document.getElementById('global-history-container').innerHTML = 
                        `<div class="alert alert-danger">Error: ${data.error}</div>`;
                }
            } catch (error) {
                addActivity(`Error loading history: ${error.message}`, 'error');
                document.getElementById('global-history-container').innerHTML = 
                    `<div class="alert alert-danger">Error: ${error.message}</div>`;
            } finally {
                document.getElementById('history-loading').style.display = 'none';
            }
        }

        function displayGlobalHistory(history) {
            const container = document.getElementById('global-history-container');
            
            if (!history || history.length === 0) {
                container.innerHTML = '<div class="alert alert-info">No history found.</div>';
                return;
            }
            
            let html = '<div class="history-list">';
            
            history.forEach((entry, index) => {
                const timestamp = new Date(entry.timestamp).toLocaleString();
                const type = entry.type || 'unknown';
                const typeIcon = type === 'batch' ? '📋' : '🔍';
                const typeLabel = type === 'batch' ? 'Batch Alert' : 'Single Search';
                
                // Get title/header based on type
                let title = 'Unknown Alert';
                let resultsCount = entry.results_count || 0;
                let user = entry.user || 'Unknown User';
                
                if (type === 'batch') {
                    const alertData = entry.alert_data || {};
                    title = alertData.header || 'Unknown Alert';
                } else {
                    const keywords = entry.keywords || [];
                    title = keywords.length > 0 ? keywords.join(', ') : 'Single Search';
                }
                
                html += `
                <div class="history-item" style="background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid ${type === 'batch' ? '#e74c3c' : '#3498db'}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                                <span style="margin-right: 8px; font-size: 16px;">${typeIcon}</span>
                                <h4 style="margin: 0; color: #2c3e50;">${title}</h4>
                                <span style="margin-left: 10px; padding: 2px 8px; background: ${type === 'batch' ? '#e74c3c' : '#3498db'}; color: white; border-radius: 12px; font-size: 11px;">${typeLabel}</span>
                            </div>
                            <p style="margin: 0; color: #7f8c8d; font-size: 12px;">Processed: ${timestamp}</p>
                            <p style="margin: 5px 0 0 0; color: #27ae60; font-size: 13px; font-weight: 600;">${resultsCount} results • User: ${user}</p>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button onclick="shareResult('${entry.hash}')" class="btn btn-sm btn-outline-secondary" title="Share URL">
                                🔗 Share
                            </button>
                            <button onclick="viewResult('${entry.hash}')" class="btn btn-sm btn-outline-primary">
                                👁️ View
                            </button>
                            <button onclick="downloadResult('${entry.hash}')" class="btn btn-sm btn-success">
                                📥 Download
                            </button>
                        </div>
                    </div>
                </div>
                `;
            });
            
            html += '</div>';
            container.innerHTML = html;
        }

        function shareResult(hash) {
            const url = `${window.location.origin}${window.location.pathname}#${hash}`;
            navigator.clipboard.writeText(url).then(() => {
                addActivity('Share URL copied to clipboard!', 'success');
                showCopyNotification();
            }).catch(() => {
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = url;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                addActivity('Share URL copied to clipboard!', 'success');
                showCopyNotification();
            });
        }

        function viewResult(hash) {
            // Load result by hash and display it
            loadResultByHash(hash, 'view');
        }

        function downloadResult(hash) {
            // Load result by hash and download it
            loadResultByHash(hash, 'download');
        }

        async function loadResultByHash(hash, action) {
            try {
                addActivity(`Loading result ${hash}...`, 'info');
                
                const response = await fetch(`${BASE_URL}/result_by_hash/${hash}`);
                const data = await response.json();
                
                if (data.success) {
                    const result = data.result;
                    
                    if (action === 'view') {
                        if (result.type === 'batch') {
                            const url = `${BASE_URL}/batch_history_html/${encodeURIComponent(result.user)}/${encodeURIComponent(result.html_file)}`;
                            window.open(url, '_blank');
                        } else {
                            const url = `${BASE_URL}/export_html/${result.session_id}`;
                            window.open(url, '_blank');
                        }
                        addActivity('Result opened in new tab', 'success');
                    } else if (action === 'download') {
                        if (result.type === 'batch') {
                            const url = `${BASE_URL}/batch_history_html/${encodeURIComponent(result.user)}/${encodeURIComponent(result.html_file)}`;
                            const link = document.createElement('a');
                            link.href = url;
                            link.download = result.html_file;
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                        } else {
                            const url = `${BASE_URL}/export_html/${result.session_id}?download=true`;
                            window.open(url, '_blank');
                        }
                        addActivity('Result downloaded', 'success');
                    }
                } else {
                    addActivity(`Error loading result: ${data.error}`, 'error');
                }
            } catch (error) {
                addActivity(`Error loading result: ${error.message}`, 'error');
            }
        }

        // Handle URL hash on page load
        function handleUrlHash() {
            const hash = window.location.hash.substring(1);
            if (hash) {
                // Auto-load the result if hash is present
                loadResultByHash(hash, 'view');
            }
        }

        // Load global history on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadGlobalHistory();
            handleUrlHash();
        });

        // Quick fill functions
        function quickFill(type) {
            const keywordsEl = document.getElementById('keywords');
            const alertNameEl = document.getElementById('alert-name');
            const sectionNameEl = document.getElementById('section-name');

            if (type === 'prostate') {
                keywordsEl.value = 'prostate cancer, orgovyx, relugolix, myfembree, OAB, overactive bladder, urology, oncology, hormone therapy, ADT';
                alertNameEl.value = 'Prostate Cancer & Urology Research';
                sectionNameEl.value = 'Clinical Updates';
            } else if (type === 'ai') {
                keywordsEl.value = 'AI, artificial intelligence, machine learning, RAG, LLM, agentic, pipelines, pharma, drug discovery, clinical trials AI';
                alertNameEl.value = 'AI in Pharma Research';
                sectionNameEl.value = 'Technology & Innovation';
            }
        }

        // Activity logging
        function addActivity(message, type = 'info') {
            const log = document.getElementById('activity-log');
            const time = new Date().toLocaleTimeString();
            
            const item = document.createElement('div');
            item.className = `activity-item ${type}`;
            item.innerHTML = `
                <div class="activity-time">${time}</div>
                <div class="activity-message">${message}</div>
            `;
            
            log.insertBefore(item, log.firstChild);
            
            // Keep only last 20 items
            while (log.children.length > 20) {
                log.removeChild(log.lastChild);
            }

            // Update status indicator
            const indicator = document.getElementById('status-indicator');
            indicator.className = 'status-indicator status-' + (type === 'error' ? 'error' : type === 'success' ? 'success' : 'processing');
        }

        // Get selected search engines
        function getSelectedEngines() {
            const engines = [];
            if (document.getElementById('engine-pubmed').checked) engines.push('pubmed');
            if (document.getElementById('engine-exa').checked) engines.push('exa');
            if (document.getElementById('engine-tavily').checked) engines.push('tavily');
            if (document.getElementById('engine-newsapi').checked) engines.push('newsapi');
            return engines;
        }

        // Perform search
        async function performSearch(event) {
            event.preventDefault();
            
            const keywords = document.getElementById('keywords').value;
            const startDate = document.getElementById('start-date').value;
            const endDate = document.getElementById('end-date').value;
            const searchType = document.getElementById('search-type').value;
            const alertName = document.getElementById('alert-name').value;
            const sectionName = document.getElementById('section-name').value;
            const searchEngines = getSelectedEngines();

            if (searchEngines.length === 0) {
                alert('Please select at least one search engine');
                return;
            }

            // Show loading
            document.getElementById('loading-overlay').classList.add('active');
            document.getElementById('search-btn').disabled = true;
            
            // Update activity
            addActivity('Starting search with ' + searchEngines.join(', '), 'info');
            addActivity('Keywords: ' + keywords.substring(0, 50) + '...', 'info');

            // Simulate progress
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 5;
                if (progress <= 90) {
                    document.getElementById('progress-fill').style.width = progress + '%';
                    document.getElementById('progress-text').textContent = progress + '% complete';
                }
            }, 500);

            try {
                const response = await fetch(`${BASE_URL}/search`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        keywords: keywords,
                        start_date: startDate,
                        end_date: endDate,
                        search_type: searchType,
                        alert_name: alertName,
                        section_name: sectionName,
                        search_engines: searchEngines
                    })
                });

                clearInterval(progressInterval);
                document.getElementById('progress-fill').style.width = '100%';
                document.getElementById('progress-text').textContent = '100% complete';

                const data = await response.json();

                if (data.error) {
                    addActivity('Error: ' + data.error, 'error');
                    alert('Error: ' + data.error);
                } else {
                    searchCount++;
                    totalResults += data.results.length;
                    if (data.results_by_source) {
                        Object.keys(data.results_by_source).forEach(source => {
                            if (source !== 'metadata' && data.results_by_source[source].length > 0) {
                                sourcesUsed.add(source);
                            }
                        });
                    }

                    // Update stats
                    document.getElementById('stat-searches').textContent = searchCount;
                    document.getElementById('stat-results').textContent = totalResults;
                    document.getElementById('stat-sources').textContent = sourcesUsed.size;

                    addActivity(`Found ${data.results.length} results`, 'success');
                    
                    // Update workflow stats if available
                    if (data.workflow_stats) {
                        updateWorkflowStats(data.workflow_stats);
                    }
                    
                    // Update source breakdown
                    if (data.results_by_source) {
                        updateSourceBreakdown(data.results_by_source);
                    }
                    
                    displayResults(data);
                }
            } catch (error) {
                clearInterval(progressInterval);
                addActivity('Network error: ' + error.message, 'error');
                alert('Error: ' + error.message);
            } finally {
                document.getElementById('loading-overlay').classList.remove('active');
                document.getElementById('search-btn').disabled = false;
                document.getElementById('progress-fill').style.width = '0%';
                document.getElementById('status-indicator').className = 'status-indicator status-idle';
            }
        }

        // Update workflow statistics
        function updateWorkflowStats(stats) {
            // Data Collection Stats
            if (stats.data_collection) {
                document.getElementById('collection-stats').style.display = 'block';
                document.getElementById('stat-collected').textContent = stats.data_collection.total_collected || 0;
                document.getElementById('stat-sources-list').textContent = 
                    (stats.data_collection.sources_used || []).join(', ') || 'None';
            }
            
            // Deduplication Stats
            if (stats.deduplication) {
                document.getElementById('dedup-stats').style.display = 'block';
                document.getElementById('stat-duplicates').textContent = stats.deduplication.duplicates_removed || 0;
                document.getElementById('stat-unique').textContent = stats.deduplication.unique_articles || 0;
                document.getElementById('stat-dup-groups').textContent = stats.deduplication.duplicate_groups || 0;
            }
            
            // Date Extraction Stats
            if (stats.date_extraction) {
                document.getElementById('date-stats').style.display = 'block';
                document.getElementById('stat-with-dates').textContent = stats.date_extraction.with_dates || 0;
                document.getElementById('stat-without-dates').textContent = stats.date_extraction.without_dates || 0;
                document.getElementById('stat-extracted-dates').textContent = stats.date_extraction.extracted_dates || 0;
            }
            
            // Date Filtering Stats
            if (stats.date_filtering) {
                document.getElementById('filter-stats').style.display = 'block';
                document.getElementById('stat-in-range').textContent = stats.date_filtering.in_range || 0;
                document.getElementById('stat-out-range').textContent = stats.date_filtering.out_of_range || 0;
                document.getElementById('stat-llm-rescued').textContent = stats.date_filtering.llm_rescued || 0;
            }
            
            // Relevance Analysis Stats
            if (stats.relevance_analysis || stats.relevance_filtering) {
                document.getElementById('relevance-stats').style.display = 'block';
                document.getElementById('stat-analyzed').textContent = 
                    (stats.relevance_analysis && stats.relevance_analysis.analyzed) || 0;
                document.getElementById('stat-kept').textContent = 
                    (stats.relevance_filtering && stats.relevance_filtering.kept) || 0;
                document.getElementById('stat-filtered').textContent = 
                    (stats.relevance_filtering && stats.relevance_filtering.filtered) || 0;
            }
        }

        // Update source breakdown
        function updateSourceBreakdown(results_by_source) {
            const container = document.getElementById('source-stats-container');
            let html = '';
            
            Object.keys(results_by_source).forEach(source => {
                if (source !== 'metadata') {
                    const count = Array.isArray(results_by_source[source]) ? 
                        results_by_source[source].length : 
                        (results_by_source[source].articles ? results_by_source[source].articles.length : 0);
                    
                    html += `
                        <div class="stat-item">
                            <span>${source.charAt(0).toUpperCase() + source.slice(1)}:</span>
                            <span class="stat-value">${count}</span>
                        </div>
                    `;
                }
            });
            
            container.innerHTML = html;
            document.getElementById('source-breakdown').style.display = 'block';
        }

        // Store all results globally for filtering
        let allResults = [];
        let currentMinScore = 65;

        // Filter results by relevance score
        function filterByRelevanceScore(minScore) {
            currentMinScore = minScore;
            const resultCards = document.querySelectorAll('.result-card');
            let shownCount = 0;
            let hiddenCount = 0;
            
            resultCards.forEach(card => {
                const score = parseInt(card.dataset.relevanceScore || '0');
                if (score >= minScore) {
                    card.style.display = 'block';
                    shownCount++;
                } else {
                    card.style.display = 'none';
                    hiddenCount++;
                }
            });
            
            document.getElementById('stat-shown-count').textContent = shownCount;
            document.getElementById('stat-hidden-count').textContent = hiddenCount;
        }

        // Setup relevance slider
        const relevanceSlider = document.getElementById('relevance-slider');
        const sliderValue = document.getElementById('slider-value');
        
        relevanceSlider.addEventListener('input', (e) => {
            const value = e.target.value;
            sliderValue.textContent = value;
            filterByRelevanceScore(parseInt(value));
        });

        // Display results
        function displayResults(data) {
            const resultsArea = document.getElementById('results-area');
            
            if (!data.results || data.results.length === 0) {
                resultsArea.innerHTML = '<div class="no-results"><div class="no-results-icon">🔍</div><p>No results found</p></div>';
                return;
            }
            
            // Store results in window object for filtering
            window.currentResults = data.results;

            let html = '<div class="alert alert-success">Found ' + data.results.length + ' results from ' + 
                      (data.results_by_source ? Object.keys(data.results_by_source).filter(k => k !== 'metadata').length : 'multiple') + 
                      ' sources</div>';
            
            // Add export buttons with relevance filter
            html += `
            <div style="margin-bottom: 20px;">
                <div style="margin-bottom: 15px;">
                    <label for="relevance-slider" style="display: block; margin-bottom: 8px; font-weight: 600; color: #2c3e50;">
                        📊 Filter by Relevance Score (≥ <span id="relevance-value">50</span>)
                    </label>
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <span style="font-size: 12px; color: #7f8c8d;">0</span>
                        <input type="range" id="relevance-slider" min="0" max="100" value="50" 
                               style="flex: 1; height: 6px; background: #ddd; border-radius: 3px; outline: none;"
                               oninput="updateRelevanceFilter(this.value)">
                        <span style="font-size: 12px; color: #7f8c8d;">100</span>
                    </div>
                    <div style="margin-top: 8px; font-size: 12px; color: #7f8c8d;">
                        <span id="filtered-count">All articles</span> will be included in export
                    </div>
                </div>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button onclick="downloadHTML('${data.session_id}')" class="btn btn-success" style="flex: 1; min-width: 200px;">
                        📥 Download as HTML
                    </button>
                    <button onclick="copyHTML('${data.session_id}')" class="btn btn-primary" style="flex: 1; min-width: 200px;">
                        📋 Copy HTML for Email
                    </button>
                </div>
            </div>
            <div id="copy-notification" style="display: none; padding: 12px; background: #27ae60; color: white; border-radius: 4px; margin-bottom: 15px; text-align: center;">
                ✓ HTML copied to clipboard! Ready to paste in email.
            </div>
            `;

            data.results.forEach(result => {
                // Enhanced result display with detailed information
                const relevanceScore = result.relevance_score || 0;
                const relevanceReason = result.relevance_reason || 'No reason provided';
                const articleType = result.article_type || 'unknown';
                const summary = result.summary || result.content?.substring(0, 300) || 'No summary available';
                const highlightedContent = result.highlighted_content || summary;
                const mentionedKeywords = result.mentioned_keywords || [];
                const clinicalSignificance = result.clinical_significance;
                const regulatoryImpact = result.regulatory_impact;
                const marketImpact = result.market_impact;
                
                // Format date properly
                let dateDisplay = 'No date';
                if (result.date) {
                    try {
                        const date = new Date(result.date);
                        dateDisplay = date.toLocaleDateString();
                    } catch (e) {
                        dateDisplay = result.date;
                    }
                }
                
                // Create keyword tags
                const keywordTags = mentionedKeywords.map(kw => 
                    `<span class="keyword-tag">${kw}</span>`
                ).join('');
                
                html += `
                    <div class="result-card enhanced-result" data-relevance-score="${relevanceScore}">
                        <div class="result-header">
                            <div class="result-title">
                                <a href="${result.url}" target="_blank">${result.title}</a>
                            </div>
                            <div class="result-scores">
                                <span class="badge badge-score">Relevance: ${relevanceScore}</span>
                                <span class="badge badge-type">${articleType}</span>
                            </div>
                        </div>
                        
                        <div class="result-summary">
                            ${highlightedContent}
                        </div>
                        
                        <div class="result-relevance">
                            <strong>Why it's relevant:</strong> ${relevanceReason}
                        </div>
                        
                        ${mentionedKeywords.length > 0 ? `
                        <div class="result-keywords">
                            <strong>Keywords found:</strong> ${keywordTags}
                        </div>
                        ` : ''}
                        
                        ${result.pertinent_keywords && result.pertinent_keywords.length > 0 ? `
                        <div class="result-pertinent-keywords">
                            <strong>Related terms:</strong> ${result.pertinent_keywords.map(kw => 
                                `<span class="keyword-tag pertinent">${kw}</span>`
                            ).join('')}
                        </div>
                        ` : ''}
                        
                        ${clinicalSignificance ? `
                        <div class="result-significance">
                            <strong>Clinical Significance:</strong> ${clinicalSignificance}
                        </div>
                        ` : ''}
                        
                        ${regulatoryImpact ? `
                        <div class="result-regulatory">
                            <strong>Regulatory Impact:</strong> ${regulatoryImpact}
                        </div>
                        ` : ''}
                        
                        ${marketImpact ? `
                        <div class="result-market">
                            <strong>Market Impact:</strong> ${marketImpact}
                        </div>
                        ` : ''}
                        
                        <div class="result-meta">
                            <span><span class="badge badge-source">${result.source || 'Unknown'}</span></span>
                            <span>📅 ${dateDisplay}</span>
                            ${result.authors ? '<span>👤 ' + result.authors.substring(0, 50) + '</span>' : ''}
                        </div>
                    </div>
                `;
            });

            resultsArea.innerHTML = html;
            
            // Show relevance filter section
            document.getElementById('relevance-filter-section').style.display = 'block';
            
            // Apply current filter
            filterByRelevanceScore(currentMinScore);
        }

        // CSV Upload
        document.getElementById('upload-area').addEventListener('click', () => {
            document.getElementById('csv-file').click();
        });

        document.getElementById('csv-file').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (file) {
                addActivity('Uploading CSV: ' + file.name, 'info');
                await uploadCSV(file);
            }
        });

        const uploadArea = document.getElementById('upload-area');
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', async (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.name.endsWith('.csv')) {
                addActivity('Processing dropped CSV: ' + file.name, 'info');
                await uploadCSV(file);
            } else {
                alert('Please drop a CSV file');
            }
        });

        // Store CSV upload data globally
        let currentCSVData = null;

        async function uploadCSV(file) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                document.getElementById('loading-overlay').classList.add('active');
                
                const response = await fetch(`${BASE_URL}/upload_csv`, {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                
                if (data.error) {
                    addActivity('CSV upload error: ' + data.error, 'error');
                    alert('Error: ' + data.error);
                } else {
                    currentCSVData = data;
                    addActivity('CSV processed: ' + data.users_with_alerts + ' users with alerts', 'success');
                    
                    // Show user selection section
                    document.getElementById('user-selection-section').style.display = 'block';
                    
                    // Populate user dropdown
                    const userSelect = document.getElementById('user-select');
                    userSelect.innerHTML = '<option value="">Choose a user...</option>';
                    
                    data.users.forEach(user => {
                        const option = document.createElement('option');
                        option.value = user;
                        option.textContent = `${user} (${data.user_email_alerts[user] ? data.user_email_alerts[user].length : 0} alerts)`;
                        userSelect.appendChild(option);
                    });
                    
                    // Set default dates
                    const today = new Date();
                    const sevenDaysAgo = new Date(today);
                    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
                    document.getElementById('batch-end-date').valueAsDate = today;
                    document.getElementById('batch-start-date').valueAsDate = sevenDaysAgo;
                    
                    document.getElementById('batch-results').innerHTML = `
                        <div class="alert alert-success">
                            CSV uploaded successfully: ${data.users_with_alerts} users with email alerts found
                        </div>
                    `;
                }
            } catch (error) {
                addActivity('CSV upload failed: ' + error.message, 'error');
                alert('Error: ' + error.message);
            } finally {
                document.getElementById('loading-overlay').classList.remove('active');
            }
        }

        // User selection handling
        document.getElementById('user-select').addEventListener('change', function() {
            const processBtn = document.getElementById('process-alerts-btn');
            processBtn.disabled = !this.value;
        });

        // Process alerts button handler
        document.getElementById('process-alerts-btn').addEventListener('click', async function() {
            const selectedUser = document.getElementById('user-select').value;
            const startDate = document.getElementById('batch-start-date').value;
            const endDate = document.getElementById('batch-end-date').value;
            
            if (!selectedUser || !currentCSVData) {
                alert('Please select a user and ensure CSV data is loaded');
                return;
            }

            try {
                document.getElementById('loading-overlay').classList.add('active');
                addActivity(`Processing alerts for user: ${selectedUser}`, 'info');
                
                const response = await fetch(`${BASE_URL}/process_user_alerts`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        upload_id: currentCSVData.upload_id,
                        selected_user: selectedUser,
                        start_date: startDate,
                        end_date: endDate
                    })
                });

                const data = await response.json();
                
                if (data.error) {
                    addActivity('Alert processing error: ' + data.error, 'error');
                    alert('Error: ' + data.error);
                } else {
                    addActivity(`Processed ${data.total_results} results for ${data.successful_alerts} alerts`, 'success');
                    
                    // Display results
                    displayBatchResults(data);
                }
            } catch (error) {
                addActivity('Alert processing failed: ' + error.message, 'error');
                alert('Error: ' + error.message);
            } finally {
                document.getElementById('loading-overlay').classList.remove('active');
            }
        });

        // Display batch processing results
        function displayBatchResults(data) {
            const batchResults = document.getElementById('batch-results');
            
            // Store batch results in window object for filtering
            window.currentBatchResults = data.results || [];
            
            let html = `
                <div class="alert alert-success">
                    <h3>🔬 Alert Processing Complete</h3>
                    <p><strong>User:</strong> ${data.user}</p>
                    <p><strong>Total Alerts:</strong> ${data.total_alerts}</p>
                    <p><strong>Successful Alerts:</strong> ${data.successful_alerts}</p>
                    <p><strong>Total Results:</strong> ${data.total_results} (relevance score > 65)</p>
                </div>
                
                <!-- HTML Export Buttons with Relevance Filter -->
                <div style="margin-bottom: 20px;">
                    <div style="margin-bottom: 15px;">
                        <label for="batch-relevance-slider" style="display: block; margin-bottom: 8px; font-weight: 600; color: #2c3e50;">
                            📊 Filter by Relevance Score (≥ <span id="batch-relevance-value">50</span>)
                        </label>
                        <div style="display: flex; align-items: center; gap: 15px;">
                            <span style="font-size: 12px; color: #7f8c8d;">0</span>
                            <input type="range" id="batch-relevance-slider" min="0" max="100" value="50" 
                                   style="flex: 1; height: 6px; background: #ddd; border-radius: 3px; outline: none;"
                                   oninput="updateBatchRelevanceFilter(this.value)">
                            <span style="font-size: 12px; color: #7f8c8d;">100</span>
                        </div>
                        <div style="margin-top: 8px; font-size: 12px; color: #7f8c8d;">
                            <span id="batch-filtered-count">All articles</span> will be included in export
                        </div>
                    </div>
                    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        <button onclick="downloadBatchHTML('${data.user}')" class="btn btn-success" style="flex: 1; min-width: 200px;">
                            📥 Download Batch HTML
                        </button>
                        <button onclick="copyBatchHTML('${data.user}')" class="btn btn-primary" style="flex: 1; min-width: 200px;">
                            📋 Copy Batch HTML for Email
                        </button>
                    </div>
                </div>
                <div id="batch-copy-notification" style="display: none; padding: 12px; background: #27ae60; color: white; border-radius: 4px; margin-bottom: 15px; text-align: center;">
                    ✓ Batch HTML copied to clipboard! Ready to paste in email.
                </div>
            `;
            
            if (data.processed_alerts && data.processed_alerts.length > 0) {
                html += '<div class="alert alert-info"><h4>📋 Processed Alerts Summary:</h4><ul>';
                data.processed_alerts.forEach(alert => {
                    html += `<li><strong>${alert.alert_title}</strong> - ${alert.subheader}: ${alert.results_count} results</li>`;
                });
                html += '</ul></div>';
            }
            
            if (data.results && data.results.length > 0) {
                html += '<div class="alert alert-info"><h4>📄 Detailed Results (sorted by relevance):</h4>';
                
                // Group results by alert for better organization
                const resultsByAlert = {};
                data.results.forEach(result => {
                    const alertContext = result.alert_context || {};
                    const alertKey = `${alertContext.alert_title || 'Unknown'}_${alertContext.subheader || 'Unknown'}`;
                    if (!resultsByAlert[alertKey]) {
                        resultsByAlert[alertKey] = {
                            alert_title: alertContext.alert_title || 'Unknown Alert',
                            subheader: alertContext.subheader || 'Unknown',
                            results: []
                        };
                    }
                    resultsByAlert[alertKey].results.push(result);
                });
                
                // Display each alert section with detailed results
                Object.values(resultsByAlert).forEach((alertGroup, groupIndex) => {
                    html += `
                        <div class="alert-section" style="margin-bottom: 30px; border: 2px solid #e0e0e0; border-radius: 8px; padding: 20px;">
                            <h5 style="color: #2c3e50; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #e0e0e0;">
                                📌 ${alertGroup.alert_title} - ${alertGroup.subheader}
                                <span style="float: right; background: #3498db; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px;">
                                    ${alertGroup.results.length} results
                                </span>
                            </h5>
                    `;
                    
                    alertGroup.results.forEach((result, index) => {
                        // Enhanced result display with detailed information (same as single search)
                        const relevanceScore = result.relevance_score || 0;
                        const relevanceReason = result.relevance_reason || 'No reason provided';
                        const articleType = result.article_type || 'unknown';
                        const summary = result.summary || result.content?.substring(0, 300) || 'No summary available';
                        const highlightedContent = result.highlighted_content || summary;
                        const mentionedKeywords = result.mentioned_keywords || [];
                        const clinicalSignificance = result.clinical_significance;
                        const regulatoryImpact = result.regulatory_impact;
                        const marketImpact = result.market_impact;
                        
                        // Format date properly
                        let dateDisplay = 'No date';
                        if (result.date) {
                            try {
                                const date = new Date(result.date);
                                dateDisplay = date.toLocaleDateString();
                            } catch (e) {
                                dateDisplay = result.date;
                            }
                        }
                        
                        // Create keyword tags
                        const keywordTags = mentionedKeywords.map(kw => 
                            `<span class="keyword-tag">${kw}</span>`
                        ).join('');
                        
                        html += `
                            <div class="result-card enhanced-result" data-relevance-score="${relevanceScore}" style="margin-bottom: 20px;">
                                <div class="result-header">
                                    <div class="result-title">
                                        <a href="${result.url}" target="_blank">${index + 1}. ${result.title}</a>
                                    </div>
                                    <div class="result-scores">
                                        <span class="badge badge-score">Relevance: ${relevanceScore}</span>
                                        <span class="badge badge-type">${articleType}</span>
                                    </div>
                                </div>
                                
                                <div class="result-summary">
                                    ${highlightedContent}
                                </div>
                                
                                <div class="result-relevance">
                                    <strong>Why it's relevant:</strong> ${relevanceReason}
                                </div>
                                
                                ${mentionedKeywords.length > 0 ? `
                                <div class="result-keywords">
                                    <strong>Keywords found:</strong> ${keywordTags}
                                </div>
                                ` : ''}
                                
                                ${clinicalSignificance ? `
                                <div class="result-significance">
                                    <strong>Clinical Significance:</strong> ${clinicalSignificance}
                                </div>
                                ` : ''}
                                
                                ${regulatoryImpact ? `
                                <div class="result-regulatory">
                                    <strong>Regulatory Impact:</strong> ${regulatoryImpact}
                                </div>
                                ` : ''}
                                
                                ${marketImpact ? `
                                <div class="result-market">
                                    <strong>Market Impact:</strong> ${marketImpact}
                                </div>
                                ` : ''}
                                
                                <div class="result-meta">
                                    <span><span class="badge badge-source">${result.source || 'Unknown'}</span></span>
                                    <span>📅 ${dateDisplay}</span>
                                    ${result.authors ? '<span>👤 ' + result.authors.substring(0, 50) + '</span>' : ''}
                                </div>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                });
                
                html += '</div>';
            }
            
            batchResults.innerHTML = html;
        }

        // Mark APIs as configured (placeholder - should come from backend)
        document.getElementById('api-openai').innerHTML = '✅';
        document.getElementById('api-tavily').innerHTML = '✅';
        document.getElementById('api-exa').innerHTML = '✅';
        document.getElementById('api-newsapi').innerHTML = '✅';
        
        // Relevance Filter Functions
        function updateRelevanceFilter(value) {
            document.getElementById('relevance-value').textContent = value;
            
            // Count filtered articles
            const results = window.currentResults || [];
            const filteredCount = results.filter(result => (result.relevance_score || 0) >= parseInt(value)).length;
            
            const countElement = document.getElementById('filtered-count');
            if (filteredCount === results.length) {
                countElement.textContent = 'All articles';
            } else {
                countElement.textContent = `${filteredCount} of ${results.length} articles`;
            }
            
            // Store current filter value
            window.currentRelevanceFilter = parseInt(value);
        }
        
        function updateBatchRelevanceFilter(value) {
            document.getElementById('batch-relevance-value').textContent = value;
            
            // Count filtered articles from batch results
            const batchResults = window.currentBatchResults || [];
            const filteredCount = batchResults.filter(result => (result.relevance_score || 0) >= parseInt(value)).length;
            
            const countElement = document.getElementById('batch-filtered-count');
            if (filteredCount === batchResults.length) {
                countElement.textContent = 'All articles';
            } else {
                countElement.textContent = `${filteredCount} of ${batchResults.length} articles`;
            }
            
            // Store current batch filter value
            window.currentBatchRelevanceFilter = parseInt(value);
        }
        
        // HTML Export Functions
        async function downloadHTML(sessionId) {
            try {
                addActivity('Generating HTML export...', 'info');
                
                // Get current relevance filter
                const relevanceFilter = window.currentRelevanceFilter || 50;
                
                // Open download in new window with filter parameter
                window.open(`${BASE_URL}/export_html/${sessionId}?download=true&min_relevance=${relevanceFilter}`, '_blank');
                
                addActivity(`HTML file downloaded successfully (relevance ≥ ${relevanceFilter})`, 'success');
            } catch (error) {
                addActivity('HTML download failed: ' + error.message, 'error');
                alert('Error downloading HTML: ' + error.message);
            }
        }
        
        async function copyHTML(sessionId) {
            try {
                addActivity('Generating HTML for clipboard...', 'info');
                
                // Get current relevance filter
                const relevanceFilter = window.currentRelevanceFilter || 50;
                
                // Fetch HTML content with filter parameter
                const response = await fetch(`${BASE_URL}/export_html/${sessionId}?min_relevance=${relevanceFilter}`);
                const data = await response.json();
                
                if (data.error) {
                    addActivity('Error: ' + data.error, 'error');
                    alert('Error: ' + data.error);
                    return;
                }
                
                // Try multiple copy methods for better compatibility
                const htmlContent = data.html;
                
                // Method 1: Modern Clipboard API
                if (navigator.clipboard && window.isSecureContext) {
                    try {
                        await navigator.clipboard.writeText(htmlContent);
                        addActivity(`HTML copied to clipboard (${data.result_count} articles, relevance ≥ ${relevanceFilter})`, 'success');
                        showCopyNotification();
                        return;
                    } catch (clipboardError) {
                        console.warn('Clipboard API failed:', clipboardError);
                    }
                }
                
                // Method 2: Fallback with textarea
                try {
                    const textarea = document.createElement('textarea');
                    textarea.value = htmlContent;
                    textarea.style.position = 'fixed';
                    textarea.style.left = '-999999px';
                    textarea.style.top = '-999999px';
                    document.body.appendChild(textarea);
                    textarea.focus();
                    textarea.select();
                    
                    const successful = document.execCommand('copy');
                    document.body.removeChild(textarea);
                    
                    if (successful) {
                        addActivity(`HTML copied to clipboard (${data.result_count} articles)`, 'success');
                        showCopyNotification();
                    } else {
                        throw new Error('execCommand copy failed');
                    }
                } catch (fallbackError) {
                    console.warn('Fallback copy failed:', fallbackError);
                    
                    // Method 3: Show HTML in modal for manual copy
                    showHTMLModal(htmlContent, data.result_count);
                }
                
            } catch (error) {
                console.error('Copy HTML error:', error);
                addActivity('HTML copy failed: ' + error.message, 'error');
                alert('Error copying HTML: ' + error.message);
            }
        }
        
        function showCopyNotification() {
            const notification = document.getElementById('copy-notification');
            if (notification) {
                notification.style.display = 'block';
                setTimeout(() => {
                    notification.style.display = 'none';
                }, 3000);
            }
        }
        
        function showHTMLModal(htmlContent, resultCount) {
            // Create modal for manual copy
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.8); z-index: 10000; display: flex; 
                align-items: center; justify-content: center; padding: 20px;
            `;
            
            modal.innerHTML = `
                <div style="background: white; border-radius: 8px; padding: 20px; max-width: 90%; max-height: 90%; overflow: auto;">
                    <h3 style="margin-top: 0;">📋 Copy HTML Manually</h3>
                    <p>Your browser doesn't support automatic copying. Please copy the HTML below manually:</p>
                    <textarea readonly style="width: 100%; height: 400px; font-family: monospace; font-size: 12px; border: 1px solid #ccc; padding: 10px;">${htmlContent}</textarea>
                    <div style="margin-top: 15px; text-align: right;">
                        <button onclick="this.closest('.modal').remove()" style="background: #6c757d; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">Close</button>
                    </div>
                </div>
            `;
            
            modal.className = 'modal';
            document.body.appendChild(modal);
            
            // Auto-select the textarea content
            const textarea = modal.querySelector('textarea');
            textarea.focus();
            textarea.select();
            
            addActivity(`HTML ready for manual copy (${resultCount} articles)`, 'info');
        }
        
        // Batch HTML functions
        async function downloadBatchHTML(user) {
            try {
                addActivity('Generating batch HTML export...', 'info');
                
                // Get current batch relevance filter
                const relevanceFilter = window.currentBatchRelevanceFilter || 50;
                
                // Open download in new window with filter parameter
                window.open(`${BASE_URL}/export_batch_html/${user}?download=true&min_relevance=${relevanceFilter}`, '_blank');
                
                addActivity(`Batch HTML file downloaded successfully (relevance ≥ ${relevanceFilter})`, 'success');
            } catch (error) {
                addActivity('Batch HTML download failed: ' + error.message, 'error');
                alert('Error downloading batch HTML: ' + error.message);
            }
        }
        
        async function copyBatchHTML(user) {
            try {
                addActivity('Generating batch HTML for clipboard...', 'info');
                
                // Get current batch relevance filter
                const relevanceFilter = window.currentBatchRelevanceFilter || 50;
                
                // Fetch HTML content with filter parameter
                const response = await fetch(`${BASE_URL}/export_batch_html/${user}?min_relevance=${relevanceFilter}`);
                const data = await response.json();
                
                if (data.error) {
                    addActivity('Error: ' + data.error, 'error');
                    alert('Error: ' + data.error);
                    return;
                }
                
                // Try multiple copy methods for better compatibility
                const htmlContent = data.html;
                
                // Method 1: Modern Clipboard API
                if (navigator.clipboard && window.isSecureContext) {
                    try {
                        await navigator.clipboard.writeText(htmlContent);
                        addActivity(`Batch HTML copied to clipboard (${data.result_count} articles, relevance ≥ ${relevanceFilter})`, 'success');
                        showBatchCopyNotification();
                        return;
                    } catch (clipboardError) {
                        console.warn('Clipboard API failed:', clipboardError);
                    }
                }
                
                // Method 2: Fallback with textarea
                try {
                    const textarea = document.createElement('textarea');
                    textarea.value = htmlContent;
                    textarea.style.position = 'fixed';
                    textarea.style.left = '-999999px';
                    textarea.style.top = '-999999px';
                    document.body.appendChild(textarea);
                    textarea.focus();
                    textarea.select();
                    
                    const successful = document.execCommand('copy');
                    document.body.removeChild(textarea);
                    
                    if (successful) {
                        addActivity(`Batch HTML copied to clipboard (${data.result_count} articles)`, 'success');
                        showBatchCopyNotification();
                    } else {
                        throw new Error('execCommand copy failed');
                    }
                } catch (fallbackError) {
                    console.warn('Fallback copy failed:', fallbackError);
                    
                    // Method 3: Show HTML in modal for manual copy
                    showBatchHTMLModal(htmlContent, data.result_count);
                }
                
            } catch (error) {
                console.error('Copy batch HTML error:', error);
                addActivity('Batch HTML copy failed: ' + error.message, 'error');
                alert('Error copying batch HTML: ' + error.message);
            }
        }
        
        function showBatchCopyNotification() {
            const notification = document.getElementById('batch-copy-notification');
            if (notification) {
                notification.style.display = 'block';
                setTimeout(() => {
                    notification.style.display = 'none';
                }, 3000);
            }
        }
        
        function showBatchHTMLModal(htmlContent, resultCount) {
            // Create modal for manual copy
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.8); z-index: 10000; display: flex; 
                align-items: center; justify-content: center; padding: 20px;
            `;
            
            modal.innerHTML = `
                <div style="background: white; border-radius: 8px; padding: 20px; max-width: 90%; max-height: 90%; overflow: auto;">
                    <h3 style="margin-top: 0;">📋 Copy Batch HTML Manually</h3>
                    <p>Your browser doesn't support automatic copying. Please copy the HTML below manually:</p>
                    <textarea readonly style="width: 100%; height: 400px; font-family: monospace; font-size: 12px; border: 1px solid #ccc; padding: 10px;">${htmlContent}</textarea>
                    <div style="margin-top: 15px; text-align: right;">
                        <button onclick="this.closest('.modal').remove()" style="background: #6c757d; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">Close</button>
                    </div>
                </div>
            `;
            
            modal.className = 'modal';
            document.body.appendChild(modal);
            
            // Auto-select the textarea content
            const textarea = modal.querySelector('textarea');
            textarea.focus();
            textarea.select();
            
            addActivity(`Batch HTML ready for manual copy (${resultCount} articles)`, 'info');
        }
    </script>
</body>
</html>
"""

@ome_blueprint.route('/')
def index():
    """Serve the main search interface"""
    return render_template_string(HTML_TEMPLATE)

@ome_blueprint.route('/search', methods=['POST'])
def search():
    """Process search request"""
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        keywords_str = data.get('keywords', '').strip()
        start_date_str = data.get('start_date', '')
        end_date_str = data.get('end_date', '')
        search_type = data.get('search_type', 'standard')
        alert_name = data.get('alert_name', '').strip()
        section_name = data.get('section_name', '').strip()
        search_engines = data.get('search_engines', ['pubmed', 'exa', 'tavily'])  # Default to all engines
        
        # Validate keywords
        if not keywords_str:
            return jsonify({'error': 'Keywords are required'}), 400
        
        # Parse keywords
        keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
        
        if len(keywords) > Config.MAX_KEYWORDS:
            return jsonify({'error': f'Maximum {Config.MAX_KEYWORDS} keywords allowed'}), 400
        
        # Parse dates with default to last 7 days
        try:
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str)
            else:
                start_date = datetime.now() - timedelta(days=7)  # Default to last 7 days
            
            if end_date_str:
                end_date = datetime.fromisoformat(end_date_str)
            else:
                end_date = datetime.now()  # Default to today
            
            if start_date > end_date:
                return jsonify({'error': 'Start date must be before end date'}), 400
                
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
        
        print(f"Processing search request: {len(keywords)} keywords, {search_type} search, from {start_date.date()} to {end_date.date()}")
        
        # Use agentic workflow if available, otherwise fallback to basic search
        if AGENT_AVAILABLE and pharma_agent:
            if MULTI_AGENT_AVAILABLE:
                print("Using Multi-Agent workflow for enhanced research...")
                import asyncio
                workflow_result = asyncio.run(pharma_agent.execute_workflow(
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    search_type=search_type,
                    search_engines=search_engines
                ))
            else:
                print("Using basic agentic workflow for enhanced research...")
                import asyncio
                workflow_result = asyncio.run(pharma_agent.execute_workflow(
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    search_type=search_type,
                    search_engines=search_engines
                ))
            
            if workflow_result['success']:
                processed_results = workflow_result['results']
                results_by_source = workflow_result.get('results_by_source', {})
                total_found = workflow_result.get('total_found', 0)
                total_filtered = workflow_result.get('total_filtered', 0)
                total_processed = workflow_result.get('total_processed', 0)
                
                print(f"SUCCESS: Agentic workflow completed: {total_processed} results")
                print(f"DEBUG: results_by_source keys: {list(results_by_source.keys()) if results_by_source else 'None'}")
            else:
                print(f"ERROR: Agentic workflow failed: {workflow_result.get('error', 'Unknown error')}")
                # Fallback to basic search
                processed_results = []
                results_by_source = {}
                total_found = total_filtered = total_processed = 0
        else:
            print("INFO: Using basic search functionality...")
            # Fallback to basic search
            raw_results = search_all_sources(keywords, Config.MAX_RESULTS_PER_SOURCE, start_date, end_date)
            filtered_results = filter_results(raw_results, keywords, search_type)
            
            processed_results = []
            for i, result in enumerate(filtered_results):
                relevance_score = calculate_relevance_score(result, keywords)
                summary = result['content'][:200] + "..." if len(result['content']) > 200 else result['content']
                highlighted_summary = highlight_keywords(summary, keywords)
                
                processed_result = result.copy()
                processed_result.update({
                    'rank': i + 1,
                    'relevance_score': relevance_score,
                    'summary': summary,
                    'highlighted_summary': highlighted_summary
                })
                processed_results.append(processed_result)
            
            processed_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            # Organize basic search results by source
            results_by_source = {
                'pubmed': [r for r in processed_results if 'pubmed' in r.get('source', '').lower()],
                'tavily': [r for r in processed_results if 'tavily' in r.get('source', '').lower()],
                'openai_curated': []
            }
            results_by_source['metadata'] = {
                'pubmed_count': len(results_by_source['pubmed']),
                'tavily_count': len(results_by_source['tavily']),
                'openai_curated_count': len(results_by_source['openai_curated']),
                'total_sources': len([k for k, v in results_by_source.items() if k != 'metadata' and len(v) > 0])
            }
            
            total_found = len(raw_results)
            total_filtered = len(filtered_results)
            total_processed = len(processed_results)
        
        # Store results for CSV download
        session_id = f"search_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        metadata = {
            'keywords': keywords,
            'search_type': search_type,
            'alert_name': alert_name,
            'section_name': section_name,
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id
        }
        
        # Generate hash for URL sharing
        metadata['hash'] = generate_result_hash(metadata)
        metadata['share_url'] = f"#{metadata['hash']}"
        
        search_results_store[session_id] = {
            'results': processed_results,
            'metadata': metadata,
            'timestamp': datetime.now()
        }
        
        # Clean up old sessions
        if len(search_results_store) > 10:
            oldest_session = min(search_results_store.keys())
            del search_results_store[oldest_session]
        
        # Extract workflow stats if available
        workflow_stats = {}
        if AGENT_AVAILABLE and pharma_agent and workflow_result:
            workflow_stats = workflow_result.get('metadata', {}).get('workflow_stats', {})
        
        return jsonify({
            'success': True,
            'results': processed_results,
            'results_by_source': results_by_source,
            'total_found': total_found,
            'total_filtered': total_filtered,
            'total_processed': total_processed,
            'session_id': session_id,
            'workflow_stats': workflow_stats,  # Add workflow stats
            'search_metadata': {
                'keywords': keywords,
                'search_type': search_type,
                'alert_name': alert_name,
                'section_name': section_name,
                'timestamp': datetime.now().isoformat(),
                'agentic_workflow': AGENT_AVAILABLE and pharma_agent is not None
            }
        })
        
    except Exception as e:
        print(f"Search error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}',
            'results': []
        }), 500

@ome_blueprint.route('/download/<session_id>')
def download_csv(session_id):
    """Download search results as CSV"""
    try:
        if session_id not in search_results_store:
            return jsonify({'error': 'Session not found'}), 404
        
        search_data = search_results_store[session_id]
        results = search_data['results']
        
        if not results:
            return jsonify({'error': 'No results to download'}), 400
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = ['Rank', 'Title', 'Summary', 'Source', 'Date', 'URL', 'Relevance Score']
        writer.writerow(headers)
        
        # Write data rows
        for result in results:
            row = [
                result.get('rank', ''),
                result.get('title', ''),
                result.get('summary', '').replace('\n', ' ').replace('\r', ' '),
                result.get('source', ''),
                result.get('date', ''),
                result.get('url', ''),
                result.get('relevance_score', '')
            ]
            writer.writerow(row)
        
        # Create response
        output.seek(0)
        csv_content = output.getvalue()
        output.close()
        
        # Create filename
        keywords_str = '_'.join(search_data['metadata']['keywords'][:3])
        filename = f"medical_search_{keywords_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Return CSV file
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"CSV download error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@ome_blueprint.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV file upload for multi-section processing"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No CSV file provided'}), 400
        
        csv_file = request.files['file']
        if csv_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not csv_file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
        
        # Read CSV content
        csv_content = csv_file.read().decode('utf-8')
        
        # Process CSV
        csv_result = process_csv_upload(csv_content)
        
        if csv_result['success']:
            # Store CSV data
            upload_id = f"csv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            csv_uploads_store[upload_id] = {
                'sections': csv_result['sections'],
                'users': csv_result['users'],
                'user_email_alerts': csv_result['user_email_alerts'],
                'timestamp': datetime.now()
            }
            
            return jsonify({
                'success': True,
                'upload_id': upload_id,
                'sections': csv_result['sections'],
                'users': csv_result['users'],
                'user_email_alerts': csv_result['user_email_alerts'],
                'total_sections': csv_result['total_sections'],
                'users_with_alerts': csv_result['users_with_alerts']
            })
        else:
            return jsonify({
                'success': False,
                'error': csv_result['error']
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'CSV upload failed: {str(e)}'
        }), 500

@ome_blueprint.route('/process_user_alerts', methods=['POST'])
def process_user_alerts_route():
    """Process alerts for a specific user from uploaded CSV"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        upload_id = data.get('upload_id')
        selected_user = data.get('selected_user')
        start_date_str = data.get('start_date', '')
        end_date_str = data.get('end_date', '')
        
        if not upload_id or not selected_user:
            return jsonify({'error': 'Upload ID and selected user are required'}), 400
        
        if upload_id not in csv_uploads_store:
            return jsonify({'error': 'Upload not found'}), 404
        
        csv_data = csv_uploads_store[upload_id]
        user_email_alerts = csv_data.get('user_email_alerts', {})
        
        # Parse dates with default to last 7 days
        try:
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str)
            else:
                start_date = datetime.now() - timedelta(days=7)
            
            if end_date_str:
                end_date = datetime.fromisoformat(end_date_str)
            else:
                end_date = datetime.now()
                
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
        
        # Process alerts for the selected user
        result = process_user_alerts(user_email_alerts, selected_user, start_date, end_date)
        
        if result['success']:
            # Store results for export
            session_id = f"user_alerts_{selected_user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            metadata = {
                'user': selected_user,
                'processed_alerts': result['processed_alerts'],
                'total_alerts': result['total_alerts'],
                'successful_alerts': result['successful_alerts'],
                'timestamp': datetime.now().isoformat(),
                'alert_type': 'user_csv_alerts',
                'session_id': session_id
            }
            
            # Generate hash for URL sharing
            metadata['hash'] = generate_result_hash(metadata)
            metadata['share_url'] = f"#{metadata['hash']}"
            
            search_results_store[session_id] = {
                'results': result['results'],
                'metadata': metadata,
                'timestamp': datetime.now()
            }
            
            return jsonify({
                'success': True,
                'session_id': session_id,
                'user': selected_user,
                'results': result['results'],
                'processed_alerts': result['processed_alerts'],
                'total_alerts': result['total_alerts'],
                'successful_alerts': result['successful_alerts'],
                'total_results': result['total_results']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Alert processing failed: {str(e)}'
        }), 500

@ome_blueprint.route('/export_html/<session_id>')
def export_html(session_id):
    """Generate email-friendly HTML for results"""
    try:
        if session_id not in search_results_store:
            return jsonify({'error': 'Session not found'}), 404
        
        search_data = search_results_store[session_id]
        results = search_data['results']
        metadata = search_data['metadata']
        
        if not results:
            return jsonify({'error': 'No results to export'}), 400
        
        # Get relevance filter from query parameters
        min_relevance = request.args.get('min_relevance', 0, type=int)
        
        # Filter results by relevance score
        filtered_results = [result for result in results if (result.get('relevance_score', 0) >= min_relevance)]
        
        if not filtered_results:
            return jsonify({'error': f'No results found with relevance score ≥ {min_relevance}'}), 400
        
        # Generate email-friendly HTML with inline styles
        html_parts = []
        
        # Create table of contents
        toc_items = []
        for i, result in enumerate(filtered_results, 1):
            title = result.get('title', f'Article {i}')
            relevance_score = result.get('relevance_score', 0)
            source = result.get('source', 'Unknown')
            date_str = 'No date'
            if result.get('date'):
                try:
                    date_obj = datetime.fromisoformat(result['date'].replace('Z', '+00:00'))
                    date_str = date_obj.strftime('%b %d, %Y')
                except:
                    date_str = str(result.get('date', 'No date'))
            
            toc_items.append(f'''
            <tr style="border-bottom: 1px solid #e0e0e0;">
                <td style="padding: 12px 8px; font-size: 14px;">
                    <a href="#article-{i}" style="color: #3498db; text-decoration: none; font-weight: 500;">
                        {i}. {title[:80]}{'...' if len(title) > 80 else ''}
                    </a>
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 13px;">
                    <span style="background: {'#27ae60' if relevance_score >= 80 else '#f39c12' if relevance_score >= 60 else '#95a5a6'}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">
                        {relevance_score}/100
                    </span>
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 12px; color: #7f8c8d;">
                    {source}
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 12px; color: #7f8c8d;">
                    {date_str}
                </td>
            </tr>''')
        
        # Header
        html_parts.append('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pharma News Research Results</title>
    <style>
        .toc-link { scroll-behavior: smooth; }
        .article-section { scroll-margin-top: 20px; }
        .keyword-highlight { 
            background: #fff3cd; 
            padding: 1px 3px; 
            border-radius: 2px; 
            font-weight: 600; 
            display: inline;
        }
    </style>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
    
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">🔬 Pharma News Research Results</h1>
        <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">AI-Powered Pharmaceutical News Analysis</p>
    </div>
    
    <!-- Search Summary -->
    <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #667eea;">
        <h2 style="margin-top: 0; color: #2c3e50; font-size: 20px;">📊 Search Summary</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; font-weight: bold; color: #555;">Keywords:</td>
                <td style="padding: 8px; color: #333;">''' + ', '.join(metadata.get('keywords', [])) + '''</td>
            </tr>
            <tr style="background: #f8f9fa;">
                <td style="padding: 8px; font-weight: bold; color: #555;">Search Type:</td>
                <td style="padding: 8px; color: #333;">''' + metadata.get('search_type', 'standard').title() + '''</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold; color: #555;">Results Found:</td>
                <td style="padding: 8px; color: #333;"><strong>''' + str(len(results)) + ''' articles</strong></td>
            </tr>
            <tr style="background: #f8f9fa;">
                <td style="padding: 8px; font-weight: bold; color: #555;">Generated:</td>
                <td style="padding: 8px; color: #333;">''' + datetime.now().strftime('%B %d, %Y at %I:%M %p') + '''</td>
            </tr>
        </table>
    </div>
    
    <!-- Table of Contents -->
    <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #e74c3c;">
        <h2 style="margin-top: 0; color: #2c3e50; font-size: 20px;">📋 Table of Contents</h2>
        <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 15px;">Click on any title to jump directly to that article</p>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #e0e0e0;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0;">Article Title</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 80px;">Score</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 100px;">Source</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 100px;">Date</th>
                </tr>
            </thead>
            <tbody>''' + ''.join(toc_items) + '''
            </tbody>
        </table>
    </div>
    
    <!-- Results -->
    <div style="margin-bottom: 30px;">
        <h2 style="color: #2c3e50; font-size: 20px; margin-bottom: 20px;">📄 Detailed Results (sorted by relevance)</h2>
''')
        
        # Add each result
        for i, result in enumerate(filtered_results, 1):
            relevance_score = result.get('relevance_score', 0)
            
            # Score color
            if relevance_score >= 80:
                score_color = '#27ae60'  # Green
            elif relevance_score >= 60:
                score_color = '#f39c12'  # Orange
            else:
                score_color = '#95a5a6'  # Gray
            
            # Format date
            date_str = 'No date'
            if result.get('date'):
                try:
                    date_obj = datetime.fromisoformat(result['date'].replace('Z', '+00:00'))
                    date_str = date_obj.strftime('%B %d, %Y')
                except:
                    date_str = str(result.get('date', 'No date'))
            
            html_parts.append(f'''
        <!-- Result {i} -->
        <div id="article-{i}" class="article-section" style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid {score_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            
            <!-- Title and Score -->
            <div style="margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #2c3e50;">
                    <a href="{result.get('url', '#')}" style="color: #3498db; text-decoration: none;">{i}. {result.get('title', 'No title')}</a>
                </h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <span style="background: {score_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                        Relevance: {relevance_score}/100
                    </span>
                    <span style="background: #e74c3c; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px;">
                        {result.get('article_type', 'unknown').title()}
                    </span>
                    <span style="color: #7f8c8d; font-size: 13px;">
                        📅 {date_str}
                    </span>
                    <span style="color: #7f8c8d; font-size: 13px;">
                        📰 {result.get('source', 'Unknown')}
                    </span>
                </div>
            </div>
            
            <!-- Summary -->
            <div style="margin-bottom: 15px; padding: 15px; background: #f8f9fa; border-radius: 6px; font-size: 14px; line-height: 1.6;">
                {result.get('highlighted_content', result.get('summary', result.get('content', 'No summary available')[:300] + '...'))}
            </div>
            
            <!-- Why Relevant -->
            {f"""<div style="margin-bottom: 12px; padding: 12px; background: #d4edda; border-left: 3px solid #28a745; border-radius: 4px; font-size: 13px;">
                <strong style="color: #155724;">Why it's relevant:</strong><br/>
                {result.get('relevance_reason', 'No reason provided')}
            </div>""" if result.get('relevance_reason') else ''}
            
            <!-- Keywords -->
            {f"""<div style="margin-bottom: 12px;">
                <strong style="font-size: 13px; color: #555;">Keywords found:</strong><br/>
                <div style="margin-top: 6px;">
                    {''.join([f'<span style="background: #3498db; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-right: 6px; margin-bottom: 6px; display: inline-block;">{kw}</span>' for kw in result.get('mentioned_keywords', [])])}
                </div>
            </div>""" if result.get('mentioned_keywords') else ''}
            
            <!-- Pertinent Keywords -->
            {f"""<div style="margin-bottom: 12px;">
                <strong style="font-size: 13px; color: #555;">Related terms:</strong><br/>
                <div style="margin-top: 6px;">
                    {''.join([f'<span style="background: #e67e22; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-right: 6px; margin-bottom: 6px; display: inline-block;">{kw}</span>' for kw in result.get('pertinent_keywords', [])])}
                </div>
            </div>""" if result.get('pertinent_keywords') else ''}
            
            <!-- Clinical Significance -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #fff3cd; border-left: 3px solid #ffc107; border-radius: 4px; font-size: 13px;">
                <strong style="color: #856404;">Clinical Significance:</strong><br/>
                {result.get('clinical_significance')}
            </div>""" if result.get('clinical_significance') and result.get('clinical_significance') != 'None' else ''}
            
            <!-- Regulatory Impact -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #d1ecf1; border-left: 3px solid #17a2b8; border-radius: 4px; font-size: 13px;">
                <strong style="color: #0c5460;">Regulatory Impact:</strong><br/>
                {result.get('regulatory_impact')}
            </div>""" if result.get('regulatory_impact') and result.get('regulatory_impact') != 'None' else ''}
            
            <!-- Market Impact -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #d4edda; border-left: 3px solid #28a745; border-radius: 4px; font-size: 13px;">
                <strong style="color: #155724;">Market Impact:</strong><br/>
                {result.get('market_impact')}
            </div>""" if result.get('market_impact') and result.get('market_impact') != 'None' else ''}
            
            <!-- Link -->
            <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;">
                <a href="{result.get('url', '#')}" style="color: #3498db; text-decoration: none; font-size: 13px;">
                    🔗 View Full Article →
                </a>
            </div>
            
        </div>
''')
        
        # Footer
        html_parts.append('''
    </div>
    
    <!-- Footer -->
    <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px; border-top: 2px solid #e0e0e0; margin-top: 30px;">
        <p style="margin: 5px 0;">Generated by <strong>Pharma News Research Agent</strong></p>
        <p style="margin: 5px 0;">AI-powered pharmaceutical news analysis with multi-source data collection</p>
        <p style="margin: 5px 0;">Powered by GPT-4, PubMed, Exa, Tavily, and NewsAPI</p>
    </div>
    
</body>
</html>
''')
        
        html_content = ''.join(html_parts)
        
        # Return as downloadable file or JSON
        download = request.args.get('download', 'false').lower() == 'true'
        
        if download:
            # Return as downloadable HTML file
            keywords_str = '_'.join(metadata.get('keywords', ['results'])[:3])
            filename = f"pharma_research_{keywords_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            return send_file(
                io.BytesIO(html_content.encode('utf-8')),
                mimetype='text/html',
                as_attachment=True,
                download_name=filename
            )
        else:
            # Return HTML content for copying
            return jsonify({
                'success': True,
                'html': html_content,
                'result_count': len(filtered_results),
                'total_results': len(results),
                'filtered_by_relevance': min_relevance
            })
        
    except Exception as e:
        print(f"HTML export error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'HTML export failed: {str(e)}'
        }), 500

@ome_blueprint.route('/export_batch_html/<user>')
def export_batch_html(user):
    """Generate email-friendly HTML for batch processing results"""
    try:
        # Find the latest batch processing results for this user from search_results_store
        user_sessions = []
        for session_id, data in search_results_store.items():
            if (session_id.startswith('user_alerts_') and 
                data.get('metadata', {}).get('user') == user):
                user_sessions.append((session_id, data))
        
        if not user_sessions:
            return jsonify({'error': 'No batch results found for this user'}), 404
        
        # Get the most recent session
        latest_session_id, batch_data = max(user_sessions, key=lambda x: x[1].get('timestamp', datetime.min))
        results = batch_data['results']
        metadata = batch_data['metadata']
        
        if not results:
            return jsonify({'error': 'No results to export'}), 400
        
        # Get relevance filter from query parameters
        min_relevance = request.args.get('min_relevance', 0, type=int)
        
        # Filter results by relevance score
        filtered_results = [result for result in results if (result.get('relevance_score', 0) >= min_relevance)]
        
        if not filtered_results:
            return jsonify({'error': f'No results found with relevance score ≥ {min_relevance}'}), 400
        
        # Generate email-friendly HTML with inline styles (same format as single search)
        html_parts = []
        
        # Create table of contents
        toc_items = []
        for i, result in enumerate(filtered_results, 1):
            title = result.get('title', f'Article {i}')
            relevance_score = result.get('relevance_score', 0)
            source = result.get('source', 'Unknown')
            date_str = 'No date'
            if result.get('date'):
                try:
                    date_obj = datetime.fromisoformat(result['date'].replace('Z', '+00:00'))
                    date_str = date_obj.strftime('%b %d, %Y')
                except:
                    date_str = str(result.get('date', 'No date'))
            
            toc_items.append(f'''
            <tr style="border-bottom: 1px solid #e0e0e0;">
                <td style="padding: 12px 8px; font-size: 14px;">
                    <a href="#article-{i}" style="color: #3498db; text-decoration: none; font-weight: 500;">
                        {i}. {title[:80]}{'...' if len(title) > 80 else ''}
                    </a>
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 13px;">
                    <span style="background: {'#27ae60' if relevance_score >= 80 else '#f39c12' if relevance_score >= 60 else '#95a5a6'}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">
                        {relevance_score}/100
                    </span>
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 12px; color: #7f8c8d;">
                    {source}
                </td>
                <td style="padding: 12px 8px; text-align: center; font-size: 12px; color: #7f8c8d;">
                    {date_str}
                </td>
            </tr>''')
        
        # Header
        html_parts.append('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batch Pharma News Research Results</title>
    <style>
        .toc-link { scroll-behavior: smooth; }
        .article-section { scroll-margin-top: 20px; }
        .keyword-highlight { 
            background: #fff3cd; 
            padding: 1px 3px; 
            border-radius: 2px; 
            font-weight: 600; 
            display: inline;
        }
    </style>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
    
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">🔬 Batch Pharma News Research Results</h1>
        <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">AI-Powered Pharmaceutical News Analysis - Batch Processing</p>
    </div>
    
    <!-- Search Summary -->
    <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #667eea;">
        <h2 style="margin-top: 0; color: #2c3e50; font-size: 20px;">📊 Batch Processing Summary</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; font-weight: bold; color: #555;">User:</td>
                <td style="padding: 8px; color: #333;">''' + metadata.get('user', 'Unknown') + '''</td>
            </tr>
            <tr style="background: #f8f9fa;">
                <td style="padding: 8px; font-weight: bold; color: #555;">Total Alerts:</td>
                <td style="padding: 8px; color: #333;">''' + str(metadata.get('total_alerts', 0)) + '''</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold; color: #555;">Successful Alerts:</td>
                <td style="padding: 8px; color: #333;">''' + str(metadata.get('successful_alerts', 0)) + '''</td>
            </tr>
            <tr style="background: #f8f9fa;">
                <td style="padding: 8px; font-weight: bold; color: #555;">Results Found:</td>
                <td style="padding: 8px; color: #333;"><strong>''' + str(len(results)) + ''' articles</strong></td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold; color: #555;">Generated:</td>
                <td style="padding: 8px; color: #333;">''' + datetime.now().strftime('%B %d, %Y at %I:%M %p') + '''</td>
            </tr>
        </table>
    </div>
    
    <!-- Table of Contents -->
    <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #e74c3c;">
        <h2 style="margin-top: 0; color: #2c3e50; font-size: 20px;">📋 Table of Contents</h2>
        <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 15px;">Click on any title to jump directly to that article</p>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #e0e0e0;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0;">Article Title</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 80px;">Score</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 100px;">Source</th>
                    <th style="padding: 12px 8px; text-align: center; font-weight: bold; color: #2c3e50; border-bottom: 2px solid #e0e0e0; width: 100px;">Date</th>
                </tr>
            </thead>
            <tbody>''' + ''.join(toc_items) + '''
            </tbody>
        </table>
    </div>
    
    <!-- Results -->
    <div style="margin-bottom: 30px;">
        <h2 style="color: #2c3e50; font-size: 20px; margin-bottom: 20px;">📄 Detailed Results (sorted by relevance)</h2>
''')
        
        # Add each result (same format as single search)
        for i, result in enumerate(filtered_results, 1):
            relevance_score = result.get('relevance_score', 0)
            
            # Score color
            if relevance_score >= 80:
                score_color = '#27ae60'  # Green
            elif relevance_score >= 60:
                score_color = '#f39c12'  # Orange
            else:
                score_color = '#95a5a6'  # Gray
            
            # Format date
            date_str = 'No date'
            if result.get('date'):
                try:
                    date_obj = datetime.fromisoformat(result['date'].replace('Z', '+00:00'))
                    date_str = date_obj.strftime('%B %d, %Y')
                except:
                    date_str = str(result.get('date', 'No date'))
            
            html_parts.append(f'''
        <!-- Result {i} -->
        <div id="article-{i}" class="article-section" style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid {score_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            
            <!-- Title and Score -->
            <div style="margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #2c3e50;">
                    <a href="{result.get('url', '#')}" style="color: #3498db; text-decoration: none;">{i}. {result.get('title', 'No title')}</a>
                </h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <span style="background: {score_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                        Relevance: {relevance_score}/100
                    </span>
                    <span style="background: #e74c3c; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px;">
                        {result.get('article_type', 'unknown').title()}
                    </span>
                    <span style="color: #7f8c8d; font-size: 13px;">
                        📅 {date_str}
                    </span>
                    <span style="color: #7f8c8d; font-size: 13px;">
                        📰 {result.get('source', 'Unknown')}
                    </span>
                </div>
            </div>
            
            <!-- Summary -->
            <div style="margin-bottom: 15px; padding: 15px; background: #f8f9fa; border-radius: 6px; font-size: 14px; line-height: 1.6;">
                {result.get('highlighted_content', result.get('summary', result.get('content', 'No summary available')[:300] + '...'))}
            </div>
            
            <!-- Why Relevant -->
            {f"""<div style="margin-bottom: 12px; padding: 12px; background: #d4edda; border-left: 3px solid #28a745; border-radius: 4px; font-size: 13px;">
                <strong style="color: #155724;">Why it's relevant:</strong><br/>
                {result.get('relevance_reason', 'No reason provided')}
            </div>""" if result.get('relevance_reason') else ''}
            
            <!-- Keywords -->
            {f"""<div style="margin-bottom: 12px;">
                <strong style="font-size: 13px; color: #555;">Keywords found:</strong><br/>
                <div style="margin-top: 6px;">
                    {''.join([f'<span style="background: #3498db; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-right: 6px; margin-bottom: 6px; display: inline-block;">{kw}</span>' for kw in result.get('mentioned_keywords', [])])}
                </div>
            </div>""" if result.get('mentioned_keywords') else ''}
            
            <!-- Pertinent Keywords -->
            {f"""<div style="margin-bottom: 12px;">
                <strong style="font-size: 13px; color: #555;">Related terms:</strong><br/>
                <div style="margin-top: 6px;">
                    {''.join([f'<span style="background: #e67e22; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-right: 6px; margin-bottom: 6px; display: inline-block;">{kw}</span>' for kw in result.get('pertinent_keywords', [])])}
                </div>
            </div>""" if result.get('pertinent_keywords') else ''}
            
            <!-- Clinical Significance -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #fff3cd; border-left: 3px solid #ffc107; border-radius: 4px; font-size: 13px;">
                <strong style="color: #856404;">Clinical Significance:</strong><br/>
                {result.get('clinical_significance')}
            </div>""" if result.get('clinical_significance') and result.get('clinical_significance') != 'None' else ''}
            
            <!-- Regulatory Impact -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #d1ecf1; border-left: 3px solid #17a2b8; border-radius: 4px; font-size: 13px;">
                <strong style="color: #0c5460;">Regulatory Impact:</strong><br/>
                {result.get('regulatory_impact')}
            </div>""" if result.get('regulatory_impact') and result.get('regulatory_impact') != 'None' else ''}
            
            <!-- Market Impact -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #d4edda; border-left: 3px solid #28a745; border-radius: 4px; font-size: 13px;">
                <strong style="color: #155724;">Market Impact:</strong><br/>
                {result.get('market_impact')}
            </div>""" if result.get('market_impact') and result.get('market_impact') != 'None' else ''}
            
            <!-- Alert Context -->
            {f"""<div style="margin-bottom: 12px; padding: 10px; background: #e2e3e5; border-left: 3px solid #6c757d; border-radius: 4px; font-size: 13px;">
                <strong style="color: #495057;">Alert Context:</strong><br/>
                {result.get('alert_context', {}).get('alert_title', 'Unknown')} - {result.get('alert_context', {}).get('subheader', 'Unknown')}
            </div>""" if result.get('alert_context') else ''}
            
            <!-- Link -->
            <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;">
                <a href="{result.get('url', '#')}" style="color: #3498db; text-decoration: none; font-size: 13px;">
                    🔗 View Full Article →
                </a>
            </div>
            
        </div>
''')
        
        # Footer
        html_parts.append('''
    </div>
    
    <!-- Footer -->
    <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px; border-top: 2px solid #e0e0e0; margin-top: 30px;">
        <p style="margin: 5px 0;">Generated by <strong>Pharma News Research Agent</strong></p>
        <p style="margin: 5px 0;">AI-powered pharmaceutical news analysis with multi-source data collection</p>
        <p style="margin: 5px 0;">Powered by GPT-4, PubMed, Exa, Tavily, and NewsAPI</p>
    </div>
    
</body>
</html>
''')
        
        html_content = ''.join(html_parts)
        
        # Return as downloadable file or JSON
        download = request.args.get('download', 'false').lower() == 'true'
        
        if download:
            # Return as downloadable HTML file
            filename = f"batch_pharma_research_{user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            return send_file(
                io.BytesIO(html_content.encode('utf-8')),
                mimetype='text/html',
                as_attachment=True,
                download_name=filename
            )
        else:
            # Return HTML content for copying
            return jsonify({
                'success': True,
                'html': html_content,
                'result_count': len(filtered_results),
                'total_results': len(results),
                'filtered_by_relevance': min_relevance
            })
        
    except Exception as e:
        print(f"Batch HTML export error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Batch HTML export failed: {str(e)}'
        }), 500

@ome_blueprint.route('/global_history')
def get_global_history_route():
    """Get all recent alerts processed (both batch and single search)"""
    try:
        history = get_global_history()
        
        return jsonify({
            'success': True,
            'history': history,
            'total_entries': len(history)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get global history: {str(e)}'
        }), 500

@ome_blueprint.route('/result_by_hash/<hash_id>')
def get_result_by_hash_route(hash_id):
    """Get result by hash ID for URL sharing"""
    try:
        result = get_result_by_hash(hash_id)
        
        if not result:
            return jsonify({'error': 'Result not found'}), 404
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get result: {str(e)}'
        }), 500

@ome_blueprint.route('/batch_history/<user>')
def get_batch_history(user):
    """Get batch processing history for a user"""
    try:
        history = get_user_batch_history(user)
        
        return jsonify({
            'success': True,
            'user': user,
            'history': history,
            'total_entries': len(history)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get batch history: {str(e)}'
        }), 500

@ome_blueprint.route('/batch_history_html/<user>/<filename>')
def get_batch_history_html(user, filename):
    """Get HTML content for a specific batch processing result"""
    try:
        user_dir = BATCH_RESULTS_DIR / user
        html_file = user_dir / filename
        
        if not html_file.exists():
            return jsonify({'error': 'HTML file not found'}), 404
        
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return html_content, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get HTML content: {str(e)}'
        }), 500

@ome_blueprint.route('/health')
def health_check():
    """Health check endpoint with API status"""
    health_data = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'max_keywords': Config.MAX_KEYWORDS if hasattr(Config, 'MAX_KEYWORDS') else 100,
            'max_results_per_source': Config.MAX_RESULTS_PER_SOURCE if hasattr(Config, 'MAX_RESULTS_PER_SOURCE') else 50
        },
        'agentic_workflow': {
            'available': AGENT_AVAILABLE,
            'initialized': pharma_agent is not None
        }
    }
    
    # Add API status if agent is available
    if AGENT_AVAILABLE and pharma_agent:
        health_data['api_status'] = pharma_agent.api_status
    
    return jsonify(health_data)

