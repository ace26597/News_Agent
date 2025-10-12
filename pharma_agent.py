"""
Agentic Workflow for Pharma News Research
Orchestrates real API calls, data curation, and intelligent processing
"""

import logging
import json
import time
import re
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from config import Config
# Define domain lists at module level
pharma_domains = [
    "fda.gov", "clinicaltrials.gov", "nih.gov", "ema.europa.eu",
    "pubmed.ncbi.nlm.nih.gov", "nature.com", "nejm.org", "thelancet.com",
    "pharmatimes.com", "fiercepharma.com", "biopharmadive.com",
    "pharmaceutical-technology.com", "drugdiscoverytoday.com"
]

news_domains = [
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
    "techcrunch.com", "wired.com", "arstechnica.com", "venturebeat.com",
    "medicalnewstoday.com", "webmd.com", "medscape.com"
]

mixed_domains = [
    "fda.gov", "clinicaltrials.gov", "nih.gov", "ema.europa.eu",
    "pubmed.ncbi.nlm.nih.gov", "nature.com", "nejm.org", "thelancet.com",
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
    "techcrunch.com", "wired.com", "arstechnica.com", "techcrunch.com",
    "wired.com", "mckinsey.com", "deloitte.com"
]

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
    
    def _extract_date_from_content(self, content: str, title: str = "") -> Optional[datetime]:
        """
        Extract publication date from article content or title
        Looks for dates in first/last 500 characters and common date patterns
        """
        if not content and not title:
            return None
        
        # Combine title and content for better date detection
        text_to_search = (title + " " + content)[:1000] + " " + content[-500:] if len(content) > 1000 else (title + " " + content)
        
        # Common date patterns
        date_patterns = [
            # ISO format: 2024-01-15, 2024/01/15
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', '%Y-%m-%d'),
            # US format: January 15, 2024 or Jan 15, 2024
            (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', '%B %d %Y'),
            (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})', '%b %d %Y'),
            # Day Month Year: 15 January 2024
            (r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', '%d %B %Y'),
            (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{4})', '%d %b %Y'),
            # Month Day, Year: Dec 15, 2024
            (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})', '%b %d %Y'),
            # Published: or Date: prefix
            (r'(?:Published|Date|Posted):\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})', '%Y-%m-%d'),
        ]
        
        extracted_dates = []
        
        for pattern, date_format in date_patterns:
            matches = re.finditer(pattern, text_to_search, re.IGNORECASE)
            for match in matches:
                try:
                    if '%B' in date_format or '%b' in date_format:
                        # Handle month name formats
                        date_str = ' '.join(match.groups())
                    else:
                        # Handle numeric formats
                        if len(match.groups()) == 3:
                            if pattern.startswith(r'(\d{4})'):
                                date_str = f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
                            else:
                                date_str = ' '.join(match.groups())
                    
                    parsed_date = datetime.strptime(date_str.strip(), date_format)
                    
                    # Validate date is reasonable (not too far in future, not too old)
                    now = datetime.now()
                    if datetime(1990, 1, 1) <= parsed_date <= now + timedelta(days=30):
                        extracted_dates.append(parsed_date)
                except (ValueError, AttributeError) as e:
                    continue
        
        # Return most recent date found (likely the publication date)
        if extracted_dates:
            return max(extracted_dates)
        
        return None
    
    def _is_date_in_range(self, article_date: datetime, start_date: datetime, end_date: datetime, 
                         source: str = "", strict: bool = True) -> bool:
        """
        Check if article date is within range with configurable strictness
        """
        # Normalize all dates for comparison
        article_date_norm = self._normalize_date_for_comparison(article_date)
        start_date_norm = self._normalize_date_for_comparison(start_date)
        end_date_norm = self._normalize_date_for_comparison(end_date)
        
        if strict:
            # Strict filtering: must be within exact range
            return start_date_norm <= article_date_norm <= end_date_norm
        else:
            # Lenient filtering: allow small buffer (3 days)
            buffer = timedelta(days=3)
            return (start_date_norm - buffer) <= article_date_norm <= (end_date_norm + buffer)
    
    def execute_research_workflow(self, keywords: List[str], start_date: datetime, 
                                end_date: datetime, search_type: str = 'standard', 
                                search_engines: List[str] = None) -> Dict[str, Any]:
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
        
        # Enhanced parameter validation
        if not keywords or not isinstance(keywords, list):
            raise ValueError("Keywords must be a non-empty list")
        
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date are required")
        
        if start_date > end_date:
            raise ValueError("Start date must be before end date")
        
        # Enhanced date range validation
        self._validate_date_range_enhanced(start_date, end_date)
        
        if search_type not in ['standard', 'title', 'co-occurrence']:
            raise ValueError("Search type must be 'standard', 'title', or 'co-occurrence'")
        
        # Set default search engines if not provided
        if search_engines is None:
            search_engines = ['pubmed', 'exa', 'tavily']
        
        # Validate search engines
        valid_engines = ['pubmed', 'exa', 'tavily']
        search_engines = [engine for engine in search_engines if engine in valid_engines]
        
        if not search_engines:
            raise ValueError("At least one valid search engine must be specified")
        
        logger.info(f"Using search engines: {search_engines}")
        
        # Clean and validate keywords
        cleaned_keywords = [kw.strip().lower() for kw in keywords if kw.strip()]
        if not cleaned_keywords:
            raise ValueError("At least one valid keyword is required")
        
        if len(cleaned_keywords) > self.config.MAX_KEYWORDS:
            raise ValueError(f"Maximum {self.config.MAX_KEYWORDS} keywords allowed")
        
        logger.info(f"Starting Pharma Research Workflow")
        logger.info(f"Keywords: {cleaned_keywords}")
        logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
        logger.info(f"Search Type: {search_type}")
        
        workflow_results = {
            'success': False,
            'results': [],
            'metadata': {
                'keywords': cleaned_keywords,
                'original_keywords': keywords,
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
            raw_data = self._collect_multi_source_data(cleaned_keywords, start_date, end_date, search_engines)
            workflow_results['workflow_steps']['data_collection'] = {
                'status': 'completed',
                'sources_used': list(raw_data.keys()),
                'total_articles': sum(len(articles) for articles in raw_data.values())
            }
            
            # Step 2: Data Validation & Filtering
            logger.info("Step 2: Validating and filtering data...")
            validated_data = self._validate_and_filter_data(raw_data, cleaned_keywords, search_type, start_date, end_date)
            workflow_results['workflow_steps']['data_validation'] = {
                'status': 'completed',
                'articles_before_filtering': sum(len(articles) for articles in raw_data.values()),
                'articles_after_filtering': len(validated_data),
                'filtering_stats': getattr(self, '_last_filtering_stats', {})
            }
            
            # Step 3: Intelligent Curation (if OpenAI is available)
            if self.api_status['openai_configured']:
                logger.info("Step 3: Intelligent curation with LLM...")
                curated_data = self._intelligent_curation(validated_data, cleaned_keywords, start_date, end_date)
                workflow_results['workflow_steps']['intelligent_curation'] = {
                    'status': 'completed',
                    'articles_curated': len(curated_data),
                    'curation_stats': getattr(self, '_last_curation_stats', {})
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
            scored_data = self._score_and_rank_articles(curated_data, cleaned_keywords)
            workflow_results['workflow_steps']['scoring_ranking'] = {
                'status': 'completed',
                'articles_scored': len(scored_data)
            }
            
            # Step 5: Content Enhancement & Highlighting
            logger.info("Step 5: Enhancing content and highlighting keywords...")
            enhanced_data = self._enhance_content_and_highlight(scored_data, cleaned_keywords)
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
    
    def _validate_date_range_enhanced(self, start_date: datetime, end_date: datetime) -> None:
        """Enhanced date range validation with comprehensive checks"""
        # Check if date range is too large (more than 1 year)
        if (end_date - start_date).days > 365:
            logger.warning("Date range is very large (>1 year), results may be limited")
        
        # Check if dates are too far in the past (more than 5 years)
        now = datetime.now()
        if start_date < now - timedelta(days=5*365):
            logger.warning("Start date is more than 5 years ago, some sources may have limited historical data")
        
        # Check if end date is in the future
        if end_date > now:
            logger.warning("End date is in the future, will be adjusted to current date")
            end_date = now
        
        # Log date range information
        logger.info(f"Date range validated: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({(end_date - start_date).days} days)")
    
    def _normalize_date_for_comparison(self, date_obj: datetime) -> datetime:
        """Normalize datetime object for consistent comparison across all retrievers"""
        if date_obj is None:
            return datetime.now()
        
        # Convert to naive datetime for consistent comparison
        if date_obj.tzinfo is not None:
            return date_obj.replace(tzinfo=None)
        return date_obj
    
    def _collect_multi_source_data(self, keywords: List[str], start_date: datetime, 
                                 end_date: datetime, search_engines: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Collect data from multiple sources with comprehensive error handling and search expansion"""
        raw_data = {}
        errors = {}
        
        # Set default search engines if not provided
        if search_engines is None:
            search_engines = ['pubmed', 'exa', 'tavily']
        
        # First attempt with original keywords
        logger.info(f"🔍 First attempt with original keywords: {keywords}")
        logger.info(f"🔍 Using search engines: {search_engines}")
        
        # PubMed (always available - no API key required)
        if 'pubmed' in search_engines:
            try:
                logger.info("🔬 Searching PubMed...")
                raw_data['pubmed'] = self._search_pubmed_real(keywords, start_date, end_date)
                logger.info(f"✅ PubMed: {len(raw_data['pubmed'])} articles")
            except Exception as e:
                logger.error(f"❌ PubMed error: {str(e)}")
                raw_data['pubmed'] = []
                errors['pubmed'] = str(e)
        else:
            logger.info("⏭️ PubMed skipped - not selected")
            raw_data['pubmed'] = []
        
        # Exa Search (requires API key) - Enhanced with retry mechanism
        if 'exa' in search_engines and self.api_status['exa_configured']:
            try:
                logger.info("🔍 Searching Exa with enhanced strategies...")
                print(f"DEBUG: Exa API status: {self.api_status['exa_configured']}")
                raw_data['exa'] = self._search_exa_langchain(keywords, start_date, end_date)
                logger.info(f"✅ Exa: {len(raw_data['exa'])} articles")
            except Exception as e:
                logger.error(f"❌ Exa error: {str(e)}")
                raw_data['exa'] = []
                errors['exa'] = str(e)
        elif 'exa' in search_engines:
            logger.warning("⚠️ Exa not configured - skipping")
            print(f"DEBUG: Exa not configured - API key missing")
            raw_data['exa'] = []
            errors['exa'] = "API key not configured"
        else:
            logger.info("⏭️ Exa skipped - not selected")
            print(f"DEBUG: Exa skipped - not selected")
            raw_data['exa'] = []
        
        # Tavily (requires API key) - Enhanced with retry mechanism
        if 'tavily' in search_engines and self.api_status['tavily_configured']:
            try:
                logger.info("🔍 Searching Tavily with enhanced strategies...")
                print(f"DEBUG: Tavily API status: {self.api_status['tavily_configured']}")
                raw_data['tavily'] = self._search_tavily_langchain(keywords, start_date, end_date)
                logger.info(f"✅ Tavily: {len(raw_data['tavily'])} articles")
            except Exception as e:
                logger.error(f"❌ Tavily error: {str(e)}")
                raw_data['tavily'] = []
                errors['tavily'] = str(e)
        elif 'tavily' in search_engines:
            logger.warning("⚠️ Tavily not configured - skipping")
            print(f"DEBUG: Tavily not configured - API key missing")
            raw_data['tavily'] = []
            errors['tavily'] = "API key not configured"
        else:
            logger.info("⏭️ Tavily skipped - not selected")
            print(f"DEBUG: Tavily skipped - not selected")
            raw_data['tavily'] = []
        
        # Check if we have any data at all
        total_articles = sum(len(articles) for articles in raw_data.values())
        
        # If no results found, try expanded search terms
        if total_articles == 0:
            logger.warning("⚠️ No articles found with original keywords, trying expanded search terms...")
            expanded_keywords = self._expand_search_terms(keywords)
            logger.info(f"🔍 Expanded keywords: {expanded_keywords}")
            
            # Try again with expanded keywords
            if expanded_keywords != keywords:
                # PubMed with expanded terms
                try:
                    logger.info("🔬 Searching PubMed with expanded terms...")
                    expanded_pubmed = self._search_pubmed_real(expanded_keywords, start_date, end_date)
                    if expanded_pubmed:
                        raw_data['pubmed'] = expanded_pubmed
                        logger.info(f"✅ PubMed (expanded): {len(expanded_pubmed)} articles")
                except Exception as e:
                    logger.error(f"❌ PubMed expanded search error: {str(e)}")
                
                # Exa with expanded terms
                if self.api_status['exa_configured']:
                    try:
                        logger.info("🔍 Searching Exa with expanded terms...")
                        expanded_exa = self._search_exa_langchain(expanded_keywords, start_date, end_date)
                        if expanded_exa:
                            raw_data['exa'] = expanded_exa
                            logger.info(f"✅ Exa (expanded): {len(expanded_exa)} articles")
                    except Exception as e:
                        logger.error(f"❌ Exa expanded search error: {str(e)}")
                
                # Tavily with expanded terms
                if self.api_status['tavily_configured']:
                    try:
                        logger.info("🔍 Searching Tavily with expanded terms...")
                        expanded_tavily = self._search_tavily_langchain(expanded_keywords, start_date, end_date)
                        if expanded_tavily:
                            raw_data['tavily'] = expanded_tavily
                            logger.info(f"✅ Tavily (expanded): {len(expanded_tavily)} articles")
                    except Exception as e:
                        logger.error(f"❌ Tavily expanded search error: {str(e)}")
        
        # Final check - if still no results, add fallback data
        total_articles = sum(len(articles) for articles in raw_data.values())
        if total_articles == 0:
            logger.warning("⚠️ No articles found even with expanded terms")
            # Add fallback sample data if all sources fail
            raw_data['fallback'] = self._generate_fallback_data(keywords, start_date, end_date)
            logger.info(f"📝 Generated {len(raw_data['fallback'])} fallback articles")
        
        # Log summary
        logger.info(f"📊 Data collection summary: {total_articles} total articles")
        for source, articles in raw_data.items():
            if articles:
                logger.info(f"   {source}: {len(articles)} articles")
        
        if errors:
            logger.warning(f"⚠️ Errors encountered: {list(errors.keys())}")
        
        return raw_data
    
    def _generate_fallback_data(self, keywords: List[str], start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Generate fallback sample data when all APIs fail"""
        fallback_articles = []
        
        # Create realistic pharma-focused sample articles
        sample_titles = [
            f"Clinical Trial Results for {keywords[0] if keywords else 'Novel Drug'} Show Promising Efficacy",
            f"FDA Reviews {keywords[0] if keywords else 'New Treatment'} for Regulatory Approval",
            f"Pharmaceutical Company Reports Positive Phase III Data for {keywords[0] if keywords else 'Therapeutic Agent'}",
            f"Market Analysis: {keywords[0] if keywords else 'Drug'} Expected to Reach $X Billion by 2025",
            f"Safety Profile of {keywords[0] if keywords else 'Treatment'} Evaluated in Long-term Study"
        ]
        
        for i, title in enumerate(sample_titles[:3]):  # Limit to 3 fallback articles
            article = {
                'title': title,
                'content': f"""
                This is a sample pharmaceutical research article about {keywords[0] if keywords else 'drug development'}. 
                Recent developments in the pharmaceutical industry have shown significant progress in clinical applications. 
                The therapeutic potential of this treatment approach continues to be evaluated in ongoing clinical trials.
                """.strip(),
                'url': f'https://example-pharma-research.com/sample-article-{i+1}',
                'date': (start_date + timedelta(days=i)).isoformat(),
                'source': 'Fallback Sample',
                'authors': 'Sample Research Team',
                'source_name': 'Pharma Research Sample',
                'pmid': f'SAMPLE{i+1:03d}',
                'doi': f'10.1000/sample.{i+1}',
                'journal': 'Sample Pharmaceutical Journal',
                'mesh_terms': ['Pharmaceutical Preparations', 'Clinical Trials', 'Drug Development'],
                'publication_type': 'Journal Article'
            }
            fallback_articles.append(article)
        
        return fallback_articles
    
    def _expand_search_terms(self, keywords: List[str]) -> List[str]:
        """Expand search terms to find related articles when no results are found"""
        expanded_terms = set(keywords)  # Start with original keywords
        
        # Pharma-specific term expansions
        pharma_expansions = {
            # Drug names and treatments
            'diabetes': ['diabetes mellitus', 'type 2 diabetes', 'insulin', 'metformin', 'glucose', 'diabetic'],
            'cancer': ['oncology', 'tumor', 'neoplasm', 'carcinoma', 'malignancy', 'chemotherapy'],
            'prostate cancer': ['prostate carcinoma', 'prostate neoplasm', 'prostate oncology', 'prostate treatment'],
            'oab': ['overactive bladder', 'urinary incontinence', 'bladder dysfunction', 'urological'],
            'orgovyx': ['relugolix', 'prostate cancer treatment', 'hormone therapy', 'androgen deprivation'],
            
            # AI and Technology terms
            'ai': ['artificial intelligence', 'machine learning', 'ML', 'deep learning', 'neural networks'],
            'artificial intelligence': ['AI', 'machine learning', 'ML', 'deep learning', 'neural networks', 'automation'],
            'rag': ['retrieval augmented generation', 'RAG', 'generative AI', 'language models', 'LLM'],
            'agentic': ['agentic AI', 'autonomous agents', 'AI agents', 'intelligent agents'],
            'pipelines': ['data pipelines', 'AI pipelines', 'machine learning pipelines', 'workflow'],
            'pharma': ['pharmaceutical', 'pharmaceuticals', 'drug development', 'biotech', 'biotechnology'],
            
            # General pharma terms
            'clinical trial': ['clinical study', 'phase trial', 'randomized trial', 'clinical research'],
            'fda': ['food and drug administration', 'regulatory approval', 'drug approval', 'fda approval'],
            'pharmaceutical': ['pharma', 'drug development', 'medication', 'therapeutic', 'pharmacology'],
            'treatment': ['therapy', 'therapeutic', 'intervention', 'medication', 'drug'],
            'drug': ['medication', 'pharmaceutical', 'therapeutic agent', 'medicine'],
            'therapy': ['treatment', 'therapeutic intervention', 'medical treatment'],
            'efficacy': ['effectiveness', 'therapeutic effect', 'clinical benefit'],
            'safety': ['adverse events', 'side effects', 'toxicity', 'safety profile'],
            'dosage': ['dosing', 'administration', 'dose response', 'pharmacokinetics'],
            'approval': ['regulatory approval', 'fda approval', 'marketing authorization'],
            'development': ['drug development', 'pharmaceutical development', 'research and development']
        }
        
        # Add expanded terms
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in pharma_expansions:
                expanded_terms.update(pharma_expansions[keyword_lower])
            
            # Add partial matches
            for term, expansions in pharma_expansions.items():
                if keyword_lower in term or term in keyword_lower:
                    expanded_terms.update(expansions)
        
        # Add general pharma context terms
        general_pharma_terms = [
            'clinical trial', 'phase', 'randomized', 'placebo', 'efficacy', 'safety',
            'adverse events', 'pharmacokinetics', 'pharmacodynamics', 'biomarker',
            'endpoint', 'primary endpoint', 'secondary endpoint', 'statistical significance',
            'regulatory', 'fda', 'ema', 'approval', 'indication', 'contraindication',
            'drug interaction', 'metabolism', 'clearance', 'bioavailability'
        ]
        
        # Add AI/tech context terms
        ai_tech_terms = [
            'artificial intelligence', 'machine learning', 'deep learning', 'neural networks',
            'automation', 'digital transformation', 'data analytics', 'predictive modeling',
            'natural language processing', 'computer vision', 'robotics', 'IoT',
            'blockchain', 'cloud computing', 'big data', 'algorithms'
        ]
        
        # Add some general terms if we have very few expanded terms
        if len(expanded_terms) < 5:
            expanded_terms.update(general_pharma_terms[:3])
            expanded_terms.update(ai_tech_terms[:3])
        
        # Convert back to list and limit to reasonable number
        expanded_list = list(expanded_terms)
        if len(expanded_list) > 25:  # Increased limit for better coverage
            expanded_list = expanded_list[:25]
        
        logger.info(f"Expanded {len(keywords)} keywords to {len(expanded_list)} terms")
        return expanded_list
    
    def _search_pubmed_real(self, keywords: List[str], start_date: datetime, 
                          end_date: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
        """Real PubMed search with enhanced date filtering and pharma focus"""
        try:
            # Create enhanced query for pharma research
            query_parts = []
            for keyword in keywords:
                # Search in multiple fields for comprehensive coverage
                query_parts.append(f'("{keyword}"[Title/Abstract] OR "{keyword}"[MeSH Terms] OR "{keyword}"[All Fields])')
            
            query = " OR ".join(query_parts)
            
            # Add pharma-specific MeSH terms for better results
            pharma_mesh_terms = [
                "Pharmaceutical Preparations[MeSH Terms]",
                "Drug Development[MeSH Terms]", 
                "Clinical Trials[MeSH Terms]",
                "Drug Approval[MeSH Terms]",
                "Therapeutics[MeSH Terms]"
            ]
            
            # Combine keyword search with pharma MeSH terms
            pharma_query = " OR ".join(pharma_mesh_terms)
            enhanced_query = f"({query}) AND ({pharma_query})"
            
            # Add flexible date range filter - use last 2 years if dates are in future
            current_date = datetime.now()
            if start_date > current_date:
                # If dates are in future, search last 2 years
                start_date = current_date - timedelta(days=730)  # 2 years ago
                end_date = current_date
            
            date_query = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
            full_query = f"({enhanced_query}) AND {date_query}"
            
            logger.info(f"PubMed query: {full_query}")
            
            # Search PubMed with enhanced parameters
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': full_query,
                'retmax': max_results,
                'retmode': 'json',
                'sort': 'relevance',
                'email': self.config.PUBMED_EMAIL,
                'tool': 'pharma-research-agent',
                'api_key': getattr(self.config, 'PUBMED_API_KEY', None)  # Optional API key for higher rate limits
            }
            
            # Remove None values
            search_params = {k: v for k, v in search_params.items() if v is not None}
            
            response = requests.get(search_url, params=search_params, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            pmids = data.get('esearchresult', {}).get('idlist', [])
            
            if not pmids:
                logger.info("No PubMed results found for the given criteria")
                return []
            
            logger.info(f"Found {len(pmids)} PubMed articles, fetching details...")
            
            # Fetch detailed information in batches to avoid URL length limits
            batch_size = 200  # PubMed recommended batch size
            all_results = []
            
            for i in range(0, len(pmids), batch_size):
                batch_pmids = pmids[i:i + batch_size]
                
                fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                fetch_params = {
                    'db': 'pubmed',
                    'id': ','.join(batch_pmids),
                    'retmode': 'xml',
                    'email': self.config.PUBMED_EMAIL,
                    'tool': 'pharma-research-agent'
                }
                
                response = requests.get(fetch_url, params=fetch_params, timeout=self.config.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                # Parse XML results for this batch
                batch_results = self._parse_pubmed_xml(response.text)
                all_results.extend(batch_results)
                
                # Small delay to be respectful to PubMed servers
                time.sleep(0.1)
            
            logger.info(f"PubMed search completed: {len(all_results)} articles processed")
            return all_results
            
        except Exception as e:
            logger.error(f"PubMed search error: {str(e)}")
            return []
    
    def _search_exa_langchain(self, keywords: List[str], start_date: datetime, 
                             end_date: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
        """Enhanced Exa search with forgiving fallback strategies and comprehensive error handling"""
        try:
            import os
            import requests
            
            # Set environment variable for Exa API key
            os.environ['EXA_API_KEY'] = self.config.EXA_API_KEY
            
            logger.info(f"🔍 Starting Exa search with keywords: {keywords}")
            logger.info(f"📅 Date range: {start_date.date()} to {end_date.date()}")
            print(f"DEBUG: Exa search called with keywords: {keywords}")
            
            # Try multiple query strategies for better results
            query_strategies = self._generate_exa_query_strategies(keywords)
            all_results = []
            strategy_stats = {}
            
            for strategy_name, strategy_config in query_strategies.items():
                logger.info(f"🔍 Trying Exa strategy '{strategy_name}': {strategy_config['query']}")
                
                results = self._execute_exa_query(strategy_config, start_date, end_date, max_results, strategy_name)
                strategy_stats[strategy_name] = {
                    'query': strategy_config['query'],
                    'type': strategy_config['type'],
                    'domains': strategy_config.get('includeDomains', 'all'),
                    'results_found': len(results),
                    'success': len(results) > 0
                }
                
                if results:
                    logger.info(f"✅ Exa strategy '{strategy_name}' returned {len(results)} results")
                    # Add strategy info to each result
                    for result in results:
                        result['search_strategy'] = strategy_name
                        result['strategy_type'] = strategy_config['type']
                    all_results.extend(results)
                else:
                    logger.warning(f"⚠️ Exa strategy '{strategy_name}' returned no results")
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_results = []
            for result in all_results:
                if result['url'] not in seen_urls:
                    seen_urls.add(result['url'])
                    unique_results.append(result)
            
            logger.info(f"📊 Exa total results: {len(all_results)}, unique: {len(unique_results)}")
            logger.info(f"📊 Exa strategy stats: {strategy_stats}")
            
            return unique_results
            
        except Exception as e:
            logger.error(f"❌ Exa search error: {str(e)}")
            return []
    
    def _generate_exa_query_strategies(self, keywords: List[str]) -> Dict[str, Dict[str, Any]]:
        """Generate multiple query strategies for Exa search with different parameters"""
        strategies = {}
        
        simple_keywords = keywords[:3]  # Use first 3 keywords
        quoted_keywords = [f'"{kw}"' for kw in simple_keywords]
        
        # Strategy 1: Simple neural search
        strategies['simple_neural'] = {
            'query': ' OR '.join(quoted_keywords),
            'type': 'neural',
            'useAutoprompt': True,
            'includeDomains': pharma_domains,  # Use pharma domains instead of None
            'excludeDomains': None
        }
        
        # Strategy 2: Pharma-focused neural search
        pharma_context = "pharmaceutical OR clinical trial OR FDA OR drug development OR medical research"
        strategies['pharma_neural'] = {
            'query': f"({' OR '.join(quoted_keywords)}) AND ({pharma_context})",
            'type': 'neural',
            'useAutoprompt': True,
            'includeDomains': pharma_domains,  # Use pharma domains instead of None
            'excludeDomains': None
        }
        
        # Strategy 3: AI/Tech focused neural search
        ai_context = "artificial intelligence OR AI OR machine learning OR technology OR innovation"
        strategies['ai_neural'] = {
            'query': f"({' OR '.join(quoted_keywords)}) AND ({ai_context})",
            'type': 'neural',
            'useAutoprompt': True,
            'includeDomains': news_domains,  # Use news domains instead of None
            'excludeDomains': None
        }
        
        # Strategy 4: Keyword search with pharma domains
        
        strategies['pharma_domains'] = {
            'query': ' OR '.join(quoted_keywords),
            'type': 'keyword',
            'useAutoprompt': False,
            'includeDomains': pharma_domains,
            'excludeDomains': None
        }
        
        # Strategy 5: Keyword search with news domains
        strategies['news_domains'] = {
            'query': ' OR '.join(quoted_keywords),
            'type': 'keyword',
            'useAutoprompt': False,
            'includeDomains': news_domains,
            'excludeDomains': None
        }
        
        # Strategy 6: Mixed domains (pharma + news + tech)
        strategies['mixed_domains'] = {
            'query': ' OR '.join(quoted_keywords),
            'type': 'keyword',
            'useAutoprompt': False,
            'includeDomains': mixed_domains,
            'excludeDomains': None
        }
        
        # Strategy 7: Individual keyword search (most forgiving)
        strategies['individual_keyword'] = {
            'query': keywords[0] if keywords else "pharmaceutical",
            'type': 'keyword',
            'useAutoprompt': False,
            'includeDomains': pharma_domains,  # Use pharma domains instead of None
            'excludeDomains': None
        }
        
        # Strategy 8: Broad search without domain restrictions
        strategies['broad_unrestricted'] = {
            'query': ' OR '.join(keywords[:2]) if len(keywords) >= 2 else keywords[0],
            'type': 'keyword',
            'useAutoprompt': False,
            'includeDomains': news_domains,  # Use news domains instead of None
            'excludeDomains': ["wikipedia.org", "reddit.com", "twitter.com", "facebook.com"]
        }
        
        # Strategy 9: Neural search with live crawl
        strategies['neural_livecrawl'] = {
            'query': ' '.join(keywords[:3]),
            'type': 'neural',
            'useAutoprompt': True,
            'livecrawl': 'always',
            'includeDomains': mixed_domains,  # Use mixed domains instead of None
            'excludeDomains': None
        }
        
        # Strategy 10: Keyword search with specific exclusions
        strategies['keyword_filtered'] = {
            'query': ' OR '.join(quoted_keywords),
            'type': 'keyword',
            'useAutoprompt': False,
            'includeDomains': None,
            'excludeDomains': ["wikipedia.org", "reddit.com", "twitter.com", "facebook.com", 
                              "instagram.com", "tiktok.com", "youtube.com", "linkedin.com"]
        }
        
        return strategies
    
    def _execute_exa_query(self, strategy_config: Dict[str, Any], start_date: datetime, end_date: datetime, 
                          max_results: int, strategy_name: str) -> List[Dict[str, Any]]:
        """Execute a single Exa query with comprehensive error handling"""
        try:
            import requests
            
            # Use direct Exa API call for better control
            exa_url = "https://api.exa.ai/search"
            
            # Build payload from strategy configuration
            # Use more forgiving date range for Exa
            current_date = datetime.now()
            if start_date > current_date:
                # If dates are in future, search last 2 years
                start_date = current_date - timedelta(days=730)  # 2 years ago
                end_date = current_date
            
            payload = {
                "query": strategy_config['query'],
                "numResults": min(max_results, 20),  # Exa limit
                "type": strategy_config['type'],
                "useAutoprompt": strategy_config.get('useAutoprompt', False),
                "livecrawl": strategy_config.get('livecrawl', 'fallback'),
                "textContentsOptions": {
                    "maxCharacters": 2000,  # Limit text length for efficiency
                    "includeHtmlTags": False  # Clean text without HTML
                },
                "summary": {
                    "query": "Generate a concise summary focusing on pharmaceutical relevance, clinical significance, and regulatory implications"
                },
                # Add proper date filtering with more forgiving range
                "startPublishedDate": start_date.isoformat() + "Z",
                "endPublishedDate": end_date.isoformat() + "Z"
            }
            
            # Add domain restrictions if specified
            if strategy_config.get('includeDomains') is not None:
                payload["includeDomains"] = strategy_config['includeDomains'][:15]  # Limit domains
            
            if strategy_config.get('excludeDomains') is not None:
                payload["excludeDomains"] = strategy_config['excludeDomains']
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.config.EXA_API_KEY
            }
            
            # Log domain info safely
            domain_count = len(payload.get('includeDomains', [])) if payload.get('includeDomains') else 0
            logger.info(f"📡 Making Exa API request with {domain_count} domains")
            
            response = requests.post(exa_url, json=payload, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"❌ Exa API error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            logger.info(f"📊 Exa API response: {len(data.get('results', []))} results")
            
            # Process results
            raw_results = data.get('results', [])
            
            if not raw_results:
                logger.warning("⚠️ Exa returned no results")
                # Try fallback search without domain restrictions
                logger.info("🔄 Trying fallback search without domain restrictions...")
                fallback_payload = payload.copy()
                if 'includeDomains' in fallback_payload:
                    del fallback_payload['includeDomains']
                # Add excludeDomains for fallback search
                fallback_payload['excludeDomains'] = ["wikipedia.org", "reddit.com", "twitter.com", "facebook.com",
                                                    "instagram.com", "tiktok.com", "youtube.com"]
                
                fallback_response = requests.post(exa_url, json=fallback_payload, headers=headers, timeout=30)
                if fallback_response.status_code == 200:
                    fallback_data = fallback_response.json()
                    raw_results = fallback_data.get('results', [])
                    logger.info(f"🔄 Fallback search returned {len(raw_results)} results")
            
            results = []
            for item in raw_results:
                try:
                    # Parse publication date
                    pub_date = datetime.now()
                    if 'publishedDate' in item and item['publishedDate']:
                        try:
                            date_str = item['publishedDate']
                            if isinstance(date_str, str):
                                if 'T' in date_str:
                                    pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                else:
                                    pub_date = datetime.fromisoformat(date_str)
                            elif hasattr(date_str, 'isoformat'):
                                pub_date = date_str
                        except Exception as date_error:
                            logger.warning(f"Could not parse Exa date '{item.get('publishedDate')}': {date_error}")
                            pub_date = datetime.now()
                    
                    # Check if article is within date range using normalized comparison
                    # Be more forgiving for Exa - include recent articles even if slightly outside range
                    pub_date_normalized = self._normalize_date_for_comparison(pub_date)
                    start_date_normalized = self._normalize_date_for_comparison(start_date)
                    end_date_normalized = self._normalize_date_for_comparison(end_date)
                    
                    # Extend end date by 30 days to catch recent articles
                    extended_end_date = end_date_normalized + timedelta(days=30)
                    
                    if not (start_date_normalized <= pub_date_normalized <= extended_end_date):
                        logger.debug(f"📅 Article date {pub_date.date()} outside extended range, skipping")
                        continue
                    elif pub_date_normalized > end_date_normalized:
                        logger.debug(f"📅 Article date {pub_date.date()} slightly outside range but including (within 30 days)")
                    
                    # Extract source name from URL
                    source_name = self._extract_source_name(item.get('url', ''))
                    
                    result = {
                        'title': item.get('title', ''),
                        'content': item.get('text', ''),  # Exa uses 'text' field
                        'url': item.get('url', ''),
                        'date': pub_date.isoformat(),
                        'source': 'Exa',
                        'authors': item.get('author', ''),
                        'source_name': source_name,
                        'raw_score': item.get('score', 0),
                        'summary': item.get('summary', ''),  # Include AI-generated summary
                        'text_content': item.get('textContent', ''),  # Include processed text content
                        'livecrawl': item.get('livecrawl', False),  # Indicate if content was live crawled
                        'search_strategy': strategy_name  # Track which strategy found this result
                    }
                    results.append(result)
                    
                except Exception as item_error:
                    logger.error(f"Error processing Exa result: {item_error}")
                    continue
            
            logger.info(f"✅ Exa search completed: {len(results)} results within date range")
            return results
            
        except Exception as e:
            logger.error(f"❌ Exa query execution error: {str(e)}")
            return []
    
            
    def _search_tavily_langchain(self, keywords: List[str], start_date: datetime, 
                                end_date: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
        """Enhanced Tavily search with forgiving fallback strategies and comprehensive error handling"""
        try:
            import os
            import requests
            
            # Set environment variable for Tavily API key
            os.environ['TAVILY_API_KEY'] = self.config.TAVILY_API_KEY
            
            logger.info(f"🔍 Starting Tavily search with keywords: {keywords}")
            logger.info(f"📅 Date range: {start_date.date()} to {end_date.date()}")
            print(f"DEBUG: Tavily search called with keywords: {keywords}")
            
            # Try multiple query strategies for better results
            query_strategies = self._generate_tavily_query_strategies(keywords)
            all_results = []
            strategy_stats = {}
            
            for strategy_name, strategy_config in query_strategies.items():
                logger.info(f"🔍 Trying Tavily strategy '{strategy_name}': {strategy_config['query']}")
                
                results = self._execute_tavily_query(strategy_config, start_date, end_date, max_results, strategy_name)
                strategy_stats[strategy_name] = {
                    'query': strategy_config['query'],
                    'search_depth': strategy_config['search_depth'],
                    'domains': strategy_config.get('include_domains', 'all'),
                    'results_found': len(results),
                    'success': len(results) > 0
                }
                
                if results:
                    logger.info(f"✅ Tavily strategy '{strategy_name}' returned {len(results)} results")
                    # Add strategy info to each result
                    for result in results:
                        result['search_strategy'] = strategy_name
                        result['strategy_type'] = strategy_config['search_depth']
                    all_results.extend(results)
                else:
                    logger.warning(f"⚠️ Tavily strategy '{strategy_name}' returned no results")
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_results = []
            for result in all_results:
                if result['url'] not in seen_urls:
                    seen_urls.add(result['url'])
                    unique_results.append(result)
            
            logger.info(f"📊 Tavily total results: {len(all_results)}, unique: {len(unique_results)}")
            logger.info(f"📊 Tavily strategy stats: {strategy_stats}")
            
            return unique_results
            
        except Exception as e:
            logger.error(f"❌ Tavily search error: {str(e)}")
            return []
    
    def _generate_tavily_query_strategies(self, keywords: List[str]) -> Dict[str, Dict[str, Any]]:
        """Generate multiple query strategies for Tavily search with different parameters"""
        strategies = {}
        
        simple_keywords = keywords[:3]  # Use first 3 keywords
        quoted_keywords = [f'"{kw}"' for kw in simple_keywords]
        
        # Strategy 1: Simple search
        strategies['simple'] = {
            'query': ' OR '.join(quoted_keywords),
            'search_depth': 'basic',
            'include_domains': pharma_domains,  # Use pharma domains instead of None
            'exclude_domains': None
        }
        
        # Strategy 2: Advanced search
        strategies['advanced'] = {
            'query': ' OR '.join(quoted_keywords),
            'search_depth': 'advanced',
            'include_domains': pharma_domains,  # Use pharma domains instead of None
            'exclude_domains': None
        }
        
        # Strategy 3: Pharma-focused search
        pharma_context = "pharmaceutical OR clinical trial OR FDA OR drug development OR medical research"
        strategies['pharma_context'] = {
            'query': f"({' OR '.join(quoted_keywords)}) AND ({pharma_context})",
            'search_depth': 'advanced',
            'include_domains': pharma_domains,  # Use pharma domains instead of None
            'exclude_domains': None
        }
        
        # Strategy 4: AI/Tech focused search
        ai_context = "artificial intelligence OR AI OR machine learning OR technology OR innovation"
        strategies['ai_context'] = {
            'query': f"({' OR '.join(quoted_keywords)}) AND ({ai_context})",
            'search_depth': 'advanced',
            'include_domains': news_domains,  # Use news domains instead of None
            'exclude_domains': None
        }
        
        # Strategy 5: Search with pharma domains
        
        strategies['pharma_domains'] = {
            'query': ' OR '.join(quoted_keywords),
            'search_depth': 'advanced',
            'include_domains': pharma_domains,
            'exclude_domains': None
        }
        
        # Strategy 6: Search with news domains
        strategies['news_domains'] = {
            'query': ' OR '.join(quoted_keywords),
            'search_depth': 'advanced',
            'include_domains': news_domains,
            'exclude_domains': None
        }
        
        # Strategy 7: Mixed domains
        strategies['mixed_domains'] = {
            'query': ' OR '.join(quoted_keywords),
            'search_depth': 'advanced',
            'include_domains': mixed_domains,
            'exclude_domains': None
        }
        
        # Strategy 8: Individual keyword search (most forgiving)
        strategies['individual'] = {
            'query': keywords[0] if keywords else "pharmaceutical",
            'search_depth': 'basic',
            'include_domains': pharma_domains,  # Use pharma domains instead of None
            'exclude_domains': None
        }
        
        # Strategy 9: Broad search without domain restrictions
        strategies['broad_unrestricted'] = {
            'query': ' OR '.join(keywords[:2]) if len(keywords) >= 2 else keywords[0],
            'search_depth': 'basic',
            'include_domains': news_domains,  # Use news domains instead of None
            'exclude_domains': ["wikipedia.org", "reddit.com", "twitter.com", "facebook.com"]
        }
        
        # Strategy 10: Search with specific exclusions
        strategies['filtered'] = {
            'query': ' OR '.join(quoted_keywords),
            'search_depth': 'advanced',
            'include_domains': mixed_domains,  # Use mixed domains instead of None
            'exclude_domains': ["wikipedia.org", "reddit.com", "twitter.com", "facebook.com", 
                               "instagram.com", "tiktok.com", "youtube.com", "linkedin.com"]
        }
        
        return strategies
    
    def _execute_tavily_query(self, strategy_config: Dict[str, Any], start_date: datetime, end_date: datetime, 
                             max_results: int, strategy_name: str) -> List[Dict[str, Any]]:
        """Execute a single Tavily query with comprehensive error handling"""
        try:
            import requests
            
            # Calculate time range for search (Tavily's time_range parameter)
            days_diff = (end_date - start_date).days
            if days_diff <= 1:
                time_range = "day"
            elif days_diff <= 7:
                time_range = "week"
            elif days_diff <= 30:
                time_range = "month"
            else:
                time_range = "year"
            
            # Enhanced pharma and medical domains
            include_domains = [
                # Government and regulatory
                "fda.gov", "clinicaltrials.gov", "cdc.gov", "nih.gov", "ema.europa.eu",
                # Medical literature
                "pubmed.ncbi.nlm.nih.gov", "nature.com", "nejm.org", "thelancet.com", 
                "bmj.com", "jama.ama-assn.org", "springer.com", "elsevier.com",
                # Pharma news and industry
                "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
                "pharmatimes.com", "fiercepharma.com", "biopharmadive.com",
                "pharmaceutical-technology.com", "drugdiscoverytoday.com",
                "pharmaexec.com", "biospace.com", "genengnews.com", "pharmalive.com",
                # Medical news
                "medicalnewstoday.com", "webmd.com", "medscape.com",
                "healthline.com", "mayoclinic.org", "clevelandclinic.org",
                "drugs.com", "rxlist.com",
                # AI/Tech news
                "techcrunch.com", "wired.com", "arstechnica.com", "venturebeat.com",
                "mckinsey.com", "deloitte.com", "pwc.com", "accenture.com"
            ]
            
            # Use direct Tavily API call instead of LangChain for better control
            tavily_url = "https://api.tavily.com/search"
            
            payload = {
                "query": strategy_config['query'],
                "search_depth": strategy_config['search_depth'],
                "include_answer": True,
                "include_raw_content": True,
                "max_results": min(max_results, 20),  # Tavily limit
                # Remove strict date filtering for Tavily - it often has no dates
            }
            
            # Add domain restrictions if specified
            if strategy_config.get('include_domains') is not None:
                payload["include_domains"] = strategy_config['include_domains'][:15]  # Limit domains
            
            if strategy_config.get('exclude_domains') is not None:
                payload["exclude_domains"] = strategy_config['exclude_domains']
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.TAVILY_API_KEY}"
            }
            
            # Log domain info safely
            domain_count = len(payload.get('include_domains', [])) if payload.get('include_domains') else 0
            logger.info(f"📡 Making Tavily API request with {domain_count} domains")
            
            response = requests.post(tavily_url, json=payload, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"❌ Tavily API error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            logger.info(f"📊 Tavily API response: {len(data.get('results', []))} results")
            
            # Process results
            raw_results = data.get('results', [])
            
            if not raw_results:
                logger.warning("⚠️ Tavily returned no results")
                # Try fallback search without domain restrictions
                logger.info("🔄 Trying fallback search without domain restrictions...")
                fallback_payload = payload.copy()
                if 'include_domains' in fallback_payload:
                    del fallback_payload['include_domains']
                if 'exclude_domains' in fallback_payload:
                    del fallback_payload['exclude_domains']
                
                fallback_response = requests.post(tavily_url, json=fallback_payload, headers=headers, timeout=30)
                if fallback_response.status_code == 200:
                    fallback_data = fallback_response.json()
                    raw_results = fallback_data.get('results', [])
                    logger.info(f"🔄 Fallback search returned {len(raw_results)} results")
            
            results = []
            for item in raw_results:
                try:
                    # Parse date with comprehensive error handling - Tavily often has no dates
                    pub_date = datetime.now()
                    date_available = False
                    
                    if 'published_date' in item and item['published_date']:
                        try:
                            date_str = item['published_date']
                            # Handle various date formats
                            if 'T' in date_str:
                                pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                date_available = True
                            elif '-' in date_str and len(date_str) == 10:  # YYYY-MM-DD format
                                pub_date = datetime.fromisoformat(date_str)
                                date_available = True
                            else:
                                # Try parsing other formats
                                try:
                                    from dateutil import parser
                                    pub_date = parser.parse(date_str)
                                    date_available = True
                                except (ImportError, Exception):
                                    # Fallback to basic parsing if dateutil not available
                                    logger.warning("dateutil not available, using fallback date parsing")
                                    pub_date = datetime.now()
                        except Exception as date_error:
                            logger.warning(f"Could not parse Tavily date '{item.get('published_date')}': {date_error}")
                            pub_date = datetime.now()
                    
                    # More lenient date filtering for Tavily - include articles without dates
                    date_in_range = True
                    if date_available:
                        pub_date_normalized = self._normalize_date_for_comparison(pub_date)
                        start_date_normalized = self._normalize_date_for_comparison(start_date)
                        end_date_normalized = self._normalize_date_for_comparison(end_date)
                        
                        # Extend date range by 30 days for Tavily to be more inclusive
                        extended_end_date = end_date_normalized + timedelta(days=30)
                        extended_start_date = start_date_normalized - timedelta(days=7)
                        
                        if not (extended_start_date <= pub_date_normalized <= extended_end_date):
                            logger.debug(f"📅 Tavily article date {pub_date.date()} outside extended range, skipping")
                            date_in_range = False
                        else:
                            logger.debug(f"📅 Tavily article date {pub_date.date()} within extended range, including")
                    else:
                        # For Tavily results without dates, include them but mark for LLM date extraction
                        logger.debug("📅 Tavily result has no published date, including for LLM date extraction")
                        date_in_range = True
                    
                    if not date_in_range:
                        continue
                    
                    # Extract source name from URL
                    source_name = self._extract_source_name(item.get('url', ''))
                    
                    result = {
                        'title': item.get('title', ''),
                        'content': item.get('content', ''),
                        'url': item.get('url', ''),
                        'date': pub_date.isoformat(),
                        'source': 'Tavily',
                        'authors': '',
                        'source_name': source_name,
                        'raw_score': item.get('score', 0),
                        'ai_answer': item.get('answer', ''),  # Include AI-generated answer
                        'raw_content': item.get('raw_content', ''),  # Include raw content
                        'search_strategy': strategy_name,  # Track which strategy found this result
                        'date_found': date_available,  # Track if date was actually found
                        'original_published_date': item.get('published_date', '')  # Store original date string
                    }
                    results.append(result)
                    
                except Exception as item_error:
                    logger.error(f"Error processing Tavily result: {item_error}")
                    continue
            
            logger.info(f"✅ Tavily search completed: {len(results)} results within date range")
            return results
            
        except Exception as e:
            logger.error(f"❌ Tavily query execution error: {str(e)}")
            return []
    
    def _extract_source_name(self, url: str) -> str:
        """Extract source name from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Map common domains to readable names
            domain_mapping = {
                'pubmed.ncbi.nlm.nih.gov': 'PubMed',
                'clinicaltrials.gov': 'ClinicalTrials.gov',
                'fda.gov': 'FDA',
                'reuters.com': 'Reuters',
                'bloomberg.com': 'Bloomberg',
                'wsj.com': 'Wall Street Journal',
                'ft.com': 'Financial Times',
                'pharmatimes.com': 'PharmaTimes',
                'fiercepharma.com': 'FiercePharma',
                'biopharmadive.com': 'BioPharma Dive',
                'nature.com': 'Nature',
                'nejm.org': 'New England Journal of Medicine',
                'thelancet.com': 'The Lancet',
                'medicalnewstoday.com': 'Medical News Today',
                'webmd.com': 'WebMD',
                'medscape.com': 'Medscape'
            }
            
            return domain_mapping.get(domain, domain.replace('www.', '').title())
        except:
            return 'Tavily Search'
    
    def _parse_pubmed_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """Enhanced PubMed XML response parsing with better metadata extraction"""
        import re
        
        results = []
        
        # Extract articles using regex (simplified parsing)
        articles = re.findall(r'<PubmedArticle>(.*?)</PubmedArticle>', xml_content, re.DOTALL)
        
        for article_xml in articles:
            try:
                # Extract title with better handling
                title_match = re.search(r'<ArticleTitle>(.*?)</ArticleTitle>', article_xml)
                title = title_match.group(1) if title_match else "No title"
                
                # Extract abstract with better handling of structured abstracts
                abstract_match = re.search(r'<AbstractText.*?>(.*?)</AbstractText>', article_xml, re.DOTALL)
                abstract = abstract_match.group(1) if abstract_match else "No abstract"
                
                # Clean up abstract text
                abstract = re.sub(r'<[^>]+>', '', abstract)  # Remove HTML tags
                abstract = re.sub(r'\s+', ' ', abstract).strip()  # Normalize whitespace
                
                # Extract PMID
                pmid_match = re.search(r'<PMID.*?>(.*?)</PMID>', article_xml)
                pmid = pmid_match.group(1) if pmid_match else "Unknown"
                
                # Extract publication date with better parsing
                pub_date = datetime.now()
                date_found = False
                
                # Try different date patterns
                date_patterns = [
                    r'<PubDate>.*?<Year>(\d{4})</Year>.*?<Month>(\d{1,2})</Month>.*?<Day>(\d{1,2})</Day>',
                    r'<PubDate>.*?<Year>(\d{4})</Year>.*?<Month>(\d{1,2})</Month>',
                    r'<PubDate>.*?<Year>(\d{4})</Year>'
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, article_xml)
                    if date_match:
                        groups = date_match.groups()
                        year = int(groups[0])
                        month = int(groups[1]) if len(groups) > 1 else 1
                        day = int(groups[2]) if len(groups) > 2 else 1
                        try:
                            pub_date = datetime(year, month, day)
                            date_found = True
                            break
                        except ValueError:
                            continue
                
                # If no date found, use current date but mark it
                if not date_found:
                    logger.debug(f"No publication date found for PMID {pmid}, using current date")
                
                # Extract authors with better formatting
                authors_match = re.findall(r'<Author>.*?<LastName>(.*?)</LastName>.*?<ForeName>(.*?)</ForeName>', article_xml)
                authors = "; ".join([f"{forename} {lastname}" for lastname, forename in authors_match[:5]])  # Limit to 5 authors
                if len(authors_match) > 5:
                    authors += " et al."
                
                # Extract journal information
                journal_match = re.search(r'<Journal>.*?<Title>(.*?)</Title>', article_xml)
                journal = journal_match.group(1) if journal_match else "Unknown Journal"
                
                # Extract DOI if available
                doi_match = re.search(r'<ELocationID.*?EIdType="doi".*?>(.*?)</ELocationID>', article_xml)
                doi = doi_match.group(1) if doi_match else ""
                
                # Extract MeSH terms for better categorization
                mesh_terms = re.findall(r'<DescriptorName.*?>(.*?)</DescriptorName>', article_xml)
                mesh_terms = mesh_terms[:10]  # Limit to first 10 MeSH terms
                
                # Extract publication type
                pub_type_match = re.search(r'<PublicationType>(.*?)</PublicationType>', article_xml)
                pub_type = pub_type_match.group(1) if pub_type_match else "Journal Article"
                
                # Create enhanced result
                result = {
                    'title': title,
                    'content': abstract,
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
                    'date': pub_date.isoformat(),
                    'source': 'PubMed',
                    'authors': authors,
                    'source_name': journal,
                    'pmid': pmid,
                    'doi': doi,
                    'journal': journal,
                    'mesh_terms': mesh_terms,
                    'publication_type': pub_type,
                    'raw_score': 0,  # PubMed doesn't provide relevance scores
                    'date_found': date_found  # Track if date was actually found
                }
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error parsing PubMed article: {str(e)}")
                continue
        
        return results
    
    def _validate_and_filter_data(self, raw_data: Dict[str, List[Dict[str, Any]]], 
                                 keywords: List[str], search_type: str, 
                                 start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Validate and filter collected data with enhanced date filtering and statistics tracking"""
        all_articles = []
        source_stats = {}
        
        # Flatten all articles and track source statistics
        for source, articles in raw_data.items():
            source_stats[source] = {
                'total_articles': len(articles),
                'articles_with_dates': 0,
                'articles_in_date_range': 0,
                'articles_outside_date_range': 0,
                'articles_without_dates': 0,
                'filtered_by_keywords': 0,
                'final_filtered': 0
            }
            all_articles.extend(articles)
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        # Apply STRICT date filtering and search type filtering
        filtered_articles = []
        keywords_lower = [kw.lower() for kw in keywords]
        
        for article in unique_articles:
            title = article.get('title', '')
            content = article.get('content', '')
            source = article.get('source', 'unknown')
            
            # IMPROVED: Try to extract date from content if not found in metadata
            article_date = None
            date_found = article.get('date_found', False)
            
            # First, try to use provided date
            if 'date' in article and article['date']:
                try:
                    article_date = datetime.fromisoformat(article['date'].replace('Z', '+00:00'))
                    date_found = True
                except:
                    pass
            
            # If no date found, try to extract from content
            if not date_found or not article_date:
                extracted_date = self._extract_date_from_content(content, title)
                if extracted_date:
                    article_date = extracted_date
                    date_found = True
                    article['extracted_date'] = extracted_date.isoformat()
                    article['date'] = extracted_date.isoformat()
                    logger.debug(f"📅 Extracted date {extracted_date.date()} from content for: {title[:50]}...")
            
            # STRICT filtering: If no date found, filter out the article
            if not date_found or not article_date:
                if source in source_stats:
                    source_stats[source]['articles_without_dates'] += 1
                logger.debug(f"❌ Filtered out (no date): {title[:50]}...")
                continue
            
            # Track articles with dates
            if source in source_stats:
                source_stats[source]['articles_with_dates'] += 1
            
            # STRICT date range check - NO extensions
            date_in_range = self._is_date_in_range(article_date, start_date, end_date, source, strict=True)
            
            if not date_in_range:
                if source in source_stats:
                    source_stats[source]['articles_outside_date_range'] += 1
                logger.debug(f"❌ Filtered out (date {article_date.date()} outside range {start_date.date()} to {end_date.date()}): {title[:50]}...")
                continue
            
            if source in source_stats:
                source_stats[source]['articles_in_date_range'] += 1
            
            # Apply search type filter
            title_lower = title.lower()
            content_lower = content.lower()
            keyword_match = False
            if search_type == 'standard':
                if any(kw in title_lower or kw in content_lower for kw in keywords_lower):
                    keyword_match = True
            elif search_type == 'title':
                if any(kw in title_lower for kw in keywords_lower):
                    keyword_match = True
            elif search_type == 'co-occurrence':
                keyword_count = sum(1 for kw in keywords_lower if kw in content_lower)
                if keyword_count >= 2:
                    keyword_match = True
            
            if keyword_match:
                if source in source_stats:
                    source_stats[source]['filtered_by_keywords'] += 1
                filtered_articles.append(article)
            else:
                logger.debug(f"🔍 Article '{article.get('title', '')[:50]}...' filtered out - no keyword match for {search_type} search")
        
        # Update final filtered count for each source
        for article in filtered_articles:
            source = article.get('source', 'unknown')
            if source in source_stats:
                source_stats[source]['final_filtered'] += 1
        
        # Log detailed statistics by source
        logger.info("📊 Data validation and filtering statistics by source:")
        for source, stats in source_stats.items():
            logger.info(f"   {source}:")
            logger.info(f"     Total articles: {stats['total_articles']}")
            logger.info(f"     Articles with dates: {stats['articles_with_dates']}")
            logger.info(f"     Articles in date range: {stats['articles_in_date_range']}")
            logger.info(f"     Articles outside date range: {stats['articles_outside_date_range']}")
            logger.info(f"     Articles without dates: {stats['articles_without_dates']}")
            logger.info(f"     Filtered by keywords: {stats['filtered_by_keywords']}")
            logger.info(f"     Final filtered: {stats['final_filtered']}")
        
        # Store statistics for later use
        self._last_filtering_stats = source_stats
        
        return filtered_articles
    
    def _intelligent_curation(self, articles: List[Dict[str, Any]], keywords: List[str], 
                             start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        """
        OPTIMIZED OpenAI-powered intelligent curation with:
        - No redundant date filtering (already done in validation)
        - Larger batches (10 articles) to reduce API calls
        - Early basic relevance filtering to reduce OpenAI calls
        - Async processing for better performance
        """
        try:
            curated_articles = []
            curation_stats = {
                'total_articles_processed': len(articles),
                'articles_curated': 0,
                'articles_filtered_by_basic_relevance': 0,
                'articles_filtered_by_ai_relevance': 0,
                'articles_with_ai_analysis': 0,
                'openai_api_calls': 0
            }
            
            # OPTIMIZATION 1: Basic keyword relevance check BEFORE OpenAI
            # This dramatically reduces OpenAI API calls
            logger.info(f"🔍 Pre-filtering {len(articles)} articles for basic relevance...")
            keywords_lower = [kw.lower() for kw in keywords]
            
            pre_filtered_articles = []
            for article in articles:
                title_lower = article.get('title', '').lower()
                content_lower = article.get('content', '')[:500].lower()  # Check first 500 chars
                
                # Calculate basic relevance score
                keyword_matches = sum(1 for kw in keywords_lower if kw in title_lower or kw in content_lower)
                title_matches = sum(1 for kw in keywords_lower if kw in title_lower)
                
                # Keep if at least 1 keyword match or 1 title match
                if keyword_matches >= 1 or title_matches >= 1:
                    article['basic_relevance_score'] = (keyword_matches * 10) + (title_matches * 20)
                    pre_filtered_articles.append(article)
                else:
                    curation_stats['articles_filtered_by_basic_relevance'] += 1
                    logger.debug(f"❌ Filtered (no keyword match): {article.get('title', '')[:50]}...")
            
            logger.info(f"✅ Pre-filter reduced articles from {len(articles)} to {len(pre_filtered_articles)} (saved {len(articles) - len(pre_filtered_articles)} OpenAI calls)")
            
            articles = pre_filtered_articles
            
            # OPTIMIZATION 2: Larger batches to reduce API calls
            batch_size = 10  # Process 10 articles per API call instead of 3
            for i in range(0, len(articles), batch_size):
                batch = articles[i:i + batch_size]
                
                # Create enhanced pharmaceutical research prompt
                keywords_str = ", ".join(keywords)
                
                prompt = f"""You are a senior pharmaceutical research analyst at Sumitomo Pharma America with expertise in drug development, clinical trials, and regulatory affairs. 

Analyze these articles for relevance to pharmaceutical research on: {keywords_str}

Context: This analysis is for Sumitomo Pharma America, focusing on therapeutic areas including oncology, psychiatry, neurology, and urology. Consider the company's portfolio and strategic interests when evaluating relevance.

For each article, provide a comprehensive analysis in JSON format with these exact fields:
1. relevance_score: Integer 0-100 (higher = more relevant to pharma research)
2. summary: Concise 2-3 sentence summary focusing on pharmaceutical aspects
3. key_insights: Key pharmaceutical insights, clinical significance, or drug development implications
4. clinical_significance: Clinical relevance, patient impact, or therapeutic implications
5. regulatory_implications: FDA/regulatory considerations, approval status, or compliance issues
6. market_impact: Commercial implications, market potential, or competitive landscape
7. research_quality: Assessment of research methodology and evidence quality (High/Medium/Low)
8. publication_date: Extract publication date from content if present (YYYY-MM-DD format), otherwise null

Focus on pharmaceutical, clinical, and regulatory aspects. Ignore non-pharma content.

Articles to analyze:
"""
                
                for j, article in enumerate(batch):
                    # Truncate content for prompt efficiency
                    content_preview = article['content'][:800] + "..." if len(article['content']) > 800 else article['content']
                    prompt += f"\n{j+1}. Title: {article['title']}\nContent: {content_preview}\nSource: {article.get('source_name', 'Unknown')}\n"
                
                prompt += f"""
Respond with a JSON array containing analysis for each article in order. Example format:
[
  {{
    "relevance_score": 85,
    "summary": "Brief pharmaceutical-focused summary",
    "key_insights": "Key pharma insights and implications",
    "clinical_significance": "Clinical relevance and patient impact",
    "regulatory_implications": "FDA/regulatory considerations",
    "market_impact": "Commercial and market implications",
    "research_quality": "High",
    "publication_date": "2024-01-15"
  }}
]
"""
                
                try:
                    # RATE LIMITING: Add small delay between API calls
                    if curation_stats['openai_api_calls'] > 0:
                        time.sleep(0.5)  # 500ms delay between calls
                    
                    logger.info(f"📞 Making OpenAI API call {curation_stats['openai_api_calls'] + 1} for batch of {len(batch)} articles...")
                    
                    response = self.openai_client.chat.completions.create(
                        model=self.config.OPENAI_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=self.config.MAX_TOKENS,
                        temperature=self.config.TEMPERATURE
                    )
                    
                    curation_stats['openai_api_calls'] += 1
                    
                    # Parse response with better error handling
                    response_text = response.choices[0].message.content.strip()
                    
                    # Clean up response text
                    if response_text.startswith('```json'):
                        response_text = response_text[7:]
                    if response_text.endswith('```'):
                        response_text = response_text[:-3]
                    
                    curation_data = json.loads(response_text)
                    
                    # Apply enhanced curation to articles
                    for j, article in enumerate(batch):
                        if j < len(curation_data):
                            curation = curation_data[j]
                            relevance_score = curation.get('relevance_score', 50)
                            
                            # Filter by relevance score during curation (increased threshold)
                            if relevance_score < 40:  # Increased from 30 to 40 for stricter filtering
                                curation_stats['articles_filtered_by_ai_relevance'] += 1
                                logger.debug(f"🔍 Curation: Article '{article.get('title', '')[:50]}...' filtered out - low relevance score {relevance_score}")
                                continue
                            
                            # Extract and validate publication date from LLM
                            extracted_date = curation.get('publication_date', None)
                            if extracted_date and extracted_date != 'null':
                                try:
                                    # Try to parse the extracted date
                                    parsed_date = datetime.fromisoformat(extracted_date)
                                    article['llm_extracted_date'] = parsed_date.isoformat()
                                    article['llm_date_found'] = True
                                except:
                                    article['llm_extracted_date'] = None
                                    article['llm_date_found'] = False
                            else:
                                article['llm_extracted_date'] = None
                                article['llm_date_found'] = False
                            
                            article.update({
                                'ai_relevance_score': relevance_score,
                                'ai_summary': curation.get('summary', article['content'][:200]),
                                'ai_insights': curation.get('key_insights', ''),
                                'ai_significance': curation.get('clinical_significance', ''),
                                'ai_regulatory': curation.get('regulatory_implications', ''),
                                'ai_market_impact': curation.get('market_impact', ''),
                                'ai_research_quality': curation.get('research_quality', 'Medium')
                            })
                            curation_stats['articles_with_ai_analysis'] += 1
                        else:
                            # Fallback for missing analysis
                            article.update({
                                'ai_relevance_score': 50,
                                'ai_summary': article['content'][:200],
                                'ai_insights': '',
                                'ai_significance': '',
                                'ai_regulatory': '',
                                'ai_market_impact': '',
                                'ai_research_quality': 'Medium'
                            })
                        
                        curated_articles.append(article)
                        curation_stats['articles_curated'] += 1
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse OpenAI response as JSON: {e}")
                    logger.error(f"Response text: {response_text[:200]}...")
                    # Fallback: add basic curation
                    for article in batch:
                        article.update({
                            'ai_relevance_score': 50,
                            'ai_summary': article['content'][:200],
                            'ai_insights': '',
                            'ai_significance': '',
                            'ai_regulatory': '',
                            'ai_market_impact': '',
                            'ai_research_quality': 'Medium'
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
                            'ai_significance': '',
                            'ai_regulatory': '',
                            'ai_market_impact': '',
                            'ai_research_quality': 'Medium'
                        })
                        curated_articles.append(article)
            
            # Log detailed curation statistics
            logger.info("📊 AI curation statistics:")
            logger.info(f"   Total articles input: {curation_stats['total_articles_processed']}")
            logger.info(f"   Filtered by basic relevance: {curation_stats['articles_filtered_by_basic_relevance']}")
            logger.info(f"   Filtered by AI relevance: {curation_stats['articles_filtered_by_ai_relevance']}")
            logger.info(f"   Articles with AI analysis: {curation_stats['articles_with_ai_analysis']}")
            logger.info(f"   OpenAI API calls made: {curation_stats['openai_api_calls']}")
            logger.info(f"   Final curated articles: {curation_stats['articles_curated']}")
            logger.info(f"   💰 Cost savings: Reduced from {curation_stats['total_articles_processed']} to {curation_stats['openai_api_calls']} API calls (~{100 - int(curation_stats['openai_api_calls'] / max(1, curation_stats['total_articles_processed']) * 100)}% reduction)")
            
            # Store curation statistics for later use
            self._last_curation_stats = curation_stats
            
            logger.info(f"AI curation completed: {len(curated_articles)} articles analyzed")
            return curated_articles
            
        except Exception as e:
            logger.error(f"Intelligent curation error: {str(e)}")
            return articles
    
    def _score_and_rank_articles(self, articles: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Enhanced scoring and ranking with AI analysis integration"""
        keywords_lower = [kw.lower() for kw in keywords]
        
        for article in articles:
            # Calculate keyword-based score
            text = (article['title'] + " " + article['content']).lower()
            keyword_count = sum(1 for kw in keywords_lower if kw in text)
            
            # Base score from keyword matching
            base_score = min(90, keyword_count * 20)
            
            # Enhanced pharma-specific bonus scoring
            pharma_terms = {
                'clinical trial': 15, 'fda': 20, 'approval': 15, 'drug': 10, 
                'pharmaceutical': 15, 'therapeutic': 10, 'dosage': 8, 
                'efficacy': 12, 'safety': 12, 'regulatory': 10,
                'phase iii': 20, 'phase ii': 15, 'phase i': 10,
                'biomarker': 8, 'pharmacokinetics': 8, 'adverse event': 8
            }
            
            pharma_bonus = 0
            for term, bonus in pharma_terms.items():
                if term in text:
                    pharma_bonus += bonus
            
            # Title bonus (keywords in title are more important)
            title_text = article.get('title', '').lower()
            title_keyword_count = sum(1 for kw in keywords_lower if kw in title_text)
            title_bonus = min(20, title_keyword_count * 8)
            
            # AI score integration (if available)
            ai_bonus = 0
            if 'ai_relevance_score' in article:
                ai_score = article['ai_relevance_score']
                ai_bonus = ai_score * 0.4  # 40% weight to AI score
                
                # Additional bonus for high research quality
                research_quality = article.get('ai_research_quality', 'Medium')
                if research_quality == 'High':
                    ai_bonus += 10
                elif research_quality == 'Low':
                    ai_bonus -= 5
            
            # Source credibility bonus
            source_bonus = 0
            source_name = article.get('source_name', '').lower()
            credible_sources = {
                'pubmed': 15, 'fda': 20, 'nejm': 15, 'nature': 15, 'lancet': 15,
                'reuters': 8, 'bloomberg': 8, 'wsj': 8, 'ft': 8,
                'fiercepharma': 10, 'biopharmadive': 10, 'pharmatimes': 8
            }
            
            for source, bonus in credible_sources.items():
                if source in source_name:
                    source_bonus += bonus
                    break
            
            # Calculate final composite score
            final_score = min(100, base_score + pharma_bonus + title_bonus + ai_bonus + source_bonus)
            article['relevance_score'] = int(final_score)
            
            # Add detailed scoring breakdown for transparency
            article['scoring_breakdown'] = {
                'base_score': int(base_score),
                'pharma_bonus': int(pharma_bonus),
                'title_bonus': int(title_bonus),
                'ai_bonus': int(ai_bonus),
                'source_bonus': int(source_bonus),
                'final_score': int(final_score)
            }
        
        # Sort by relevance score (descending)
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
        """Enhanced final result aggregation with comprehensive metadata"""
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
                
                # Enhanced AI analysis fields
                'ai_insights': article.get('ai_insights', ''),
                'ai_significance': article.get('ai_significance', ''),
                'ai_regulatory': article.get('ai_regulatory', ''),
                'ai_market_impact': article.get('ai_market_impact', ''),
                'ai_research_quality': article.get('ai_research_quality', 'Medium'),
                'ai_relevance_score': article.get('ai_relevance_score', 0),
                
                # Enhanced metadata
                'scoring_breakdown': article.get('scoring_breakdown', {}),
                'pmid': article.get('pmid', ''),
                'doi': article.get('doi', ''),
                'journal': article.get('journal', ''),
                'mesh_terms': article.get('mesh_terms', []),
                'publication_type': article.get('publication_type', ''),
                'image_url': article.get('image_url', ''),
                'raw_score': article.get('raw_score', 0)
            }
            final_results.append(result)
        
        return final_results
    
    def _organize_results_by_source(self, final_results: List[Dict[str, Any]], raw_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Enhanced organization of results by source for UI display"""
        results_by_source = {
            'pubmed': [],
            'exa': [],
            'tavily': [],
            'openai_curated': []
        }
        
        # Group results by source
        for result in final_results:
            source = result.get('source', '').lower()
            
            if 'pubmed' in source:
                results_by_source['pubmed'].append(result)
            elif 'exa' in source:
                results_by_source['exa'].append(result)
            elif 'tavily' in source:
                results_by_source['tavily'].append(result)
            else:
                # Check if this is an AI-curated result (has enhanced AI analysis)
                if (result.get('ai_insights') or result.get('ai_significance') or 
                    result.get('ai_regulatory') or result.get('ai_market_impact')):
                    results_by_source['openai_curated'].append(result)
                else:
                    # Fallback based on source name or URL
                    source_name = result.get('source_name', '').lower()
                    if any(term in source_name for term in ['pubmed', 'journal', 'medical']):
                        results_by_source['pubmed'].append(result)
                    elif any(term in source_name for term in ['news', 'reuters', 'bloomberg']):
                        results_by_source['exa'].append(result)
                    else:
                        results_by_source['tavily'].append(result)
        
        # Add comprehensive source metadata with enhanced statistics
        results_by_source['metadata'] = {
            'pubmed_count': len(results_by_source['pubmed']),
            'exa_count': len(results_by_source['exa']),
            'tavily_count': len(results_by_source['tavily']),
            'openai_curated_count': len(results_by_source['openai_curated']),
            'total_sources': len([k for k, v in results_by_source.items() if k != 'metadata' and len(v) > 0]),
            'source_breakdown': {
                'pubmed': {
                    'count': len(results_by_source['pubmed']),
                    'description': 'Peer-reviewed medical literature and clinical studies'
                },
                'exa': {
                    'count': len(results_by_source['exa']),
                    'description': 'AI-powered neural search across pharmaceutical domains'
                },
                'tavily': {
                    'count': len(results_by_source['tavily']),
                    'description': 'Comprehensive web search across pharma domains'
                },
                'openai_curated': {
                    'count': len(results_by_source['openai_curated']),
                    'description': 'AI-analyzed results with clinical insights and market impact'
                }
            },
            # Add filtering and curation statistics
            'filtering_stats': getattr(self, '_last_filtering_stats', {}),
            'curation_stats': getattr(self, '_last_curation_stats', {}),
            'date_filtering_applied': True,
            'curation_date_filtering_applied': True
        }
        
        return results_by_source
