"""
Alert Metadata Analysis Utility
Provides analysis and reporting capabilities for alert metadata
"""

import csv
import json
import argparse
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict
import statistics


class MetadataAnalyzer:
    """Analyze alert metadata to optimize retrieval strategies"""
    
    def __init__(self, csv_file_path: str = "alert_metadata.csv"):
        self.csv_file_path = csv_file_path
        self.data = []
        self.load_data()
    
    def load_data(self):
        """Load metadata from CSV file"""
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                self.data = list(reader)
            print(f"✅ Loaded {len(self.data)} alert records from {self.csv_file_path}")
        except FileNotFoundError:
            print(f"⚠️ Metadata file not found: {self.csv_file_path}")
            print("   No alerts have been processed yet.")
            self.data = []
        except Exception as e:
            print(f"❌ Error loading metadata: {e}")
            self.data = []
    
    def analyze_retriever_performance(self, n_alerts: Optional[int] = None) -> Dict[str, Any]:
        """Analyze performance of each retriever"""
        if not self.data:
            return {}
        
        data_to_analyze = self.data[-n_alerts:] if n_alerts else self.data
        
        retrievers = ['pubmed', 'exa', 'tavily', 'newsapi']
        analysis = {}
        
        for retriever in retrievers:
            total_retrieved = 0
            total_kept = 0
            total_duplicates = 0
            relevance_scores = []
            execution_times = []
            unique_contributions = []
            
            for alert in data_to_analyze:
                try:
                    retrieved = int(alert.get(f'{retriever}_total_retrieved', 0))
                    kept = int(alert.get(f'{retriever}_final_kept', 0))
                    dup_rate = float(alert.get(f'{retriever}_duplicate_rate', 0))
                    relevance = float(alert.get(f'{retriever}_avg_relevance', 0))
                    exec_time = float(alert.get(f'{retriever}_execution_time', 0))
                    unique_contrib = int(alert.get(f'{retriever}_unique_contribution', 0))
                    
                    total_retrieved += retrieved
                    total_kept += kept
                    total_duplicates += int(retrieved * dup_rate / 100) if retrieved > 0 else 0
                    
                    if relevance > 0:
                        relevance_scores.append(relevance)
                    if exec_time > 0:
                        execution_times.append(exec_time)
                    if unique_contrib > 0:
                        unique_contributions.append(unique_contrib)
                        
                except (ValueError, TypeError):
                    continue
            
            analysis[retriever] = {
                'alerts_analyzed': len(data_to_analyze),
                'total_retrieved': total_retrieved,
                'total_kept': total_kept,
                'total_duplicates': total_duplicates,
                'effectiveness_rate': (total_kept / total_retrieved * 100) if total_retrieved > 0 else 0,
                'duplicate_rate': (total_duplicates / total_retrieved * 100) if total_retrieved > 0 else 0,
                'avg_relevance': statistics.mean(relevance_scores) if relevance_scores else 0,
                'avg_execution_time': statistics.mean(execution_times) if execution_times else 0,
                'avg_unique_contribution': statistics.mean(unique_contributions) if unique_contributions else 0,
                'avg_articles_per_alert': total_retrieved / len(data_to_analyze) if data_to_analyze else 0
            }
        
        return analysis
    
    def analyze_strategy_performance(self, n_alerts: Optional[int] = None) -> Dict[str, Any]:
        """Analyze which strategies are most effective"""
        if not self.data:
            return {}
        
        data_to_analyze = self.data[-n_alerts:] if n_alerts else self.data
        
        strategy_stats = defaultdict(lambda: {
            'total_retrieved': 0,
            'total_kept': 0,
            'total_duplicates': 0,
            'occurrences': 0,
            'relevance_scores': []
        })
        
        for alert in data_to_analyze:
            strategy_details_json = alert.get('retriever_strategy_details_json', '{}')
            try:
                strategy_details = json.loads(strategy_details_json)
                
                for retriever, strategies in strategy_details.items():
                    for strategy_name, metrics in strategies.items():
                        key = f"{retriever}_{strategy_name}"
                        
                        retrieved = metrics.get('articles_retrieved', 0)
                        kept = metrics.get('articles_final_kept', 0)
                        after_dedup = metrics.get('articles_after_dedup_cross_retriever', 0)
                        relevance = metrics.get('avg_relevance_score', 0)
                        
                        strategy_stats[key]['total_retrieved'] += retrieved
                        strategy_stats[key]['total_kept'] += kept
                        strategy_stats[key]['total_duplicates'] += (retrieved - after_dedup)
                        strategy_stats[key]['occurrences'] += 1
                        
                        if relevance > 0:
                            strategy_stats[key]['relevance_scores'].append(relevance)
            
            except json.JSONDecodeError:
                continue
        
        # Calculate effectiveness metrics
        analysis = {}
        for strategy_key, stats in strategy_stats.items():
            relevance_scores = stats['relevance_scores']
            
            analysis[strategy_key] = {
                'occurrences': stats['occurrences'],
                'total_retrieved': stats['total_retrieved'],
                'total_kept': stats['total_kept'],
                'total_duplicates': stats['total_duplicates'],
                'effectiveness_rate': (
                    (stats['total_kept'] / stats['total_retrieved'] * 100)
                    if stats['total_retrieved'] > 0 else 0
                ),
                'duplicate_rate': (
                    (stats['total_duplicates'] / stats['total_retrieved'] * 100)
                    if stats['total_retrieved'] > 0 else 0
                ),
                'avg_relevance': statistics.mean(relevance_scores) if relevance_scores else 0,
                'avg_retrieved_per_alert': (
                    stats['total_retrieved'] / stats['occurrences']
                    if stats['occurrences'] > 0 else 0
                )
            }
        
        # Sort by effectiveness rate (descending)
        analysis = dict(sorted(analysis.items(), key=lambda x: x[1]['effectiveness_rate'], reverse=True))
        
        return analysis
    
    def identify_low_performing_strategies(self, min_effectiveness: float = 10.0, 
                                          min_occurrences: int = 3) -> List[Dict[str, Any]]:
        """Identify strategies that should be considered for removal"""
        strategy_analysis = self.analyze_strategy_performance()
        
        low_performers = []
        for strategy, metrics in strategy_analysis.items():
            if (metrics['occurrences'] >= min_occurrences and 
                metrics['effectiveness_rate'] < min_effectiveness):
                low_performers.append({
                    'strategy': strategy,
                    'effectiveness_rate': metrics['effectiveness_rate'],
                    'duplicate_rate': metrics['duplicate_rate'],
                    'avg_retrieved': metrics['avg_retrieved_per_alert'],
                    'occurrences': metrics['occurrences'],
                    'avg_relevance': metrics['avg_relevance']
                })
        
        # Sort by effectiveness rate (ascending)
        low_performers.sort(key=lambda x: x['effectiveness_rate'])
        
        return low_performers
    
    def analyze_deduplication_effectiveness(self) -> Dict[str, Any]:
        """Analyze how effective deduplication is across alerts"""
        if not self.data:
            return {}
        
        total_collected = 0
        total_after_dedup = 0
        total_duplicates = 0
        duplicate_rates = []
        
        for alert in self.data:
            try:
                collected = int(alert.get('total_articles_collected', 0))
                after_dedup = int(alert.get('total_unique_after_dedup', 0))
                duplicates = int(alert.get('total_duplicates_removed', 0))
                dup_rate = float(alert.get('overall_duplicate_rate', 0))
                
                total_collected += collected
                total_after_dedup += after_dedup
                total_duplicates += duplicates
                
                if dup_rate > 0:
                    duplicate_rates.append(dup_rate)
                    
            except (ValueError, TypeError):
                continue
        
        return {
            'total_alerts': len(self.data),
            'total_articles_collected': total_collected,
            'total_unique_articles': total_after_dedup,
            'total_duplicates_removed': total_duplicates,
            'overall_duplicate_rate': (total_duplicates / total_collected * 100) if total_collected > 0 else 0,
            'avg_duplicate_rate_per_alert': statistics.mean(duplicate_rates) if duplicate_rates else 0,
            'min_duplicate_rate': min(duplicate_rates) if duplicate_rates else 0,
            'max_duplicate_rate': max(duplicate_rates) if duplicate_rates else 0
        }
    
    def analyze_date_extraction(self) -> Dict[str, Any]:
        """Analyze date extraction effectiveness"""
        if not self.data:
            return {}
        
        total_with_original = 0
        total_extracted = 0
        total_without = 0
        total_rescued = 0
        success_rates = []
        
        for alert in self.data:
            try:
                with_original = int(alert.get('articles_with_original_dates', 0))
                extracted = int(alert.get('articles_with_extracted_dates', 0))
                without = int(alert.get('articles_without_dates', 0))
                rescued = int(alert.get('articles_rescued_by_llm', 0))
                success_rate = float(alert.get('llm_date_extraction_success_rate', 0))
                
                total_with_original += with_original
                total_extracted += extracted
                total_without += without
                total_rescued += rescued
                
                if success_rate > 0:
                    success_rates.append(success_rate)
                    
            except (ValueError, TypeError):
                continue
        
        total_articles = total_with_original + total_extracted + total_without
        
        return {
            'total_alerts': len(self.data),
            'total_articles_processed': total_articles,
            'articles_with_original_dates': total_with_original,
            'articles_with_extracted_dates': total_extracted,
            'articles_without_dates': total_without,
            'articles_rescued_by_llm': total_rescued,
            'overall_success_rate': (total_extracted / total_articles * 100) if total_articles > 0 else 0,
            'avg_success_rate_per_alert': statistics.mean(success_rates) if success_rates else 0,
            'rescue_rate': (total_rescued / total_extracted * 100) if total_extracted > 0 else 0
        }
    
    def analyze_relevance_distribution(self) -> Dict[str, Any]:
        """Analyze relevance score distribution"""
        if not self.data:
            return {}
        
        total_high = 0
        total_medium = 0
        total_low = 0
        avg_scores = []
        
        for alert in self.data:
            try:
                high = int(alert.get('articles_relevance_high_80plus', 0))
                medium = int(alert.get('articles_relevance_medium_60_79', 0))
                low = int(alert.get('articles_relevance_low_below60', 0))
                avg_score = float(alert.get('avg_relevance_score', 0))
                
                total_high += high
                total_medium += medium
                total_low += low
                
                if avg_score > 0:
                    avg_scores.append(avg_score)
                    
            except (ValueError, TypeError):
                continue
        
        total_articles = total_high + total_medium + total_low
        
        return {
            'total_alerts': len(self.data),
            'total_articles_analyzed': total_articles,
            'articles_high_relevance': total_high,
            'articles_medium_relevance': total_medium,
            'articles_low_relevance': total_low,
            'high_relevance_percentage': (total_high / total_articles * 100) if total_articles > 0 else 0,
            'medium_relevance_percentage': (total_medium / total_articles * 100) if total_articles > 0 else 0,
            'low_relevance_percentage': (total_low / total_articles * 100) if total_articles > 0 else 0,
            'avg_relevance_score': statistics.mean(avg_scores) if avg_scores else 0,
            'min_relevance_score': min(avg_scores) if avg_scores else 0,
            'max_relevance_score': max(avg_scores) if avg_scores else 0
        }
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate a comprehensive analysis report"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("ALERT METADATA ANALYSIS REPORT")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total Alerts Analyzed: {len(self.data)}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Retriever Performance
        report_lines.append("📊 RETRIEVER PERFORMANCE ANALYSIS")
        report_lines.append("-" * 80)
        retriever_analysis = self.analyze_retriever_performance()
        for retriever, metrics in retriever_analysis.items():
            report_lines.append(f"\n{retriever.upper()}:")
            report_lines.append(f"  Total Retrieved: {metrics['total_retrieved']:,}")
            report_lines.append(f"  Total Kept: {metrics['total_kept']:,}")
            report_lines.append(f"  Effectiveness Rate: {metrics['effectiveness_rate']:.2f}%")
            report_lines.append(f"  Duplicate Rate: {metrics['duplicate_rate']:.2f}%")
            report_lines.append(f"  Avg Relevance Score: {metrics['avg_relevance']:.2f}")
            report_lines.append(f"  Avg Articles/Alert: {metrics['avg_articles_per_alert']:.1f}")
            report_lines.append(f"  Avg Execution Time: {metrics['avg_execution_time']:.2f}s")
        report_lines.append("")
        
        # Low Performing Strategies
        report_lines.append("\n⚠️  LOW PERFORMING STRATEGIES (Consider Removal)")
        report_lines.append("-" * 80)
        low_performers = self.identify_low_performing_strategies()
        if low_performers:
            for strategy_info in low_performers[:10]:  # Top 10 worst
                report_lines.append(f"\n  Strategy: {strategy_info['strategy']}")
                report_lines.append(f"    Effectiveness: {strategy_info['effectiveness_rate']:.2f}%")
                report_lines.append(f"    Duplicate Rate: {strategy_info['duplicate_rate']:.2f}%")
                report_lines.append(f"    Avg Retrieved: {strategy_info['avg_retrieved']:.1f}")
                report_lines.append(f"    Occurrences: {strategy_info['occurrences']}")
        else:
            report_lines.append("  No low-performing strategies identified")
        report_lines.append("")
        
        # Deduplication Analysis
        report_lines.append("\n🔄 DEDUPLICATION EFFECTIVENESS")
        report_lines.append("-" * 80)
        dedup_analysis = self.analyze_deduplication_effectiveness()
        report_lines.append(f"  Total Articles Collected: {dedup_analysis.get('total_articles_collected', 0):,}")
        report_lines.append(f"  Total Unique Articles: {dedup_analysis.get('total_unique_articles', 0):,}")
        report_lines.append(f"  Total Duplicates Removed: {dedup_analysis.get('total_duplicates_removed', 0):,}")
        report_lines.append(f"  Overall Duplicate Rate: {dedup_analysis.get('overall_duplicate_rate', 0):.2f}%")
        report_lines.append(f"  Avg Duplicate Rate/Alert: {dedup_analysis.get('avg_duplicate_rate_per_alert', 0):.2f}%")
        report_lines.append("")
        
        # Date Extraction Analysis
        report_lines.append("\n📅 DATE EXTRACTION EFFECTIVENESS")
        report_lines.append("-" * 80)
        date_analysis = self.analyze_date_extraction()
        report_lines.append(f"  Total Articles Processed: {date_analysis.get('total_articles_processed', 0):,}")
        report_lines.append(f"  With Original Dates: {date_analysis.get('articles_with_original_dates', 0):,}")
        report_lines.append(f"  With Extracted Dates: {date_analysis.get('articles_with_extracted_dates', 0):,}")
        report_lines.append(f"  Without Dates: {date_analysis.get('articles_without_dates', 0):,}")
        report_lines.append(f"  Rescued by LLM: {date_analysis.get('articles_rescued_by_llm', 0):,}")
        report_lines.append(f"  Overall Success Rate: {date_analysis.get('overall_success_rate', 0):.2f}%")
        report_lines.append(f"  LLM Rescue Rate: {date_analysis.get('rescue_rate', 0):.2f}%")
        report_lines.append("")
        
        # Relevance Distribution
        report_lines.append("\n🎯 RELEVANCE SCORE DISTRIBUTION")
        report_lines.append("-" * 80)
        relevance_analysis = self.analyze_relevance_distribution()
        report_lines.append(f"  Total Articles Analyzed: {relevance_analysis.get('total_articles_analyzed', 0):,}")
        report_lines.append(f"  High Relevance (≥80): {relevance_analysis.get('articles_high_relevance', 0):,} ({relevance_analysis.get('high_relevance_percentage', 0):.1f}%)")
        report_lines.append(f"  Medium Relevance (60-79): {relevance_analysis.get('articles_medium_relevance', 0):,} ({relevance_analysis.get('medium_relevance_percentage', 0):.1f}%)")
        report_lines.append(f"  Low Relevance (<60): {relevance_analysis.get('articles_low_relevance', 0):,} ({relevance_analysis.get('low_relevance_percentage', 0):.1f}%)")
        report_lines.append(f"  Avg Relevance Score: {relevance_analysis.get('avg_relevance_score', 0):.2f}")
        report_lines.append("")
        
        report_lines.append("=" * 80)
        report_lines.append("END OF REPORT")
        report_lines.append("=" * 80)
        
        report = "\n".join(report_lines)
        
        # Save to file if requested
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"✅ Report saved to: {output_file}")
        
        return report


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(description="Analyze alert metadata to optimize retrieval strategies")
    parser.add_argument('--csv', default='alert_metadata.csv', help='Path to metadata CSV file')
    parser.add_argument('--output', '-o', help='Save report to file')
    parser.add_argument('--recent', '-r', type=int, help='Analyze only the N most recent alerts')
    
    args = parser.parse_args()
    
    analyzer = MetadataAnalyzer(args.csv)
    
    if not analyzer.data:
        print("\n⚠️  No metadata available for analysis.")
        print("   Process some alerts first to generate metadata.")
        return
    
    report = analyzer.generate_report(args.output)
    print(report)


if __name__ == '__main__':
    main()

