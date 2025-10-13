"""
Multi-Agent Pharma News Research System
Simplified version with specialized agents for date extraction, relevance analysis, and content enhancement
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from openai import OpenAI
from config import Config
from difflib import SequenceMatcher

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
    article_type: Optional[str] = None
    clinical_significance: Optional[str] = None
    regulatory_impact: Optional[str] = None
    market_impact: Optional[str] = None

class DateExtractionAgent:
    """Agent responsible for extracting and validating dates from articles"""
    
    def __init__(self, config: Config):
        self.config = config
        self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        
    def extract_date(self, article: Dict[str, Any]) -> Optional[datetime]:
        """Extract date from article using multiple strategies with full context"""
        title = article.get('title', '')
        content = article.get('content', '')
        raw_date = article.get('date', '')
        url = article.get('url', '')
        # Build metadata string from article fields
        metadata = f"Source: {article.get('source', 'Unknown')}"
        if article.get('authors'):
            metadata += f" | Authors: {article.get('authors', '')[:200]}"
        
        # Strategy 1: Parse existing date if available
        if raw_date:
            try:
                parsed_date = self._parse_date_string(raw_date)
                if parsed_date and self._is_valid_date(parsed_date):
                    logger.debug(f"✅ Found valid date in metadata: {parsed_date.date()}")
                    return parsed_date
            except Exception as e:
                logger.debug(f"Failed to parse metadata date: {e}")
        
        # Strategy 2: Extract from content using LLM with full context (URL, content, metadata)
        extracted_date = self._llm_extract_date(title, content, url, metadata)
        if extracted_date and self._is_valid_date(extracted_date):
            logger.debug(f"✅ LLM extracted date: {extracted_date.date()}")
            return extracted_date
            
        # Strategy 3: Regex patterns as fallback (including URL patterns)
        extracted_date = self._regex_extract_date(title, content, url)
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
    
    def _llm_extract_date(self, title: str, content: str, url: str = "", metadata: str = "") -> Optional[datetime]:
        """Use fast LLM to extract publication date from complete article context"""
        try:
            # Build comprehensive context with URL, metadata, and full content
            article_context = f"""
ARTICLE FOR DATE EXTRACTION:

URL: {url[:200] if url else "N/A"}

Title: {title[:500]}

Content (first 3000 characters):
{content[:3000]}

Metadata/Additional Info:
{metadata[:500] if metadata else "N/A"}

CONTEXT:
- This is a pharmaceutical/medical research article
- We need to find the publication or release date
- Look for explicit dates in the URL, title, content, or metadata
- Common patterns: "Published on", "Posted", "Released", "Date:", timestamps, dates in URL path, etc.
- The URL often contains the publication date (e.g., /2024/03/15/ or /20240315/)
"""
            
            system_prompt = """You are a date extraction specialist. Your job is to find publication dates in medical and pharmaceutical articles.

Return ONLY the date in YYYY-MM-DD format. If no date is found, return exactly "none" (lowercase).
Do not include any other text, explanation, or formatting."""

            user_prompt = f"""{article_context}

TASK: Extract the publication date from this article.

INSTRUCTIONS:
1. Check URL first - often contains date (e.g., /2024/03/15/ or /20240315/)
2. Look for explicit dates in content (publication date, posted date, release date)
3. Check title and metadata for dates
4. Prefer dates near the beginning or end of the content
5. Only return dates that are clearly publication dates
6. Format: YYYY-MM-DD (e.g., 2024-03-15)
7. If no date found: return exactly "none"

