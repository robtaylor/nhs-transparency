#!/usr/bin/env -S uv run --script
"""
Fetch contracts from Contracts Finder using Playwright.

The Contracts Finder CSV export ignores URL parameters, so we need to use
a real browser to:
1. Navigate to the search page
2. Set filters (closed notices, awarded contracts)
3. Enter search keywords
4. Click "Download CSV"

Usage:
    uv run scripts/fetch_contracts_playwright.py --keyword "NHS England" --output data/contracts.csv
"""

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def fetch_contracts(
    keyword: str,
    output_path: Path,
    headless: bool = True,
) -> int:
    """
    Search Contracts Finder and download CSV with proper filters.

    Args:
        keyword: Search keyword (e.g., "NHS England", "Palantir")
        output_path: Where to save the CSV file
        headless: Run browser in headless mode

    Returns:
        Number of lines in downloaded CSV
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("Navigating to Contracts Finder...")
        page.goto("https://www.contractsfinder.service.gov.uk/Search/Results")

        # Wait for page to load
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Enter search keyword FIRST
        print(f"Searching for: {keyword}")
        keyword_input = page.locator("#keywords")
        keyword_input.fill(keyword)

        # Uncheck "Open" notices (checked by default)
        open_checkbox = page.locator("#open")
        if open_checkbox.is_checked():
            open_checkbox.uncheck()

        # Check "Closed" notices
        closed_checkbox = page.locator("#closed")
        if not closed_checkbox.is_checked():
            closed_checkbox.check()

        # Check "Awarded contract" procurement stage
        awarded_checkbox = page.locator("#awarded")
        if not awarded_checkbox.is_checked():
            awarded_checkbox.check()

        # Click "Update results" button
        print("Applying filters (closed + awarded)...")
        update_button = page.locator("#adv_search_button")
        update_button.click()

        # Wait for results to update
        page.wait_for_load_state("networkidle")
        time.sleep(3)  # Extra wait for dynamic content

        # Get result count
        result_count_el = page.locator(".search-result-count")
        result_count = result_count_el.text_content() if result_count_el.count() > 0 else "unknown"
        print(f"Found {result_count} notices")

        # Set up download handler
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Click download CSV link
        print("Downloading CSV...")
        with page.expect_download() as download_info:
            # Find and click the CSV download link
            csv_link = page.locator("a:has-text('Download results as a CSV file')")
            if csv_link.count() == 0:
                # Try alternative selector
                csv_link = page.locator("a[href*='GetCsvFile']")

            if csv_link.count() > 0:
                csv_link.click()
            else:
                print("ERROR: Could not find CSV download link")
                browser.close()
                return 0

        download = download_info.value
        download.save_as(output_path)

        print(f"Saved to: {output_path}")

        browser.close()

        # Count lines in downloaded file
        with open(output_path) as f:
            line_count = sum(1 for _ in f)

        return line_count


def main():
    parser = argparse.ArgumentParser(
        description="Fetch contracts from Contracts Finder using Playwright"
    )
    parser.add_argument(
        "--keyword", "-k", required=True, help="Search keyword (e.g., 'NHS England', 'Palantir')"
    )
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output CSV file path")
    parser.add_argument(
        "--no-headless", action="store_true", help="Run browser in visible mode (for debugging)"
    )

    args = parser.parse_args()

    line_count = fetch_contracts(
        keyword=args.keyword,
        output_path=args.output,
        headless=not args.no_headless,
    )

    print(f"Downloaded {line_count} lines")


if __name__ == "__main__":
    main()
