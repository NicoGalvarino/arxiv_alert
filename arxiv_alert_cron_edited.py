#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modified version of arxiv_alert_script.py to run with cron instead of schedule
Fetches recent arXiv papers and generates HTML alerts
"""

import urllib.request
import urllib.parse
import urllib.error
import feedparser
from datetime import date, timedelta, datetime
from bs4 import BeautifulSoup
import requests
import os
import logging
import json
from pathlib import Path

# Override date for testing - set to None to use actual date
OVERRIDE_DATE = None

def get_current_date():
    """Get the current date, with optional override for testing"""
    return OVERRIDE_DATE if OVERRIDE_DATE is not None else date.today()

# Set up logging
import os
home_dir = os.path.expanduser('~')
log_file = os.path.join(home_dir, 'Documents', 'arxiv_alert', 'arxiv_alert.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_processed_papers():
    """Load the list of previously processed paper IDs"""
    home_dir = os.path.expanduser('~')
    processed_file = os.path.join(home_dir, 'Documents', 'arxiv_alert', 'processed_papers.json')
    try:
        with open(processed_file, 'r') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_processed_papers(processed_papers):
    """Save the list of processed paper IDs"""
    home_dir = os.path.expanduser('~')
    processed_file = os.path.join(home_dir, 'Documents', 'arxiv_alert', 'processed_papers.json')
    os.makedirs(os.path.dirname(processed_file), exist_ok=True)
    with open(processed_file, 'w') as f:
        json.dump(list(processed_papers), f)

def clean_old_processed_papers(processed_papers, days_to_keep=30):
    """Clean old entries to prevent the file from growing indefinitely"""
    # Keep only the most recent entries
    if len(processed_papers) > 1000:
        processed_papers = set(list(processed_papers)[-500:])
    return processed_papers

def test_simple_query():
    """Test with a very basic query"""
    base_url = 'http://export.arxiv.org/api/query?'
    simple_query = 'search_query=cat:astro-ph.ga&max_results=5'

    try:
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        response = urllib.request.urlopen(base_url + simple_query, timeout=30, context=ssl_context).read()
        feed = feedparser.parse(response)
        logging.info(f"Simple query returned {len(feed.entries)} entries")
        return len(feed.entries) > 0
    except Exception as e:
        logging.error(f"Simple query failed: {e}")
        return False

def find_matching_keywords(title, abstract, keywords):
    """
    Find which keywords from the search list are present in the title or abstract
    """
    matching_keywords = []
    title_lower = title.lower()
    abstract_lower = abstract.lower()

    for keyword in keywords:
        # Remove quotes from keywords for matching
        clean_keyword = keyword.strip('"').lower()

        if clean_keyword in title_lower or clean_keyword in abstract_lower:
            # Indicate where the keyword was found
            found_in = []
            if clean_keyword in title_lower:
                found_in.append("title")
            if clean_keyword in abstract_lower:
                found_in.append("abstract")

            matching_keywords.append(f"{keyword} ({', '.join(found_in)})")

    return matching_keywords

def get_paper_comments(arxiv_id):
    """
    Fetch comments for a specific arXiv paper by accessing its abstract page
    """
    url = f"https://arxiv.org/abs/{arxiv_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Look for comments in the metadata section
            comments_element = soup.find('td', class_='tablecell comments mathjax')
            if comments_element:
                return comments_element.get_text(strip=True)
        return "No comments"
    except Exception as e:
        logging.error(f"Error fetching comments for {arxiv_id}: {e}")
        return "Comments unavailable"

def parse_arxiv_date(date_str):
    """Parse arXiv date string to datetime object"""
    try:
        # arXiv dates are in format: 2024-11-20T12:34:56Z
        return datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None

def is_date_in_range(entry, start_date, end_date):
    """Check if entry's submitted date is within the specified range"""
    try:
        entry_id = getattr(entry, 'id', 'unknown')
        if '/' in entry_id:
            entry_id = entry_id.split('/abs/')[-1]

        # Priority 1: Check arxiv_updated (usually matches submittedDate from query)
        if hasattr(entry, 'arxiv_updated') and entry.arxiv_updated:
            updated_date = parse_arxiv_date(entry.arxiv_updated)
            if updated_date:
                in_range = start_date <= updated_date <= end_date
                if not in_range:
                    logging.info(f"Paper {entry_id} arxiv_updated {updated_date} outside range {start_date} to {end_date}")
                return in_range

        # Priority 2: Check updated field (also often matches submittedDate)
        if hasattr(entry, 'updated') and entry.updated:
            updated_date = parse_arxiv_date(entry.updated)
            if updated_date:
                in_range = start_date <= updated_date <= end_date
                if not in_range:
                    logging.info(f"Paper {entry_id} updated {updated_date} outside range {start_date} to {end_date}")
                return in_range

        # Priority 3: Check published date
        if hasattr(entry, 'published') and entry.published:
            published_date = parse_arxiv_date(entry.published)
            if published_date:
                in_range = start_date <= published_date <= end_date
                if not in_range:
                    logging.info(f"Paper {entry_id} published {published_date} outside range {start_date} to {end_date}")
                return in_range

        # Priority 4: Fallback to arxiv:created if available (from arxiv namespace)
        if hasattr(entry, 'arxiv_created') and entry.arxiv_created:
            created_date = parse_arxiv_date(entry.arxiv_created)
            if created_date:
                in_range = start_date <= created_date <= end_date
                if not in_range:
                    logging.info(f"Paper {entry_id} created {created_date} outside range {start_date} to {end_date}")
                return in_range

        # If no date found, log warning but don't filter out (API already filtered by submittedDate)
        logging.warning(f"Could not parse date for entry {entry_id}, including by default (API already filtered)")
        return True  # Include by default if date parsing fails (API query already filtered)
    except Exception as e:
        entry_id = getattr(entry, 'id', 'unknown')
        logging.error(f"Error checking date for entry {entry_id}: {e}")
        return True  # Include by default on error

