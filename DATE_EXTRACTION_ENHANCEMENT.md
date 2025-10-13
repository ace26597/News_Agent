# Smart Date Extraction Enhancement

## Overview
Enhanced the date extraction system to intelligently handle articles without publication dates using AI-powered content analysis.

## Problem Solved
Previously, articles without explicit publication dates were discarded, potentially losing valuable recent content. Many web articles don't have structured metadata but mention dates in their content, URL, or text.

## Solution Implemented

### 1. **Two-Tier LLM Strategy**
- **Main Model (`gpt-4o-mini`)**: Used for relevance analysis and curation
- **Date Extraction Model (`gpt-3.5-turbo`)**: Faster, cheaper model specifically for date extraction

### 2. **Complete Context Analysis**
The LLM now receives comprehensive information:
- **URL** (up to 200 chars) - Often contains dates like `/2024/03/15/`
- **Title** (up to 500 chars)
- **Content** (up to 3000 chars) - Significantly increased from 1500
- **Metadata** - Source, authors, and other available fields

### 3. **Smart Extraction Strategy**
The system follows this hierarchy:

**Step 1: Metadata Parsing**
- Attempts to parse any existing date field
- Supports multiple date formats

**Step 2: LLM Date Extraction** ⭐ (Enhanced)
- Uses `gpt-3.5-turbo` for cost efficiency
- Analyzes URL, title, content, and metadata
- Looks for publication indicators like "Published on", "Posted", timestamps
- Extracts dates from URL patterns

**Step 3: Regex Fallback**
- Pattern matching for common date formats
- Backup when LLM extraction fails

### 4. **Intelligent Filtering**
Articles are kept if:
1. They have a valid publication date in metadata, OR
2. LLM successfully extracts a date from content/URL/metadata, AND
3. The date falls within the search date range

## Configuration

### New Constants Added

```python
# In constants.py
DATE_EXTRACTION_MODEL = "gpt-3.5-turbo"  # Faster/cheaper for date extraction
```

### Files Modified

1. **constants.py** - Added `DATE_EXTRACTION_MODEL` setting
2. **constants.py.example** - Updated template with new setting
3. **config.py** - Added configuration support for date extraction model
4. **multi_agent_pharma.py** - Enhanced date extraction logic:
   - Updated `extract_date()` to use complete article context
   - Modified `_llm_extract_date()` with expanded context (URL, metadata, 3000 chars content)
   - Added tracking for "LLM rescued" articles
   - Improved logging and statistics

## Benefits

✅ **Cost Efficient**: Uses cheaper `gpt-3.5-turbo` for date extraction instead of `gpt-4o-mini`

✅ **More Comprehensive**: Analyzes URL patterns, full content (3000 chars vs 1500), and metadata

✅ **Better Coverage**: Rescues articles that would have been discarded

✅ **Transparent**: Tracks and logs "LLM rescued" articles separately

✅ **Maintains Quality**: Only includes articles with dates within the specified range

## Usage Statistics

The system now reports:
- Articles with existing dates
- Articles without dates (before LLM extraction)
- Articles with LLM-extracted dates
- **Articles "rescued" by LLM** (had no date but LLM found one within range)

Example output:
```
✅ DATE EXTRACTION COMPLETE: 45 with dates, 12 without
✅ DATE FILTERING COMPLETE: 40 in range, 8 rescued by LLM date extraction
```

## Example Scenarios

### Scenario 1: Date in URL
**Article**: `https://pharmanews.com/2024/03/15/new-drug-approval`
- No metadata date
- LLM extracts `2024-03-15` from URL
- Article included if date is in range ✅

### Scenario 2: Date in Content
**Content**: "Posted on March 15, 2024 - FDA approves new treatment..."
- No metadata date
- LLM finds "March 15, 2024" in content
- Article included if date is in range ✅

### Scenario 3: No Date Found
**Article**: Generic content with no date indicators
- No metadata date
- LLM cannot find any date
- Article discarded ❌

## Cost Optimization

Using `gpt-3.5-turbo` for date extraction instead of `gpt-4o-mini`:
- **~10x cheaper** per API call
- **Faster response times**
- **Sufficient for date extraction task**
- Main model still used for complex relevance analysis

## Testing

To verify the enhancement:
1. Run a search with date range
2. Check console output for "LLM rescued" count
3. Review articles with extracted dates
4. Verify dates are within specified range

