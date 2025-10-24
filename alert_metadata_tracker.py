"""
Alert Metadata Tracker
Comprehensive tracking system for analyzing retrieval performance across alerts
"""

import csv
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetrieverStrategyMetrics:
    """Metrics for a specific strategy within a retriever"""
    strategy_name: str
    articles_retrieved: int = 0
    articles_with_dates: int = 0
    articles_without_dates: int = 0
    articles_after_dedup_within_strategy: int = 0
    articles_after_dedup_cross_strategy: int = 0
    articles_after_dedup_cross_retriever: int = 0
    articles_in_date_range: int = 0
    articles_out_of_date_range: int = 0
    articles_relevant_high: int = 0  # relevance >= 80
    articles_relevant_medium: int = 0  # 60 <= relevance < 80
    articles_relevant_low: int = 0  # relevance < 60
    articles_final_kept: int = 0
    avg_relevance_score: float = 0.0
    unique_contribution: int = 0  # Articles unique to this strategy
    duplicate_rate: float = 0.0
    execution_time_seconds: float = 0.0
    error_occurred: bool = False
    error_message: str = ""


@dataclass
class RetrieverMetrics:
    """Aggregated metrics for an entire retriever"""
    retriever_name: str
    total_articles_retrieved: int = 0
    strategies_used: List[str] = field(default_factory=list)
    strategy_metrics: Dict[str, RetrieverStrategyMetrics] = field(default_factory=dict)
    articles_after_dedup: int = 0
    articles_with_dates: int = 0
    articles_in_date_range: int = 0
    articles_final_kept: int = 0
    avg_relevance_score: float = 0.0
    unique_contribution: int = 0  # Articles unique to this retriever
    duplicate_rate_within_retriever: float = 0.0
    duplicate_rate_cross_retriever: float = 0.0
    execution_time_seconds: float = 0.0


