# Alert Metadata Tracking System

## Overview

This system provides comprehensive tracking and analysis of retrieval performance across all alerts (batch processing, single inputs, scheduled alerts). It automatically logs detailed metrics to CSV after each alert execution, enabling data-driven optimization of retrieval strategies.

## Components

### 1. **alert_metadata_tracker.py**
Core tracking module that logs metadata for every alert execution.

**Key Classes:**
- `AlertMetadata`: Complete metadata structure for an alert
- `RetrieverMetrics`: Per-retriever performance metrics
- `RetrieverStrategyMetrics`: Strategy-level detailed metrics
- `AlertMetadataTracker`: Main tracking and logging class

**Features:**
- Automatic CSV logging after each alert
- Comprehensive metrics collection
- Strategy-level performance tracking
- Deduplication effectiveness analysis
- Date extraction success tracking
- Relevance score distribution

### 2. **analyze_metadata.py**
Analysis utility for generating insights and recommendations.

**Features:**
- Retriever performance comparison
- Strategy effectiveness analysis
- Low-performing strategy identification
- Deduplication effectiveness analysis
- Date extraction success rates
- Relevance distribution analysis
- Comprehensive report generation

### 3. **alert_metadata.csv**
Auto-generated CSV file containing all alert metadata (created automatically on first alert).

## Tracked Metrics

### Alert Identification
- Alert ID, name, subheader, type, user
- Timestamp of execution
- Keywords (primary, alias, combined)
- Search type (standard/cooccurrence)
- Date range

### Collection Statistics
- Total articles collected per retriever
- Total unique articles after deduplication
- Duplicate count and rates
- Duplicate groups found

### Per-Retriever Metrics
For each retriever (PubMed, Exa, Tavily, NewsAPI):
- Total articles retrieved
- Articles after deduplication
- Strategies used
- Unique contribution (articles only from this retriever)
- Cross-retriever duplicate rate
- Average relevance score
- Final articles kept
- Execution time

### Strategy-Level Details (JSON)
Detailed breakdown for each strategy within each retriever:
- Articles retrieved per strategy
- Articles after within-strategy dedup
- Articles after cross-strategy dedup
- Articles after cross-retriever dedup
- Articles in date range
- Relevance breakdown (high/medium/low)
- Unique contribution per strategy
- Duplicate rates
- Execution time
- Error tracking

### Date Extraction Metrics
- Articles with original dates
- Articles with LLM-extracted dates
- Articles without dates
- LLM extraction success rate
- Articles rescued by LLM date extraction

### Relevance Metrics
- Articles analyzed for relevance
- High relevance count (≥80)
- Medium relevance count (60-79)
- Low relevance count (<60)
- Average relevance score
- Article type breakdown (research, news, press release, etc.)

### Performance Metrics
- Total execution time
- Time per phase (collection, dedup, date extraction, relevance analysis)
- Success status and errors

## Usage

### Automatic Tracking (No Action Required)

Metadata is automatically logged after every alert execution. The system is integrated into:
- Multi-agent workflow (`multi_agent_pharma.py`)
- Batch processing (`ome_blueprint.py`)
- Single alert processing

### Analyzing Metadata

#### Command Line Analysis

```bash
# Generate full analysis report
python analyze_metadata.py

# Analyze recent alerts only
python analyze_metadata.py --recent 50

# Save report to file
python analyze_metadata.py --output report.txt

# Use custom CSV file
python analyze_metadata.py --csv custom_metadata.csv
```

#### Programmatic Analysis

```python
from analyze_metadata import MetadataAnalyzer

# Initialize analyzer
analyzer = MetadataAnalyzer("alert_metadata.csv")

# Analyze retriever performance
retriever_analysis = analyzer.analyze_retriever_performance()

# Identify low-performing strategies
low_performers = analyzer.identify_low_performing_strategies(
    min_effectiveness=10.0,  # Less than 10% effectiveness
    min_occurrences=3         # Appeared in at least 3 alerts
)

# Analyze deduplication effectiveness
dedup_analysis = analyzer.analyze_deduplication_effectiveness()

# Analyze date extraction success
date_analysis = analyzer.analyze_date_extraction()

# Analyze relevance distribution
relevance_analysis = analyzer.analyze_relevance_distribution()

# Generate comprehensive report
report = analyzer.generate_report("analysis_report.txt")
print(report)
```

## Analysis Insights

### 1. **Retriever Effectiveness**

Identify which retrievers provide the best:
- **Effectiveness Rate**: `(kept / retrieved * 100)`
- **Unique Contribution**: Articles only found by this retriever
- **Duplicate Rate**: How many articles are duplicates
- **Relevance Quality**: Average relevance score

**Use Case**: Remove or deprioritize retrievers with consistently low effectiveness and high duplicate rates.

### 2. **Strategy Optimization**

For each retriever strategy (e.g., `exa_simple_neural`, `tavily_pharma_context`):
- **Effectiveness Rate**: How many retrieved articles are kept
- **Duplicate Rate**: How many are duplicates
- **Avg Articles per Alert**: Consistency of results
- **Avg Relevance**: Quality of results

**Use Case**: Disable strategies that consistently produce duplicates or low-relevance articles.

