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
from bs4 import BeautifulSoup  # Added BeautifulSoup for parsing comments
import requests  # Added requests for fetching web pages
import smtplib  # Added for sending emails
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os  # For file operations
import schedule  # For scheduling daily runs
import time  # For sleep between schedule checks
# from webbrowser import open_new_tab

def send_email(file_path, recipient_emails, subject):
    """Send email with HTML file as attachment and content"""
    # Email server configuration
    smtp_server = "smtp.gmail.com"  # Change to your SMTP server
    smtp_port = 587  # Change if your SMTP server uses a different port
    sender_email = "nguerra@ug.uchile.cl"  # Change to your email
    password = "npio mzgm izsf glqc"
    
    # Read the HTML file
    with open(file_path, 'r') as file:
        html_content = file.read()
    
    # For each recipient
    for recipient in recipient_emails:
        # Create message container
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient
        
        # Create both plain text and HTML versions of the message
        text_part = MIMEText("ArXiv Alert - Please see the attached HTML file or view the HTML content in this email.")
        html_part = MIMEText(html_content, 'html')
        
        # Attach HTML file
        with open(file_path, 'rb') as file:
            attachment = MIMEApplication(file.read(), Name=os.path.basename(file_path))
            attachment['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        
        # Attach parts to the message
        msg.attach(text_part)
        msg.attach(html_part)
        msg.attach(attachment)
        
        # Send the message
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()  # Secure the connection
            server.login(sender_email, password)
            server.sendmail(sender_email, recipient, msg.as_string())
            server.quit()
            print(f"Email sent successfully to {recipient}")
        except Exception as e:
            print(f"Failed to send email to {recipient}: {e}")

def get_paper_comments(arxiv_id):
    """Fetch comments for a specific arXiv paper by accessing its abstract page"""
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
        return "Comments unavailable"

def arxiv_alert(html_name, amount_of_days, categories=None, keywords=None, authors=None, max_results=20):
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
    yesterday = date.today() - timedelta(1)
    dby = yesterday - timedelta(amount_of_days)
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
    body += f"<font color='#DDAD5C'><em>Update: from {dby.strftime('%d %b %Y')} to {yesterday.strftime('%d %b %Y')}</em></font>"
    
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
        
        # Get comments for this paper
        comments = get_paper_comments(arxiv_id)
        
        # Add target="_blank" attribute to make the link open in a new tab
        body += '<a href="%s" target="_blank"><h2>%s</h2></a>' % (pdf_link, entry.title)
    
        try:
            body += '<strong><u>Authors:</u></strong>  %s</br>' % ', '.join(author.name for author in entry.authors)
        except AttributeError:
            pass

        # Lets get all the categories
        all_categories = [t['term'] for t in entry.tags]
        body += '<strong><u>Categories:</u></strong> %s</br>' % (', ').join(all_categories)
        
        # Add comments section
        body += '<strong><u>Comments:</u></strong> %s</br>' % comments
    
        # The abstract is in the <summary> element
        body += '<p><strong><u>Abstract:</u></strong> %s</p>' %  entry.summary
        body += '</br>'
    body += "</body>"
        
    # Create the HTML file and open it in a new tab
    
    my_path = f'./' + html_name + '.html'
    f = open(my_path,'w')
    f.write(body)
    f.close()
    
    # Return the file path for email sending
    return my_path
    
    # filename = 'file://' + my_path
    # try:
    #     open_new_tab(filename)
    # except:
    #     ""
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

# List of email recipients
# recipients = ['nicolas.guerravaras@eso.org']

def run_daily_task():
    """Function to run the arXiv alert and send emails"""
    print(f"Running arXiv alerts for {date.today()}")

    today = date.today()
    # logging.info(f"Running arXiv alerts for {today}")
    
    if today.weekday() == 0 or today.weekday() == 1:  # monday, tuesday
        # Use longer lookback period to ensure we find papers
        html_file_astro = arxiv_alert('astro/astro_arxiv_' + str(today), 3, categories_astroph, keywords_astroph, excluded_categories=excluded_astro_categories)
        html_file_ml = arxiv_alert('ml/ml_arxiv_' + str(today), 3, categories_ml, keywords_ml)
    else:
        # Use longer lookback period to ensure we find papers
        # html_file_astro = arxiv_alert('astro/astro_arxiv_' + str(today), 2, categories_astroph, keywords_astroph, excluded_categories=excluded_astro_categories)
        html_file_ml = arxiv_alert('ml/ml_arxiv_' + str(today), 2, categories_ml, keywords_ml)
    
    # Generate the HTML files
    # html_file_astro = arxiv_alert('astro_arxiv_' + str(date.today()), 1, categories_astroph, keywords_astroph)
    # html_file_ml = arxiv_alert('ml_arxiv_' + str(date.today()), 1, categories_ml, keywords_ml)
    
    # Send emails with the generated HTML files
    # today = date.today().strftime('%Y-%m-%d')
    # send_email(html_file_astro, recipients, f"ArXiv Astrophysics Alert - {today}")
    # send_email(html_file_ml, recipients, f"ArXiv Machine Learning Alert - {today}")
    
    print(f"Daily task completed for {date.today()}")

# Schedule the task to run daily at 9:00 AM
schedule.every().day.at("09:00").do(run_daily_task)

if __name__ == "__main__":
    # Run once when the script is started
    run_daily_task()
    
    # Keep the script running and check for scheduled tasks
    # print("Script is running. Press Ctrl+C to stop.")
    # try:
    #     while True:
    #         schedule.run_pending()
    #         time.sleep(60)  # Check every minute
    # except KeyboardInterrupt:
    #     print("Script stopped manually.")