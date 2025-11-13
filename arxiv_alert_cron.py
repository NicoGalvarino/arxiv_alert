#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modified version of arxiv_alert_script.py to run with cron instead of schedule
"""

import urllib.request, urllib.parse, urllib.error
import feedparser
from datetime import date, timedelta
from bs4 import BeautifulSoup
import requests
import smtplib
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
logging.basicConfig(
    filename='/Users/nguerrav/Documents/arxiv/arxiv_alert.log', 
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_processed_papers():
    """Load the list of previously processed paper IDs"""
    processed_file = '/Users/nguerrav/Documents/arxiv/processed_papers.json'
    try:
        with open(processed_file, 'r') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_processed_papers(processed_papers):
    """Save the list of processed paper IDs"""
    processed_file = '/Users/nguerrav/Documents/arxiv/processed_papers.json'
    with open(processed_file, 'w') as f:
        json.dump(list(processed_papers), f)

def clean_old_processed_papers(processed_papers, days_to_keep=7):
    """Clean old entries to prevent the file from growing indefinitely"""
    # This is a simple approach - you could also store timestamps and clean based on actual dates
    if len(processed_papers) > 1000:  # Arbitrary threshold
        # Keep only the most recent entries (rough approximation)
        processed_papers = set(list(processed_papers)[-500:])
    return processed_papers

def test_simple_query():
    """Test with a very basic query"""
    base_url = 'http://export.arxiv.org/api/query?'
    simple_query = 'search_query=cat:astro-ph.ga&max_results=5'
    
    try:
        response = urllib.request.urlopen(base_url + simple_query).read()
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
    Adapted from: https://github.com/pulsar-xliu/filter_arxiv_by_keywords
    """
    url = f"https://arxiv.org/abs/{arxiv_id}"
    try:
        response = requests.get(url)
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

