#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 23:48:36 2020

@author: m.goibert
"""

"""
Adapted from
http://arxiv.org/help/api/examples/python_arXiv_parsing_example.txt

with modifications by Alex Breitweiser

This is free software.  Feel free to do what you want
with it, but please play nice with the arXiv API!
"""

import urllib.request, urllib.parse, urllib.error
import feedparser
from datetime import date, timedelta
from webbrowser import open_new_tab

def arxiv_alert(categories=None, keywords=None, authors=None, max_results=20):
    # API query url for ArXiv
    base_url = 'http://export.arxiv.org/api/query?'
    
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
            search_query += 'ti:%s+OR+' %(keyw)
        search_query = search_query[:-4] + '%29+OR+%28'
        for keyw in keywords:
            search_query += 'abs:%s+OR+' %(keyw)
        search_query = search_query[:-4] + '%29'
    if authors is not None:
        if len(search_query) > 0:
            search_query += '+AND+%28'
        else:
            search_query += '%28'
        for author in authors:
            search_query += 'au:%s+OR+' % (author)
    search_query = search_query[:-4] + '%29'
        # 3rd step : when --> 1 week from 8pm to 8pm
    yesterday = date.today() - timedelta(1)
    dby = yesterday - timedelta(7)
    start_date = dby.strftime("%Y%m%d")+"2000"
    end_date = yesterday.strftime("%Y%m%d") + "2000"
    search_query += f'+lastUpdatedDate:[{start_date}+TO+{end_date}]'
    
    # Define numbers of results we want to show
    min_results = 0
    max_results = max_results
    
    # Wrap up all that in the general query
    query = f'search_query={search_query}&start={min_results}&max_results={max_results}'
    
    # Use namespaces from Opensearch and ArXiv in feedparser
    feedparser._FeedParserMixin.namespaces['http://a9.com/-/spec/opensearch/1.1/'] = 'opensearch'
    feedparser._FeedParserMixin.namespaces['http://arxiv.org/schemas/atom'] = 'arxiv'
    
    # Request
    response = urllib.request.urlopen(base_url+query).read()
    
    # Produce the HTML content
    feed = feedparser.parse(response)
    body = str()
    body += "<link href='https://fonts.googleapis.com/css?family=Montserrat' rel='stylesheet'>"
    body += "<style> \
    body {font-family: 'Montserrat'; background: #F3F3F3; width: 740px; margin: 0 auto; line-height: 150%; margin-top: 50px; font-size: 15px} \
        h1 {font-size: 70px} \
        a {color: #45ABC2} \
        em {font-size: 120%} </style>"
    body += "<h1><center>ArXiv Alert</center></h1>"
    body += f"<font color='#DDAD5C'><em>Week update: from {dby.strftime('%d %b %Y')} to {yesterday.strftime('%d %b %Y')}</em></font>"
    
    for entry in feed.entries:
        arxiv_id = entry.id.split('/abs/')[-1]
        if arxiv_id[-2:] != 'v1':
            continue # Only new papers
        pdf_link = ''
        for link in entry.links:
            if link.rel == 'alternate':
                continue
            elif link.title == 'pdf':
                pdf_link = link.href # Pdf link in the title
        body += '<a href="%s"><h2>%s</h2></a>' % (pdf_link, entry.title)
    
        try:
            body += '<strong><u>Authors:</u></strong>  %s</br>' % ', '.join(author.name for author in entry.authors)
        except AttributeError:
            pass

        # Lets get all the categories
        all_categories = [t['term'] for t in entry.tags]
        body += '<strong><u>Categories:</u></strong> %s</br>' % (', ').join(all_categories)
    
        # The abstract is in the <summary> element
        body += '<p><strong><u>Abstract:</u></strong> %s</p>' %  entry.summary
        body += '</br>'
    body += "</body>"
        
    # Create the HTML file and open it in a new tab
    
    my_path = f'./arxiv_test.html'
    f = open(my_path,'w')
    f.write(body)
    f.close()
    
    filename = 'file://' + my_path
    try:
        open_new_tab(filename)
    except:
        ""

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
arxiv_alert(categories_astroph, keywords_astroph)
