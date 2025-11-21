#!/usr/bin/env python3
"""
Test script to verify arxiv_alert_cron.py functionality
"""

import sys
import os
from datetime import date, timedelta

# Add the directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import functions from the main script
from arxiv_alert_cron import (
    build_arxiv_query,
    parse_arxiv_date,
    is_date_in_range,
    get_current_date,
    find_matching_keywords
)

def test_build_arxiv_query():
    """Test query building"""
    print("Testing build_arxiv_query...")
    
    # Test with categories
    query1 = build_arxiv_query(categories=['astro-ph.ga', 'astro-ph.co'])
    print(f"Query with categories: {query1[:100]}...")
    assert 'cat:astro-ph.ga' in query1, "Categories not in query"
    
    # Test with keywords
    query2 = build_arxiv_query(keywords=['JWST', 'galaxy'])
    print(f"Query with keywords: {query2[:100]}...")
    assert 'ti:' in query2 or 'abs:' in query2, "Keywords not in query"
    
    # Test with date range
    today = date.today()
    yesterday = today - timedelta(days=1)
    query3 = build_arxiv_query(
        categories=['astro-ph.ga'],
        start_date=yesterday,
        end_date=yesterday
    )
    print(f"Query with dates: {query3[:100]}...")
    assert 'submittedDate:' in query3, "Date range not in query"
    
    print("✓ build_arxiv_query tests passed\n")

def test_parse_arxiv_date():
    """Test date parsing"""
    print("Testing parse_arxiv_date...")
    
    # Test valid date
    date1 = parse_arxiv_date("2024-11-20T12:34:56Z")
    assert date1 == date(2024, 11, 20), f"Expected 2024-11-20, got {date1}"
    
    # Test invalid date
    date2 = parse_arxiv_date("invalid")
    assert date2 is None, "Should return None for invalid date"
    
    # Test None
    date3 = parse_arxiv_date(None)
    assert date3 is None, "Should return None for None input"
    
    print("✓ parse_arxiv_date tests passed\n")

def test_find_matching_keywords():
    """Test keyword matching"""
    print("Testing find_matching_keywords...")
    
    title = "JWST observations of galaxy evolution"
    abstract = "We study the formation of galaxies using ALMA data"
    keywords = ['JWST', 'ALMA', 'galaxy evolution', 'nonexistent']
    
    matches = find_matching_keywords(title, abstract, keywords)
    print(f"Found matches: {matches}")
    
    assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"
    assert any('JWST' in m for m in matches), "JWST should be found"
    assert any('ALMA' in m for m in matches), "ALMA should be found"
    assert any('galaxy evolution' in m for m in matches), "galaxy evolution should be found"
    
    print("✓ find_matching_keywords tests passed\n")

def test_date_range_logic():
    """Test date range calculation"""
    print("Testing date range logic...")
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    amount_of_days = 3
    
    start_window = yesterday - timedelta(days=amount_of_days - 1)
    
    print(f"Today: {today}")
    print(f"Yesterday: {yesterday}")
    print(f"Start window: {start_window}")
    print(f"Date range: {start_window} to {yesterday}")
    
    # Verify the range is correct
    days_in_range = (yesterday - start_window).days + 1
    assert days_in_range == amount_of_days, f"Expected {amount_of_days} days, got {days_in_range}"
    
    print("✓ Date range logic tests passed\n")

def test_query_url_encoding():
    """Test that query is properly URL encoded"""
    print("Testing query URL encoding...")
    
    from urllib.parse import urlencode, quote
    
    query = build_arxiv_query(
        categories=['astro-ph.ga'],
        keywords=['galaxy evolution', 'JWST'],
        start_date=date(2024, 11, 18),
        end_date=date(2024, 11, 19)
    )
    
    # Build URL params
    params = {
        'search_query': query,
        'start': 0,
        'max_results': 10
    }
    
    url_string = urlencode(params)
    print(f"Encoded query (first 200 chars): {url_string[:200]}...")
    
    # Check that special characters are encoded
    assert '%28' in url_string or '(' in url_string, "Query should contain parentheses or encoded version"
    
    print("✓ URL encoding tests passed\n")

