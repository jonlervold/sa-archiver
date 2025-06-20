#!/usr/bin/env python3
# app.py - Web frontend for SA Thread Archiver

import os
import re
import subprocess
import threading
import json
import glob
import html
import requests
import hashlib
from urllib.parse import urljoin, urlparse
from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

app = Flask(__name__)

# Store running jobs
running_jobs = {}

def fix_unicode_encoding(text):
    """Fix common Unicode encoding issues that occur during HTML->JSON conversion."""
    if not text:
        return text
    
    # Simple replacements for specific characters - handle both UTF-8 and encoded forms
    replacements = {
        # UTF-8 smart quotes and apostrophes
        "'": "'",    # Smart single quote (right)
        "'": "'",    # Smart single quote (left)  
        """: '"',    # Smart double quote open
        """: '"',    # Smart double quote close
        "′": "'",    # Prime (often used as apostrophe)
        "″": '"',    # Double prime (often used as quotes)
        # UTF-8 ellipsis and dots
        "…": '...',  # Ellipsis to three dots
        # UTF-8 dashes
        "—": "-",    # Em dash
        "–": "-",    # En dash
        "−": "-",    # Minus sign
        # UTF-8 spaces
        " ": " ",    # Non-breaking space
        " ": " ",    # En quad
        " ": " ",    # Em quad
        " ": " ",    # Thin space
        # CP1252/Latin1 encoded forms (common in web scraping) - using hex escapes to avoid syntax issues
        '\xe2\x80\x99': "'",  # Right single quotation mark (â€™)
        '\xe2\x80\x98': "'",  # Left single quotation mark (â€˜)
        '\xe2\x80\x9c': '"',  # Left double quotation mark (â€œ)
        '\xe2\x80\x9d': '"',  # Right double quotation mark (â€)
        '\xe2\x80\xa6': '...',  # Horizontal ellipsis (â€¦)
        '\xe2\x80\x94': '-',  # Em dash (â€")
        '\xe2\x80\x93': '-',  # En dash (â€")
        '\xe2\x80\xb3': '"',  # Double prime (â€³)
        '\xe2\x80\xb2': "'",  # Prime (â€²)
        '\xc2\xa0': ' ',     # Non-breaking space (Â )
        '\xc2': '',          # Isolated Latin supplement prefix
        # Windows-1252 encoded forms
        '\x82': "'",  # Single low-9 quotation mark
        '\x84': '"',  # Double low-9 quotation mark
        '\x85': '...',  # Horizontal ellipsis
        '\x87': '++', # Double dagger (convert to plus)
        '\x88': '^',  # Modifier letter circumflex accent
        '\x89': '%',  # Per mille sign
        '\x8B': '<',  # Single left-pointing angle quotation mark
        '\x8C': 'OE', # Latin capital ligature OE
        '\x8D': '',   # Reverse line feed (remove)
        '\x8E': 'Z',  # Latin capital letter Z with caron
        '\x8F': '',   # Single shift three (remove)
        '\x90': '',   # Device control string (remove)
        '\x91': "'",  # Left single quotation mark
        '\x92': "'",  # Right single quotation mark
        '\x93': '"',  # Left double quotation mark
        '\x94': '"',  # Right double quotation mark
        '\x95': '*',  # Bullet (convert to asterisk)
        '\x96': '-',  # En dash
        '\x97': '-',  # Em dash
        '\x98': '~',  # Small tilde
        '\x99': '(TM)', # Trade mark sign
        '\x9A': 's',  # Latin small letter s with caron
        '\x9B': '>',  # Single right-pointing angle quotation mark
        '\x9C': 'oe', # Latin small ligature oe
        '\x9D': '',   # Operating system command (remove)
        '\x9E': 'z',  # Latin small letter z with caron
        '\x9F': 'Y',  # Latin capital letter Y with diaeresis
        '\xa0': ' ',  # Non-breaking space
        '\xa1': '!',  # Inverted exclamation mark
        '\xa2': 'cent', # Cent sign
        '\xa3': 'GBP', # Pound sign
        '\xa4': '$',  # Generic currency symbol
        '\xa5': 'JPY', # Yen sign
        '\xa6': '|',  # Broken bar
        '\xa7': 'S',  # Section sign
        '\xa8': '"',  # Diaeresis
        '\xa9': '(C)', # Copyright sign
        '\xaa': 'a',  # Feminine ordinal indicator
        '\xab': '<<', # Left-pointing double angle quotation mark
        '\xac': 'NOT', # Not sign
        '\xad': '-',  # Soft hyphen
        '\xae': '(R)', # Registered sign
        '\xaf': '-',  # Macron
        '\xb0': 'deg', # Degree sign
        '\xb1': '+-', # Plus-minus sign
        '\xb2': '2',  # Superscript two
        '\xb3': '3',  # Superscript three
        '\xb4': "'",  # Acute accent
        '\xb5': 'u',  # Micro sign
        '\xb6': 'P',  # Pilcrow sign
        '\xb7': '*',  # Middle dot
        '\xb8': ',',  # Cedilla
        '\xb9': '1',  # Superscript one
        '\xba': 'o',  # Masculine ordinal indicator
        '\xbb': '>>', # Right-pointing double angle quotation mark
        '\xbc': '1/4', # Vulgar fraction one quarter
        '\xbd': '1/2', # Vulgar fraction one half
        '\xbe': '3/4', # Vulgar fraction three quarters
        '\xbf': '?',  # Inverted question mark
    }
    
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    
    return text

