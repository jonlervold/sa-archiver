#!/usr/bin/env python3
"""
JSON to HTML Thread Converter
Converts SA thread JSON files into standalone HTML pages with pagination.
"""

import os
import json
import glob
import re
from pathlib import Path
from datetime import datetime

def get_page_numbers(json_folder):
    """Get list of available page numbers from JSON files."""
    print(f"DEBUG: Checking JSON folder: {json_folder}")
    json_files = glob.glob(os.path.join(json_folder, "*.json"))
    print(f"DEBUG: Found {len(json_files)} JSON files")
    page_numbers = []
    
    for json_file in json_files:
        filename = Path(json_file).stem
        print(f"DEBUG: Processing file: {filename}")
        if filename.isdigit():
            page_numbers.append(int(filename))
            print(f"DEBUG: Added page number: {filename}")
        else:
            print(f"DEBUG: Skipping non-numeric file: {filename}")
    
    result = sorted(page_numbers)
    print(f"DEBUG: Final page numbers: {result}")
    return result

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
    font-size: 13px;
    background-color: #2E2E2E;
    color: #FFFFFF;
    line-height: 1.4;
    margin: 0;
    padding: 20px;
}

.container {
    max-width: 1000px;
    margin: 0 auto;
    border-radius: 5px;
}

.thread-header {
    background: linear-gradient(to bottom, #5C7A96, #4A6480);
    padding: 15px 20px;
    border-bottom: 1px solid #666;
    text-align: center;
}

.thread-title {
    font-size: 18px;
    font-weight: bold;
    color: #FFFFFF;
    margin-bottom: 5px;
}

.thread-info {
    font-size: 11px;
    color: #CCCCCC;
}

.pagination {
    background-color: #4A6480;
    padding: 10px 20px;
    border-bottom: 1px solid #666;
    text-align: center;
}

.pagination.bottom {
    border-bottom: none;
    border-top: 1px solid #666;
}

.pagination a {
    color: #FFFFFF;
    text-decoration: none;
    padding: 5px 10px;
    margin: 0 2px;
    background-color: #5C7A96;
    border: 1px solid #7A98B6;
    border-radius: 3px;
    display: inline-block;
}

.pagination a:hover {
    background-color: #6A86A2;
}

.pagination .current {
    background-color: #8AA6C2;
    color: #FFFFFF;
    padding: 5px 10px;
    margin: 0 2px;
    border: 1px solid #AAC6E2;
    border-radius: 3px;
    display: inline-block;
    font-weight: bold;
}

.pagination .nav {
    font-weight: bold;
    background-color: #3A5470;
}

.posts {
    padding: 0;
}

.post {
    border-bottom: 1px solid #666;
    background-color: #404040;
}

.post:last-child {
    border-bottom: none;
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
    font-size: 14px;
}

.post-date {
    color: #CCCCCC;
    font-size: 11px;
}

.post-content {
    padding: 15px 20px;
    background-color: #404040;
    color: #FFFFFF;
}

.post-content img {
    max-width: 100%;
    height: auto;
    border: 1px solid #666;
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
    font-style: italic;
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

.footer {
    background-color: #363636;
    padding: 15px 20px;
    text-align: center;
    font-size: 11px;
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
    }
    
    .post-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 5px;
    }
    
    .pagination a, .pagination .current {
        padding: 3px 6px;
        font-size: 11px;
    }
}
"""

def generate_pagination(current_page, all_pages, base_name=""):
    """Generate pagination HTML."""
    pagination_html = ['<div class="pagination">']
    
    # Previous page link
    if current_page > min(all_pages):
        prev_page = current_page - 1
        pagination_html.append(f'<a href="{prev_page}.html" class="nav">← Previous</a>')
    
    # Page numbers
    for page in all_pages:
        if page == current_page:
            pagination_html.append(f'<span class="current">{page}</span>')
        else:
            pagination_html.append(f'<a href="{page}.html">{page}</a>')
    
    # Next page link
    if current_page < max(all_pages):
        next_page = current_page + 1
        pagination_html.append(f'<a href="{next_page}.html" class="nav">Next →</a>')
    
    pagination_html.append('</div>')
    return '\n'.join(pagination_html)

def generate_page_html(page_data, current_page, all_pages, thread_title):
    """Generate HTML for a single page."""
    
    pagination = generate_pagination(current_page, all_pages)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{thread_title} - Page {current_page}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header class="thread-header">
            <h1 class="thread-title">{thread_title}</h1>
            <div class="thread-info">
                Page {current_page} of {max(all_pages)} • {page_data['total_posts']} posts • 
                <a href="index.html" style="color: #CCCCCC;">Thread Index</a>
            </div>
        </header>
        
        {pagination}
        
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
        
        <div class="pagination bottom">
            {pagination.replace('<div class="pagination">', '').replace('</div>', '')}
        </div>
        
        <footer class="footer">
            Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • 
            SA Thread Archive
        </footer>
    </div>
</body>
</html>"""
    
    return html

