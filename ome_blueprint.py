"""
Pharma News Research Agent - Flask Blueprint
Real API integration with agentic workflow for pharmaceutical news research

This blueprint can be integrated into any Flask application at the /OME/ endpoint.

Usage:
    from ome_blueprint import ome_blueprint
    
    app = Flask(__name__)
    app.register_blueprint(ome_blueprint, url_prefix='/OME')
"""

import os
import sys
import json
import csv
import io
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests
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
    """Search NewsAPI for news articles (enhanced demo version with pharma focus)"""
    # Enhanced sample data focused on pharma news
    pharma_sources = [
        "Reuters Health", "Medical News Today", "PharmaTimes", "FiercePharma", 
        "BioPharma Dive", "Pharmaceutical Technology", "Drug Discovery Today"
    ]
    
    sample_results = []
    for i in range(min(max_results, 8)):  # Limit to 8 realistic samples
        keyword = keywords[0] if keywords else "pharmaceutical"
        source = pharma_sources[i % len(pharma_sources)]
        
        # Create more realistic pharma news titles
        titles = [
            f"New {keyword} Treatment Shows Promise in Clinical Trials",
            f"FDA Approves Expanded Use of {keyword} for Additional Indications",
            f"Pharmaceutical Company Reports Positive Results for {keyword} Study",
            f"Research Reveals New Mechanism of Action for {keyword}",
            f"Global Market for {keyword} Expected to Reach $X Billion by 2025",
            f"Patient Outcomes Improve with Novel {keyword} Formulation",
            f"Regulatory Update: {keyword} Receives Fast Track Designation",
            f"Investment in {keyword} Development Reaches Record High"
        ]
        
        title = titles[i % len(titles)]
        
        # Create more detailed content
        content = f"""
        Recent developments in {keyword} research have shown significant progress in clinical applications. 
        The pharmaceutical industry continues to invest heavily in {keyword} development, with several 
        companies reporting positive results from ongoing studies. Regulatory agencies are closely 
        monitoring the safety and efficacy profiles of {keyword} treatments, with some products 
        receiving expedited review status. Market analysts predict continued growth in the {keyword} 
        sector, driven by increasing patient demand and technological advances in drug delivery systems.
        """.strip()
        
        result = {
            'title': title,
            'content': content,
            'url': f'https://example-pharma-news.com/{keyword.lower().replace(" ", "-")}-article-{i+1}',
            'date': (datetime.now() - timedelta(days=i)).isoformat(),  # Stagger dates
            'source': source
        }
        sample_results.append(result)
    
    return sample_results

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
        
        for row in csv_reader:
            # Extract required columns
            aliases = row.get('aliases', '').strip()
            keywords = row.get('keywords', '').strip()
            search_type = row.get('search_type', 'standard').strip()
            subheader = row.get('subheader', '').strip()
            header = row.get('header', '').strip()
            user = row.get('user', '').strip()
            
            # Combine aliases and keywords, make unique
            all_keywords = []
            if aliases:
                all_keywords.extend([alias.strip() for alias in aliases.split(',') if alias.strip()])
            if keywords:
                all_keywords.extend([kw.strip() for kw in keywords.split(',') if kw.strip()])
            
            # Remove duplicates and empty strings
            unique_keywords = list(dict.fromkeys([kw for kw in all_keywords if kw]))
            
            if unique_keywords:  # Only add if we have keywords
                section = {
                    'aliases': aliases,
                    'keywords': keywords,
                    'combined_keywords': unique_keywords,
                    'search_type': search_type,
                    'subheader': subheader,
                    'header': header,
                    'user': user,
                    'section_id': f"{user}_{header}_{subheader}".replace(' ', '_').replace('/', '_')
                }
                sections.append(section)
                users.add(user)
        
        return {
            'success': True,
            'sections': sections,
            'users': list(users),
            'total_sections': len(sections)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'CSV processing failed: {str(e)}',
            'sections': [],
            'users': [],
            'total_sections': 0
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
                workflow_result = pharma_agent.execute_research_workflow(
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    search_type=search_type
                )
                
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
                    Upload a CSV file with columns: aliases, keywords, search_type, subheader, header, user
                </div>

                <div class="upload-area" id="upload-area">
                    <div style="font-size: 48px; margin-bottom: 10px;">📄</div>
                    <p><strong>Click to upload</strong> or drag and drop</p>
                    <p style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">CSV files only</p>
                    <input type="file" id="csv-file" accept=".csv" style="display: none;">
                </div>

                <div id="batch-results" style="margin-top: 20px;"></div>
            </div>

            <!-- Results History Tab -->
            <div class="tab-content" id="tab-results">
                <div class="alert alert-info">
                    Previous search results will appear here
                </div>
                <div id="history-container"></div>
            </div>
        </div>

        <!-- Right Sidebar - Filters & Activity Panel -->
        <div class="right-sidebar">
            <!-- Relevance Score Filter -->
            <div class="sidebar-section" id="relevance-filter-section" style="display:none;">
                <h3>🎚️ Relevance Filter</h3>
                <div style="margin-bottom: 10px;">
                    <label style="font-size: 12px; color: #7f8c8d;">Min Score: <span id="slider-value">50</span></label>
                    <input type="range" id="relevance-slider" min="0" max="100" value="50" 
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
            });
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
        let currentMinScore = 50;

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

            let html = '<div class="alert alert-success">Found ' + data.results.length + ' results from ' + 
                      (data.results_by_source ? Object.keys(data.results_by_source).filter(k => k !== 'metadata').length : 'multiple') + 
                      ' sources</div>';

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
                    addActivity('CSV processed: ' + data.sections.length + ' sections', 'success');
                    document.getElementById('batch-results').innerHTML = `
                        <div class="alert alert-success">
                            CSV uploaded successfully: ${data.sections.length} sections found
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

        // Mark APIs as configured (placeholder - should come from backend)
        document.getElementById('api-openai').innerHTML = '✅';
        document.getElementById('api-tavily').innerHTML = '✅';
        document.getElementById('api-exa').innerHTML = '✅';
        document.getElementById('api-newsapi').innerHTML = '✅';
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
                workflow_result = pharma_agent.execute_research_workflow(
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    search_type=search_type,
                    search_engines=search_engines
                )
            
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
        search_results_store[session_id] = {
            'results': processed_results,
            'metadata': {
                'keywords': keywords,
                'search_type': search_type,
                'alert_name': alert_name,
                'section_name': section_name,
                'timestamp': datetime.now().isoformat()
            },
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
                'timestamp': datetime.now()
            }
            
            return jsonify({
                'success': True,
                'upload_id': upload_id,
                'sections': csv_result['sections'],
                'users': csv_result['users'],
                'total_sections': csv_result['total_sections']
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