def build_arxiv_query(categories=None, keywords=None, authors=None, start_date=None, end_date=None):
    """
    Build arXiv API query string with proper formatting
    Note: URL encoding will be done by urlencode, so we build the query without encoding here
    """
    query_parts = []

    # Categories - format: (cat:cat1 OR cat:cat2)
    if categories:
        cat_parts = [f"cat:{cat}" for cat in categories]
        query_parts.append(f"({' OR '.join(cat_parts)})")

    # Keywords in title or abstract - format: ((ti:kw1 OR abs:kw1) OR (ti:kw2 OR abs:kw2))
    if keywords:
        keyword_or_parts = []
        for kw in keywords:
            # Don't encode here - urlencode will do it
            keyword_or_parts.append(f"(ti:{kw} OR abs:{kw})")
        query_parts.append(f"({' OR '.join(keyword_or_parts)})")

    # Authors - format: (au:auth1 OR au:auth2)
    if authors:
        author_parts = [f"au:{auth}" for auth in authors]
        query_parts.append(f"({' OR '.join(author_parts)})")

    # Date range - format: submittedDate:[YYYYMMDDHHmm TO YYYYMMDDHHmm]
    if start_date and end_date:
        start_str = start_date.strftime("%Y%m%d") + "0000"
        end_str = end_date.strftime("%Y%m%d") + "2359"
        query_parts.append(f"submittedDate:[{start_str}+TO+{end_str}]")

    # Combine all parts with AND
    if query_parts:
        full_query = '+AND+'.join(query_parts)
    else:
        full_query = '*'

    return full_query

def fetch_arxiv_batch(categories=None, keywords_batch=None, authors=None, start_date=None, end_date=None, max_results=200, start=0):
    """
    Fetch a single batch of papers from arXiv API with pagination support
    Returns feedparser object or None on error
    """
    base_url = 'http://export.arxiv.org/api/query?'

    # Build query for this batch
    search_query = build_arxiv_query(
        categories=categories,
        keywords=keywords_batch,
        authors=authors,
        start_date=start_date,
        end_date=end_date
    )

    # Build full query URL
    query_params = {
        'search_query': search_query,
        'start': start,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }

    query_string = urllib.parse.urlencode(query_params)
    full_url = base_url + query_string

    try:
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        response = urllib.request.urlopen(full_url, timeout=60, context=ssl_context).read()
        return feedparser.parse(response)
    except Exception as e:
        logging.warning(f"Error fetching batch: {e}")
        return None