def generate_index_html(all_pages, thread_title, thread_folder):
    """Generate index page for the thread."""
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{thread_title} - Thread Index</title>
    <link rel="stylesheet" href="style.css">
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

def convert_thread_to_html(thread_folder):
    """Convert a thread folder with JSON files to HTML."""
    
    json_folder = os.path.join(thread_folder, 'json')
    
    if not os.path.exists(json_folder):
        print(f"No json folder found in {thread_folder}")
        return
    
    # Get available pages
    all_pages = get_page_numbers(json_folder)
    
    if not all_pages:
        print(f"No valid JSON files found in {json_folder}")
        return
    
    print(f"Found pages: {all_pages}")
    
    # Determine thread title from folder name
    thread_title = Path(thread_folder).name.replace('_', ' ').title()
    
    # Generate CSS file
    css_path = os.path.join(thread_folder, 'style.css')
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(generate_css())
    print(f"Generated: {css_path}")
    
    # Generate index page
    index_path = os.path.join(thread_folder, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(generate_index_html(all_pages, thread_title, thread_folder))
    print(f"Generated: {index_path}")
    
    # Generate individual pages
    for page_num in all_pages:
        json_file = os.path.join(json_folder, f'{page_num}.json')
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                page_data = json.load(f)
            
            page_html = generate_page_html(page_data, page_num, all_pages, thread_title)
            
            html_path = os.path.join(thread_folder, f'{page_num}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page_html)
            
            print(f"Generated: {html_path}")
            
        except Exception as e:
            print(f"Error processing page {page_num}: {e}")

def main():
    """Main function - convert all thread folders in output directory."""
    
    print("DEBUG: Script starting...")
    output_dir = 'output'
    print(f"DEBUG: Looking for output directory: {output_dir}")
    
    if not os.path.exists(output_dir):
        print(f"Output directory '{output_dir}' not found!")
        return
    
    print("DEBUG: Output directory found, looking for thread folders...")
    # Find all thread folders (folders that contain a 'json' subfolder)
    thread_folders = []
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        print(f"DEBUG: Checking item: {item_path}")
        if os.path.isdir(item_path):
            json_path = os.path.join(item_path, 'json')
            if os.path.exists(json_path):
                thread_folders.append(item_path)
                print(f"DEBUG: Added thread folder: {item_path}")
            else:
                print(f"DEBUG: No JSON folder in: {item_path}")
        else:
            print(f"DEBUG: Not a directory: {item_path}")
    
    if not thread_folders:
        print("No thread folders with JSON data found!")
        return
    
    print(f"Found {len(thread_folders)} thread folders to convert:")
    for folder in thread_folders:
        print(f"  - {Path(folder).name}")
    
    print("\nConverting threads to HTML...")
    for thread_folder in thread_folders:
        print(f"\nProcessing: {Path(thread_folder).name}")
        convert_thread_to_html(thread_folder)
    
    print(f"\nConversion complete! You can now upload any thread folder to static hosting.")
    print("Each thread folder contains:")
    print("  - index.html (thread overview)")
    print("  - 1.html, 2.html, etc. (individual pages)")
    print("  - style.css (styling)")
    print("  - All original images and files")

if __name__ == "__main__":
    print("DEBUG: Script called directly")
    main() 