Return ONLY the date or "none"."""
            
            # Use faster, cheaper model for date extraction
            response = self.openai_client.chat.completions.create(
                model=self.config.DATE_EXTRACTION_MODEL,  # Use gpt-3.5-turbo instead
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=50,
                temperature=0.0
            )
            
            date_str = response.choices[0].message.content.strip().lower()
            if date_str != "none" and date_str:
                extracted_date = self._parse_date_string(date_str)
                if extracted_date:
                    logger.info(f"✅ LLM extracted date {extracted_date.date()} from content: {title[:60]}...")
                    return extracted_date
                
        except Exception as e:
            logger.debug(f"LLM date extraction failed: {e}")
            
        return None
    
    def _regex_extract_date(self, title: str, content: str, url: str = "") -> Optional[datetime]:
        """Extract date using regex patterns from title, content, and URL"""
        # Include URL in the search text - dates are often in URL paths
        text_to_search = (url + " " + title + " " + content)[:2000]
        
        date_patterns = [
            # URL-specific patterns (e.g., /2024/03/15/ or /20240315/)
            (r'/(\d{4})/(\d{1,2})/(\d{1,2})/', '%Y-%m-%d'),
            (r'/(\d{8})/', '%Y%m%d'),  # /20240315/
            # Standard date formats
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
                    elif date_format == '%Y%m%d':
                        # Handle /20240315/ format
                        date_str = match.group(1)
                    else:
                        if pattern.startswith(r'(\d{4})') or pattern.startswith(r'/(\d{4})'):
                            # Handle YYYY-MM-DD or /YYYY/MM/DD/ formats
                            groups = match.groups()
                            if len(groups) >= 3:
                                date_str = f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
                            else:
                                date_str = ' '.join(groups)
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
        self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        
    def analyze_relevance(self, article: ArticleData, keywords: List[str], search_type: str) -> Dict[str, Any]:
        """Analyze article relevance and provide detailed scoring"""
        try:
            # Create rich context for the agent
            article_context = f"""
ARTICLE DETAILS:
Title: {article.title}
Source: {article.source}
URL: {article.url}
Date: {article.extracted_date.strftime('%Y-%m-%d') if article.extracted_date else 'Unknown'}
Content Preview: {article.content[:3000]}...

SEARCH CONTEXT:
Keywords: {', '.join(keywords)}
Search Type: {search_type}
Domain: Pharmaceutical/Medical Research
"""
            
            system_prompt = """You are an expert pharmaceutical research analyst. Your job is to evaluate medical and pharmaceutical articles for relevance, quality, and significance.

You MUST respond with ONLY valid JSON. No markdown, no code blocks, no extra text - just raw JSON."""

            user_prompt = f"""{article_context}

TASK: Analyze this article and provide a comprehensive relevance assessment.

OUTPUT FORMAT (raw JSON only, no markdown):
{{
    "relevance_score": <number 0-100>,
    "relevance_reason": "<detailed explanation>",
    "article_type": "<research|news|press_release|company_page|clinical_trial|regulatory|other>",
    "mentioned_keywords": ["<keyword1>", "<keyword2>", ...],
    "clinical_significance": "<clinical relevance explanation or 'None'>",
    "regulatory_impact": "<regulatory implications or 'None'>",
    "market_impact": "<market implications or 'None'>",
    "summary": "<2-3 sentence summary>"
}}

SCORING GUIDELINES:
- 90-100: Perfect match, highly relevant research/clinical data, directly addresses keywords
- 80-89: Very relevant, important news or study results, strong keyword presence
- 70-79: Relevant, useful information, moderate keyword presence
- 60-69: Somewhat relevant, minor connection to keywords
- 50-59: Barely relevant, weak connection
- 0-49: Not relevant, no meaningful connection

EVALUATION CRITERIA:
1. Keyword Presence: How many search keywords appear in title and content?
2. Content Quality: Is this credible research, news, or promotional material?
3. Clinical Significance: Does it discuss clinical trials, efficacy, safety, or patient outcomes?
4. Regulatory Relevance: Are there FDA approvals, regulatory decisions, or guidelines?
5. Market Impact: Business implications, commercial developments, or market dynamics?
6. Source Credibility: Is it from a reputable source (PubMed, peer-reviewed, official news)?

