"""
LangGraph-based Pharma News Research Agent
Multi-agent pipeline for intelligent pharmaceutical news research
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from dataclasses import dataclass

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ArticleData:
    """Structured article data"""
    title: str
    content: str
    url: str
    source: str
    raw_date: Optional[str] = None
    extracted_date: Optional[datetime] = None
    relevance_score: Optional[int] = None
    relevance_reason: Optional[str] = None
    summary: Optional[str] = None
    highlighted_content: Optional[str] = None
    mentioned_keywords: Optional[List[str]] = None
    article_type: Optional[str] = None  # 'research', 'news', 'press_release', 'company_page', etc.
    clinical_significance: Optional[str] = None
    regulatory_impact: Optional[str] = None
    market_impact: Optional[str] = None

class AgentState(TypedDict):
    """State for the LangGraph workflow"""
    # Input
    keywords: List[str]
    start_date: datetime
    end_date: datetime
    search_type: str
    search_engines: List[str]
    
    # Raw data
    raw_articles: List[Dict[str, Any]]
    
    # Processed data
    articles: List[ArticleData]
    
    # Results
    final_results: List[ArticleData]
    
    # Metadata
    workflow_stats: Dict[str, Any]
    errors: List[str]

class DateExtractionAgent:
    """Agent responsible for extracting and validating dates from articles"""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.1,
            max_tokens=1000
        )
        
    def extract_date(self, article: Dict[str, Any]) -> Optional[datetime]:
        """Extract date from article using multiple strategies"""
        title = article.get('title', '')
        content = article.get('content', '')
        raw_date = article.get('date', '')
        
        # Strategy 1: Parse existing date if available
        if raw_date:
            try:
                parsed_date = self._parse_date_string(raw_date)
                if parsed_date and self._is_valid_date(parsed_date):
                    logger.debug(f"✅ Found valid date in metadata: {parsed_date.date()}")
                    return parsed_date
            except Exception as e:
                logger.debug(f"Failed to parse metadata date: {e}")
        
        # Strategy 2: Extract from content using LLM
        extracted_date = self._llm_extract_date(title, content)
        if extracted_date and self._is_valid_date(extracted_date):
            logger.debug(f"✅ LLM extracted date: {extracted_date.date()}")
            return extracted_date
            
        # Strategy 3: Regex patterns as fallback
        extracted_date = self._regex_extract_date(title, content)
        if extracted_date and self._is_valid_date(extracted_date):
            logger.debug(f"✅ Regex extracted date: {extracted_date.date()}")
            return extracted_date
            
        logger.debug(f"❌ No valid date found for: {title[:50]}...")
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse various date string formats"""
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y/%m/%d'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
    
    def _llm_extract_date(self, title: str, content: str) -> Optional[datetime]:
        """Use LLM to extract publication date from content"""
        try:
            prompt = ChatPromptTemplate.from_template("""
            Extract the publication date from this pharmaceutical/medical article.
            
            Title: {title}
            Content: {content}
            
            Look for:
            - Publication dates
            - Press release dates  
            - Article dates
            - Study dates
            - Release dates
            
            Return ONLY the date in YYYY-MM-DD format, or "none" if no date found.
            """)
            
            response = self.llm.invoke(
                prompt.format(title=title[:200], content=content[:1000])
            )
            
            date_str = response.content.strip().lower()
            if date_str != "none" and date_str:
                return self._parse_date_string(date_str)
                
        except Exception as e:
            logger.debug(f"LLM date extraction failed: {e}")
            
        return None
    
    def _regex_extract_date(self, title: str, content: str) -> Optional[datetime]:
        """Extract date using regex patterns"""
        text_to_search = (title + " " + content)[:1500]
        
        date_patterns = [
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', '%Y-%m-%d'),
            (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', '%B %d %Y'),
            (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})', '%b %d %Y'),
            (r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', '%d %B %Y'),
            (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{4})', '%d %b %Y'),
            (r'(?:Published|Date|Posted|Released):\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})', '%Y-%m-%d'),
        ]
        
        extracted_dates = []
        
        for pattern, date_format in date_patterns:
            matches = re.finditer(pattern, text_to_search, re.IGNORECASE)
            for match in matches:
                try:
                    if '%B' in date_format or '%b' in date_format:
                        date_str = ' '.join(match.groups())
                    else:
                        if pattern.startswith(r'(\d{4})'):
                            date_str = f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
                        else:
                            date_str = ' '.join(match.groups())
                    
                    parsed_date = datetime.strptime(date_str.strip(), date_format)
                    extracted_dates.append(parsed_date)
                except (ValueError, AttributeError):
                    continue
        
        if extracted_dates:
            # Return the most recent valid date
            valid_dates = [d for d in extracted_dates if self._is_valid_date(d)]
            return max(valid_dates) if valid_dates else None
            
        return None
    
    def _is_valid_date(self, date: datetime) -> bool:
        """Check if date is within reasonable range"""
        now = datetime.now()
        return datetime(1990, 1, 1) <= date <= now + timedelta(days=30)

class RelevanceAgent:
    """Agent responsible for determining article relevance and type"""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.2,
            max_tokens=2000
        )
        self.parser = JsonOutputParser()
        
    def analyze_relevance(self, article: ArticleData, keywords: List[str], search_type: str) -> Dict[str, Any]:
        """Analyze article relevance and provide detailed scoring"""
        try:
            prompt = ChatPromptTemplate.from_template("""
            Analyze this pharmaceutical/medical article for relevance to the search query.
            
            Search Keywords: {keywords}
            Search Type: {search_type}
            
            Article Title: {title}
            Article Content: {content}
            
            Provide analysis in this JSON format:
            {{
                "relevance_score": 0-100,
                "relevance_reason": "Detailed explanation of relevance",
                "article_type": "research|news|press_release|company_page|clinical_trial|regulatory|other",
                "mentioned_keywords": ["list", "of", "found", "keywords"],
                "clinical_significance": "Clinical relevance explanation",
                "regulatory_impact": "Regulatory implications if any",
                "market_impact": "Market implications if any",
                "summary": "2-3 sentence summary of the article"
            }}
            
            Scoring Criteria:
            - 90-100: Perfect match, highly relevant research/clinical data
            - 80-89: Very relevant, important news or study results
            - 70-79: Relevant, useful information
            - 60-69: Somewhat relevant, minor connection
            - 50-59: Barely relevant, weak connection
            - 0-49: Not relevant, filter out
            
            Consider:
            - Keyword matches in title vs content
            - Article type and credibility
            - Clinical/medical significance
            - Recency and importance
            - Source reliability
            """)
            
            response = self.llm.invoke(prompt.format(
                keywords=', '.join(keywords),
                search_type=search_type,
                title=article.title,
                content=article.content[:2000]  # Limit content size
            ))
            
            # Parse JSON response
            analysis = json.loads(response.content)
            
            # Validate and clean the analysis
            analysis['relevance_score'] = max(0, min(100, analysis.get('relevance_score', 0)))
            analysis['mentioned_keywords'] = analysis.get('mentioned_keywords', [])
            analysis['article_type'] = analysis.get('article_type', 'other')
            
            return analysis
            
        except Exception as e:
            logger.error(f"Relevance analysis failed: {e}")
            return {
                'relevance_score': 0,
                'relevance_reason': f"Analysis failed: {str(e)}",
                'article_type': 'unknown',
                'mentioned_keywords': [],
                'clinical_significance': None,
                'regulatory_impact': None,
                'market_impact': None,
                'summary': f"Failed to analyze: {article.title[:100]}..."
            }

