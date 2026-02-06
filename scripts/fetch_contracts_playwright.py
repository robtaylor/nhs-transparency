#!/usr/bin/env -S uv run --script
"""
Fetch contracts from Contracts Finder using Playwright.

The Contracts Finder CSV export ignores URL parameters, so we need to use
a real browser to:
1. Navigate to the search page
2. Set filters (closed notices, awarded contracts)
3. Enter search keywords
4. Optionally filter by date range
5. Click "Download CSV"

Usage:
    uv run scripts/fetch_contracts_playwright.py --keyword "Palantir" --output data/contracts.csv
    uv run scripts/fetch_contracts_playwright.py --keyword "NHS England" --year 2024 --output data/contracts-2024.csv
"""

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright


def fetch_contracts(
    keyword: str,
    output_path: Path,
    headless: bool = True,
    download_timeout: int = 300000,  # 5 minutes
    year: int | None = None,
) -> int:
    """
    Search Contracts Finder and download CSV with proper filters.

    Args:
        keyword: Search keyword (e.g., "NHS England", "Palantir")
        output_path: Where to save the CSV file
        headless: Run browser in headless mode
        download_timeout: Timeout for CSV download in milliseconds
        year: Optional year to filter by (e.g., 2024)

    Returns:
        Number of lines in downloaded CSV (0 on failure)
    """
    browser = None
    playwright = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Set a longer default timeout
        page.set_default_timeout(60000)

        print("Navigating to Contracts Finder...")
        page.goto("https://www.contractsfinder.service.gov.uk/Search/Results")

        # Wait for the search form to be ready
        page.wait_for_selector("#keywords", state="visible")
        time.sleep(2)

        # Enter search keyword
        print(f"Searching for: {keyword}")
        page.fill("#keywords", keyword)

        # Set notice status filters
        # Uncheck "Open" (checked by default), check "Closed"
        open_cb = page.locator("#open")
        if open_cb.is_checked():
            open_cb.click()
            time.sleep(0.5)

        closed_cb = page.locator("#closed")
        if not closed_cb.is_checked():
            closed_cb.click()
            time.sleep(0.5)

        # Check "Awarded contract" procurement stage
        awarded_cb = page.locator("#awarded")
        if not awarded_cb.is_checked():
            awarded_cb.click()
            time.sleep(0.5)

        # Set date range if year specified
        if year:
            print(f"Filtering by year: {year}")
            # GOV.UK date inputs use separate day/month/year fields
            # published_date_from-day, published_date_from-month, published_date_from-year
            # published_date_to-day, published_date_to-month, published_date_to-year
            page.fill("#published_date_from-day", "01")
            page.fill("#published_date_from-month", "01")
            page.fill("#published_date_from-year", str(year))
            time.sleep(0.3)
            page.fill("#published_date_to-day", "31")
            page.fill("#published_date_to-month", "12")
            page.fill("#published_date_to-year", str(year))
            time.sleep(0.3)

        # Click "Update results" and wait for navigation
        print("Applying filters (closed + awarded)...")
        with page.expect_response(
            lambda r: "Search/Results" in r.url, timeout=60000
        ):
            page.click("#adv_search_button")

        # Wait for results to load
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Get result count
        result_count = "unknown"
        try:
            result_el = page.locator(".search-result-count")
            if result_el.count() > 0:
                result_count = result_el.text_content()
        except Exception:
            pass
        print(f"Found {result_count} notices")

        # Prepare output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Find the CSV download link
        print("Downloading CSV...")
        csv_link = page.locator("a:has-text('Download results as a CSV file')")

        if csv_link.count() == 0:
            csv_link = page.locator("a[href*='GetCsvFile']")

        if csv_link.count() == 0:
            print("ERROR: Could not find CSV download link")
            # Take a screenshot for debugging
            page.screenshot(path=str(output_path.parent / "debug-screenshot.png"))
            return 0

        # Click and wait for download with extended timeout
        try:
            with page.expect_download(timeout=download_timeout) as download_info:
                csv_link.click()

            download = download_info.value
            download.save_as(output_path)
            print(f"Saved to: {output_path}")
        except PlaywrightTimeout:
            print(f"ERROR: Download timed out after {download_timeout // 1000}s")
            return 0

        # Count lines
        with open(output_path) as f:
            return sum(1 for _ in f)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 0

    finally:
        # Clean up resources
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if playwright:
            try:
                playwright.stop()
            except Exception:
                pass


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
    parser.add_argument(
        "--year", "-y", type=int, help="Filter by publication year (e.g., 2024)"
    )
    parser.add_argument(
        "--timeout", "-t", type=int, default=300,
        help="Download timeout in seconds (default: 300)"
    )

    args = parser.parse_args()

    line_count = fetch_contracts(
        keyword=args.keyword,
        output_path=args.output,
        headless=not args.no_headless,
        download_timeout=args.timeout * 1000,
        year=args.year,
    )

    print(f"Downloaded {line_count} lines")
    sys.exit(0 if line_count > 0 else 1)


if __name__ == "__main__":
    main()
