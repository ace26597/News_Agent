"""
Pharma News Research Agent - Flask Application
Real API integration with agentic workflow for pharmaceutical news research
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

# Try to import Flask, install if not available
try:
    from flask import Flask, render_template_string, request, jsonify, send_file
except ImportError:
    print("Installing Flask...")
    os.system("pip install flask")
    from flask import Flask, render_template_string, request, jsonify, send_file

# Import our agentic workflow
try:
    from pharma_agent import PharmaNewsAgent
    from config import Config
    AGENT_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Agentic workflow not available: {e}")
    print("INFO: Falling back to basic search functionality")
    AGENT_AVAILABLE = False

# Configuration
if not AGENT_AVAILABLE:
    class Config:
        MAX_KEYWORDS = 100
        MAX_RESULTS_PER_SOURCE = 50

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'

# Initialize Pharma News Agent (if available)
pharma_agent = None
if AGENT_AVAILABLE:
    try:
        pharma_agent = PharmaNewsAgent()
        print("Pharma News Agent initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Pharma News Agent: {e}")
        AGENT_AVAILABLE = False

# In-memory storage for search results
search_results_store = {}

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

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical News Search</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
        }
        .search-form {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        .form-group {
            margin-bottom: 1rem;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: bold;
        }
        input, textarea, select {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 1rem;
        }
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        .form-row {
            display: flex;
            gap: 1rem;
        }
        .form-row .form-group {
            flex: 1;
        }
        .search-btn {
            background: #667eea;
            color: white;
            padding: 1rem 2rem;
            border: none;
            border-radius: 5px;
            font-size: 1.1rem;
            cursor: pointer;
            width: 100%;
        }
        .search-btn:hover {
            background: #5a6fd8;
        }
        .search-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .loading {
            text-align: center;
            padding: 2rem;
            font-size: 1.2rem;
            color: #667eea;
        }
        .results {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .result-item {
            border: 1px solid #eee;
            padding: 1.5rem;
            margin-bottom: 1rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .result-title {
            font-size: 1.2rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }
        .result-title a {
            color: #667eea;
            text-decoration: none;
        }
        .result-title a:hover {
            text-decoration: underline;
        }
        .result-summary {
            margin-bottom: 1rem;
            line-height: 1.6;
        }
        .result-meta {
            display: flex;
            gap: 1rem;
            font-size: 0.9rem;
            color: #666;
        }
        .relevance-score {
            background: #667eea;
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            font-weight: bold;
        }
        .download-btn {
            background: #28a745;
            color: white;
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin-bottom: 1rem;
        }
        .download-btn:hover {
            background: #218838;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 1rem;
            border-radius: 5px;
            margin-bottom: 1rem;
        }
        .success {
            background: #d4edda;
            color: #155724;
            padding: 1rem;
            border-radius: 5px;
            margin-bottom: 1rem;
        }
        .source-section {
            margin-bottom: 1.5rem;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
        }
        .source-header {
            background: #f8f9fa;
            padding: 1rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #ddd;
            transition: background-color 0.3s ease;
        }
        .source-header:hover {
            background: #e9ecef;
        }
        .source-header h3 {
            margin: 0;
            color: #495057;
            font-size: 1.2rem;
        }
        .expand-icon {
            font-size: 1.2rem;
            color: #667eea;
            transition: transform 0.3s ease;
        }
        .source-content {
            padding: 1rem;
            background: white;
        }
        .source-content .result-item {
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #f0f0f0;
        }
        .source-content .result-item:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }
        .source-description {
            margin: 0.5rem 0 0 0;
            color: #6c757d;
            font-size: 0.9rem;
            font-style: italic;
        }
        .no-results {
            color: #6c757d;
            font-style: italic;
            text-align: center;
            padding: 2rem;
        }
        .ai-insights, .ai-significance {
            margin-top: 0.5rem;
            padding: 0.5rem;
            background: #f8f9fa;
            border-left: 3px solid #667eea;
            border-radius: 0 4px 4px 0;
            font-size: 0.9rem;
        }
        .ai-insights {
            border-left-color: #28a745;
        }
        .ai-significance {
            border-left-color: #ffc107;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Pharma News Research Agent</h1>
        <p>Deep research across PubMed, pharmaceutical news, and clinical sources with AI-powered curation</p>
    </div>

    <form class="search-form" id="searchForm">
        <div class="form-group">
            <label for="keywords">Keywords (comma-separated, max 100)</label>
            <textarea id="keywords" name="keywords" rows="3" placeholder="e.g., orgovyx, prostate cancer, diabetes, insulin, clinical trial, FDA approval..." required></textarea>
            <div id="keywordCount" style="font-size: 0.9rem; color: #666; margin-top: 0.25rem;">0 keywords entered</div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label for="startDate">Start Date</label>
                <input type="date" id="startDate" name="startDate">
            </div>
            <div class="form-group">
                <label for="endDate">End Date</label>
                <input type="date" id="endDate" name="endDate">
            </div>
        </div>

        <div class="form-group">
            <label for="searchType">Search Type</label>
            <select id="searchType" name="searchType">
                <option value="standard">Standard - Any keyword in article</option>
                <option value="title">Title - Keyword in article title</option>
                <option value="co-occurrence">Co-occurrence - 2+ keywords together</option>
            </select>
        </div>

        <button type="submit" class="search-btn" id="searchBtn">Research Pharma Sources</button>
    </form>

    <div id="loading" class="loading" style="display: none;">
        Researching pharma sources... Analyzing PubMed, clinical trials, and pharmaceutical news...
    </div>

    <div id="results" class="results" style="display: none;">
        <h2>Search Results</h2>
        <div id="resultsContent"></div>
    </div>

    <script>
        // Set default dates
        const today = new Date();
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(today.getDate() - 7);
        
        document.getElementById('endDate').value = today.toISOString().split('T')[0];
        document.getElementById('startDate').value = sevenDaysAgo.toISOString().split('T')[0];

        // Update keyword count
        document.getElementById('keywords').addEventListener('input', function() {
            const keywords = this.value.split(',').filter(kw => kw.trim());
            const count = document.getElementById('keywordCount');
            count.textContent = `${keywords.length} keywords entered`;
            
            if (keywords.length > 100) {
                count.style.color = '#dc3545';
                count.textContent = `${keywords.length} keywords (max 100)`;
            } else {
                count.style.color = '#666';
            }
        });

        // Handle form submission
        document.getElementById('searchForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const keywords = document.getElementById('keywords').value.trim();
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const searchType = document.getElementById('searchType').value;
            
            if (!keywords) {
                alert('Please enter at least one keyword');
                return;
            }
            
            const keywordList = keywords.split(',').filter(kw => kw.trim());
            if (keywordList.length > 100) {
                alert('Maximum 100 keywords allowed');
                return;
            }
            
            if (startDate && endDate && startDate > endDate) {
                alert('Start date must be before end date');
                return;
            }
            
            // Show loading
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';
            document.getElementById('searchBtn').disabled = true;
            
            try {
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        keywords: keywords,
                        start_date: startDate,
                        end_date: endDate,
                        search_type: searchType
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    displayResults(result);
                } else {
                    showError(result.error || 'Search failed');
                }
            } catch (error) {
                showError('Network error. Please check your connection and try again.');
            } finally {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('searchBtn').disabled = false;
            }
        });

        function displayResults(result) {
            const resultsDiv = document.getElementById('results');
            const contentDiv = document.getElementById('resultsContent');
            
            if (result.results.length === 0) {
                contentDiv.innerHTML = '<p>No results found. Try adjusting your keywords or search criteria.</p>';
            } else {
                // Use the pre-organized results_by_source from the backend
                const resultsBySource = result.results_by_source || {};
                const metadata = resultsBySource.metadata || {};
                
                let html = `
                    <div style="margin-bottom: 1rem;">
                        <button class="download-btn" onclick="downloadCSV('${result.session_id}')">Download CSV</button>
                        <span style="margin-left: 1rem; color: #666;">
                            Found ${result.total_found} articles, ${result.total_filtered} after filtering, ${result.total_processed} final results
                        </span>
                    </div>
                `;
                
                // Define source configurations
                const sourceConfigs = [
                    {
                        key: 'pubmed',
                        title: 'PubMed Medical Literature',
                        description: 'Peer-reviewed medical research and clinical studies',
                        icon: '📚',
                        results: resultsBySource.pubmed || []
                    },
                    {
                        key: 'tavily',
                        title: 'Tavily Web Search',
                        description: 'Enhanced web search for pharmaceutical news and updates',
                        icon: '🔍',
                        results: resultsBySource.tavily || []
                    },
                    {
                        key: 'openai_curated',
                        title: 'AI-Curated Insights',
                        description: 'Intelligently curated and analyzed results with AI insights',
                        icon: '🧠',
                        results: resultsBySource.openai_curated || []
                    }
                ];
                
                // Create expandable sections for each source
                sourceConfigs.forEach(sourceConfig => {
                    const sourceResults = sourceConfig.results;
                    const sourceId = sourceConfig.key;
                    
                    html += `
                        <div class="source-section">
                            <div class="source-header" onclick="toggleSource('${sourceId}')">
                                <h3>${sourceConfig.icon} ${sourceConfig.title} (${sourceResults.length} results)</h3>
                                <p class="source-description">${sourceConfig.description}</p>
                                <span class="expand-icon" id="icon-${sourceId}">▼</span>
                            </div>
                            <div class="source-content" id="content-${sourceId}" style="display: none;">
                    `;
                    
                    if (sourceResults.length === 0) {
                        html += `<p class="no-results">No results found from this source.</p>`;
                    } else {
                        sourceResults.forEach((item, index) => {
                            const date = new Date(item.date).toLocaleDateString();
                            html += `
                                <div class="result-item">
                                    <div class="result-title">
                                        <a href="${item.url}" target="_blank">${item.title}</a>
                                    </div>
                                    <div class="result-summary">${item.highlighted_summary}</div>
                                    <div class="result-meta">
                                        <span><strong>${item.source}</strong></span>
                                        <span>Date: ${date}</span>
                                        <span class="relevance-score">Score: ${item.relevance_score}</span>
                                    </div>
                                    ${item.ai_insights ? `<div class="ai-insights"><strong>AI Insights:</strong> ${item.ai_insights}</div>` : ''}
                                    ${item.ai_significance ? `<div class="ai-significance"><strong>Clinical Significance:</strong> ${item.ai_significance}</div>` : ''}
                                </div>
                            `;
                        });
                    }
                    
                    html += `
                            </div>
                        </div>
                    `;
                });
                
                contentDiv.innerHTML = html;
            }
            
            resultsDiv.style.display = 'block';
        }
        
        function toggleSource(sourceId) {
            const content = document.getElementById(`content-${sourceId}`);
            const icon = document.getElementById(`icon-${sourceId}`);
            
            if (content.style.display === 'none') {
                content.style.display = 'block';
                icon.textContent = '▲';
            } else {
                content.style.display = 'none';
                icon.textContent = '▼';
            }
        }

        function showError(message) {
            const resultsDiv = document.getElementById('results');
            const contentDiv = document.getElementById('resultsContent');
            
            contentDiv.innerHTML = `<div class="error">ERROR: ${message}</div>`;
            resultsDiv.style.display = 'block';
        }

        function downloadCSV(sessionId) {
            window.open(`/download/${sessionId}`, '_blank');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the main search interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/search', methods=['POST'])
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
            print("Using agentic workflow for enhanced research...")
            workflow_result = pharma_agent.execute_research_workflow(
                keywords=keywords,
                start_date=start_date,
                end_date=end_date,
                search_type=search_type
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
                'timestamp': datetime.now().isoformat()
            },
            'timestamp': datetime.now()
        }
        
        # Clean up old sessions
        if len(search_results_store) > 10:
            oldest_session = min(search_results_store.keys())
            del search_results_store[oldest_session]
        
        return jsonify({
            'success': True,
            'results': processed_results,
            'results_by_source': results_by_source,
            'total_found': total_found,
            'total_filtered': total_filtered,
            'total_processed': total_processed,
            'session_id': session_id,
            'search_metadata': {
                'keywords': keywords,
                'search_type': search_type,
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

@app.route('/download/<session_id>')
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

@app.route('/health')
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

if __name__ == '__main__':
    print("=" * 60)
    print("Pharma News Research Agent")
    print("=" * 60)
    print("Starting server...")
    
    if AGENT_AVAILABLE and pharma_agent:
        print("Agentic workflow enabled with real API integration")
        print("Available APIs:")
        api_status = pharma_agent.api_status
        for api, status in api_status.items():
            status_icon = "OK" if status else "NO"
            print(f"   {status_icon} {api.replace('_', ' ').title()}")
    else:
        print("Agentic workflow not available - using basic search")
        print("Add API keys to .env file for enhanced functionality")
    
    print("Open your browser and go to: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        app.run(host='127.0.0.1', port=5000, debug=False)
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        print("Make sure port 5000 is not in use by another application")
