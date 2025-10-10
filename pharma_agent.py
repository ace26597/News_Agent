"""
Agentic Workflow for Pharma News Research
Orchestrates real API calls, data curation, and intelligent processing
"""

import logging
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PharmaNewsAgent:
    """Main agentic workflow orchestrator for pharma news research"""
    
    def __init__(self):
        self.config = Config()
        self.api_status = self.config.get_api_status()
        logger.info(f"API Status: {self.api_status}")
        
        # Initialize API clients
        self.openai_client = None
        if self.api_status['openai_configured']:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.config.OPENAI_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.api_status['openai_configured'] = False
        
        self.tavily_client = None
        if self.api_status['tavily_configured']:
            try:
                from tavily import TavilyClient
                self.tavily_client = TavilyClient(api_key=self.config.TAVILY_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize Tavily client: {e}")
                self.api_status['tavily_configured'] = False
    
    def execute_research_workflow(self, keywords: List[str], start_date: datetime, 
                                end_date: datetime, search_type: str = 'standard') -> Dict[str, Any]:
        """
        Execute the complete agentic research workflow
        
        Workflow Steps:
        1. Data Collection (Multi-source API calls)
        2. Data Validation & Filtering
        3. Intelligent Curation (LLM-powered)
        4. Relevance Scoring & Ranking
        5. Content Enhancement & Highlighting
        6. Result Aggregation & Formatting
        """
        
        logger.info(f"Starting Pharma Research Workflow")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
        logger.info(f"Search Type: {search_type}")
        
        workflow_results = {
            'success': False,
            'results': [],
            'metadata': {
                'keywords': keywords,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'search_type': search_type,
                'timestamp': datetime.now().isoformat(),
                'api_status': self.api_status
            },
            'workflow_steps': {}
        }
        
        try:
            # Step 1: Multi-source Data Collection
            logger.info("📡 Step 1: Collecting data from multiple sources...")
            raw_data = self._collect_multi_source_data(keywords, start_date, end_date)
            workflow_results['workflow_steps']['data_collection'] = {
                'status': 'completed',
                'sources_used': list(raw_data.keys()),
                'total_articles': sum(len(articles) for articles in raw_data.values())
            }
            
            # Step 2: Data Validation & Filtering
            logger.info("Step 2: Validating and filtering data...")
            validated_data = self._validate_and_filter_data(raw_data, keywords, search_type, start_date, end_date)
            workflow_results['workflow_steps']['data_validation'] = {
                'status': 'completed',
                'articles_before_filtering': sum(len(articles) for articles in raw_data.values()),
                'articles_after_filtering': len(validated_data)
            }
            
            # Step 3: Intelligent Curation (if OpenAI is available)
            if self.api_status['openai_configured']:
                logger.info("Step 3: Intelligent curation with LLM...")
                curated_data = self._intelligent_curation(validated_data, keywords)
                workflow_results['workflow_steps']['intelligent_curation'] = {
                    'status': 'completed',
                    'articles_curated': len(curated_data)
                }
            else:
                logger.info("WARNING: Step 3: Skipping LLM curation (OpenAI not configured)")
                curated_data = validated_data
                workflow_results['workflow_steps']['intelligent_curation'] = {
                    'status': 'skipped',
                    'reason': 'OpenAI API key not configured'
                }
            
            # Step 4: Relevance Scoring & Ranking
            logger.info("Step 4: Scoring relevance and ranking...")
            scored_data = self._score_and_rank_articles(curated_data, keywords)
            workflow_results['workflow_steps']['scoring_ranking'] = {
                'status': 'completed',
                'articles_scored': len(scored_data)
            }
            
            # Step 5: Content Enhancement & Highlighting
            logger.info("Step 5: Enhancing content and highlighting keywords...")
            enhanced_data = self._enhance_content_and_highlight(scored_data, keywords)
            workflow_results['workflow_steps']['content_enhancement'] = {
                'status': 'completed',
                'articles_enhanced': len(enhanced_data)
            }
            
            # Step 6: Final Result Aggregation
            logger.info("Step 6: Aggregating final results...")
            final_results = self._aggregate_final_results(enhanced_data)
            
            workflow_results.update({
                'success': True,
                'results': final_results,
                'results_by_source': self._organize_results_by_source(final_results, raw_data),
                'total_found': sum(len(articles) for articles in raw_data.values()),
                'total_filtered': len(validated_data),
                'total_processed': len(final_results)
            })
            
            logger.info(f"SUCCESS: Workflow completed successfully: {len(final_results)} final results")
            
        except Exception as e:
            logger.error(f"ERROR: Workflow failed: {str(e)}")
            workflow_results['error'] = str(e)
            workflow_results['success'] = False
        
        return workflow_results
    
    def _collect_multi_source_data(self, keywords: List[str], start_date: datetime, 
                                  end_date: datetime) -> Dict[str, List[Dict[str, Any]]]:
        """Collect data from multiple sources"""
        raw_data = {}
        
        # PubMed (always available - no API key required)
        try:
            raw_data['pubmed'] = self._search_pubmed_real(keywords, start_date, end_date)
            logger.info(f"PubMed: {len(raw_data['pubmed'])} articles")
        except Exception as e:
            logger.error(f"PubMed error: {str(e)}")
            raw_data['pubmed'] = []
        
        # NewsAPI (requires API key)
        if self.api_status['newsapi_configured']:
            try:
                raw_data['newsapi'] = self._search_newsapi_real(keywords, start_date, end_date)
                logger.info(f"📰 NewsAPI: {len(raw_data['newsapi'])} articles")
            except Exception as e:
                logger.error(f"NewsAPI error: {str(e)}")
                raw_data['newsapi'] = []
        else:
            logger.warning("NewsAPI not configured - skipping")
            raw_data['newsapi'] = []
        
        # Tavily (requires API key)
        if self.api_status['tavily_configured']:
            try:
                raw_data['tavily'] = self._search_tavily_real(keywords, start_date, end_date)
                logger.info(f"Tavily: {len(raw_data['tavily'])} articles")
            except Exception as e:
                logger.error(f"Tavily error: {str(e)}")
                raw_data['tavily'] = []
        else:
            logger.warning("Tavily not configured - skipping")
            raw_data['tavily'] = []
        
        return raw_data
    
    def _search_pubmed_real(self, keywords: List[str], start_date: datetime, 
                          end_date: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
        """Real PubMed search with proper date filtering"""
        try:
            # Create enhanced query for pharma research
            query_parts = []
            for keyword in keywords:
                # Search in multiple fields for comprehensive coverage
                query_parts.append(f'("{keyword}"[Title/Abstract] OR "{keyword}"[MeSH Terms] OR "{keyword}"[All Fields])')
            
            query = " OR ".join(query_parts)
            
            # Add date range filter
            date_query = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
            full_query = f"({query}) AND {date_query}"
            
            # Search PubMed
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': full_query,
                'retmax': max_results,
                'retmode': 'json',
                'sort': 'relevance',
                'email': self.config.PUBMED_EMAIL
            }
            
            response = requests.get(search_url, params=search_params, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            pmids = data.get('esearchresult', {}).get('idlist', [])
            
            if not pmids:
                return []
            
            # Fetch detailed information
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'xml'
            }
            
            response = requests.get(fetch_url, params=fetch_params, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Parse XML results
            return self._parse_pubmed_xml(response.text)
            
        except Exception as e:
            logger.error(f"PubMed search error: {str(e)}")
            return []
    
    def _search_newsapi_real(self, keywords: List[str], start_date: datetime, 
                           end_date: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
        """Real NewsAPI search with pharma focus"""
        try:
            # Create query for pharma news
            query = " OR ".join(keywords)
            
            # Add pharma-specific domains
            domains = [
                "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
                "pharmatimes.com", "fiercepharma.com", "biopharmadive.com",
                "pharmaceutical-technology.com", "drugdiscoverytoday.com",
                "medicalnewstoday.com", "webmd.com", "medscape.com"
            ]
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'domains': ','.join(domains),
                'from': start_date.strftime('%Y-%m-%d'),
                'to': end_date.strftime('%Y-%m-%d'),
                'sortBy': 'relevancy',
                'pageSize': min(max_results, 100),
                'apiKey': self.config.NEWSAPI_KEY,
                'language': 'en'
            }
            
            response = requests.get(url, params=params, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            articles = data.get('articles', [])
            
            # Process and format articles
            results = []
            for article in articles:
                if article.get('title') and article.get('url'):
                    # Parse publication date
                    pub_date = datetime.now()
                    if article.get('publishedAt'):
                        try:
                            pub_date = datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00'))
                        except:
                            pass
                    
                    result = {
                        'title': article.get('title', ''),
                        'content': article.get('description', '') or article.get('content', ''),
                        'url': article.get('url', ''),
                        'date': pub_date.isoformat(),
                        'source': 'NewsAPI',
                        'authors': article.get('author', ''),
                        'source_name': article.get('source', {}).get('name', 'Unknown')
                    }
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"NewsAPI search error: {str(e)}")
            return []
    
    def _search_tavily_real(self, keywords: List[str], start_date: datetime, 
                          end_date: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
        """Real Tavily search for enhanced pharma research"""
        try:
            from tavily import TavilyClient
            
            client = TavilyClient(api_key=self.config.TAVILY_API_KEY)
            
            # Create comprehensive query
            query = " OR ".join(keywords)
            
            # Focus on pharma and medical domains
            include_domains = [
                "pubmed.ncbi.nlm.nih.gov", "clinicaltrials.gov", "fda.gov",
                "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
                "pharmatimes.com", "fiercepharma.com", "biopharmadive.com",
                "pharmaceutical-technology.com", "drugdiscoverytoday.com"
            ]
            
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=["wikipedia.org", "reddit.com"],
                days=7  # Focus on recent content
            )
            
            results = []
            for item in response.get('results', []):
                # Parse date
                pub_date = datetime.now()
                if 'published_date' in item:
                    try:
                        pub_date = datetime.fromisoformat(item['published_date'].replace('Z', '+00:00'))
                    except:
                        pass
                
                # Check if article is within date range
                if start_date <= pub_date <= end_date:
                    result = {
                        'title': item.get('title', ''),
                        'content': item.get('content', ''),
                        'url': item.get('url', ''),
                        'date': pub_date.isoformat(),
                        'source': 'Tavily',
                        'authors': '',
                        'source_name': 'Tavily Search'
                    }
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Tavily search error: {str(e)}")
            return []
    
    def _parse_pubmed_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """Parse PubMed XML response"""
        import re
        
        results = []
        
        # Extract articles using regex (simplified parsing)
        articles = re.findall(r'<PubmedArticle>(.*?)</PubmedArticle>', xml_content, re.DOTALL)
        
        for article_xml in articles:
            try:
                # Extract title
                title_match = re.search(r'<ArticleTitle>(.*?)</ArticleTitle>', article_xml)
                title = title_match.group(1) if title_match else "No title"
                
                # Extract abstract
                abstract_match = re.search(r'<AbstractText.*?>(.*?)</AbstractText>', article_xml)
                abstract = abstract_match.group(1) if abstract_match else "No abstract"
                
                # Extract PMID
                pmid_match = re.search(r'<PMID.*?>(.*?)</PMID>', article_xml)
                pmid = pmid_match.group(1) if pmid_match else "Unknown"
                
                # Extract publication date
                date_match = re.search(r'<PubDate>.*?<Year>(\d{4})</Year>.*?<Month>(\d{1,2})</Month>.*?<Day>(\d{1,2})</Day>', article_xml)
                if date_match:
                    year, month, day = date_match.groups()
                    pub_date = datetime(int(year), int(month), int(day))
                else:
                    pub_date = datetime.now()
                
                # Extract authors
                authors_match = re.findall(r'<Author>.*?<LastName>(.*?)</LastName>.*?<ForeName>(.*?)</ForeName>', article_xml)
                authors = "; ".join([f"{forename} {lastname}" for lastname, forename in authors_match[:3]])
                if len(authors_match) > 3:
                    authors += " et al."
                
                result = {
                    'title': title,
                    'content': abstract,
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
                    'date': pub_date.isoformat(),
                    'source': 'PubMed',
                    'authors': authors,
                    'source_name': 'PubMed'
                }
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error parsing PubMed article: {str(e)}")
                continue
        
        return results
    
    def _validate_and_filter_data(self, raw_data: Dict[str, List[Dict[str, Any]]], 
                                 keywords: List[str], search_type: str, 
                                 start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Validate and filter collected data"""
        all_articles = []
        
        # Flatten all articles
        for source, articles in raw_data.items():
            all_articles.extend(articles)
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        # Apply search type filtering
        filtered_articles = []
        keywords_lower = [kw.lower() for kw in keywords]
        
        for article in unique_articles:
            title = article.get('title', '').lower()
            content = article.get('content', '').lower()
            
            # Check date range
            try:
                article_date = datetime.fromisoformat(article['date'].replace('Z', '+00:00'))
                if not (start_date <= article_date <= end_date):
                    continue
            except:
                continue
            
            # Apply search type filter
            if search_type == 'standard':
                if any(kw in title or kw in content for kw in keywords_lower):
                    filtered_articles.append(article)
            elif search_type == 'title':
                if any(kw in title for kw in keywords_lower):
                    filtered_articles.append(article)
            elif search_type == 'co-occurrence':
                keyword_count = sum(1 for kw in keywords_lower if kw in content)
                if keyword_count >= 2:
                    filtered_articles.append(article)
        
        return filtered_articles
    
    def _intelligent_curation(self, articles: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Use OpenAI for intelligent curation and summarization"""
        try:
            import openai
            
            openai.api_key = self.config.OPENAI_API_KEY
            
            curated_articles = []
            
            # Process articles in batches
            batch_size = 5
            for i in range(0, len(articles), batch_size):
                batch = articles[i:i + batch_size]
                
                # Create curation prompt
                keywords_str = ", ".join(keywords)
                
                prompt = f"""
You are a pharmaceutical research expert. Analyze these articles for relevance to: {keywords_str}

For each article, provide:
1. A relevance score (0-100)
2. A concise summary (2-3 sentences)
3. Key pharma insights
4. Clinical significance

Articles:
"""
                
                for j, article in enumerate(batch):
                    prompt += f"\n{j+1}. Title: {article['title']}\nContent: {article['content'][:500]}...\n"
                
                prompt += "\nRespond in JSON format: [{'score': X, 'summary': '...', 'insights': '...', 'significance': '...'}]"
                
                try:
                    response = self.openai_client.chat.completions.create(
                        model=self.config.OPENAI_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=self.config.MAX_TOKENS,
                        temperature=self.config.TEMPERATURE
                    )
                    
                    curation_data = json.loads(response.choices[0].message.content)
                    
                    # Apply curation to articles
                    for j, article in enumerate(batch):
                        if j < len(curation_data):
                            article.update({
                                'ai_relevance_score': curation_data[j].get('score', 50),
                                'ai_summary': curation_data[j].get('summary', article['content'][:200]),
                                'ai_insights': curation_data[j].get('insights', ''),
                                'ai_significance': curation_data[j].get('significance', '')
                            })
                        curated_articles.append(article)
                    
                except Exception as e:
                    logger.error(f"OpenAI curation error: {str(e)}")
                    # Fallback: add basic curation
                    for article in batch:
                        article.update({
                            'ai_relevance_score': 50,
                            'ai_summary': article['content'][:200],
                            'ai_insights': '',
                            'ai_significance': ''
                        })
                        curated_articles.append(article)
            
            return curated_articles
            
        except Exception as e:
            logger.error(f"Intelligent curation error: {str(e)}")
            return articles
    
    def _score_and_rank_articles(self, articles: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Score and rank articles by relevance"""
        keywords_lower = [kw.lower() for kw in keywords]
        
        for article in articles:
            # Calculate keyword-based score
            text = (article['title'] + " " + article['content']).lower()
            keyword_count = sum(1 for kw in keywords_lower if kw in text)
            
            # Base score
            base_score = min(90, keyword_count * 20)
            
            # Pharma-specific bonus
            pharma_terms = ['clinical trial', 'fda', 'approval', 'drug', 'pharmaceutical', 
                           'therapeutic', 'dosage', 'efficacy', 'safety', 'regulatory']
            pharma_bonus = sum(1 for term in pharma_terms if term in text) * 5
            
            # Title bonus
            title_keywords = sum(1 for kw in keywords_lower if kw in article['title'].lower())
            title_bonus = title_keywords * 10
            
            # AI score bonus (if available)
            ai_bonus = 0
            if 'ai_relevance_score' in article:
                ai_bonus = article['ai_relevance_score'] * 0.3
            
            # Calculate final score
            final_score = min(100, base_score + pharma_bonus + title_bonus + ai_bonus)
            article['relevance_score'] = int(final_score)
        
        # Sort by relevance score
        articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return articles
    
    def _enhance_content_and_highlight(self, articles: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Enhance content and highlight keywords"""
        for article in articles:
            # Create summary
            if 'ai_summary' in article and article['ai_summary']:
                summary = article['ai_summary']
            else:
                summary = article['content'][:200] + "..." if len(article['content']) > 200 else article['content']
            
            # Highlight keywords in summary
            highlighted_summary = self._highlight_keywords(summary, keywords)
            
            article.update({
                'summary': summary,
                'highlighted_summary': highlighted_summary
            })
        
        return articles
    
    def _highlight_keywords(self, text: str, keywords: List[str]) -> str:
        """Highlight keywords in text"""
        import re
        
        highlighted_text = text
        for keyword in keywords:
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            highlighted_text = pattern.sub(
                f'<mark style="background-color: yellow; font-weight: bold;">{keyword}</mark>',
                highlighted_text
            )
        
        return highlighted_text
    
    def _aggregate_final_results(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggregate and format final results"""
        final_results = []
        
        for i, article in enumerate(articles):
            result = {
                'rank': i + 1,
                'title': article.get('title', ''),
                'summary': article.get('summary', ''),
                'highlighted_summary': article.get('highlighted_summary', ''),
                'url': article.get('url', ''),
                'date': article.get('date', ''),
                'source': article.get('source', ''),
                'relevance_score': article.get('relevance_score', 0),
                'authors': article.get('authors', ''),
                'source_name': article.get('source_name', ''),
                'ai_insights': article.get('ai_insights', ''),
                'ai_significance': article.get('ai_significance', '')
            }
            final_results.append(result)
        
        return final_results
    
    def _organize_results_by_source(self, final_results: List[Dict[str, Any]], raw_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Organize results by source for UI display"""
        results_by_source = {
            'pubmed': [],
            'tavily': [],
            'openai_curated': []
        }
        
        # Group results by source
        for result in final_results:
            source = result.get('source', '').lower()
            if 'pubmed' in source:
                results_by_source['pubmed'].append(result)
            elif 'tavily' in source:
                results_by_source['tavily'].append(result)
            else:
                # OpenAI curated results (enhanced with AI insights)
                if result.get('ai_insights') or result.get('ai_significance'):
                    results_by_source['openai_curated'].append(result)
                else:
                    # Fallback to PubMed if no clear source
                    results_by_source['pubmed'].append(result)
        
        # Add source metadata
        results_by_source['metadata'] = {
            'pubmed_count': len(results_by_source['pubmed']),
            'tavily_count': len(results_by_source['tavily']),
            'openai_curated_count': len(results_by_source['openai_curated']),
            'total_sources': len([k for k, v in results_by_source.items() if k != 'metadata' and len(v) > 0])
        }
        
        return results_by_source