def extract_posts_from_html(html_file_path):
    """Extract all posts from a single HTML page."""
    import re  # Move import to top
    
    # Try different encodings to handle various file formats
    encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
    html_content = None
    used_encoding = None
    
    for encoding in encodings:
        try:
            with open(html_file_path, 'r', encoding=encoding) as file:
                html_content = file.read()
                used_encoding = encoding
                break
        except UnicodeDecodeError:
            continue
    
    if html_content is None:
        print(f"  -> Could not decode {html_file_path}")
        return []
    
    print(f"  -> Decoded {html_file_path} using {used_encoding}")
    
    # Apply Unicode fixes to the entire HTML content early
    html_content = fix_unicode_encoding(html_content)
    
    soup = BeautifulSoup(html_content, 'html.parser', from_encoding='utf-8')
    posts = []
    
    # Find all td elements with class 'postbody' that contain google ad markers
    postbody_elements = soup.find_all('td', class_='postbody')
    print(f"  -> Found {len(postbody_elements)} postbody elements")
    
    for postbody in postbody_elements:
        try:
            # Check if this postbody contains ad markers
            postbody_html = str(postbody)
            if 'google_ad_section_start' not in postbody_html or 'google_ad_section_end' not in postbody_html:
                continue
            
            # Extract content between the markers
            start_marker = '<!-- google_ad_section_start -->'
            end_marker = '<!-- google_ad_section_end -->'
            
            start_idx = postbody_html.find(start_marker)
            end_idx = postbody_html.find(end_marker, start_idx)
            
            if start_idx == -1 or end_idx == -1:
                continue
            
            post_content_html = postbody_html[start_idx + len(start_marker):end_idx].strip()
            
            if not post_content_html:
                continue
            
            # Fix Unicode encoding issues
            post_content_html = fix_unicode_encoding(post_content_html)
            
            # Find the author element
            author_elem = None
            table_row = postbody.find_parent('tr')
            if table_row:
                author_elem = table_row.find('dt', class_=re.compile(r'author'))
            
            if not author_elem:
                table = postbody.find_parent('table')
                if table:
                    author_elem = table.find('dt', class_=re.compile(r'author'))
            
            if not author_elem:
                continue
                
            # Extract username
            username = author_elem.get_text().strip()
            
            # Find datetime - simple approach with error handling
            post_datetime = None
            
            try:
                table = postbody.find_parent('table')
                if table:
                    postdate_elem = table.find('td', class_='postdate')
                    if postdate_elem:
                        # Get all the text content and strip whitespace/newlines
                        postdate_text = postdate_elem.get_text().strip()
                        
                        # Split by lines and get the last non-empty line (should be the date)
                        lines = [line.strip() for line in postdate_text.split('\n') if line.strip()]
                        if lines:
                            # The date is typically the last line in the postdate element
                            potential_date = lines[-1]
                            # Simple check: does it look like a date?
                            if re.search(r'\w{3}\s+\d+.*\d{4}', potential_date):
                                post_datetime = potential_date
                        
                        # If that didn't work, try extracting text after the last </a> tag more carefully
                        if not post_datetime:
                            postdate_html = str(postdate_elem)
                            # Find the position of the last </a> tag
                            last_a_pos = postdate_html.rfind('</a>')
                            if last_a_pos != -1:
                                # Get everything after the last </a> tag until </td>
                                after_links = postdate_html[last_a_pos + 4:]  # +4 for length of '</a>'
                                # Extract text, removing HTML tags
                                clean_text = re.sub(r'<[^>]+>', '', after_links).strip()
                                if clean_text and re.search(r'\w{3}\s+\d+.*\d{4}', clean_text):
                                    post_datetime = clean_text
            except Exception as e:
                # If date parsing fails, continue with null date rather than skipping the post
                post_datetime = None
            
            # Create post data (even if date parsing failed)
            post_data = {
                'username': fix_unicode_encoding(username),
                'datetime': fix_unicode_encoding(post_datetime) if post_datetime else post_datetime,
                'content': post_content_html
            }
            posts.append(post_data)
                
        except Exception as e:
            print(f"  -> Error processing post: {e}")
            continue
    
    print(f"  -> Extracted {len(posts)} posts")
    return posts

def run_json_transformation(job_id, input_folder, output_folder):
    """Run JSON transformation in a separate thread"""
    try:
        running_jobs[job_id]['status'] = 'running'
        running_jobs[job_id]['progress'] = f"Starting JSON transformation..."
        
        input_path = os.path.join('/app/output', input_folder)
        output_path = os.path.join('/app/output', output_folder)
        
        if not os.path.exists(input_path):
            running_jobs[job_id]['status'] = 'error'
            running_jobs[job_id]['progress'] = f"Input folder '{input_folder}' not found"
            return
        
        # Create output directory
        os.makedirs(output_path, exist_ok=True)
        
        # Find all HTML files
        html_pattern = os.path.join(input_path, "**/*.html")
        html_files = glob.glob(html_pattern, recursive=True)
        
        if not html_files:
            running_jobs[job_id]['status'] = 'error'
            running_jobs[job_id]['progress'] = f"No HTML files found in '{input_folder}'"
            return
        
        total_files = len(html_files)
        processed_files = 0
        
        running_jobs[job_id]['progress'] = f"Processing {total_files} HTML files..."
        
        for html_file in html_files:
            if running_jobs[job_id]['status'] == 'cancelled':
                break
                
            try:
                # Extract posts from this HTML file
                posts = extract_posts_from_html(html_file)
                
                if posts:
                    # Generate output filename based on page number
                    html_filename = Path(html_file).name
                    
                    # Extract page number from filename (e.g., pagenumber=25)
                    page_match = re.search(r'pagenumber=(\d+)', html_filename)
                    if page_match:
                        page_number = page_match.group(1)
                        json_filename = f"{page_number}.json"
                    else:
                        # Fallback: try to find any number in the filename
                        number_match = re.search(r'(\d+)', html_filename)
                        if number_match:
                            json_filename = f"{number_match.group(1)}.json"
                        else:
                            # Last resort: use original filename
                            json_filename = html_filename.replace('.html', '.json')
                    
                    json_output_path = os.path.join(output_path, json_filename)
                    
                    # Create page data structure
                    page_data = {
                        'source_file': html_filename,
                        'total_posts': len(posts),
                        'posts': posts
                    }
                    
                    # Write JSON file
                    with open(json_output_path, 'w', encoding='utf-8') as json_file:
                        json.dump(page_data, json_file, indent=2, ensure_ascii=False)
                
                processed_files += 1
                running_jobs[job_id]['progress'] = f"Processed {processed_files}/{total_files} files"
                
            except Exception as e:
                continue
        
        if running_jobs[job_id]['status'] != 'cancelled':
            running_jobs[job_id]['status'] = 'completed'
            running_jobs[job_id]['progress'] = f"JSON transformation complete. Output saved to: {output_folder}"
            
    except Exception as e:
        running_jobs[job_id]['status'] = 'error'
        running_jobs[job_id]['progress'] = f"Error: {str(e)}"