def test_category_filtering():
    """Test category filtering logic (case-insensitive)"""
    print("Testing category filtering...")
    
    # Create mock entry objects
    class MockTag:
        def __init__(self, term):
            self.term = term
    
    class MockEntry:
        def __init__(self, categories, entry_id="test123"):
            self.tags = [MockTag(cat) for cat in categories]
            self.id = f"http://arxiv.org/abs/{entry_id}"
    
    # Test case 1: Article with matching category (case-insensitive)
    entry1 = MockEntry(['astro-ph.CO', 'gr-qc'])
    all_categories = [t.term for t in entry1.tags]
    all_categories_lower = [cat.lower() for cat in all_categories]
    required_categories = ['astro-ph.co', 'astro-ph.ga', 'astro-ph.he']
    required_categories_lower = [cat.lower() for cat in required_categories]
    has_required = any(cat_lower in required_categories_lower for cat_lower in all_categories_lower)
    assert has_required, f"Should match astro-ph.CO (case-insensitive). Paper categories: {', '.join(all_categories)}, Required: {', '.join(required_categories)}"
    print("  ✓ Case-insensitive matching works (astro-ph.CO matches astro-ph.co)")
    
    # Test case 2: Article with excluded category
    entry2 = MockEntry(['astro-ph.SR', 'astro-ph.GA'])
    all_categories2 = [t.term for t in entry2.tags]
    all_categories_lower2 = [cat.lower() for cat in all_categories2]
    excluded_categories = ['astro-ph.EP', 'astro-ph.SR']
    excluded_categories_lower = [cat.lower() for cat in excluded_categories]
    has_excluded = any(cat_lower in excluded_categories_lower for cat_lower in all_categories_lower2)
    excluded_found = [cat for cat, cat_lower in zip(all_categories2, all_categories_lower2) if cat_lower in excluded_categories_lower]
    assert has_excluded, f"Should detect excluded category astro-ph.SR. Paper categories: {', '.join(all_categories2)}, Excluded found: {', '.join(excluded_found)}, All excluded: {', '.join(excluded_categories)}"
    print("  ✓ Excluded category detection works (astro-ph.SR detected)")
    
    # Test case 3: Article without required categories
    entry3 = MockEntry(['hep-ph', 'gr-qc'])
    all_categories3 = [t.term for t in entry3.tags]
    all_categories_lower3 = [cat.lower() for cat in all_categories3]
    has_required3 = any(cat_lower in required_categories_lower for cat_lower in all_categories_lower3)
    assert not has_required3, f"Should not match - no required categories. Paper categories: {', '.join(all_categories3)}, Required: {', '.join(required_categories)}"
    print("  ✓ Non-matching categories correctly rejected")
    
    # Test case 4: Article with multiple categories, one matches
    entry4 = MockEntry(['astro-ph.ga', 'hep-ph', 'math.OC'])
    all_categories4 = [t.term for t in entry4.tags]
    all_categories_lower4 = [cat.lower() for cat in all_categories4]
    has_required4 = any(cat_lower in required_categories_lower for cat_lower in all_categories_lower4)
    assert has_required4, f"Should match - has astro-ph.ga. Paper categories: {', '.join(all_categories4)}, Required: {', '.join(required_categories)}"
    print("  ✓ Article with multiple categories matches if one is required")
    
    print("✓ Category filtering tests passed\n")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing arxiv_alert_cron.py functionality")
    print("=" * 60 + "\n")
    
    try:
        test_build_arxiv_query()
        test_parse_arxiv_date()
        test_find_matching_keywords()
        test_date_range_logic()
        test_query_url_encoding()
        test_category_filtering()
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

