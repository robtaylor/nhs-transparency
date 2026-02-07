#!/usr/bin/env python3
"""
Generate individual contract detail pages.

Creates a page for each contract showing full details including
description, dates, values, and links to related entities.
"""

import argparse
import re
import sqlite3
from pathlib import Path

# Maximum value considered as "awarded" vs "framework ceiling"
MAX_AWARDED_VALUE = 200_000_000


def slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:80]


def format_value(value: int | None) -> str:
    """Format a contract value as a human-readable string."""
    if value is None or value == 0:
        return "Unknown"
    if value >= 1_000_000_000:
        return f"\u00a3{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"\u00a3{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"\u00a3{value / 1_000:.0f}K"
    return f"\u00a3{value:,}"


def format_date(date_str: str | None) -> str:
    """Format a date string for display."""
    if not date_str:
        return "Not specified"
    # Return just the date part if it's an ISO datetime
    return date_str[:10]


CONTRACT_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_short} - NHS Transparency</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .card {{ @apply bg-white rounded-lg shadow-md p-6 mb-6; }}
        .label {{ @apply text-gray-500 text-sm font-medium; }}
        .value {{ @apply text-gray-900; }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <header class="bg-indigo-900 text-white py-6">
        <div class="container mx-auto px-4">
            <a href="index.html" class="text-indigo-300 hover:text-white text-sm">← Back to Dashboard</a>
            <h1 class="text-xl font-bold mt-2 leading-tight">{title}</h1>
            <p class="text-indigo-200 mt-1">Contract Details</p>
        </div>
    </header>

    <main class="container mx-auto px-4 py-8">
        <!-- Key Stats -->
        <section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="card text-center">
                <div class="text-2xl font-bold text-green-600">{value}</div>
                <div class="text-gray-600 text-sm">{value_label}</div>
            </div>
            <div class="card text-center">
                <div class="text-lg font-semibold text-gray-700">{award_date}</div>
                <div class="text-gray-600 text-sm">Award Date</div>
            </div>
            <div class="card text-center">
                <div class="text-lg font-semibold text-gray-700">{contract_period}</div>
                <div class="text-gray-600 text-sm">Contract Period</div>
            </div>
            <div class="card text-center">
                <div class="text-lg font-semibold {status_color}">{status}</div>
                <div class="text-gray-600 text-sm">Status</div>
            </div>
        </section>

        <!-- Parties -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Parties</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <div class="label">Buyer</div>
                    <div class="value text-lg">
                        <a href="trust-{buyer_slug}.html" class="text-blue-600 hover:underline">{buyer_name}</a>
                    </div>
                </div>
                <div>
                    <div class="label">Supplier</div>
                    <div class="value text-lg">{supplier_html}</div>
                    {supplier_details}
                </div>
            </div>
        </section>

        <!-- Description -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Description</h2>
            <div class="prose max-w-none text-gray-700 whitespace-pre-wrap">{description}</div>
        </section>

        <!-- Contract Details -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Contract Details</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                    <div class="label">Contract Type</div>
                    <div class="value">{contract_type}</div>
                </div>
                <div>
                    <div class="label">Procurement Route</div>
                    <div class="value">{procurement_route}</div>
                </div>
                <div>
                    <div class="label">Location</div>
                    <div class="value">{location}</div>
                </div>
                <div>
                    <div class="label">Published Date</div>
                    <div class="value">{published_date}</div>
                </div>
                <div>
                    <div class="label">CPV Codes</div>
                    <div class="value">{cpv_codes}</div>
                </div>
                <div>
                    <div class="label">Suitable for SME</div>
                    <div class="value">{suitable_for_sme}</div>
                </div>
            </div>
        </section>

        <!-- Value Breakdown -->
        {value_breakdown}

        <!-- External Links -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">External Links</h2>
            <div class="space-y-2">
                {external_links}
            </div>
        </section>
    </main>

    <footer class="bg-gray-800 text-gray-400 py-6">
        <div class="container mx-auto px-4 text-center">
            <p>NHS Transparency Project - Open Data for Public Good</p>
            <p class="text-sm mt-2">
                <a href="index.html" class="text-blue-400 hover:underline">Return to Dashboard</a>
            </p>
        </div>
    </footer>
</body>
</html>
"""


def generate_contract_page(conn: sqlite3.Connection, contract: dict, output_dir: Path) -> str:
    """Generate a detail page for a specific contract."""
    external_id = contract["external_id"]
    slug = slugify(external_id)

    # Title handling
    title = contract["title"] or "Untitled Contract"
    title_short = (title[:60] + "...") if len(title) > 60 else title

    # Value handling
    value_gbp = contract["value_gbp"]
    value_low = contract["value_low_gbp"]
    value_high = contract["value_high_gbp"]
    is_framework = contract["contract_type"] == "framework"

    if is_framework and value_high and value_high > MAX_AWARDED_VALUE:
        value = format_value(value_high)
        value_label = "Framework Ceiling"
    elif value_gbp:
        value = format_value(value_gbp)
        value_label = "Awarded Value"
    elif value_high:
        value = format_value(value_high)
        value_label = "Estimated Value"
    else:
        value = "Not disclosed"
        value_label = "Value"

    # Value breakdown section
    value_breakdown = ""
    if value_low or value_high or (value_gbp and (value_low or value_high)):
        breakdown_rows = ""
        if value_gbp:
            breakdown_rows += f'<tr><td class="py-1">Awarded Value</td><td class="text-right font-semibold text-green-700">{format_value(value_gbp)}</td></tr>'
        if value_low:
            breakdown_rows += f'<tr><td class="py-1">Minimum Value</td><td class="text-right">{format_value(value_low)}</td></tr>'
        if value_high:
            breakdown_rows += f'<tr><td class="py-1">Maximum Value</td><td class="text-right">{format_value(value_high)}</td></tr>'

        value_breakdown = f"""
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Value Breakdown</h2>
            <table class="w-full max-w-md">
                <tbody>{breakdown_rows}</tbody>
            </table>
            <p class="text-gray-500 text-sm mt-3">
                Note: Maximum values for framework agreements represent spending ceilings, not actual spend.
            </p>
        </section>
        """

    # Dates
    award_date = format_date(contract["award_date"])
    start_date = format_date(contract["start_date"])
    end_date = format_date(contract["end_date"])

    if start_date != "Not specified" and end_date != "Not specified":
        contract_period = f"{start_date} to {end_date}"
    elif start_date != "Not specified":
        contract_period = f"From {start_date}"
    elif end_date != "Not specified":
        contract_period = f"Until {end_date}"
    else:
        contract_period = "Not specified"

    # Status
    status = contract["status"] or ("Framework" if is_framework else "Awarded")
    status_color = "text-green-600" if status.lower() in ("awarded", "closed") else "text-blue-600"

    # Buyer
    buyer_name = contract["buyer_name"] or "Unknown"
    buyer_slug = slugify(buyer_name)

    # Supplier
    supplier_name = contract["supplier_name"]
    if supplier_name:
        supplier_slug = slugify(supplier_name)
        supplier_html = f'<a href="supplier-{supplier_slug}.html" class="text-blue-600 hover:underline">{supplier_name}</a>'
    else:
        supplier_html = "Not specified"

    # Supplier details
    supplier_details = ""
    supplier_address = contract["supplier_address"]
    is_sme = contract["is_sme"]
    is_vcse = contract["is_vcse"]

    details_parts = []
    if supplier_address:
        details_parts.append(f"<div class='text-sm text-gray-500 mt-1'>{supplier_address}</div>")
    if is_sme:
        details_parts.append(
            "<span class='inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded mt-1 mr-1'>SME</span>"
        )
    if is_vcse:
        details_parts.append(
            "<span class='inline-block bg-green-100 text-green-800 text-xs px-2 py-1 rounded mt-1'>VCSE</span>"
        )
    supplier_details = "".join(details_parts)

    # Description
    description = contract["description"] or "No description available."
    # Escape HTML in description
    description = description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Other details
    contract_type = contract["contract_type"] or "Not specified"
    if is_framework:
        contract_type = "Framework Agreement"

    procurement_route = contract["procurement_route"] or "Not specified"
    location = contract["location"] or "Not specified"
    published_date = format_date(contract["published_date"])
    cpv_codes = contract["cpv_codes"] or "Not specified"
    suitable_for_sme = (
        "Yes"
        if contract["suitable_for_sme"]
        else ("No" if contract["suitable_for_sme"] is False else "Not specified")
    )

    # External links
    external_links = ""
    notice_url = contract["notice_url"]
    if notice_url:
        external_links += f'<a href="{notice_url}" target="_blank" class="text-blue-600 hover:underline block">View on Contracts Finder →</a>'
    if not external_links:
        external_links = '<span class="text-gray-500">No external links available</span>'

    # Generate HTML
    html = CONTRACT_PAGE_TEMPLATE.format(
        title=title,
        title_short=title_short,
        value=value,
        value_label=value_label,
        award_date=award_date,
        contract_period=contract_period,
        status=status,
        status_color=status_color,
        buyer_name=buyer_name,
        buyer_slug=buyer_slug,
        supplier_html=supplier_html,
        supplier_details=supplier_details,
        description=description,
        contract_type=contract_type,
        procurement_route=procurement_route,
        location=location,
        published_date=published_date,
        cpv_codes=cpv_codes,
        suitable_for_sme=suitable_for_sme,
        value_breakdown=value_breakdown,
        external_links=external_links,
    )

    # Write file
    output_path = output_dir / f"contract-{slug}.html"
    output_path.write_text(html)

    return slug


def main():
    parser = argparse.ArgumentParser(description="Generate contract detail pages")
    parser.add_argument("--db", type=Path, required=True, help="Database path")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output directory")

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    args.output.mkdir(parents=True, exist_ok=True)

    # Get all contracts
    cursor = conn.execute(
        """
        SELECT
            external_id, title, description,
            buyer_name, supplier_name, supplier_address,
            value_gbp, value_low_gbp, value_high_gbp,
            award_date, start_date, end_date,
            contract_type, procurement_route, notice_url,
            cpv_codes, published_date, is_sme, is_vcse,
            status, location, suitable_for_sme, suitable_for_vcse
        FROM contracts
        ORDER BY award_date DESC
        """
    )
    contracts = cursor.fetchall()

    count = 0
    for contract in contracts:
        generate_contract_page(conn, dict(contract), args.output)
        count += 1
        if count % 100 == 0:
            print(f"Generated {count} contract pages...")

    conn.close()
    print(f"\nGenerated {count} contract pages")


if __name__ == "__main__":
    main()