Return ONLY the JSON object, nothing else."""
            
            response = self.openai_client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2000,
                temperature=0.1,
                response_format={"type": "json_object"}  # Enforce JSON mode
            )
            
            # Get response content
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                # Extract JSON from markdown code block
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
                else:
                    # Try to find JSON object
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(0)
            
            # Parse JSON response
            analysis = json.loads(response_text)
            
            # Validate and clean the analysis
            analysis['relevance_score'] = max(0, min(100, analysis.get('relevance_score', 0)))
            analysis['mentioned_keywords'] = analysis.get('mentioned_keywords', [])
            analysis['article_type'] = analysis.get('article_type', 'other')
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Relevance analysis - JSON parse error: {e}")
            logger.error(f"Response was: {response.choices[0].message.content[:500]}")
            # Return a default score of 50 (neutral) instead of 0 when parsing fails
            return {
                'relevance_score': 50,  # Neutral score - don't discard on parse errors
                'relevance_reason': f"JSON parsing failed, article may be relevant: {article.title[:100]}",
                'article_type': 'unknown',
                'mentioned_keywords': keywords,  # Assume keywords present
                'clinical_significance': 'Unable to analyze due to parsing error',
                'regulatory_impact': 'Unable to analyze',
                'market_impact': 'Unable to analyze',
                'summary': article.content[:200] + "..." if len(article.content) > 200 else article.content
            }
        except Exception as e:
            logger.error(f"Relevance analysis failed: {e}")
            # Return neutral score instead of 0
            return {
                'relevance_score': 50,  # Neutral score - don't discard on errors
                'relevance_reason': f"Analysis failed but article collected: {str(e)[:100]}",
                'article_type': 'unknown',
                'mentioned_keywords': keywords,
                'clinical_significance': 'Unable to analyze',
                'regulatory_impact': 'Unable to analyze',
                'market_impact': 'Unable to analyze',
                'summary': article.title[:150] + "..." if len(article.title) > 150 else article.title
            }

class ContentEnhancementAgent:
    """Agent responsible for content enhancement and keyword highlighting"""
    
    def __init__(self, config: Config):
        self.config = config
    
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

class MultiAgentPharmaAgent:
    """Main Multi-Agent Pharma Research Agent"""
    
    def __init__(self, config: Config):
        self.config = config
        self.date_agent = DateExtractionAgent(config)
        self.relevance_agent = RelevanceAgent(config)
        self.content_agent = ContentEnhancementAgent(config)
        
        # Import the existing data collection logic
        from pharma_agent import PharmaNewsAgent
        self.data_collector = PharmaNewsAgent()
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles using SequenceMatcher"""
        return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
    
    def _deduplicate_articles(self, articles: List[Dict[str, Any]], similarity_threshold: float = 0.75) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Remove near-duplicate articles, keeping the one with most information
        
        Args:
            articles: List of article dictionaries
            similarity_threshold: Similarity ratio above which articles are considered duplicates (0.0-1.0)
        
        Returns:
            Tuple of (deduplicated articles, stats dict)
        """
        if not articles:
            return articles, {'duplicates_removed': 0, 'unique_articles': 0}
        
        logger.info(f"🔄 Starting deduplication of {len(articles)} articles...")
        
        deduplicated = []
        seen_groups = []  # List of lists, each inner list contains similar articles
        
        for article in articles:
            title = article.get('title', '')
            if not title:
                deduplicated.append(article)
                continue
            
            # Find if this article is similar to any existing group
            found_group = False
            for group in seen_groups:
                # Compare with first article in group (representative)
                representative = group[0]
                similarity = self._calculate_title_similarity(title, representative.get('title', ''))
                
                if similarity >= similarity_threshold:
                    # Add to existing group
                    group.append(article)
                    found_group = True
                    break
            
            if not found_group:
                # Create new group
                seen_groups.append([article])
        
        # From each group, keep the article with most information
        for group in seen_groups:
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Select best article from group based on:
                # 1. Content length (more content = more information)
                # 2. If content is similar, prefer the one with more metadata
                best_article = max(group, key=lambda a: (
                    len(a.get('content') or ''),
                    len(a.get('authors') or ''),
                    len(a.get('url') or '')
                ))
                deduplicated.append(best_article)
                
                # Log deduplication
                titles = [a.get('title', '')[:60] + '...' for a in group]
                logger.info(f"📋 Deduplicated {len(group)} similar articles, kept: {best_article.get('title', '')[:60]}...")
        
        duplicates_removed = len(articles) - len(deduplicated)
        stats = {
            'duplicates_removed': duplicates_removed,
            'unique_articles': len(deduplicated),
            'duplicate_groups': len([g for g in seen_groups if len(g) > 1])
        }
        
        logger.info(f"✅ Deduplication complete: {duplicates_removed} duplicates removed, {len(deduplicated)} unique articles remain")
        print(f"🔄 DEDUPLICATION: Removed {duplicates_removed} duplicates, kept {len(deduplicated)} unique articles")
        
        return deduplicated, stats
        
    async def execute_workflow(self, keywords: List[str], start_date: datetime, 
                             end_date: datetime, search_type: str = 'standard',
                             search_engines: List[str] = None) -> Dict[str, Any]:
        """Execute the complete multi-agent workflow"""
        
        if search_engines is None:
            search_engines = ['pubmed', 'exa', 'tavily', 'newsapi']
        
        logger.info("🚀 Starting Multi-Agent Pharma Research Workflow")
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
                'workflow_stats': {}
            }
        }
        
        try:
            # Step 1: Collect raw data
            logger.info("📡 Step 1: Collecting data from multiple sources...")
            print("🔍 AGENT WORKFLOW: Starting data collection from APIs...")
            print(f"   - Keywords: {keywords}")
            print(f"   - Sources: {search_engines}")
            raw_data = self.data_collector._collect_multi_source_data(
                keywords, start_date, end_date, search_engines
            )
            
            # Flatten all articles into a single list
            raw_articles = []
            for source, articles in raw_data.items():
                for article in articles:
                    article['source'] = source
                    raw_articles.append(article)
            
            workflow_results['metadata']['workflow_stats']['data_collection'] = {
                'total_collected': len(raw_articles),
                'sources_used': list(raw_data.keys())
            }
            
            logger.info(f"✅ Collected {len(raw_articles)} articles from {len(raw_data)} sources")
            print(f"✅ DATA COLLECTION COMPLETE: {len(raw_articles)} articles from {list(raw_data.keys())}")
            
            # Step 1.5: Deduplicate articles (remove near-duplicates)
            logger.info("🔄 Step 1.5: Deduplicating articles...")
            print("🔄 DEDUPLICATION AGENT: Removing near-duplicate articles...")
            raw_articles, dedup_stats = self._deduplicate_articles(raw_articles, similarity_threshold=0.75)
            
            workflow_results['metadata']['workflow_stats']['deduplication'] = dedup_stats
            logger.info(f"✅ Deduplication complete: {dedup_stats}")
            
            # Step 2: Extract dates
            logger.info("📅 Step 2: Extracting dates from articles...")
            print("📅 DATE EXTRACTION AGENT: Processing article dates...")
            articles = []
            date_stats = {"with_dates": 0, "without_dates": 0, "extracted_dates": 0}
            
            for raw_article in raw_articles:
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
            
            workflow_results['metadata']['workflow_stats']['date_extraction'] = date_stats
            logger.info(f"✅ Date extraction complete: {date_stats}")
            print(f"✅ DATE EXTRACTION COMPLETE: {date_stats['with_dates']} with dates, {date_stats['without_dates']} without")
            
            # Step 3: Filter by date range
            # Note: Articles without dates were processed by LLM in Step 2
            # If LLM found a date in content/URL/metadata, the article has extracted_date
            # Only articles where LLM couldn't find ANY date are filtered out here
            logger.info("🗓️ Step 3: Filtering articles by date range...")
            filtered_articles = []
            date_filter_stats = {"in_range": 0, "out_of_range": 0, "no_date": 0, "llm_rescued": 0}
            
            for article in articles:
                if not article.extracted_date:
                    date_filter_stats["no_date"] += 1
                    logger.debug(f"❌ Discarding article (no date after LLM extraction): {article.title[:60]}...")
                    continue
                    
                if start_date <= article.extracted_date <= end_date:
                    filtered_articles.append(article)
                    date_filter_stats["in_range"] += 1
                    # Track articles that were saved by LLM date extraction
                    if not article.raw_date:
                        date_filter_stats["llm_rescued"] += 1
                        logger.info(f"✅ LLM rescued article with extracted date: {article.title[:60]}...")
                else:
                    date_filter_stats["out_of_range"] += 1
                    logger.debug(f"📅 Article date {article.extracted_date.date()} outside range: {article.title[:60]}...")
            
            workflow_results['metadata']['workflow_stats']['date_filtering'] = date_filter_stats
            logger.info(f"✅ Date filtering complete: {date_filter_stats}")
            print(f"✅ DATE FILTERING COMPLETE: {date_filter_stats['in_range']} in range, {date_filter_stats['llm_rescued']} rescued by LLM date extraction")
            
            # Step 4: Analyze relevance
            logger.info("🎯 Step 4: Analyzing article relevance...")
            print(f"🎯 RELEVANCE AGENT: Analyzing {len(filtered_articles)} articles using AI...")
            relevance_stats = {"analyzed": 0, "failed": 0}
            
            for article in filtered_articles:
                try:
                    analysis = self.relevance_agent.analyze_relevance(
                        article, keywords, search_type
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
                    # Set neutral score instead of 0 on failure
                    article.relevance_score = 50
                    article.relevance_reason = f"Analysis failed but article collected: {str(e)}"
                    article.mentioned_keywords = keywords
                    article.summary = article.title[:200]
            
            workflow_results['metadata']['workflow_stats']['relevance_analysis'] = relevance_stats
            logger.info(f"✅ Relevance analysis complete: {relevance_stats}")
            print(f"✅ RELEVANCE ANALYSIS COMPLETE: {relevance_stats['analyzed']} analyzed, {relevance_stats['failed']} failed")
            
            # Show score distribution for debugging
            if filtered_articles:
                scores = [a.relevance_score for a in filtered_articles if a.relevance_score is not None]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    max_score = max(scores)
                    min_score = min(scores)
                    print(f"📊 Score Distribution: Min={min_score}, Max={max_score}, Avg={avg_score:.1f}")
                    print(f"📊 Score Breakdown: {len([s for s in scores if s >= 80])} high (≥80), "
                          f"{len([s for s in scores if 50 <= s < 80])} medium (50-79), "
                          f"{len([s for s in scores if s < 50])} low (<50)")
            
            # Step 5: Filter by relevance
            logger.info("🔍 Step 5: Filtering articles by relevance...")
            min_relevance = 40  # Lowered from 50 to 40 to be more inclusive
            final_articles = []
            relevance_filter_stats = {"kept": 0, "filtered_out": 0}
            
            for article in filtered_articles:
                if article.relevance_score and article.relevance_score >= min_relevance:
                    final_articles.append(article)
                    relevance_filter_stats["kept"] += 1
                    logger.debug(f"✅ Kept: {article.title[:60]}... (score: {article.relevance_score})")
                else:
                    relevance_filter_stats["filtered_out"] += 1
                    logger.debug(f"❌ Filtered: {article.title[:60]}... (score: {article.relevance_score})")
            
            workflow_results['metadata']['workflow_stats']['relevance_filtering'] = relevance_filter_stats
            logger.info(f"✅ Relevance filtering complete: {relevance_filter_stats}")
            print(f"🔍 RELEVANCE FILTERING: Kept {relevance_filter_stats['kept']} articles (≥{min_relevance}), "
                  f"filtered {relevance_filter_stats['filtered_out']} (< {min_relevance})")
            
            # Step 6: Enhance content
            logger.info("✨ Step 6: Enhancing content with keyword highlighting...")
            print(f"✨ CONTENT ENHANCEMENT AGENT: Adding highlights to {len(final_articles)} articles...")
            for article in final_articles:
                article.highlighted_content = self.content_agent.enhance_content(
                    article, keywords
                )
            print(f"✅ CONTENT ENHANCEMENT COMPLETE")
            
            # Step 7: Sort and finalize results
            logger.info("📊 Step 7: Finalizing results...")
            sorted_articles = sorted(
                final_articles, 
                key=lambda x: x.relevance_score or 0, 
                reverse=True
            )
            
            # Format results for API response
            results = []
            for article in sorted_articles:
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
            
            workflow_results['results'] = results
            workflow_results['success'] = True
            workflow_results['metadata']['workflow_stats']['final_results'] = len(results)
            workflow_results['metadata']['workflow_stats']['completion_time'] = datetime.now().isoformat()
            
            logger.info(f"✅ Multi-Agent workflow complete: {len(results)} final results")
            print(f"\n🎉 WORKFLOW COMPLETE: {len(results)} high-quality articles with scores and highlights!")
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            workflow_results['success'] = False
            workflow_results['error'] = str(e)
        
        return workflow_results
