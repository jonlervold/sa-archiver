#!/usr/bin/env python3
"""
SomethingAwful Thread Parser
Converts HTML forum pages to JSON format, extracting essential post data.
"""

import os
import re
import json
import glob
from bs4 import BeautifulSoup
from pathlib import Path

def parse_post_content(html_content):
    """Extract post content between google_ad_section markers."""
    start_marker = '<!-- google_ad_section_start -->'
    end_marker = '<!-- google_ad_section_end -->'
    
    start_idx = html_content.find(start_marker)
    end_idx = html_content.find(end_marker, start_idx)
    
    if start_idx != -1 and end_idx != -1:
        # Extract content between markers
        content = html_content[start_idx + len(start_marker):end_idx].strip()
        return content
    return None

def extract_posts_from_html(html_file_path):
    """Extract all posts from a single HTML page."""
    # Try different encodings to handle various file formats
    encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
    html_content = None
    
    for encoding in encodings:
        try:
            with open(html_file_path, 'r', encoding=encoding) as file:
                html_content = file.read()
                break
        except UnicodeDecodeError:
            continue
    
    if html_content is None:
        print(f"  -> Could not decode file with any supported encoding")
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    posts = []
    
    # Find all td elements with class 'postbody' that contain google ad markers
    postbody_elements = soup.find_all('td', class_='postbody')
    
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
            
            # Find the author element - look in the same row or nearby elements
            author_elem = None
            
            # Try to find author in the same table row
            table_row = postbody.find_parent('tr')
            if table_row:
                author_elem = table_row.find('dt', class_=re.compile(r'author'))
            
            # If not found, look in parent table or surrounding area
            if not author_elem:
                table = postbody.find_parent('table')
                if table:
                    author_elem = table.find('dt', class_=re.compile(r'author'))
            
            if not author_elem:
                continue
                
            # Extract username
            username = author_elem.get_text().strip()
            
            # Find datetime in the surrounding content
            datetime_pattern = r'[A-Z][a-z]{2} \d{1,2}, \d{4} \d{1,2}:\d{2}'
            post_datetime = None
            
            # Look for datetime in postdate class elements within the table
            table = postbody.find_parent('table')
            if table:
                postdate_elem = table.find('td', class_='postdate')
                if postdate_elem:
                    datetime_match = re.search(datetime_pattern, postdate_elem.get_text())
                    post_datetime = datetime_match.group(0) if datetime_match else None
            
            # Fallback: search in the entire table if not found in postdate
            if not post_datetime and table:
                datetime_match = re.search(datetime_pattern, table.get_text())
                post_datetime = datetime_match.group(0) if datetime_match else None
            
            # Create post data
            post_data = {
                'username': username,
                'datetime': post_datetime,
                'content': post_content_html
            }
            posts.append(post_data)
                
        except Exception as e:
            print(f"  -> Error processing post: {e}")
            continue
    
    return posts

def process_all_html_files(input_directory, output_directory):
    """Process all HTML files in the input directory."""
    # Create output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)
    
    # Find all HTML files
    html_pattern = os.path.join(input_directory, "**/*.html")
    html_files = glob.glob(html_pattern, recursive=True)
    
    print(f"Found {len(html_files)} HTML files to process")
    
    for html_file in html_files:
        try:
            print(f"Processing: {html_file}")
            
            # Extract posts from this HTML file
            posts = extract_posts_from_html(html_file)
            
            if posts:
                # Generate output filename based on input filename
                html_filename = Path(html_file).name
                json_filename = html_filename.replace('.html', '.json')
                output_path = os.path.join(output_directory, json_filename)
                
                # Create page data structure
                page_data = {
                    'source_file': html_filename,
                    'total_posts': len(posts),
                    'posts': posts
                }
                
                # Write JSON file
                with open(output_path, 'w', encoding='utf-8') as json_file:
                    json.dump(page_data, json_file, indent=2, ensure_ascii=False)
                
                print(f"  -> Extracted {len(posts)} posts to {output_path}")
            else:
                print(f"  -> No posts found in {html_file}")
                
        except Exception as e:
            print(f"Error processing {html_file}: {e}")

def main():
    """Main function to run the parser."""
    # Define input and output directories
    input_dir = "animorphs/forums.somethingawful.com"
    output_dir = "json_output"
    
    print("SomethingAwful Thread Parser")
    print("=" * 50)
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print()
    
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist!")
        return
    
    # Process all HTML files
    process_all_html_files(input_dir, output_dir)
    
    print("\nProcessing complete!")

if __name__ == "__main__":
    main() 