def extract_images_from_sa_page(page_url, cookie_header, output_path, job_id, page_num, downloaded_urls=None):
    """
    Custom image extractor for SomethingAwful forum pages.
    Downloads all images found in posts and saves them with descriptive filenames.
    Uses downloaded_urls set to avoid duplicates across pages.
    """
    images_downloaded = 0
    errors = []
    duplicates_skipped = 0
    
    if downloaded_urls is None:
        downloaded_urls = set()
    
    try:
        # Setup session with authentication
        session = requests.Session()
        session.headers.update({
            'Cookie': cookie_header,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        print(f"Fetching page: {page_url}")
        response = session.get(page_url, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Create single images directory for all images
        images_dir = os.path.join(output_path, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        # Find all images in posts
        image_urls = set()  # Use set to avoid duplicates
        
        # Look for images in post content
        postbody_elements = soup.find_all('td', class_='postbody')
        for postbody in postbody_elements:
            # Find all img tags
            for img in postbody.find_all('img'):
                src = img.get('src')
                if src:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(page_url, src)
                    image_urls.add(absolute_url)
            
            # Also look for linked images (a tags with image hrefs)
            for link in postbody.find_all('a'):
                href = link.get('href')
                if href and any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                    absolute_url = urljoin(page_url, href)
                    image_urls.add(absolute_url)
        
        # Also find attachment images
        for attachment in soup.find_all('a', href=re.compile(r'attachment\.php')):
            href = attachment.get('href')
            if href:
                absolute_url = urljoin(page_url, href)
                image_urls.add(absolute_url)
        
        # Look for images in signatures and avatars too
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and ('avatar' in src.lower() or 'signature' in src.lower() or any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'])):
                absolute_url = urljoin(page_url, src)
                image_urls.add(absolute_url)
        
        # Filter out common non-content images (like smilies, icons, etc.)
        filtered_urls = set()
        for url in image_urls:
            # Skip common forum system images
            if any(skip in url.lower() for skip in ['smilies', 'icons', 'buttons', 'spacer.gif', 'clear.gif', 'transparent.gif']):
                continue
            # Skip very small images (likely icons)
            if any(size in url.lower() for size in ['16x16', '20x20', '24x24', '32x32']):
                continue
            filtered_urls.add(url)
        
        image_urls = filtered_urls
        
        print(f"Found {len(image_urls)} unique images on page {page_num}")
        
        # Download each image
        for i, img_url in enumerate(image_urls):
            try:
                # Check if we've already downloaded this image
                if img_url in downloaded_urls:
                    print(f"Skipping duplicate image {i+1}/{len(image_urls)}: {img_url}")
                    duplicates_skipped += 1
                    continue
                    
                print(f"Downloading image {i+1}/{len(image_urls)}: {img_url}")
                
                # Download image
                img_response = session.get(img_url, timeout=30, stream=True)
                img_response.raise_for_status()
                
                # Determine file extension from URL or Content-Type
                parsed_url = urlparse(img_url)
                original_filename = os.path.basename(parsed_url.path)
                
                # Handle attachment.php URLs specially
                if 'attachment.php' in img_url:
                    # Try to get filename from Content-Disposition header
                    cd_header = img_response.headers.get('Content-Disposition', '')
                    if 'filename=' in cd_header:
                        try:
                            filename_part = cd_header.split('filename=')[1].strip('"\'')
                            if filename_part:
                                original_filename = filename_part
                        except:
                            pass
                
                if not original_filename or '.' not in original_filename:
                    # Try to determine extension from Content-Type
                    content_type = img_response.headers.get('Content-Type', '')
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        ext = '.jpg'
                    elif 'png' in content_type:
                        ext = '.png'
                    elif 'gif' in content_type:
                        ext = '.gif'
                    elif 'webp' in content_type:
                        ext = '.webp'
                    elif 'bmp' in content_type:
                        ext = '.bmp'
                    else:
                        ext = '.jpg'  # Default
                    
                    # Create filename from URL hash
                    url_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
                    if 'attachment.php' in img_url:
                        original_filename = f"attachment_{url_hash}{ext}"
                    elif 'avatar' in img_url.lower():
                        original_filename = f"avatar_{url_hash}{ext}"
                    else:
                        original_filename = f"image_{url_hash}{ext}"
                
                # Clean filename
                safe_filename = re.sub(r'[^\w\-_\.]', '_', original_filename)
                if not safe_filename:
                    safe_filename = f"image_{hashlib.md5(img_url.encode()).hexdigest()[:8]}.jpg"
                
                # Try original filename first, add hash only if file already exists
                final_filename = safe_filename
                file_path = os.path.join(images_dir, final_filename)
                
                # Handle filename collisions (different URLs, same filename)
                if os.path.exists(file_path):
                    name_part, ext_part = os.path.splitext(safe_filename)
                    url_hash = hashlib.md5(img_url.encode()).hexdigest()[:6]
                    final_filename = f"{name_part}_{url_hash}{ext_part}"
                    file_path = os.path.join(images_dir, final_filename)
                
                # Skip if file already exists
                if os.path.exists(file_path):
                    print(f"File already exists: {final_filename}")
                    continue
                
                # Save image
                with open(file_path, 'wb') as f:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Mark URL as downloaded
                downloaded_urls.add(img_url)
                images_downloaded += 1
                print(f"Saved: {final_filename}")
                
                # Update progress periodically
                if images_downloaded % 5 == 0:
                    running_jobs[job_id]['progress'] = f"Page {page_num}: Downloaded {images_downloaded} images..."
                
            except Exception as e:
                error_msg = f"Failed to download {img_url}: {str(e)}"
                print(error_msg)
                errors.append(error_msg)
                continue
        
        # Append to overall summary file
        summary_file = os.path.join(images_dir, '_download_summary.txt')
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"Page {page_num} Image Download Summary\n")
            f.write(f"{'='*50}\n")
            f.write(f"Source URL: {page_url}\n")
            f.write(f"Total images found: {len(image_urls)}\n")
            f.write(f"Successfully downloaded: {images_downloaded}\n")
            f.write(f"Duplicates skipped: {duplicates_skipped}\n")
            f.write(f"Errors: {len(errors)}\n")
            if errors:
                f.write("\nErrors encountered:\n")
                for error in errors:
                    f.write(f"- {error}\n")
            f.write(f"\nImage URLs found:\n")
            for url in sorted(image_urls):
                status = "DOWNLOADED" if url in downloaded_urls else "SKIPPED/ERROR"
                f.write(f"- {status}: {url}\n")
            f.write(f"\n")
        
        return images_downloaded, errors, duplicates_skipped
        
    except Exception as e:
        error_msg = f"Failed to process page {page_num}: {str(e)}"
        print(error_msg)
        return 0, [error_msg], 0

def run_archiver(job_id, base_url, start_page, end_page, folder, download_mode, bbuserid, bbpassword):
    """Run the archiver in a separate thread"""
    try:
        # Remove pagenumber from base URL if present
        base_no_page = re.sub(r'([&?])pagenumber=[^&]*', '', base_url)
        
        # Create output directory if it doesn't exist
        output_path = os.path.join('/app/output', folder)
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        cookie_header = f"bbuserid={bbuserid}; bbpassword={bbpassword}"
        
        running_jobs[job_id]['status'] = 'running'
        running_jobs[job_id]['progress'] = f"Starting download..."

        # Initialize summary file and duplicate tracking for images mode
        downloaded_urls = set()  # Track URLs across all pages to avoid duplicates
        if download_mode == "2" or download_mode == "images":
            images_dir = os.path.join(output_path, 'images')
            os.makedirs(images_dir, exist_ok=True)
            summary_file = os.path.join(images_dir, '_download_summary.txt')
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"SA Thread Image Download Summary\n")
                f.write(f"================================\n")
                f.write(f"Base URL: {base_no_page}\n")
                f.write(f"Pages to process: {start_page} to {end_page}\n")
                f.write(f"Output folder: {folder}\n")
                f.write(f"All images will be saved to: /images/ folder\n")
                f.write(f"Duplicate images will be skipped automatically\n")
                f.write(f"Download started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        for page in range(int(start_page), int(end_page) + 1):
            if running_jobs[job_id]['status'] == 'cancelled':
                break
                
            page_url = f"{base_no_page}&pagenumber={page}"
            running_jobs[job_id]['progress'] = f"Downloading page {page} of {end_page}"

            if download_mode == "2" or download_mode == "images":
                # Images only mode using custom SA image extractor
                try:
                    running_jobs[job_id]['progress'] = f"Extracting images from page {page}..."
                    
                    # Use custom image extractor
                    images_downloaded, errors, duplicates_skipped = extract_images_from_sa_page(
                        page_url, cookie_header, output_path, job_id, page, downloaded_urls
                    )
                    
                    # Count total images downloaded so far
                    total_images = 0
                    if os.path.exists(output_path):
                        for root, dirs, files in os.walk(output_path):
                            total_images += len([f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))])
                    
                    if images_downloaded > 0:
                        running_jobs[job_id]['progress'] = f"Page {page} completed - {images_downloaded} images downloaded, {duplicates_skipped} duplicates skipped ({total_images} total)"
                    elif duplicates_skipped > 0:
                        running_jobs[job_id]['progress'] = f"Page {page} completed - No new images, {duplicates_skipped} duplicates skipped"
                    else:
                        running_jobs[job_id]['progress'] = f"Page {page} completed - No images found"
                    
                    if errors:
                        print(f"Errors on page {page}: {len(errors)} errors occurred")
                        for error in errors[:3]:  # Show first 3 errors
                            print(f"  - {error}")
                        if len(errors) > 3:
                            print(f"  ... and {len(errors) - 3} more errors")
                    
                except Exception as e:
                    print(f"Custom image extractor exception for page {page}: {e}")
                    running_jobs[job_id]['progress'] = f"Error on page {page}: {str(e)}"
            else:
                # Full page mode using wget with centralized directory structure
                wget_args = [
                    "wget",
                    "--no-clobber",
                    "--page-requisites",
                    "--convert-links",
                    "--adjust-extension",
                    "--span-hosts",
                    "--no-parent",
                    "--no-host-directories",
                    "--cut-dirs=1",
                    f"--directory-prefix={output_path}",
                    f"--header=Cookie: {cookie_header}",
                    page_url
                ]
                
                result = subprocess.run(wget_args, capture_output=True, text=True)

        if running_jobs[job_id]['status'] != 'cancelled':
            if download_mode == "2" or download_mode == "images":
                # Count total images downloaded
                images_dir = os.path.join(output_path, 'images')
                total_images = 0
                if os.path.exists(images_dir):
                    image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))]
                    total_images = len(image_files)
                
                # Add final summary to the existing summary file
                summary_file = os.path.join(images_dir, '_download_summary.txt')
                with open(summary_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"FINAL SUMMARY\n")
                    f.write(f"{'='*60}\n")
                    f.write(f"Base URL: {base_no_page}\n")
                    f.write(f"Pages processed: {start_page} to {end_page}\n")
                    f.write(f"Total unique images downloaded: {total_images}\n")
                    f.write(f"Total unique URLs processed: {len(downloaded_urls)}\n")
                    f.write(f"Output folder: {folder}\n")
                    f.write(f"All images saved to: /images/ folder\n")
                    f.write(f"Duplicates automatically avoided\n")
                    f.write(f"Download completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                running_jobs[job_id]['status'] = 'completed'
                running_jobs[job_id]['progress'] = f"Image download complete! {total_images} images saved to: {folder}/images/"
            else:
                running_jobs[job_id]['status'] = 'completed'
                running_jobs[job_id]['progress'] = f"Download complete. Files saved to: {folder}"
            
    except Exception as e:
        running_jobs[job_id]['status'] = 'error'
        running_jobs[job_id]['progress'] = f"Error: {str(e)}"

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/archive')
def archive():
    return render_template('archive.html')

@app.route('/json')
def json_page():
    # Get list of available folders in output directory
    output_dir = '/app/output'
    folders = []
    if os.path.exists(output_dir):
        folders = [f for f in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, f))]
    return render_template('json_transform.html', folders=folders)