class ContentEnhancementAgent:
    """Agent responsible for content enhancement and keyword highlighting"""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.3,
            max_tokens=1500
        )
    
    def enhance_content(self, article: ArticleData, keywords: List[str]) -> str:
        """Create highlighted version of content with keyword emphasis"""
        content = article.content
        mentioned_keywords = article.mentioned_keywords or []
        
        # Combine search keywords with mentioned keywords
        all_keywords = list(set(keywords + mentioned_keywords))
        
        # Create highlighted content
        highlighted_content = content
        for keyword in all_keywords:
            if keyword.lower() in highlighted_content.lower():
                # Use case-insensitive replacement while preserving original case
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                highlighted_content = pattern.sub(
                    f'<mark class="keyword-highlight">{keyword}</mark>',
                    highlighted_content
                )
        
        return highlighted_content

class LangGraphPharmaAgent:
    """Main LangGraph-based Pharma Research Agent"""
    
    def __init__(self, config: Config):
        self.config = config
        self.date_agent = DateExtractionAgent(config)
        self.relevance_agent = RelevanceAgent(config)
        self.content_agent = ContentEnhancementAgent(config)
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("collect_data", self._collect_data_node)
        workflow.add_node("extract_dates", self._extract_dates_node)
        workflow.add_node("filter_by_date", self._filter_by_date_node)
        workflow.add_node("analyze_relevance", self._analyze_relevance_node)
        workflow.add_node("filter_by_relevance", self._filter_by_relevance_node)
        workflow.add_node("enhance_content", self._enhance_content_node)
        workflow.add_node("finalize_results", self._finalize_results_node)
        
        # Define the flow
        workflow.set_entry_point("collect_data")
        
        workflow.add_edge("collect_data", "extract_dates")
        workflow.add_edge("extract_dates", "filter_by_date")
        workflow.add_edge("filter_by_date", "analyze_relevance")
        workflow.add_edge("analyze_relevance", "filter_by_relevance")
        workflow.add_edge("filter_by_relevance", "enhance_content")
        workflow.add_edge("enhance_content", "finalize_results")
        workflow.add_edge("finalize_results", END)
        
        return workflow.compile()
    
    def _collect_data_node(self, state: AgentState) -> AgentState:
        """Collect raw data from all sources"""
        logger.info("📡 Collecting data from multiple sources...")
        
        # Import the existing data collection logic
        from pharma_agent import PharmaNewsAgent
        temp_agent = PharmaNewsAgent()
        
        try:
            raw_data = temp_agent._collect_multi_source_data(
                state["keywords"],
                state["start_date"], 
                state["end_date"],
                state["search_engines"]
            )
            
            # Flatten all articles into a single list
            raw_articles = []
            for source, articles in raw_data.items():
                for article in articles:
                    article['source'] = source
                    raw_articles.append(article)
            
            state["raw_articles"] = raw_articles
            state["workflow_stats"] = {
                "total_collected": len(raw_articles),
                "sources_used": list(raw_data.keys())
            }
            
            logger.info(f"✅ Collected {len(raw_articles)} articles from {len(raw_data)} sources")
            
        except Exception as e:
            logger.error(f"Data collection failed: {e}")
            state["errors"].append(f"Data collection failed: {str(e)}")
            state["raw_articles"] = []
        
        return state
    
    def _extract_dates_node(self, state: AgentState) -> AgentState:
        """Extract dates from all articles"""
        logger.info("📅 Extracting dates from articles...")
        
        articles = []
        date_stats = {"with_dates": 0, "without_dates": 0, "extracted_dates": 0}
        
        for raw_article in state["raw_articles"]:
            article_data = ArticleData(
                title=raw_article.get('title', ''),
                content=raw_article.get('content', ''),
                url=raw_article.get('url', ''),
                source=raw_article.get('source', ''),
                raw_date=raw_article.get('date', '')
            )
            
            # Extract date using the date agent
            extracted_date = self.date_agent.extract_date(raw_article)
            if extracted_date:
                article_data.extracted_date = extracted_date
                date_stats["with_dates"] += 1
                if not raw_article.get('date'):
                    date_stats["extracted_dates"] += 1
            else:
                date_stats["without_dates"] += 1
            
            articles.append(article_data)
        
        state["articles"] = articles
        state["workflow_stats"]["date_extraction"] = date_stats
        
        logger.info(f"✅ Date extraction complete: {date_stats}")
        
        return state
    
    def _filter_by_date_node(self, state: AgentState) -> AgentState:
        """Filter articles by date range"""
        logger.info("🗓️ Filtering articles by date range...")
        
        start_date = state["start_date"]
        end_date = state["end_date"]
        
        filtered_articles = []
        date_filter_stats = {"in_range": 0, "out_of_range": 0, "no_date": 0}
        
        for article in state["articles"]:
            if not article.extracted_date:
                date_filter_stats["no_date"] += 1
                continue
                
            if start_date <= article.extracted_date <= end_date:
                filtered_articles.append(article)
                date_filter_stats["in_range"] += 1
            else:
                date_filter_stats["out_of_range"] += 1
        
        state["articles"] = filtered_articles
        state["workflow_stats"]["date_filtering"] = date_filter_stats
        
        logger.info(f"✅ Date filtering complete: {date_filter_stats}")
        
        return state
    
    def _analyze_relevance_node(self, state: AgentState) -> AgentState:
        """Analyze relevance of all articles"""
        logger.info("🎯 Analyzing article relevance...")
        
        relevance_stats = {"analyzed": 0, "failed": 0}
        
        for article in state["articles"]:
            try:
                analysis = self.relevance_agent.analyze_relevance(
                    article, 
                    state["keywords"], 
                    state["search_type"]
                )
                
                # Update article with analysis results
                article.relevance_score = analysis["relevance_score"]
                article.relevance_reason = analysis["relevance_reason"]
                article.article_type = analysis["article_type"]
                article.mentioned_keywords = analysis["mentioned_keywords"]
                article.clinical_significance = analysis["clinical_significance"]
                article.regulatory_impact = analysis["regulatory_impact"]
                article.market_impact = analysis["market_impact"]
                article.summary = analysis["summary"]
                
                relevance_stats["analyzed"] += 1
                
            except Exception as e:
                logger.error(f"Relevance analysis failed for {article.title}: {e}")
                relevance_stats["failed"] += 1
                article.relevance_score = 0
                article.relevance_reason = f"Analysis failed: {str(e)}"
        
        state["workflow_stats"]["relevance_analysis"] = relevance_stats
        
        logger.info(f"✅ Relevance analysis complete: {relevance_stats}")
        
        return state
    
    def _filter_by_relevance_node(self, state: AgentState) -> AgentState:
        """Filter articles by relevance score"""
        logger.info("🔍 Filtering articles by relevance...")
        
        # Keep articles with relevance score >= 50
        min_relevance = 50
        filtered_articles = []
        relevance_filter_stats = {"kept": 0, "filtered_out": 0}
        
        for article in state["articles"]:
            if article.relevance_score and article.relevance_score >= min_relevance:
                filtered_articles.append(article)
                relevance_filter_stats["kept"] += 1
            else:
                relevance_filter_stats["filtered_out"] += 1
        
        state["articles"] = filtered_articles
        state["workflow_stats"]["relevance_filtering"] = relevance_filter_stats
        
        logger.info(f"✅ Relevance filtering complete: {relevance_filter_stats}")
        
        return state
    
    def _enhance_content_node(self, state: AgentState) -> AgentState:
        """Enhance content with keyword highlighting"""
        logger.info("✨ Enhancing content with keyword highlighting...")
        
        for article in state["articles"]:
            article.highlighted_content = self.content_agent.enhance_content(
                article, 
                state["keywords"]
            )
        
        logger.info(f"✅ Content enhancement complete for {len(state['articles'])} articles")
        
        return state
    
    def _finalize_results_node(self, state: AgentState) -> AgentState:
        """Finalize and sort results"""
        logger.info("📊 Finalizing results...")
        
        # Sort by relevance score (descending)
        sorted_articles = sorted(
            state["articles"], 
            key=lambda x: x.relevance_score or 0, 
            reverse=True
        )
        
        state["final_results"] = sorted_articles
        
        # Update final stats
        state["workflow_stats"]["final_results"] = len(sorted_articles)
        state["workflow_stats"]["completion_time"] = datetime.now().isoformat()
        
        logger.info(f"✅ Workflow complete: {len(sorted_articles)} final results")
        
        return state
    
    async def execute_workflow(self, keywords: List[str], start_date: datetime, 
                             end_date: datetime, search_type: str = 'standard',
                             search_engines: List[str] = None) -> Dict[str, Any]:
        """Execute the complete LangGraph workflow"""
        
        if search_engines is None:
            search_engines = ['pubmed', 'exa', 'tavily']
        
        # Initialize state
        initial_state = AgentState(
            keywords=keywords,
            start_date=start_date,
            end_date=end_date,
            search_type=search_type,
            search_engines=search_engines,
            raw_articles=[],
            articles=[],
            final_results=[],
            workflow_stats={},
            errors=[]
        )
        
        # Execute workflow
        final_state = await self.workflow.ainvoke(initial_state)
        
        # Format results for API response
        results = []
        for article in final_state["final_results"]:
            results.append({
                'title': article.title,
                'content': article.content,
                'url': article.url,
                'source': article.source,
                'date': article.extracted_date.isoformat() if article.extracted_date else None,
                'raw_date': article.raw_date,
                'relevance_score': article.relevance_score,
                'relevance_reason': article.relevance_reason,
                'summary': article.summary,
                'highlighted_content': article.highlighted_content,
                'mentioned_keywords': article.mentioned_keywords,
                'article_type': article.article_type,
                'clinical_significance': article.clinical_significance,
                'regulatory_impact': article.regulatory_impact,
                'market_impact': article.market_impact
            })
        
        return {
            'success': True,
            'results': results,
            'metadata': {
                'keywords': keywords,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'search_type': search_type,
                'timestamp': datetime.now().isoformat(),
                'workflow_stats': final_state["workflow_stats"],
                'errors': final_state["errors"]
            }
        }