def arxiv_alert(html_name, amount_of_days, categories=None, keywords=None, authors=None, excluded_categories=None):
    """
    Main function to fetch arXiv papers and generate HTML alert
    Splits large keyword queries into batches to avoid API errors
    """
    processed_papers = load_processed_papers()
    new_processed_papers = set()

    # Calculate date range
    today = get_current_date()
    if amount_of_days < 1:
        amount_of_days = 1

    yesterday = today - timedelta(days=1)
    start_window = yesterday - timedelta(days=amount_of_days - 1)
    
    # Note: arXiv API uses UTC timezone. To ensure we capture all articles from start_date,
    # we extend the start window by 1 day earlier to account for timezone differences
    # This ensures articles submitted on start_date in any timezone are included
    api_start_window = start_window - timedelta(days=1)

    logging.info(f"Date range for filtering: {start_window.strftime('%Y-%m-%d')} to {yesterday.strftime('%Y-%m-%d')}")
    logging.info(f"Date range for API query: {api_start_window.strftime('%Y-%m-%d')} to {yesterday.strftime('%Y-%m-%d')} (extended to account for UTC)")
    print(f"Date range: {start_window.strftime('%Y-%m-%d')} to {yesterday.strftime('%Y-%m-%d')}")

    # Set max results per API call (arXiv API limit is 2000, but we use smaller chunks for pagination)
    max_results_per_call = 200
    
    # Maximum total results to fetch per keyword batch (to avoid excessive API calls)
    max_total_results = min(2000, 200 * amount_of_days)

    # Split keywords into batches if there are too many (to avoid API errors)
    # arXiv API has limits on query length, so we split into batches of ~15 keywords
    keyword_batches = []
    if keywords and len(keywords) > 15:
        batch_size = 15
        for i in range(0, len(keywords), batch_size):
            keyword_batches.append(keywords[i:i + batch_size])
        logging.info(f"Split {len(keywords)} keywords into {len(keyword_batches)} batches")
    elif keywords:
        keyword_batches = [keywords]
    else:
        keyword_batches = [None]

    # Fetch papers from all batches with pagination
    all_entries = []
    all_entry_ids = set()  # To avoid duplicates

    for batch_idx, keyword_batch in enumerate(keyword_batches):
        logging.info(f"Fetching keyword batch {batch_idx + 1}/{len(keyword_batches)}")
        
        # Paginate through results for this keyword batch
        start = 0
        page_num = 0
        total_fetched = 0
        
        while start < max_total_results:
            page_num += 1
            logging.info(f"  Fetching page {page_num} (start={start}, max_results={max_results_per_call})")
            
            feed = fetch_arxiv_batch(
                categories=categories,
                keywords_batch=keyword_batch,
                authors=authors,
                start_date=api_start_window,  # Use extended start window for API query
                end_date=yesterday,
                max_results=max_results_per_call,
                start=start
            )

            if feed and hasattr(feed, 'entries'):
                if len(feed.entries) == 0:
                    # No more results
                    logging.info(f"  No more results on page {page_num}")
                    break
                
                # Log dates of all returned entries for debugging
                dates_found = []
                page_entries = 0
                
                for entry in feed.entries:
                    entry_id = entry.id.split('/abs/')[-1]
                    
                    # Collect date information
                    date_info = {}
                    if hasattr(entry, 'arxiv_updated') and entry.arxiv_updated:
                        date_info['arxiv_updated'] = parse_arxiv_date(entry.arxiv_updated)
                    if hasattr(entry, 'updated') and entry.updated:
                        date_info['updated'] = parse_arxiv_date(entry.updated)
                    if hasattr(entry, 'published') and entry.published:
                        date_info['published'] = parse_arxiv_date(entry.published)
                    dates_found.append(date_info)
                    
                    if entry_id not in all_entry_ids:
                        all_entry_ids.add(entry_id)
                        all_entries.append(entry)
                        page_entries += 1
                
                total_fetched += len(feed.entries)
                
                # Log summary of dates for this page
                if dates_found:
                    unique_dates = set()
                    for d_info in dates_found:
                        for key, val in d_info.items():
                            if val:
                                unique_dates.add(val)
                    logging.info(f"  Page {page_num}: {len(feed.entries)} entries ({page_entries} new), dates: {sorted(unique_dates)}")
                
                # If we got fewer results than requested, we've reached the end
                if len(feed.entries) < max_results_per_call:
                    logging.info(f"  Reached end of results (got {len(feed.entries)}, expected {max_results_per_call})")
                    break
                
                # Move to next page
                start += max_results_per_call
            else:
                logging.warning(f"  Page {page_num} failed or returned no results")
                break
        
        logging.info(f"Keyword batch {batch_idx + 1}: fetched {total_fetched} total entries, {len(all_entries)} unique total")

    # If no entries found, create error message HTML
    if len(all_entries) == 0:
        body = str()
        body += "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        body += "<link href='https://fonts.googleapis.com/css?family=Montserrat' rel='stylesheet'>"
        body += """<style>
        body {font-family: 'Montserrat', sans-serif; background: #F3F3F3; width: 740px; margin: 0 auto; line-height: 150%; margin-top: 50px; font-size: 15px}
        h1 {font-size: 70px}
        a {color: #45ABC2}
        em {font-size: 120%}
        </style>
        </head><body>"""
        body += "<h1><center>ArXiv Alert</center></h1>"
        body += f"<font color='#DDAD5C'><em>Update: from {start_window.strftime('%d %b %Y')} to {yesterday.strftime('%d %b %Y')}</em></font><br><br>"
        body += f'<p><strong>No papers found</strong> for this period.</p>'
        body += f'<p>Tried {len(keyword_batches)} batch(es) of queries.</p>'
        body += "</body></html>"

        # Save HTML file with timestamp
        home_dir = os.path.expanduser('~')
        output_dir = os.path.join(home_dir, 'Documents', 'arxiv_alert', 'arxiv_htmls')
        os.makedirs(output_dir, exist_ok=True)
        subdir = os.path.dirname(html_name)
        if subdir:
            full_output_dir = os.path.join(output_dir, subdir)
            os.makedirs(full_output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            my_path = os.path.join(full_output_dir, os.path.basename(html_name) + '_' + timestamp + '.html')
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            my_path = os.path.join(output_dir, html_name + '_' + timestamp + '.html')

        try:
            with open(my_path, 'w', encoding='utf-8') as f:
                f.write(body)
            logging.info(f"Created HTML file: {my_path}")
            return my_path
        except Exception as save_error:
            logging.error(f"Error writing HTML file: {save_error}")
            return None

    # Process all entries
    logging.info(f"Total unique entries found: {len(all_entries)}")
    if len(all_entries) > 0:
        logging.info(f"First entry title: {all_entries[0].title}")
        if hasattr(all_entries[0], 'published'):
            logging.info(f"First entry published: {all_entries[0].published}")

    # Build HTML content
    body = str()
    body += "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    body += "<link href='https://fonts.googleapis.com/css?family=Montserrat' rel='stylesheet'>"

    # MathJax for LaTeX rendering
    body += """
    <script type="text/x-mathjax-config">
    MathJax.Hub.Config({
        tex2jax: {
            inlineMath: [['$','$']],
            processEscapes: true
        },
        "HTML-CSS": {
            availableFonts: ["TeX"]
        }
    });
    </script>
    <script type="text/javascript" async
        src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML">
    </script>
    """

    body += """<style>
    body {font-family: 'Montserrat', sans-serif; background: #F3F3F3; width: 740px; margin: 0 auto; line-height: 150%; margin-top: 50px; font-size: 15px}
    h1 {font-size: 70px}
    a {color: #45ABC2}
    em {font-size: 120%}
    </style>
    </head><body>"""
    body += "<h1><center>ArXiv Alert</center></h1>"
    body += f"<font color='#DDAD5C'><em>Update: from {start_window.strftime('%d %b %Y')} to {yesterday.strftime('%d %b %Y')}</em></font><br><br>"

    new_papers_count = 0
    total_papers_count = len(all_entries)
    filtered_papers_count = 0
    no_keywords_count = 0
    date_filtered_count = 0
    already_processed_count = 0
    shown_papers_count = 0  # Count of papers shown in HTML

    for entry in all_entries:
        arxiv_id = entry.id.split('/abs/')[-1]
        base_arxiv_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id

        # Check if already processed (but still show it in HTML)
        is_already_processed = base_arxiv_id in processed_papers
        if is_already_processed:
            already_processed_count += 1

        # Additional date filtering (double-check, but be lenient since API already filtered)
        # Log date information for debugging
        entry_date_info = []
        if hasattr(entry, 'arxiv_updated') and entry.arxiv_updated:
            date_val = parse_arxiv_date(entry.arxiv_updated)
            if date_val:
                entry_date_info.append(f"arxiv_updated={date_val}")
        if hasattr(entry, 'updated') and entry.updated:
            date_val = parse_arxiv_date(entry.updated)
            if date_val:
                entry_date_info.append(f"updated={date_val}")
        if hasattr(entry, 'published') and entry.published:
            date_val = parse_arxiv_date(entry.published)
            if date_val:
                entry_date_info.append(f"published={date_val}")
        
        date_check = is_date_in_range(entry, start_window, yesterday)
        if not date_check and entry_date_info:
            # Log but don't filter out - API already filtered by submittedDate
            logging.info(f"Paper {arxiv_id} date check: {', '.join(entry_date_info)} vs range {start_window} to {yesterday} - including anyway")
        elif not date_check:
            # If no date info at all, still include (API already filtered)
            logging.info(f"Paper {arxiv_id} - no date info found, including anyway (API already filtered)")

        # Get all categories
        all_categories = [t['term'] for t in entry.tags]
        
        # Normalize categories for case-insensitive comparison (lowercase)
        all_categories_lower = [cat.lower() for cat in all_categories]

        # Check if article has at least one category from the required list (case-insensitive)
        if categories:
            required_categories_lower = [cat.lower() for cat in categories]
            has_required_category = any(cat_lower in required_categories_lower for cat_lower in all_categories_lower)
            if not has_required_category:
                filtered_papers_count += 1
                logging.info(f"Filtered out paper {arxiv_id} due to not matching required categories. Paper categories: {all_categories}, Required: {categories}")
                continue

        # Check excluded categories (case-insensitive)
        if excluded_categories:
            excluded_categories_lower = [cat.lower() for cat in excluded_categories]
            has_excluded_category = any(cat_lower in excluded_categories_lower for cat_lower in all_categories_lower)
            if has_excluded_category:
                filtered_papers_count += 1
                excluded_found = [cat for cat, cat_lower in zip(all_categories, all_categories_lower) if cat_lower in excluded_categories_lower]
                logging.info(f"Filtered out paper {arxiv_id} due to excluded categories: {excluded_found}")
                continue

        # Check keywords
        matching_keywords = []
        if keywords is not None:
            matching_keywords = find_matching_keywords(entry.title, entry.summary, keywords)
            if not matching_keywords:
                no_keywords_count += 1
                logging.info(f"Filtered out paper {arxiv_id} due to no matching keywords")
                continue

        # Add to processed papers only if it's new
        if not is_already_processed:
            new_processed_papers.add(base_arxiv_id)
            new_papers_count += 1

        # Always add to HTML (even if already processed)
        shown_papers_count += 1

        # Get PDF link
        pdf_link = entry.id  # Default to abstract page
        for link in entry.links:
            if link.get('type') == 'application/pdf':
                pdf_link = link.href
                break

        # Get comments
        comments = get_paper_comments(arxiv_id)

        # Build HTML for this paper
        # Add indicator if paper was already seen before
        new_badge = ''
        if is_already_processed:
            new_badge = ' <span style="color: #999; font-size: 0.8em;">(seen before)</span>'
        else:
            new_badge = ' <span style="color: #45ABC2; font-size: 0.8em; font-weight: bold;">[NEW]</span>'

        body += f'<a href="{pdf_link}" target="_blank"><h2>{entry.title}{new_badge}</h2></a>'

        try:
            authors_list = ', '.join(author.name for author in entry.authors)
            body += f'<strong><u>Authors:</u></strong> {authors_list}<br>'
        except (AttributeError, TypeError):
            pass

        body += f'<strong><u>Categories:</u></strong> {", ".join(all_categories)}<br>'
        body += f'<strong><u>Comments:</u></strong> {comments}<br>'

        # Add published date
        if hasattr(entry, 'published'):
            try:
                pub_date = parse_arxiv_date(entry.published)
                if pub_date:
                    body += f'<strong><u>Published:</u></strong> {pub_date.strftime("%Y-%m-%d")}<br>'
            except:
                pass

        # Add matching keywords
        if keywords is None:
            body += '<strong><u>Matching Keywords:</u></strong> Not evaluated (no keywords configured)<br>'
        elif matching_keywords:
            body += f'<strong><u>Matching Keywords:</u></strong> {", ".join(matching_keywords)}<br>'
        else:
            body += '<strong><u>Matching Keywords:</u></strong> None<br>'

        # Abstract
        body += f'<p><strong><u>Abstract:</u></strong> {entry.summary}</p>'
        body += '<br><hr><br>'

    # Add message if no papers shown
    if shown_papers_count == 0:
        body += f'<p><em>No papers found for this period.</em></p>'
        body += f'<p>Statistics: Found {total_papers_count} total papers, '
        body += f'{already_processed_count} already processed, '
        body += f'{no_keywords_count} filtered by keywords, '
        body += f'{filtered_papers_count} filtered by excluded categories.</p>'
    else:
        # Add summary at the end
        seen_before_count = shown_papers_count - new_papers_count
        body += f'<hr><p><em>Summary: Showing {shown_papers_count} papers ({new_papers_count} new, {seen_before_count} seen before)</em></p>'

    body += "</body></html>"

    # Update processed papers
    processed_papers.update(new_processed_papers)
    processed_papers = clean_old_processed_papers(processed_papers)
    save_processed_papers(processed_papers)

    # Log statistics
    logging.info(f"Found {total_papers_count} total papers")
    logging.info(f"Already processed: {already_processed_count}, Filtered: {date_filtered_count} by date, {filtered_papers_count} by excluded categories, {no_keywords_count} by keywords")
    logging.info(f"Showing {shown_papers_count} papers in HTML ({new_papers_count} new, {shown_papers_count - new_papers_count} seen before)")

    # Save HTML file
    home_dir = os.path.expanduser('~')
    output_dir = os.path.join(home_dir, 'Documents', 'arxiv_alert', 'arxiv_htmls')
    os.makedirs(output_dir, exist_ok=True)

    # Create subdirectory if needed
    # Add timestamp to filename to avoid overwriting old files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    subdir = os.path.dirname(html_name)
    if subdir:
        full_output_dir = os.path.join(output_dir, subdir)
        os.makedirs(full_output_dir, exist_ok=True)
        my_path = os.path.join(full_output_dir, os.path.basename(html_name) + '_' + timestamp + '.html')
    else:
        my_path = os.path.join(output_dir, html_name + '_' + timestamp + '.html')

    try:
        with open(my_path, 'w', encoding='utf-8') as f:
            f.write(body)
        logging.info(f"Created HTML file: {my_path}")
        return my_path
    except Exception as e:
        logging.error(f"Error writing HTML file: {e}")
        return None

# Categories and keywords definitions
categories_astroph = ['astro-ph.co', 'astro-ph.ga', 'astro-ph.he']
keywords_astroph = [
    'ALMA', 'ALMACAL',
    'MUSE', 'MUSE-ALMA',
    'JWST', 'James Webb Space Telescope',
    '4MOST', 'DESI', 'Euclid', 'SDSS',
    'galaxy evolution', 'galaxy formation', 'galactic chemical evolution', 'galaxy chemical evolution',
    'galactic outlflows', 'galactic outlflow', 'outflows', 'outflow',
    'dust', 'dust evolution', 'stellar mass function', 'quiescent galaxies', 'atomic hydrogen',
    'baryon cycle', 'baryon budget', 'metal budget', 'baryon density', 'cosmic abundance', 'cosmic evolution', 'cosmic gas',
    'atomic gas', 'molecular gas', 'interstellar dust', 'ISM', 'kinematics',
    'quasar absorption lines', 'QSO absorption lines', 'QSO absorber', 'quasar absorber', 'MgII absorber', 'MgII absorbers',
    'high z', 'high redshift',
    'feedback', 'stellar feedback',
    'AGN', 'AGN feedback',
    'active galactic nuclei', 'QSO', 'quasar',
    'BAL QSO', 'broad absorption line quasar', 'broad absorption line QSO',
    'AGN variability', 'active galactic nuclei variability', 'blazar variability', 'time-domain', 'time domain',
    'CGM', 'circumgalactic medium', 'IGM', 'intergalactic medium', 'halo', 'haloes',
    'damped lyman alpha system', 'DLA',
    'lyman limit system', 'LLS'
]
excluded_astro_categories = ['astro-ph.EP', 'astro-ph.SR']

categories_ml = ['astro-ph.co', 'astro-ph.ga', 'astro-ph.he', 'astro-ph.im',
                  "cs.ai", "cs.gl", "cs.lg", "stat.ml"]
keywords_ml = [
    'astroinformatics', 'astro-informatics', 'data-driven',
    'variational autoencoder', 'VAE',
    'convolutional',
    'anomaly detection', 'contextual anomaly detection',
    'dimensionality reduction', 'dimension reduction', 'latent space',
    'explainability', 'explainable',
    'neural network',
    'multimodal', 'multi-modal', 'multimodality', 'multi-modality',
    'domain adaptation', 'transfer learning',
    'time-domain', 'time sequence', 'sequential data',
    'invertible neural network',
    'over-sampling',
    'transformer', 'attention',
    'data augmentation',
    'causality', 'causation',
    'literature review', 'literature discovery'
]

def run_daily_task():
    """Function to run the arXiv alert and generate HTML files"""
    today = get_current_date()
    logging.info(f"Running arXiv alerts for {today}")

    # Generate the HTML files
    # Change amount_of_days here to change the search period:
    # - 1 = yesterday only
    # - 2 = yesterday and the day before (2 days)
    # - 3 = last 3 days
    # - 7 = last week

    if today.weekday() == 0 or today.weekday() == 1:  # Monday, Tuesday
        # Use longer lookback period to ensure we find papers
        days_to_search = 3
        html_file_astro = arxiv_alert('astro/astro_arxiv_' + str(today), days_to_search,
                                      categories_astroph, keywords_astroph,
                                      excluded_categories=excluded_astro_categories)
        html_file_ml = arxiv_alert('ml/ml_arxiv_' + str(today), days_to_search,
                                   categories_ml, keywords_ml)
    else:
        # Regular daily lookback
        days_to_search = 10
        html_file_astro = arxiv_alert('astro/astro_arxiv_' + str(today), days_to_search,
                                      categories_astroph, keywords_astroph,
                                      excluded_categories=excluded_astro_categories)
        html_file_ml = arxiv_alert('ml/ml_arxiv_' + str(today), days_to_search,
                                   categories_ml, keywords_ml)

    logging.info(f"Daily task completed for {today}")

    # Test API availability
    if not test_simple_query():
        logging.error("Even simple query failed - API might be down")

if __name__ == "__main__":
    run_daily_task()