def arxiv_alert(html_name, amount_of_days, categories=None, keywords=None, authors=None, excluded_categories=None#, max_results=30
                ):
    
    processed_papers = load_processed_papers()
    new_processed_papers = set()

    # API query url for ArXiv
    base_url = 'http://export.arxiv.org/api/query?'

    max_results = 20 * amount_of_days
    
    # Define the query
    search_query = str()
        # 1st step : our categories
    if categories is not None:
        search_query += '%28'
        for cat in categories:
            search_query += 'cat:%s+OR+' % (cat)
            # 2nd step : our keywords (in title or abstract)
        search_query = search_query[:-4] + '%29'

    if keywords is not None:
        if len(search_query) > 0:
            search_query += '+AND+%28'
        else:
            search_query += '%28'
        for keyw in keywords:
            search_query += 'ti:%s+OR+' % urllib.parse.quote(keyw)
        search_query = search_query[:-4] + '%29+OR+%28'
        for keyw in keywords:
            search_query += 'abs:%s+OR+' % urllib.parse.quote(keyw)
        search_query = search_query[:-4] + '%29'

    if authors is not None:
        if len(search_query) > 0:
            search_query += '+AND+%28'
        else:
            search_query += '%28'
        for author in authors:
            search_query += 'au:%s+OR+' % urllib.parse.quote(author)

    search_query = search_query[:-4] + '%29'
        # 3rd step : when --> 1 week from 8pm to 8pm
    today = get_current_date()
    # yesterday = date.today() - timedelta(1)
    dby = today - timedelta(amount_of_days + 1)
    start_date = dby.strftime("%Y%m%d") + "0000"
    # Use yesterday as end date to avoid timezone issues with "today"
    yesterday = today - timedelta(1)
    end_date = yesterday.strftime("%Y%m%d") + "2000"
    # end_date = today.strftime("%Y%m%d") + "2000"
    
    # search_query += f'+lastUpdatedDate:[{start_date}+TO+{end_date}]'
    search_query += f'+AND+submittedDate:[{start_date}+TO+{end_date}]'
    
    # Define numbers of results we want to show
    min_results = 0
    max_results = max_results
    
    # Wrap up all that in the general query
    query = f'search_query={search_query}&start={min_results}&max_results={max_results}'
    logging.info(f"Generated query: {base_url+query}")
    logging.info(f"Date range: {start_date} to {end_date}")
    print(f"Date range: {start_date} to {end_date}")

    # Use namespaces from Opensearch and ArXiv in feedparser
    feedparser._FeedParserMixin.namespaces['http://a9.com/-/spec/opensearch/1.1/'] = 'opensearch'
    feedparser._FeedParserMixin.namespaces['http://arxiv.org/schemas/atom'] = 'arxiv'
    
    # Request
    try:
        response = urllib.request.urlopen(base_url+query).read()
    except Exception as e:
        logging.error(f"Error fetching arXiv results: {e}")
        return None
    
    # Produce the HTML content
    feed = feedparser.parse(response)

    # Add after feed parsing (around line 150)
    logging.info(f"Number of entries found: {len(feed.entries)}")
    if len(feed.entries) > 0:
        logging.info(f"First entry title: {feed.entries[0].title}")
    
    body = str()
    body += "<link href='https://fonts.googleapis.com/css?family=Montserrat' rel='stylesheet'>"
    
    # latex embedding

    # mathjax
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
    
    body += "<style> \
    body {font-family: 'Montserrat'; background: #F3F3F3; width: 740px; margin: 0 auto; line-height: 150%; margin-top: 50px; font-size: 15px} \
        h1 {font-size: 70px} \
        a {color: #45ABC2} \
        em {font-size: 120%} </style>"
    body += "<h1><center>ArXiv Alert</center></h1>"
    body += f"<font color='#DDAD5C'><em>Update: from {dby.strftime('%d %b %Y')} to {today.strftime('%d %b %Y')}</em></font>"

    new_papers_count = 0
    total_papers_count = len(feed.entries)
    filtered_papers_count = 0  # Count papers filtered due to excluded categories
    no_keywords_count = 0  # Count papers filtered due to no matching keywords

    for entry in feed.entries:
        arxiv_id = entry.id.split('/abs/')[-1]

        # Only new papers
        base_arxiv_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
        # # Skip if this paper was already processed
        if base_arxiv_id in processed_papers:
            continue

            # Get all categories for this paper
        all_categories = [t['term'] for t in entry.tags]
        
        # Check if paper has any excluded categories
        if excluded_categories:
            has_excluded_category = any(cat in all_categories for cat in excluded_categories)
            if has_excluded_category:
                filtered_papers_count += 1
                logging.info(f"Filtered out paper {arxiv_id} due to excluded categories: {[cat for cat in excluded_categories if cat in all_categories]}")
                continue
            
        matching_keywords = []
        if keywords is not None:
            matching_keywords = find_matching_keywords(entry.title, entry.summary, keywords)

            if not matching_keywords:
                no_keywords_count += 1
                logging.info(f"Filtered out paper {arxiv_id} due to no matching keywords")
                continue
        
        # Add to new processed papers
        new_processed_papers.add(base_arxiv_id)
        new_papers_count += 1

        pdf_link = ''
        for link in entry.links:
            if link.rel == 'alternate':
                continue
            elif link.title == 'pdf':
                pdf_link = link.href  # Pdf link in the title
        
        comments = get_paper_comments(arxiv_id)

        body += '<a href="%s" target="_blank"><h2>%s</h2></a>' % (pdf_link, entry.title)
    
        try:
            body += '<strong><u>Authors:</u></strong>  %s</br>' % ', '.join(author.name for author in entry.authors)
        except AttributeError:
            pass

        # Lets get all the categories
        all_categories = [t['term'] for t in entry.tags]
        body += '<strong><u>Categories:</u></strong> %s</br>' % (', ').join(all_categories)
        body += '<strong><u>Comments:</u></strong> %s</br>' % comments    
        
        # Add matching keywords
        body += '<strong><u>Matching Keywords:</u></strong> %s</br>' % ', '.join(matching_keywords)
        # if matching_keywords:
        #     body += '<strong><u>Matching Keywords:</u></strong> %s</br>' % ', '.join(matching_keywords)
        # else:
        #     body += '<strong><u>Matching Keywords:</u></strong> None found</br>'
    
        # The abstract is in the <summary> element
        body += '<p><strong><u>Abstract:</u></strong> %s</p>' %  entry.summary
        body += '</br>'
    
    # body = body.replace(
    #     f"<font color='#DDAD5C'><em>Update: from {dby.strftime('%d %b %Y')} to {today.strftime('%d %b %Y')}</em></font>",
    #     f"<font color='#DDAD5C'><em>Update: from {dby.strftime('%d %b %Y')} to {today.strftime('%d %b %Y')} ({new_papers_count} new papers out of {total_papers_count} total)</em></font>"
    # )
    
    body += "</body>"

    processed_papers.update(new_processed_papers)
    processed_papers = clean_old_processed_papers(processed_papers)
    save_processed_papers(processed_papers)
    
    # Log statistics
    logging.info(f"Found {total_papers_count} total papers, {new_papers_count} new papers")

    
    # Set path to be absolute for cron job
    output_dir = '/Users/nguerrav/Documents/arxiv/arxiv_htmls'
    os.makedirs(output_dir, exist_ok=True)
    
    my_path = os.path.join(output_dir, html_name + '.html')
    try:
        with open(my_path, 'w') as f:
            f.write(body)
        logging.info(f"Created HTML file: {my_path}")
        return my_path
    except Exception as e:
        logging.error(f"Error writing HTML file: {e}")
        return None