### 3. **Deduplication Analysis**

Track:
- Overall duplicate rate across all retrievers
- Which retrievers contribute most duplicates
- Duplicate groups (multiple similar articles)

**Use Case**: Understand if certain retrievers or strategies consistently retrieve the same content.

### 4. **Date Extraction Success**

Monitor:
- LLM date extraction success rate
- Articles rescued by LLM (would have been discarded without date extraction)
- Articles still without dates

**Use Case**: Evaluate if LLM date extraction is worth the cost, or if improvements needed.

### 5. **Relevance Distribution**

Analyze:
- Percentage of high/medium/low relevance articles
- Average relevance scores per retriever
- Relevance trends over time

**Use Case**: Identify if query generation or retrieval strategies need adjustment.

## Optimization Workflow

### Weekly Review Process

1. **Generate Analysis Report**
   ```bash
   python analyze_metadata.py --recent 50 --output weekly_report.txt
   ```

2. **Identify Low Performers**
   - Look for strategies with <10% effectiveness rate
   - Look for strategies with >80% duplicate rate
   - Look for retrievers with <5% unique contribution

3. **Make Adjustments**
   - Disable consistently poor strategies
   - Adjust query generation for low-relevance retrievers
   - Modify search parameters for high-duplicate strategies

4. **Monitor Impact**
   - Compare next week's metrics
   - Track improvements in effectiveness rates
   - Watch for changes in duplicate rates

### Example Optimization Decisions

**Scenario 1**: Exa's `broad_unrestricted` strategy shows:
- 5% effectiveness rate
- 85% duplicate rate
- 0 unique contribution
- **Action**: Disable this strategy

**Scenario 2**: Tavily shows:
- 2 articles avg per alert
- 1.5 of those are duplicates
- 75% relevance score
- **Action**: Keep but deprioritize (run last, limit results)

**Scenario 3**: PubMed shows:
- 30% effectiveness rate
- 45% unique contribution
- 85 avg relevance score
- **Action**: Prioritize and potentially increase result limits

## CSV Schema

### Main Columns (70+ columns)

**Identification**: alert_id, execution_timestamp, alert_name, subheader, alert_type, user

**Keywords**: primary_keywords, alias_keywords, all_keywords, search_type

**Collection**: total_articles_collected, total_unique_after_dedup, total_duplicates_removed, overall_duplicate_rate

**Retrievers** (4 retrievers × 8 metrics = 32 columns):
- `{retriever}_total_retrieved`
- `{retriever}_after_dedup`
- `{retriever}_strategies_used`
- `{retriever}_unique_contribution`
- `{retriever}_duplicate_rate`
- `{retriever}_avg_relevance`
- `{retriever}_final_kept`
- `{retriever}_execution_time`

**Dates**: articles_with_original_dates, articles_with_extracted_dates, llm_date_extraction_success_rate

**Relevance**: articles_relevance_high_80plus, articles_relevance_medium_60_79, articles_relevance_low_below60, avg_relevance_score

**Strategies** (JSON): retriever_strategy_details_json

**Performance**: total_execution_time, data_collection_time, deduplication_time, date_extraction_time, relevance_analysis_time

## Best Practices

### 1. **Regular Analysis**
- Run weekly analysis reports
- Track trends over time
- Document optimization decisions

### 2. **Gradual Changes**
- Disable one strategy at a time
- Monitor impact before making more changes
- Keep metadata for rollback reference

### 3. **Context Matters**
- Consider alert type (some strategies work better for specific topics)
- Check if low performance is due to poor results or just topic mismatch
- Look at relevance scores, not just effectiveness rates

### 4. **Cost vs. Benefit**
- Balance API costs with result quality
- Consider execution time in optimization
- High duplicate rate may be acceptable if unique contributions are valuable

### 5. **Data-Driven Decisions**
- Wait for sufficient data (10-20 alerts minimum)
- Use statistics (averages, not outliers)
- Test hypotheses with A/B comparison periods

## Troubleshooting

### CSV File Not Created
- Ensure write permissions in working directory
- Check for errors in console output
- Verify `get_tracker()` is being called

### Missing Data in Analysis
- Confirm alerts have been executed successfully
- Check CSV file exists and contains data
- Verify file path in analyzer initialization

### Strategy Details Not Available
- Ensure strategies are properly tracked in workflow
- Check `retriever_strategy_details_json` column in CSV
- Update tracking code if new strategies added

## Future Enhancements

Potential additions to the tracking system:

1. **Time-Series Analysis**: Track performance trends over time
2. **A/B Testing Framework**: Compare strategy configurations
3. **Auto-Optimization**: Automatically disable poor strategies
4. **Cost Tracking**: Monitor API costs per retriever/strategy
5. **Alert Type Segmentation**: Separate analysis by alert type
6. **User-Specific Analysis**: Track performance per user
7. **Real-time Dashboard**: Web interface for live metrics
8. **ML-Based Recommendations**: Predict optimal strategy combinations

## Support

For questions or issues with the metadata tracking system:
1. Check this README
2. Review example outputs in `analyze_metadata.py`
3. Examine CSV structure in `alert_metadata.csv`
4. Consult code documentation in `alert_metadata_tracker.py`

