#!/usr/bin/env python3
# archive_sa_thread.py

import os
import re
import subprocess
import sys

def main():
    print("Enter full URL to first page of the thread:")
    base_url = input()
    print("Enter the first page number to download:")
    start_page = input()
    print("Enter the final page number to download:")
    end_page = input()
    print("Enter folder name to save the thread into:")
    folder = input()

    print()
    print("Select download mode:")
    print("1) Full page")
    print("2) Images only")
    while True:
        download_mode = input("Enter choice (1 or 2): ")
        if download_mode in ["1", "2"]:
            break

    print("Enter your bbuserid:")
    bbuserid = input()
    print("Enter your bbpassword:")
    bbpassword = input()

    # Remove pagenumber from base URL if present
    base_no_page = re.sub(r'([&?])pagenumber=[^&]*', '', base_url)

    print()
    print("Downloading thread:")
    print(f"  URL without pagenumber: {base_no_page}")
    print(f"  Pages: {start_page} to {end_page}")
    print(f"  Output folder: {folder}")
    print(f"  Mode: {'Images only' if download_mode == '2' else 'Full page'}")
    print()

    # Create output directory if it doesn't exist
    if not os.path.exists(folder):
        os.makedirs(folder)

    cookie_header = f"bbuserid={bbuserid}; bbpassword={bbpassword}"

    for page in range(int(start_page), int(end_page) + 1):
        page_url = f"{base_no_page}&pagenumber={page}"
        print(f"Downloading page {page}: {page_url}")

        if download_mode == "2":
            # Images only mode using gallery-dl
            subprocess.run([
                "gallery-dl",
                "--header", f"Cookie: {cookie_header}",
                "-d", folder,
                page_url
            ])
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
                f"--directory-prefix={folder}",
                f"--header=Cookie: {cookie_header}",
                page_url
            ]
            
            subprocess.run(wget_args)

    print()
    print(f"Download complete. Files saved to: {folder}")

if __name__ == "__main__":
    main() 