# Categories and keywords definitions
categories_astroph = ['astro-ph.co', 'astro-ph.ga', 'astro-ph.he'
                        ]
keywords_astroph = [
    'ALMA', #'"ALMA"', 
    'ALMACAL', #'"ALMACAL"', 
    'MUSE', 'MUSE-ALMA', #'"MUSE"', '"MUSE-ALMA"', 
    'JWST', #'"JWST"', 
    'James Webb Space Telescope', 
    '4MOST', 'DESI', 'Euclid', 'SDSS', #'"4MOST"', '"DESI"', '"Euclid"', '"SDSS"', 
    'galaxy evolution', 'galaxy formation', 'galactic chemical evolution', 'galaxy chemical evolution', 
    'galactic outlflows', 'galactic outlflow', 'outflows', 'outflow', 
    'dust', 'dust evolution', 'stellar mass function', 'quiescent galaxies', 'atomic hydrogen', 
    'baryon cycle', 'baryon budget', 'metal budget', 'baryon density', 'cosmic abundance', 'cosmic evolution', 'cosmic gas', 
    'atomic gas', 'molecular gas', 'interstellar dust', 'ISM', 'kinematics', 
    'quasar absorption lines', 'QSO absorption lines', 'QSO absorber', 'quasar absorber', 'MgII absorber', 'MgII absorbers', 
    'high z', 'high redshift', 
    'feedback', 'stellar feedback', 
    'AGN', 'AGN feedback', #'"AGN"', 
    'active galactic nuclei', 'QSO', #'"QSO"', 
    'quasar', 
    'BAL QSO', #'"BAL QSO"', 
    'broad absorption line quasar', 'broad absorption line QSO', 
    'AGN variability', 'active galactic nuclei variability', 'blazar variability', 'time-domain', 'time domain', 
    'CGM', #'"CGM"', 
    'circumgalactic medium', 'IGM', #'"IGM"', 
    'intergalactic medium', 'halo', 'haloes', 
    'damped lyman alpha system', 'DLA', #'"DLA"', 
    'lyman limit system', 'LLS'
]
excluded_astro_categories = ['astro-ph.EP', 'astro-ph.SR']


categories_ml = ['astro-ph.co', 'astro-ph.ga', 'astro-ph.he', 'astro-ph.im', 
                    "cs.ai",   # AI
                    "cs.gl",   # general literature
                    "cs.lg",   # machine learning
                    "stat.ml"  # machine learning
                    ]
keywords_ml = [
    'astroinformatics', 'astro-informatics', 'data-driven', 
    'variational autoencoder', 'VAE', #'"VAE"', 
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
    """Function to run the arXiv alert and send emails"""
    today = get_current_date()
    logging.info(f"Running arXiv alerts for {today}")
    
    # Generate the HTML files
    if today.weekday() == 0 or today.weekday() == 1:  # monday, tuesday
        # Use longer lookback period to ensure we find papers
        html_file_astro = arxiv_alert('astro/astro_arxiv_' + str(today), 3, categories_astroph, keywords_astroph, excluded_categories=excluded_astro_categories)
        html_file_ml = arxiv_alert('ml/ml_arxiv_' + str(today), 3, categories_ml, keywords_ml)
    else:
        # Use longer lookback period to ensure we find papers
        html_file_astro = arxiv_alert('astro/astro_arxiv_' + str(today), 2, categories_astroph, keywords_astroph, excluded_categories=excluded_astro_categories)
        html_file_ml = arxiv_alert('ml/ml_arxiv_' + str(today), 2, categories_ml, keywords_ml)
    
    logging.info(f"Daily task completed for {today}")

    if not test_simple_query():
        logging.error("Even simple query failed - API might be down")
        return

if __name__ == "__main__":

    run_daily_task()