@dataclass
class AlertMetadata:
    """Complete metadata for an alert execution"""
    # Alert identification
    alert_id: str  # Unique identifier
    alert_name: str
    subheader: str
    alert_type: str  # batch, single, scheduled, etc.
    user: str
    
    # Keywords and search configuration
    primary_keywords: List[str] = field(default_factory=list)
    alias_keywords: List[str] = field(default_factory=list)
    all_keywords: List[str] = field(default_factory=list)
    search_type: str = "standard"  # standard or cooccurrence
    
    # Date range
    start_date: str = ""
    end_date: str = ""
    
    # Retriever metrics
    retrievers_used: List[str] = field(default_factory=list)
    retriever_metrics: Dict[str, RetrieverMetrics] = field(default_factory=dict)
    
    # Overall statistics
    total_articles_collected: int = 0
    total_unique_articles_after_dedup: int = 0
    total_duplicates_removed: int = 0
    duplicate_groups_found: int = 0
    
    # Date extraction statistics
    articles_with_original_dates: int = 0
    articles_with_extracted_dates: int = 0
    articles_without_dates: int = 0
    llm_date_extraction_success_rate: float = 0.0
    
    # Date filtering statistics
    articles_in_date_range: int = 0
    articles_out_of_date_range: int = 0
    articles_rescued_by_llm_date: int = 0
    
    # Relevance statistics
    articles_analyzed_for_relevance: int = 0
    articles_relevance_high: int = 0  # >= 80
    articles_relevance_medium: int = 0  # 60-79
    articles_relevance_low: int = 0  # < 60
    articles_final_kept: int = 0
    avg_relevance_score: float = 0.0
    
    # Article type breakdown
    article_types: Dict[str, int] = field(default_factory=dict)
    
    # Query generation (if dynamic queries used)
    dynamic_queries_generated: bool = False
    queries_per_source: Dict[str, int] = field(default_factory=dict)
    
    # Performance metrics
    total_execution_time_seconds: float = 0.0
    data_collection_time_seconds: float = 0.0
    deduplication_time_seconds: float = 0.0
    date_extraction_time_seconds: float = 0.0
    relevance_analysis_time_seconds: float = 0.0
    
    # Success indicators
    workflow_successful: bool = True
    errors_encountered: List[str] = field(default_factory=list)
    
    # Timestamp
    execution_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AlertMetadataTracker:
    """Tracks and stores alert metadata for analysis"""
    
    def __init__(self, csv_file_path: str = "alert_metadata.csv"):
        self.csv_file_path = csv_file_path
        self.ensure_csv_exists()
    
    def ensure_csv_exists(self):
        """Ensure the CSV file exists with proper headers"""
        if not os.path.exists(self.csv_file_path):
            self._create_csv_with_headers()
    
    def _create_csv_with_headers(self):
        """Create CSV file with comprehensive headers"""
        headers = [
            # Alert Identification
            'alert_id', 'execution_timestamp', 'alert_name', 'subheader', 'alert_type', 'user',
            
            # Keywords
            'primary_keywords', 'alias_keywords', 'all_keywords', 'search_type',
            
            # Date Range
            'start_date', 'end_date',
            
            # Retrievers Used
            'retrievers_used', 'num_retrievers',
            
            # Overall Collection Statistics
            'total_articles_collected', 'total_unique_after_dedup', 'total_duplicates_removed',
            'duplicate_groups_found', 'overall_duplicate_rate',
            
            # Date Extraction Statistics
            'articles_with_original_dates', 'articles_with_extracted_dates', 'articles_without_dates',
            'llm_date_extraction_success_rate',
            
            # Date Filtering Statistics
            'articles_in_date_range', 'articles_out_of_date_range', 'articles_rescued_by_llm',
            
            # Relevance Statistics
            'articles_analyzed', 'articles_relevance_high_80plus', 'articles_relevance_medium_60_79',
            'articles_relevance_low_below60', 'articles_final_kept', 'avg_relevance_score',
            
            # Article Types
            'article_types_json',
            
            # Per-Retriever Statistics (PubMed)
            'pubmed_total_retrieved', 'pubmed_after_dedup', 'pubmed_strategies_used',
            'pubmed_unique_contribution', 'pubmed_duplicate_rate', 'pubmed_avg_relevance',
            'pubmed_final_kept', 'pubmed_execution_time',
            
            # Per-Retriever Statistics (Exa)
            'exa_total_retrieved', 'exa_after_dedup', 'exa_strategies_used',
            'exa_unique_contribution', 'exa_duplicate_rate', 'exa_avg_relevance',
            'exa_final_kept', 'exa_execution_time',
            
            # Per-Retriever Statistics (Tavily)
            'tavily_total_retrieved', 'tavily_after_dedup', 'tavily_strategies_used',
            'tavily_unique_contribution', 'tavily_duplicate_rate', 'tavily_avg_relevance',
            'tavily_final_kept', 'tavily_execution_time',
            
            # Per-Retriever Statistics (NewsAPI)
            'newsapi_total_retrieved', 'newsapi_after_dedup', 'newsapi_strategies_used',
            'newsapi_unique_contribution', 'newsapi_duplicate_rate', 'newsapi_avg_relevance',
            'newsapi_final_kept', 'newsapi_execution_time',
            
            # Strategy-Level Details (JSON for detailed analysis)
            'retriever_strategy_details_json',
            
            # Query Generation
            'dynamic_queries_generated', 'queries_per_source_json',
            
            # Performance Metrics
            'total_execution_time', 'data_collection_time', 'deduplication_time',
            'date_extraction_time', 'relevance_analysis_time',
            
            # Success Indicators
            'workflow_successful', 'errors_encountered'
        ]
        
        with open(self.csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
        
        logger.info(f"Created metadata CSV file: {self.csv_file_path}")
    
    def log_alert_metadata(self, metadata: AlertMetadata):
        """Append alert metadata to CSV file"""
        try:
            # Convert metadata to CSV row
            row = self._metadata_to_csv_row(metadata)
            
            # Append to CSV
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=row.keys())
                writer.writerow(row)
            
            logger.info(f"✅ Logged metadata for alert: {metadata.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log alert metadata: {e}")
            return False
    
    def _metadata_to_csv_row(self, metadata: AlertMetadata) -> Dict[str, Any]:
        """Convert AlertMetadata to CSV row dictionary"""
        
        # Calculate overall duplicate rate
        overall_duplicate_rate = (
            (metadata.total_duplicates_removed / metadata.total_articles_collected * 100)
            if metadata.total_articles_collected > 0 else 0.0
        )
        
        row = {
            # Alert Identification
            'alert_id': metadata.alert_id,
            'execution_timestamp': metadata.execution_timestamp,
            'alert_name': metadata.alert_name,
            'subheader': metadata.subheader,
            'alert_type': metadata.alert_type,
            'user': metadata.user,
            
            # Keywords
            'primary_keywords': ', '.join(metadata.primary_keywords),
            'alias_keywords': ', '.join(metadata.alias_keywords),
            'all_keywords': ', '.join(metadata.all_keywords),
            'search_type': metadata.search_type,
            
            # Date Range
            'start_date': metadata.start_date,
            'end_date': metadata.end_date,
            
            # Retrievers Used
            'retrievers_used': ', '.join(metadata.retrievers_used),
            'num_retrievers': len(metadata.retrievers_used),
            
            # Overall Statistics
            'total_articles_collected': metadata.total_articles_collected,
            'total_unique_after_dedup': metadata.total_unique_articles_after_dedup,
            'total_duplicates_removed': metadata.total_duplicates_removed,
            'duplicate_groups_found': metadata.duplicate_groups_found,
            'overall_duplicate_rate': f"{overall_duplicate_rate:.2f}",
            
            # Date Extraction Statistics
            'articles_with_original_dates': metadata.articles_with_original_dates,
            'articles_with_extracted_dates': metadata.articles_with_extracted_dates,
            'articles_without_dates': metadata.articles_without_dates,
            'llm_date_extraction_success_rate': f"{metadata.llm_date_extraction_success_rate:.2f}",
            
            # Date Filtering Statistics
            'articles_in_date_range': metadata.articles_in_date_range,
            'articles_out_of_date_range': metadata.articles_out_of_date_range,
            'articles_rescued_by_llm': metadata.articles_rescued_by_llm_date,
            
            # Relevance Statistics
            'articles_analyzed': metadata.articles_analyzed_for_relevance,
            'articles_relevance_high_80plus': metadata.articles_relevance_high,
            'articles_relevance_medium_60_79': metadata.articles_relevance_medium,
            'articles_relevance_low_below60': metadata.articles_relevance_low,
            'articles_final_kept': metadata.articles_final_kept,
            'avg_relevance_score': f"{metadata.avg_relevance_score:.2f}",
            
            # Article Types
            'article_types_json': json.dumps(metadata.article_types),
            
            # Query Generation
            'dynamic_queries_generated': metadata.dynamic_queries_generated,
            'queries_per_source_json': json.dumps(metadata.queries_per_source),
            
            # Performance Metrics
            'total_execution_time': f"{metadata.total_execution_time_seconds:.2f}",
            'data_collection_time': f"{metadata.data_collection_time_seconds:.2f}",
            'deduplication_time': f"{metadata.deduplication_time_seconds:.2f}",
            'date_extraction_time': f"{metadata.date_extraction_time_seconds:.2f}",
            'relevance_analysis_time': f"{metadata.relevance_analysis_time_seconds:.2f}",
            
            # Success Indicators
            'workflow_successful': metadata.workflow_successful,
            'errors_encountered': '; '.join(metadata.errors_encountered) if metadata.errors_encountered else ''
        }
        
        # Add per-retriever statistics
        for retriever_name in ['pubmed', 'exa', 'tavily', 'newsapi']:
            if retriever_name in metadata.retriever_metrics:
                metrics = metadata.retriever_metrics[retriever_name]
                row.update({
                    f'{retriever_name}_total_retrieved': metrics.total_articles_retrieved,
                    f'{retriever_name}_after_dedup': metrics.articles_after_dedup,
                    f'{retriever_name}_strategies_used': ', '.join(metrics.strategies_used),
                    f'{retriever_name}_unique_contribution': metrics.unique_contribution,
                    f'{retriever_name}_duplicate_rate': f"{metrics.duplicate_rate_cross_retriever:.2f}",
                    f'{retriever_name}_avg_relevance': f"{metrics.avg_relevance_score:.2f}",
                    f'{retriever_name}_final_kept': metrics.articles_final_kept,
                    f'{retriever_name}_execution_time': f"{metrics.execution_time_seconds:.2f}"
                })
            else:
                row.update({
                    f'{retriever_name}_total_retrieved': 0,
                    f'{retriever_name}_after_dedup': 0,
                    f'{retriever_name}_strategies_used': '',
                    f'{retriever_name}_unique_contribution': 0,
                    f'{retriever_name}_duplicate_rate': '0.00',
                    f'{retriever_name}_avg_relevance': '0.00',
                    f'{retriever_name}_final_kept': 0,
                    f'{retriever_name}_execution_time': '0.00'
                })
        
        # Add strategy-level details as JSON
        strategy_details = {}
        for retriever_name, retriever_metrics in metadata.retriever_metrics.items():
            strategy_details[retriever_name] = {
                strategy_name: asdict(strategy_metrics)
                for strategy_name, strategy_metrics in retriever_metrics.strategy_metrics.items()
            }
        row['retriever_strategy_details_json'] = json.dumps(strategy_details)
        
        return row
    
    def get_recent_alerts(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get the n most recent alerts from the CSV"""
        try:
            if not os.path.exists(self.csv_file_path):
                return []
            
            with open(self.csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                return rows[-n:] if len(rows) > n else rows
        except Exception as e:
            logger.error(f"Failed to read recent alerts: {e}")
            return []
    
    def analyze_retriever_performance(self, retriever_name: str, n_alerts: int = 50) -> Dict[str, Any]:
        """Analyze performance of a specific retriever across recent alerts"""
        try:
            recent_alerts = self.get_recent_alerts(n_alerts)
            
            if not recent_alerts:
                return {}
            
            total_retrieved = 0
            total_kept = 0
            total_duplicates = 0
            relevance_scores = []
            strategies_performance = {}
            
            for alert in recent_alerts:
                retrieved_key = f'{retriever_name}_total_retrieved'
                kept_key = f'{retriever_name}_final_kept'
                relevance_key = f'{retriever_name}_avg_relevance'
                
                if retrieved_key in alert:
                    total_retrieved += int(alert.get(retrieved_key, 0))
                    total_kept += int(alert.get(kept_key, 0))
                    
                    try:
                        relevance = float(alert.get(relevance_key, 0))
                        if relevance > 0:
                            relevance_scores.append(relevance)
                    except ValueError:
                        pass
            
            analysis = {
                'retriever_name': retriever_name,
                'alerts_analyzed': len(recent_alerts),
                'total_articles_retrieved': total_retrieved,
                'total_articles_kept': total_kept,
                'average_relevance': sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0,
                'effectiveness_rate': (total_kept / total_retrieved * 100) if total_retrieved > 0 else 0,
                'avg_articles_per_alert': total_retrieved / len(recent_alerts) if recent_alerts else 0
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze retriever performance: {e}")
            return {}
    
    def analyze_strategy_performance(self, n_alerts: int = 50) -> Dict[str, Any]:
        """Analyze which strategies are most effective across all retrievers"""
        try:
            recent_alerts = self.get_recent_alerts(n_alerts)
            
            if not recent_alerts:
                return {}
            
            strategy_stats = {}
            
            for alert in recent_alerts:
                strategy_details_json = alert.get('retriever_strategy_details_json', '{}')
                try:
                    strategy_details = json.loads(strategy_details_json)
                    
                    for retriever, strategies in strategy_details.items():
                        for strategy_name, metrics in strategies.items():
                            key = f"{retriever}_{strategy_name}"
                            
                            if key not in strategy_stats:
                                strategy_stats[key] = {
                                    'total_retrieved': 0,
                                    'total_kept': 0,
                                    'total_duplicates': 0,
                                    'occurrences': 0
                                }
                            
                            strategy_stats[key]['total_retrieved'] += metrics.get('articles_retrieved', 0)
                            strategy_stats[key]['total_kept'] += metrics.get('articles_final_kept', 0)
                            strategy_stats[key]['occurrences'] += 1
                            
                            # Calculate duplicates
                            retrieved = metrics.get('articles_retrieved', 0)
                            after_dedup = metrics.get('articles_after_dedup_cross_retriever', 0)
                            strategy_stats[key]['total_duplicates'] += (retrieved - after_dedup)
                
                except json.JSONDecodeError:
                    continue
            
            # Calculate effectiveness for each strategy
            for strategy_key, stats in strategy_stats.items():
                stats['effectiveness_rate'] = (
                    (stats['total_kept'] / stats['total_retrieved'] * 100)
                    if stats['total_retrieved'] > 0 else 0
                )
                stats['duplicate_rate'] = (
                    (stats['total_duplicates'] / stats['total_retrieved'] * 100)
                    if stats['total_retrieved'] > 0 else 0
                )
                stats['avg_retrieved_per_alert'] = (
                    stats['total_retrieved'] / stats['occurrences']
                    if stats['occurrences'] > 0 else 0
                )
            
            return strategy_stats
            
        except Exception as e:
            logger.error(f"Failed to analyze strategy performance: {e}")
            return {}


# Global tracker instance
_tracker_instance = None


def get_tracker(csv_file_path: str = "alert_metadata.csv") -> AlertMetadataTracker:
    """Get or create the global tracker instance"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = AlertMetadataTracker(csv_file_path)
    return _tracker_instance