@app.route('/standalone')
def standalone():
    # Get list of thread folders that have JSON data
    thread_folders = []
    if os.path.exists('/app/output'):
        for folder in sorted(os.listdir('/app/output')):
            folder_path = os.path.join('/app/output', folder)
            json_path = os.path.join(folder_path, 'json')
            if os.path.isdir(folder_path) and os.path.exists(json_path):
                # Check if there are any JSON files
                json_files = [f for f in os.listdir(json_path) if f.endswith('.json') and f[:-5].isdigit()]
                if json_files:
                    thread_folders.append(folder)
    
    return render_template('standalone.html', thread_folders=thread_folders)

@app.route('/gallery')
def gallery():
    # Get list of folders that have images
    image_folders = []
    if os.path.exists('/app/output'):
        for folder in sorted(os.listdir('/app/output')):
            folder_path = os.path.join('/app/output', folder)
            images_path = os.path.join(folder_path, 'images')
            if os.path.isdir(folder_path) and os.path.exists(images_path):
                # Check if there are any image files
                image_files = [f for f in os.listdir(images_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')) and not f.startswith('_')]
                if image_files:
                    image_folders.append(folder)
    
    return render_template('gallery.html', image_folders=image_folders)

@app.route('/convert_to_gallery', methods=['POST'])
def convert_to_gallery():
    try:
        folder_name = request.form.get('folder_name')
        custom_title = request.form.get('custom_title', '').strip()
        
        if not folder_name:
            return jsonify({'error': 'No folder selected'}), 400
        
        # Check if the folder exists and has images
        thread_path = os.path.join('/app/output', folder_name)
        images_path = os.path.join(thread_path, 'images')
        
        if not os.path.exists(images_path):
            return jsonify({'error': f'Images folder not found for {folder_name}'}), 400
        
        # Use custom title if provided, otherwise derive from folder name
        if not custom_title:
            custom_title = Path(folder_name).name.replace('_', ' ').title()
        
        # Create a unique job ID
        job_id = f"gallery_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        running_jobs[job_id] = {
            'status': 'starting',
            'progress': 'Initializing image gallery conversion...'
        }
        
        # Start the conversion in a separate thread
        thread = threading.Thread(
            target=convert_images_to_gallery,
            args=(job_id, folder_name, custom_title)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'job_id': job_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/convert_standalone', methods=['POST'])
def convert_standalone():
    try:
        folder_name = request.form.get('folder_name')
        custom_title = request.form.get('custom_title', '').strip()
        
        if not folder_name:
            return jsonify({'error': 'No folder selected'}), 400
        
        # Check if the folder exists and has JSON data
        thread_path = os.path.join('/app/output', folder_name)
        json_path = os.path.join(thread_path, 'json')
        
        if not os.path.exists(json_path):
            return jsonify({'error': f'JSON folder not found for {folder_name}'}), 400
        
        # Use custom title if provided, otherwise derive from folder name
        if not custom_title:
            custom_title = Path(folder_name).name.replace('_', ' ').title()
        
        # Create a unique job ID
        job_id = f"standalone_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        running_jobs[job_id] = {
            'status': 'starting',
            'progress': 'Initializing standalone HTML conversion...'
        }
        
        # Start the conversion in a separate thread
        thread = threading.Thread(
            target=convert_thread_to_standalone_html,
            args=(job_id, folder_name, custom_title)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'job_id': job_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/start_archiving', methods=['POST'])
def start_archiving():
    try:
        # Debug: Log all form data received
        print("=== DEBUG: Form data received ===")
        print(f"request.form: {dict(request.form)}")
        print(f"request.files: {dict(request.files)}")
        print(f"request.data: {request.data}")
        print(f"request.content_type: {request.content_type}")
        for key, value in request.form.items():
            print(f"{key}: {value}")
        print("=== END DEBUG ===")
        
        url = request.form.get('base_url')
        start_page = request.form.get('start_page', '1')
        end_page = request.form.get('end_page', '1')
        folder_name = request.form.get('folder')
        mode = request.form.get('download_mode', '1')
        username = request.form.get('bbuserid')
        password = request.form.get('bbpassword')
        
        print(f"Parsed values: url={url}, folder_name={folder_name}, username={username}, password={'***' if password else None}")
        
        if not all([url, folder_name, username, password]):
            missing_fields = []
            if not url: missing_fields.append('base_url')
            if not folder_name: missing_fields.append('folder')
            if not username: missing_fields.append('bbuserid')
            if not password: missing_fields.append('bbpassword')
            print(f"MISSING FIELDS ERROR: {missing_fields}")
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Create a unique job ID
        job_id = f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        running_jobs[job_id] = {
            'status': 'starting',
            'progress': 'Initializing...'
        }
        
        # Start the archiving process in a separate thread
        thread = threading.Thread(
            target=run_archiver,
            args=(job_id, url, start_page, end_page, folder_name, mode, username, password)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'job_id': job_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/start_json_transform', methods=['POST'])
def start_json_transform():
    try:
        input_folder = request.form.get('input_folder')
        
        if not input_folder:
            return jsonify({'error': 'Input folder is required'}), 400
        
        # Create a unique job ID
        job_id = f"json_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        running_jobs[job_id] = {
            'status': 'starting',
            'progress': 'Initializing JSON transformation...'
        }
        
        # Start the JSON conversion in a separate thread  
        thread = threading.Thread(
            target=convert_html_to_json,
            args=(job_id, input_folder)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'job_id': job_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/convert_json', methods=['POST'])
def convert_json():
    try:
        folder_name = request.form.get('folder_name')
        
        if not folder_name:
            return jsonify({'error': 'Folder name is required'}), 400
        
        # Create a unique job ID
        job_id = f"json_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        running_jobs[job_id] = {
            'status': 'starting',
            'progress': 'Initializing JSON conversion...'
        }
        
        # Start the JSON conversion in a separate thread  
        thread = threading.Thread(
            target=convert_html_to_json,
            args=(job_id, folder_name)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'job_id': job_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<job_id>')
def status(job_id):
    if job_id in running_jobs:
        return jsonify(running_jobs[job_id])
    else:
        return jsonify({'status': 'not_found'}), 404

@app.route('/job_status/<job_id>')
def job_status(job_id):
    if job_id in running_jobs:
        return jsonify(running_jobs[job_id])
    else:
        return jsonify({'status': 'not_found'}), 404

@app.route('/cancel_job/<job_id>', methods=['POST'])
def cancel_job(job_id):
    if job_id in running_jobs:
        running_jobs[job_id]['status'] = 'cancelled'
        return jsonify({'message': 'Job cancelled'})
    else:
        return jsonify({'error': 'Job not found'}), 404

@app.route('/jobs')
def jobs():
    return jsonify(running_jobs)

def get_page_numbers(json_folder):
    """Get list of available page numbers from JSON files."""
    json_files = glob.glob(os.path.join(json_folder, "*.json"))
    page_numbers = []
    
    for json_file in json_files:
        filename = Path(json_file).stem
        if filename.isdigit():
            page_numbers.append(int(filename))
    
    return sorted(page_numbers)

def generate_css():
    """Generate CSS for the HTML pages."""
    return """
/* SA Thread Archive Styles */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: Verdana, Arial, sans-serif;
    font-size: 16px;
    background-color: #2E2E2E;
    color: #FFFFFF;
    line-height: 1.4;
    margin: 0;
    padding: 20px;
}

.container {
    max-width: 1000px;
    margin: 0 auto;
    background-color: transparent;
}

.header-container {
    background-color: #404040;
    margin-bottom: 25px;
    border-radius: 5px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    border: 1px solid #555;
}

.thread-header {
    background: linear-gradient(to bottom, #5C7A96, #4A6480);
    padding: 15px 20px;
    border-bottom: 1px solid #666;
    text-align: center;
}

.thread-title {
    font-size: 24px;
    font-weight: bold;
    color: #FFFFFF;
    margin-bottom: 5px;
}

.thread-info {
    font-size: 14px;
    color: #CCCCCC;
}

.pagination {
    background-color: #4A6480;
    padding: 10px 20px;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 15px;
}

.pagination.bottom {
    border-top: 1px solid #666;
}

.footer-container {
    background-color: #404040;
    margin-top: 25px;
    border-radius: 5px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    border: 1px solid #555;
}

.pagination a {
    color: #FFFFFF;
    text-decoration: none;
    padding: 8px 12px;
    background-color: #5C7A96;
    border: 1px solid #7A98B6;
    border-radius: 3px;
    display: inline-block;
    font-weight: bold;
}

.pagination a:hover {
    background-color: #6A86A2;
}

.pagination .nav {
    background-color: #3A5470;
}

.page-dropdown {
    background-color: #5C7A96;
    color: #FFFFFF;
    border: 1px solid #7A98B6;
    border-radius: 3px;
    padding: 8px 12px;
    font-size: 14px;
    font-family: Verdana, Arial, sans-serif;
    cursor: pointer;
}

.page-dropdown:hover {
    background-color: #6A86A2;
}

.page-dropdown:focus {
    outline: none;
    border-color: #8AA6C2;
}

.posts {
    padding: 0;
    margin: 25px 0;
    background-color: #2E2E2E;
}

.post {
    background-color: #404040;
    margin-bottom: 25px;
    border-radius: 5px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    border: 1px solid #555;
}

.post:last-child {
    margin-bottom: 0;
}

.post-header {
    background: linear-gradient(to bottom, #5C7A96, #4A6480);
    padding: 8px 15px;
    border-bottom: 1px solid #666;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.post-author {
    font-weight: bold;
    color: #FFFFFF;
    font-size: 18px;
}

.post-date {
    color: #CCCCCC;
    font-size: 14px;
}

.post-content {
    padding: 15px 20px;
    background-color: #404040;
    color: #FFFFFF;
}

.post-content img {
    max-width: 100%;
    height: auto;
}

.post-content a {
    color: #8AA6C2;
}

.post-content a:visited {
    color: #9AAACC;
}

.post-content blockquote {
    background-color: #363636;
    border-left: 3px solid #5C7A96;
    padding: 10px 15px;
    margin: 10px 0;
}

.post-content pre, .post-content code {
    background-color: #2A2A2A;
    border: 1px solid #555;
    padding: 5px;
    font-family: 'Courier New', monospace;
    overflow-x: auto;
}

.post-content hr {
    border: none;
    border-top: 1px solid #666;
    margin: 15px 0;
}

/* Spoiler styling - click to toggle */
.spoiler-toggle {
    display: none;
}

.bbc-spoiler {
    background-color: #000000;
    color: #000000;
    padding: 2px 4px;
    border-radius: 2px;
    cursor: pointer;
    display: inline;
    transition: all 0.3s ease;
    position: relative;
}

.bbc-spoiler::before {
    content: "Click to reveal spoiler";
    position: absolute;
    top: -25px;
    left: 0;
    background-color: #666;
    color: #fff;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 12px;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s;
    z-index: 10;
}

.bbc-spoiler:hover::before {
    opacity: 1;
}

/* When checkbox is checked, reveal the spoiler */
.spoiler-toggle:checked + .bbc-spoiler {
    background-color: #4A4A4A;
    color: #FFFFFF;
    border: 1px solid #666;
    box-shadow: 0 0 3px rgba(255, 255, 255, 0.1);
}

.spoiler-toggle:checked + .bbc-spoiler::before {
    content: "Click to hide spoiler";
}

.footer {
    background-color: #363636;
    padding: 15px 20px;
    text-align: center;
    font-size: 12px;
    color: #AAAAAA;
    border-top: 1px solid #666;
}

.index-page {
    background-color: #404040;
    padding: 30px;
    text-align: center;
}

.index-title {
    font-size: 24px;
    margin-bottom: 20px;
    color: #FFFFFF;
}

.page-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    gap: 10px;
    max-width: 600px;
    margin: 0 auto 30px;
}

.page-link {
    display: block;
    padding: 10px;
    background-color: #5C7A96;
    color: #FFFFFF;
    text-decoration: none;
    border: 1px solid #7A98B6;
    border-radius: 5px;
    transition: background-color 0.2s;
}

.page-link:hover {
    background-color: #6A86A2;
}

@media (max-width: 768px) {
    body {
        padding: 10px;
        font-size: 18px;
    }
    
    .thread-title {
        font-size: 28px;
    }
    
    .thread-info {
        font-size: 16px;
    }
    
    .post-author {
        font-size: 20px;
    }
    
    .post-date {
        font-size: 16px;
    }
    
    .post-content {
        font-size: 18px;
        padding: 18px;
    }
    
    .post-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 5px;
        padding: 12px 18px;
    }
    
    .pagination {
        flex-direction: column;
        gap: 10px;
        padding: 15px 20px;
    }
    
    .pagination a {
        padding: 12px 16px;
        font-size: 16px;
    }
    
    .page-dropdown {
        width: 100%;
        max-width: 200px;
        font-size: 16px;
        padding: 12px 16px;
    }
    
    .index-title {
        font-size: 28px;
    }
    
    .footer {
        font-size: 14px;
        padding: 18px 20px;
    }
}

"""

def generate_pagination_html(current_page, all_pages):
    """Generate pagination HTML with dropdown."""
    pagination_html = []
    
    # Previous page link
    if current_page > min(all_pages):
        prev_page = current_page - 1
        pagination_html.append(f'<a href="{prev_page}.html" class="nav">← Previous</a>')
    
    # Page dropdown
    dropdown_html = '<select class="page-dropdown" onchange="window.location.href=this.value">'
    for page in all_pages:
        selected = 'selected' if page == current_page else ''
        dropdown_html += f'<option value="{page}.html" {selected}>Page {page}</option>'
    dropdown_html += '</select>'
    pagination_html.append(dropdown_html)
    
    # Next page link
    if current_page < max(all_pages):
        next_page = current_page + 1
        pagination_html.append(f'<a href="{next_page}.html" class="nav">Next →</a>')
    
    return '\n'.join(pagination_html)

def generate_page_html(page_data, current_page, all_pages, thread_title):
    """Generate HTML for a single page."""
    
    pagination = generate_pagination_html(current_page, all_pages)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{thread_title} - Page {current_page}</title>
    <link rel="stylesheet" href="thread-style.css">
</head>
<body>
    <div class="container">
        <div class="header-container">
            <header class="thread-header">
                <h1 class="thread-title">{thread_title}</h1>
                <div class="thread-info">
                    Page {current_page} of {max(all_pages)} • {page_data['total_posts']} posts • 
                    <a href="index.html" style="color: #CCCCCC;">Thread Index</a>
                </div>
            </header>
            
            <div class="pagination">
                {pagination}
            </div>
        </div>
        
        <div class="posts">"""
    
    for i, post in enumerate(page_data['posts'], 1):
        post_html = f"""
            <article class="post">
                <header class="post-header">
                    <div class="post-author">{post['username']}</div>
                    <div class="post-date">{post['datetime'] or 'Unknown Date'}</div>
                </header>
                <div class="post-content">
                    {post['content']}
                </div>
            </article>"""
        html += post_html
    
    html += f"""
        </div>
        
        <div class="footer-container">
            <div class="pagination bottom">
                {pagination}
            </div>
            
            <footer class="footer">
                Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • 
                SA Thread Archive
            </footer>
        </div>
    </div>
    
    <script>
        // Initialize spoiler toggle functionality
        document.addEventListener('DOMContentLoaded', function() {{
            const spoilers = document.querySelectorAll('.bbc-spoiler');
            let spoilerCounter = 0;
            
            spoilers.forEach(function(spoiler) {{
                // Create unique ID for each spoiler
                const spoilerId = 'spoiler-' + spoilerCounter++;
                
                // Create checkbox
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'spoiler-toggle';
                checkbox.id = spoilerId;
                
                // Insert checkbox before spoiler
                spoiler.parentNode.insertBefore(checkbox, spoiler);
                
                // Add click handler to spoiler to toggle checkbox
                spoiler.addEventListener('click', function(e) {{
                    e.preventDefault();
                    checkbox.checked = !checkbox.checked;
                }});
            }});
        }});
    </script>
</body>
</html>"""
    
    return html

def generate_gallery_page_html(page_images, page_num, total_pages, title, folder_name):
    """Generate HTML for a single gallery page with images."""
    
    # Navigation
    prev_link = f'gallery_page_{page_num-1}.html' if page_num > 1 else '#'
    next_link = f'gallery_page_{page_num+1}.html' if page_num < total_pages else '#'
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Gallery Page {page_num}</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }}
        .header {{ 
            text-align: center; 
            margin-bottom: 30px; 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }}
        .navigation {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin: 20px 0; 
            padding: 15px; 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }}
        .nav-button {{ 
            padding: 10px 20px; 
            background: #007bff; 
            color: white; 
            text-decoration: none; 
            border-radius: 5px; 
            transition: background 0.3s; 
        }}
        .nav-button:hover {{ background: #0056b3; }}
        .nav-button:disabled, .nav-button[href="#"] {{ 
            background: #ccc; 
            pointer-events: none; 
        }}
        .image-thread {{ 
            max-width: 1000px; 
            margin: 0 auto; 
        }}
        .image-post {{ 
            background: white; 
            border-radius: 8px; 
            margin-bottom: 30px; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1); 
            overflow: hidden; 
            transition: transform 0.2s; 
        }}
        .image-post:hover {{ transform: translateY(-2px); }}
        .image-post-header {{ 
            background: #f8f9fa; 
            padding: 15px 20px; 
            border-bottom: 1px solid #e9ecef; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
        }}
        .image-filename {{ 
            font-weight: bold; 
            color: #333; 
            word-break: break-all; 
        }}
        .image-meta {{ 
            color: #666; 
            font-size: 12px; 
            display: flex; 
            gap: 15px; 
        }}
        .image-content {{ 
            padding: 20px; 
            text-align: center; 
        }}
        .image-content img {{ 
            max-width: 100%; 
            height: auto; 
            border-radius: 4px; 
            cursor: pointer; 
            transition: transform 0.2s; 
        }}
        .image-content img:hover {{ 
            transform: scale(1.02); 
        }}
        .image-actions {{ 
            padding: 15px 20px; 
            background: #f8f9fa; 
            border-top: 1px solid #e9ecef; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
        }}
        .image-size {{ 
            color: #666; 
            font-size: 12px; 
        }}
        .view-full-btn {{ 
            background: #007bff; 
            color: white; 
            border: none; 
            padding: 8px 16px; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 12px; 
            transition: background 0.2s; 
        }}
        .view-full-btn:hover {{ 
            background: #0056b3; 
        }}
        .lightbox {{ 
            display: none; 
            position: fixed; 
            z-index: 1000; 
            left: 0; 
            top: 0; 
            width: 100%; 
            height: 100%; 
            background-color: rgba(0,0,0,0.9); 
        }}
        .lightbox-content {{ 
            position: absolute; 
            top: 50%; 
            left: 50%; 
            transform: translate(-50%, -50%); 
            max-width: 90%; 
            max-height: 90%; 
        }}
        .lightbox-content img {{ 
            width: 100%; 
            height: 100%; 
            object-fit: contain; 
        }}
        .close {{ 
            position: absolute; 
            top: 20px; 
            right: 30px; 
            color: white; 
            font-size: 30px; 
            font-weight: bold; 
            cursor: pointer; 
        }}
        .page-info {{ 
            text-align: center; 
            color: #666; 
            margin: 10px 0; 
        }}
        .thread-stats {{ 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 8px; 
            margin: 20px auto; 
            max-width: 1000px; 
            text-align: center; 
            color: #666; 
            font-size: 14px; 
        }}
        .image-number {{ 
            background: #007bff; 
            color: white; 
            padding: 2px 8px; 
            border-radius: 12px; 
            font-size: 11px; 
            font-weight: bold; 
        }}
        .scroll-to-top {{ 
            position: fixed; 
            bottom: 30px; 
            right: 30px; 
            background: #007bff; 
            color: white; 
            border: none; 
            border-radius: 50%; 
            width: 50px; 
            height: 50px; 
            font-size: 18px; 
            cursor: pointer; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); 
            transition: all 0.3s; 
            opacity: 0; 
            visibility: hidden; 
        }}
        .scroll-to-top.visible {{ 
            opacity: 1; 
            visibility: visible; 
        }}
        .scroll-to-top:hover {{ 
            background: #0056b3; 
            transform: translateY(-2px); 
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>Image Gallery from: {folder_name}</p>
        <div class="page-info">Page {page_num} of {total_pages} ({len(page_images)} images)</div>
    </div>
    
    <div class="thread-stats">
        Showing images {((page_num-1)*100)+1} to {((page_num-1)*100)+len(page_images)} • Scroll down to view all images • Click any image for full size
    </div>
    
    <div class="navigation">
        <a href="{prev_link}" class="nav-button" {'style="background: #ccc; pointer-events: none;"' if page_num <= 1 else ''}>← Previous</a>
        <a href="index.html" class="nav-button">Gallery Index</a>
        <a href="{next_link}" class="nav-button" {'style="background: #ccc; pointer-events: none;"' if page_num >= total_pages else ''}>Next →</a>
    </div>
    
    <div class="image-thread">"""
    
    # Add images in thread format
    for i, img in enumerate(page_images):
        image_number = ((page_num - 1) * 100) + i + 1
        html += f"""
        <div class="image-post">
            <div class="image-post-header">
                <div class="image-filename">{img['filename']}</div>
                <div class="image-meta">
                    <span class="image-number">#{image_number}</span>
                    <span>{img['size_human']}</span>
                </div>
            </div>
            <div class="image-content">
                <img src="../images/{img['filename']}" alt="{img['filename']}" onclick="openLightbox('../images/{img['filename']}')" />
            </div>
            <div class="image-actions">
                <div class="image-size">File size: {img['size_human']}</div>
                <button class="view-full-btn" onclick="openLightbox('../images/{img['filename']}')">🔍 View Full Size</button>
            </div>
        </div>"""
    
    html += f"""
    </div>
    
    <div class="navigation">
        <a href="{prev_link}" class="nav-button" {'style="background: #ccc; pointer-events: none;"' if page_num <= 1 else ''}>← Previous</a>
        <a href="index.html" class="nav-button">Gallery Index</a>
        <a href="{next_link}" class="nav-button" {'style="background: #ccc; pointer-events: none;"' if page_num >= total_pages else ''}>Next →</a>
    </div>
    
    <!-- Scroll to top button -->
    <button id="scrollToTop" class="scroll-to-top" onclick="scrollToTop()" title="Scroll to top">↑</button>
    
    <!-- Lightbox -->
    <div id="lightbox" class="lightbox" onclick="closeLightbox()">
        <span class="close" onclick="closeLightbox()">&times;</span>
        <div class="lightbox-content">
            <img id="lightbox-img" src="" alt="" />
        </div>
    </div>
    
    <script>
        function openLightbox(src) {{
            document.getElementById('lightbox').style.display = 'block';
            document.getElementById('lightbox-img').src = src;
        }}
        
        function closeLightbox() {{
            document.getElementById('lightbox').style.display = 'none';
        }}
        
        function scrollToTop() {{
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}
        
        // Show/hide scroll to top button
        window.addEventListener('scroll', function() {{
            const scrollButton = document.getElementById('scrollToTop');
            if (window.pageYOffset > 300) {{
                scrollButton.classList.add('visible');
            }} else {{
                scrollButton.classList.remove('visible');
            }}
        }});
        
        // Keyboard navigation
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeLightbox();
        }});
        
        // Add smooth scrolling for better UX
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {{
                    target.scrollIntoView({{ behavior: 'smooth' }});
                }}
            }});
        }});
    </script>
</body>
</html>"""
    
    return html

def generate_gallery_index_html(total_pages, total_images, title, folder_name):
    """Generate HTML for the gallery index page."""
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Image Gallery</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }}
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
            background: white; 
            padding: 30px; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }}
        h1 {{ 
            text-align: center; 
            color: #333; 
            margin-bottom: 10px; 
        }}
        .subtitle {{ 
            text-align: center; 
            color: #666; 
            margin-bottom: 30px; 
        }}
        .stats {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px; 
        }}
        .stat-card {{ 
            background: #f8f9fa; 
            padding: 20px; 
            border-radius: 8px; 
            text-align: center; 
            border-left: 4px solid #007bff; 
        }}
        .stat-number {{ 
            font-size: 2em; 
            font-weight: bold; 
            color: #007bff; 
        }}
        .stat-label {{ 
            color: #666; 
            margin-top: 5px; 
        }}
        .page-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); 
            gap: 15px; 
            margin-top: 30px; 
        }}
        .page-link {{ 
            display: block; 
            padding: 20px; 
            background: #007bff; 
            color: white; 
            text-decoration: none; 
            border-radius: 8px; 
            text-align: center; 
            transition: background 0.3s; 
        }}
        .page-link:hover {{ 
            background: #0056b3; 
        }}
        .page-title {{ 
            font-weight: bold; 
            margin-bottom: 5px; 
        }}
        .page-info {{ 
            font-size: 0.9em; 
            opacity: 0.9; 
        }}
        .footer {{ 
            text-align: center; 
            margin-top: 30px; 
            padding-top: 20px; 
            border-top: 1px solid #eee; 
            color: #666; 
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="subtitle">Image Gallery Index</div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{total_images}</div>
                <div class="stat-label">Total Images</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_pages}</div>
                <div class="stat-label">Gallery Pages</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">100</div>
                <div class="stat-label">Images per Page</div>
            </div>
        </div>
        
        <h2>Browse Gallery Pages</h2>
        <div class="page-grid">"""
    
    # Add page links
    for page_num in range(1, total_pages + 1):
        start_img = (page_num - 1) * 100 + 1
        end_img = min(page_num * 100, total_images)
        
        html += f"""
            <a href="gallery_page_{page_num}.html" class="page-link">
                <div class="page-title">Page {page_num}</div>
                <div class="page-info">Images {start_img}-{end_img}</div>
            </a>"""
    
    html += f"""
        </div>
        
        <div class="footer">
            <p>Gallery generated from: {folder_name}</p>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>"""
    
    return html

def generate_index_html(all_pages, thread_title):
    """Generate index page for the thread."""
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{thread_title} - Thread Index</title>
    <link rel="stylesheet" href="thread-style.css">
</head>
<body>
    <div class="container">
        <div class="index-page">
            <h1 class="index-title">{thread_title}</h1>
            <p>Thread Archive • {len(all_pages)} pages</p>
            
            <div class="page-list">"""
    
    for page in all_pages:
        html += f'<a href="{page}.html" class="page-link">Page {page}</a>\n'
    
    html += f"""
            </div>
            
            <p style="color: #AAAAAA; font-size: 11px;">
                Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                SA Thread Archive
            </p>
        </div>
    </div>
</body>
</html>"""
    
    return html

def convert_html_to_json(job_id, folder_name):
    """Convert HTML files to JSON format."""
    try:
        running_jobs[job_id]['status'] = 'running'
        running_jobs[job_id]['progress'] = f"Starting JSON conversion for {folder_name}..."
        
        input_folder = folder_name
        output_folder = f"{folder_name}/json"
        
        # Call the existing JSON transformation function
        run_json_transformation(job_id, input_folder, output_folder)
        
    except Exception as e:
        running_jobs[job_id]['status'] = 'error'
        running_jobs[job_id]['progress'] = f"Error: {str(e)}"

def convert_images_to_gallery(job_id, folder_name, custom_title):
    """Convert images from images-only download to browsable HTML gallery pages."""
    try:
        running_jobs[job_id]['status'] = 'running'
        running_jobs[job_id]['progress'] = 'Scanning images...'
        
        # Paths
        thread_path = os.path.join('/app/output', folder_name)
        images_path = os.path.join(thread_path, 'images')
        gallery_path = os.path.join(thread_path, 'gallery')
        
        # Create gallery directory
        os.makedirs(gallery_path, exist_ok=True)
        
        # Get all image files
        all_images = []
        for filename in os.listdir(images_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')) and not filename.startswith('_'):
                file_path = os.path.join(images_path, filename)
                file_size = os.path.getsize(file_path)
                all_images.append({
                    'filename': filename,
                    'size': file_size,
                    'size_human': f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"
                })
        
        # Sort images by filename
        all_images.sort(key=lambda x: x['filename'])
        
        running_jobs[job_id]['progress'] = f'Found {len(all_images)} images, creating gallery pages...'
        
        # Split into pages of 100 images each
        images_per_page = 100
        total_pages = (len(all_images) + images_per_page - 1) // images_per_page
        
        # Generate gallery pages
        for page_num in range(1, total_pages + 1):
            start_idx = (page_num - 1) * images_per_page
            end_idx = min(start_idx + images_per_page, len(all_images))
            page_images = all_images[start_idx:end_idx]
            
            # Create HTML for this page
            html_content = generate_gallery_page_html(
                page_images, page_num, total_pages, custom_title, folder_name
            )
            
            # Save page
            page_filename = f'gallery_page_{page_num}.html'
            page_path = os.path.join(gallery_path, page_filename)
            with open(page_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            running_jobs[job_id]['progress'] = f'Generated page {page_num} of {total_pages}...'
        
        # Create index page
        running_jobs[job_id]['progress'] = 'Creating gallery index...'
        index_html = generate_gallery_index_html(total_pages, len(all_images), custom_title, folder_name)
        index_path = os.path.join(gallery_path, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_html)
        
        # Create summary file
        summary_path = os.path.join(gallery_path, '_gallery_info.txt')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"Image Gallery Summary\n")
            f.write(f"====================\n")
            f.write(f"Title: {custom_title}\n")
            f.write(f"Source folder: {folder_name}\n")
            f.write(f"Total images: {len(all_images)}\n")
            f.write(f"Gallery pages: {total_pages}\n")
            f.write(f"Images per page: {images_per_page}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Access: Open gallery/index.html in your browser\n")
        
        running_jobs[job_id]['status'] = 'completed'
        running_jobs[job_id]['progress'] = f'Gallery created! {len(all_images)} images in {total_pages} pages. Open gallery/index.html to view.'
        
    except Exception as e:
        running_jobs[job_id]['status'] = 'error'
        running_jobs[job_id]['progress'] = f'Error: {str(e)}'
        print(f"Error in convert_images_to_gallery: {e}")

def convert_thread_to_standalone_html(job_id, thread_folder, custom_title):
    """Convert a thread folder with JSON files to standalone HTML."""
    try:
        running_jobs[job_id]['status'] = 'running'
        running_jobs[job_id]['progress'] = f"Converting {Path(thread_folder).name} to standalone HTML..."
        
        thread_path = os.path.join('/app/output', thread_folder)
        json_folder = os.path.join(thread_path, 'json')
        
        if not os.path.exists(json_folder):
            running_jobs[job_id]['status'] = 'error'
            running_jobs[job_id]['progress'] = f"No json folder found in {thread_folder}"
            return
        
        # Get available pages
        all_pages = get_page_numbers(json_folder)
        
        if not all_pages:
            running_jobs[job_id]['status'] = 'error'
            running_jobs[job_id]['progress'] = f"No valid JSON files found in {thread_folder}"
            return
        
        # Use the provided custom title
        thread_title = custom_title
        
        running_jobs[job_id]['progress'] = f"Generating CSS and index page..."
        
        # Generate CSS file
        css_path = os.path.join(thread_path, 'thread-style.css')
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(generate_css())
        
        # Generate index page
        index_path = os.path.join(thread_path, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(generate_index_html(all_pages, thread_title))
        
        # Generate individual pages
        total_pages = len(all_pages)
        for i, page_num in enumerate(all_pages, 1):
            if running_jobs[job_id]['status'] == 'cancelled':
                break
                
            running_jobs[job_id]['progress'] = f"Generating page {page_num} ({i}/{total_pages})..."
            
            json_file = os.path.join(json_folder, f'{page_num}.json')
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    page_data = json.load(f)
                
                page_html = generate_page_html(page_data, page_num, all_pages, thread_title)
                
                html_path = os.path.join(thread_path, f'{page_num}.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page_html)
                    
            except Exception as e:
                print(f"Error processing page {page_num}: {e}")
                continue
        
        if running_jobs[job_id]['status'] != 'cancelled':
            running_jobs[job_id]['status'] = 'completed'
            running_jobs[job_id]['progress'] = f"Standalone HTML conversion complete! Generated {len(all_pages)} pages for '{thread_title}'"
            
    except Exception as e:
        running_jobs[job_id]['status'] = 'error'
        running_jobs[job_id]['progress'] = f"Error: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 