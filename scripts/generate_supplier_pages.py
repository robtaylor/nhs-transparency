#!/usr/bin/env python3
"""
Generate individual supplier detail pages showing all their contracts.

Creates a page for each supplier with significant contract activity,
showing all buyers they've worked with and contract details.
"""

import argparse
import re
import sqlite3
from pathlib import Path

# Maximum value considered as "awarded" vs "framework ceiling"
MAX_AWARDED_VALUE = 200_000_000

# Minimum contracts to generate a detail page
MIN_CONTRACTS = 2


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
        return f"£{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"£{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"£{value / 1_000:.0f}K"
    return f"£{value:,}"


SUPPLIER_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{supplier_name} - NHS Transparency</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .card {{ @apply bg-white rounded-lg shadow-md p-6 mb-6; }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <header class="bg-green-900 text-white py-6">
        <div class="container mx-auto px-4">
            <a href="index.html" class="text-green-300 hover:text-white text-sm">← Back to Dashboard</a>
            <span class="mx-2 text-green-500">|</span>
            <a href="suppliers.html" class="text-green-300 hover:text-white text-sm">All Suppliers</a>
            <h1 class="text-2xl font-bold mt-2">{supplier_name}</h1>
            <p class="text-green-200 mt-1">Supplier Contract Analysis</p>
        </div>
    </header>

    <main class="container mx-auto px-4 py-8">
        <!-- Summary Stats -->
        <section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="card text-center">
                <div class="text-3xl font-bold text-green-600">{total_contracts}</div>
                <div class="text-gray-600 text-sm">Total Contracts</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-blue-600">{total_value}</div>
                <div class="text-gray-600 text-sm">Total Awarded Value</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-purple-600">{unique_buyers}</div>
                <div class="text-gray-600 text-sm">NHS Organizations</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-gray-600">{date_range}</div>
                <div class="text-gray-600 text-sm">Contract Period</div>
            </div>
        </section>

        <!-- Top Buyers -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">NHS Organizations Served</h2>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead>
                        <tr class="border-b bg-gray-50">
                            <th class="text-left py-2 px-2">Organization</th>
                            <th class="text-right py-2 px-2">Contracts</th>
                            <th class="text-right py-2 px-2">Total Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {buyer_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- All Contracts -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">
                All Contracts
                <span class="text-gray-500 font-normal text-sm ml-2">({total_contracts} total)</span>
            </h2>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b bg-gray-50">
                            <th class="text-left py-2 px-2">Date</th>
                            <th class="text-left py-2 px-2">Buyer</th>
                            <th class="text-left py-2 px-2">Title</th>
                            <th class="text-right py-2 px-2">Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {contract_rows}
                    </tbody>
                </table>
            </div>
            {pagination}
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


def generate_supplier_page(conn: sqlite3.Connection, supplier_name: str, output_dir: Path) -> str:
    """Generate a detail page for a specific supplier."""
    cursor = conn.cursor()

    # Get summary stats - match case-insensitively
    cursor.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as total_value,
            COUNT(DISTINCT buyer_name) as unique_buyers,
            MIN(award_date) as earliest,
            MAX(award_date) as latest
        FROM contracts
        WHERE UPPER(supplier_name) = UPPER(?)
        """,
        (MAX_AWARDED_VALUE, supplier_name),
    )
    stats = cursor.fetchone()

    # Date range
    earliest = stats[3][:4] if stats[3] else "?"
    latest = stats[4][:4] if stats[4] else "?"
    date_range = f"{earliest}-{latest}" if earliest != latest else earliest

    # Get buyers for this supplier
    cursor.execute(
        """
        SELECT
            buyer_name,
            COUNT(*) as contract_count,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as total_value
        FROM contracts
        WHERE UPPER(supplier_name) = UPPER(?)
        GROUP BY buyer_name
        ORDER BY total_value DESC
        LIMIT 20
        """,
        (MAX_AWARDED_VALUE, supplier_name),
    )
    buyers = cursor.fetchall()

    buyer_rows = ""
    for row in buyers:
        name = (row[0][:50] + "...") if len(row[0]) > 50 else row[0]
        buyer_slug = slugify(row[0])
        value = format_value(row[2])
        buyer_rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2 px-2">
                    <a href="trust-{buyer_slug}.html" class="text-blue-600 hover:underline">{name}</a>
                </td>
                <td class="text-right py-2 px-2">{row[1]}</td>
                <td class="text-right py-2 px-2 font-semibold">{value}</td>
            </tr>
        """

    if not buyer_rows:
        buyer_rows = '<tr><td colspan="3" class="py-4 text-center text-gray-500">No buyer data available</td></tr>'

    # Get all contracts (up to 100)
    cursor.execute(
        """
        SELECT award_date, buyer_name, title, value_gbp, notice_url
        FROM contracts
        WHERE UPPER(supplier_name) = UPPER(?)
        ORDER BY award_date DESC, value_gbp DESC
        LIMIT 100
        """,
        (supplier_name,),
    )
    contracts = cursor.fetchall()

    contract_rows = ""
    for row in contracts:
        date = row[0][:10] if row[0] else "Unknown"
        buyer = (row[1][:35] + "...") if row[1] and len(row[1]) > 35 else (row[1] or "Unknown")
        buyer_slug = slugify(row[1]) if row[1] else ""
        title = (row[2][:45] + "...") if row[2] and len(row[2]) > 45 else (row[2] or "Unknown")
        value = format_value(row[3])

        if row[4]:
            title_html = f'<a href="{row[4]}" class="text-blue-600 hover:underline" target="_blank">{title}</a>'
        else:
            title_html = title

        buyer_html = (
            f'<a href="trust-{buyer_slug}.html" class="hover:underline">{buyer}</a>'
            if buyer_slug
            else buyer
        )

        contract_rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2 px-2">{date}</td>
                <td class="py-2 px-2">{buyer_html}</td>
                <td class="py-2 px-2">{title_html}</td>
                <td class="text-right py-2 px-2 font-semibold text-green-700">{value}</td>
            </tr>
        """

    if not contract_rows:
        contract_rows = '<tr><td colspan="4" class="py-4 text-center text-gray-500">No contracts found</td></tr>'

    # Pagination note
    pagination = ""
    if stats[0] > 100:
        pagination = (
            f'<p class="text-gray-500 text-sm mt-4">Showing 100 of {stats[0]} contracts</p>'
        )

    # Generate HTML
    slug = slugify(supplier_name)
    html = SUPPLIER_PAGE_TEMPLATE.format(
        supplier_name=supplier_name,
        total_contracts=stats[0],
        total_value=format_value(stats[1]),
        unique_buyers=stats[2],
        date_range=date_range,
        buyer_rows=buyer_rows,
        contract_rows=contract_rows,
        pagination=pagination,
    )

    # Write file
    output_path = output_dir / f"supplier-{slug}.html"
    output_path.write_text(html)

    return slug


def generate_supplier_index(suppliers: list[tuple], output_dir: Path) -> None:
    """Generate an index page listing all suppliers."""
    rows = ""
    for name, slug, total, total_value, buyer_count in suppliers:
        display_name = (name[:50] + "...") if len(name) > 50 else name
        rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2 px-2">
                    <a href="supplier-{slug}.html" class="text-blue-600 hover:underline">{display_name}</a>
                </td>
                <td class="text-right py-2 px-2">{total}</td>
                <td class="text-right py-2 px-2">{buyer_count}</td>
                <td class="text-right py-2 px-2 text-green-700 font-semibold">{format_value(total_value)}</td>
            </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Suppliers - NHS Transparency</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <header class="bg-green-900 text-white py-6">
        <div class="container mx-auto px-4">
            <a href="index.html" class="text-green-300 hover:text-white text-sm">← Back to Dashboard</a>
            <h1 class="text-2xl font-bold mt-2">NHS IT Suppliers</h1>
            <p class="text-green-200 mt-1">All suppliers with NHS contracts</p>
        </div>
    </header>

    <main class="container mx-auto px-4 py-8">
        <div class="bg-white rounded-lg shadow-md p-6">
            <p class="text-gray-600 mb-4">
                Select a supplier to see all their NHS contracts, including which organizations
                they serve and total contract values.
            </p>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead>
                        <tr class="border-b bg-gray-50">
                            <th class="text-left py-2 px-2">Supplier</th>
                            <th class="text-right py-2 px-2">Contracts</th>
                            <th class="text-right py-2 px-2">NHS Orgs</th>
                            <th class="text-right py-2 px-2">Total Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <footer class="bg-gray-800 text-gray-400 py-6">
        <div class="container mx-auto px-4 text-center">
            <p>NHS Transparency Project - Open Data for Public Good</p>
        </div>
    </footer>
</body>
</html>
"""

    output_path = output_dir / "suppliers.html"
    output_path.write_text(html)
    print(f"Generated supplier index: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate supplier detail pages")
    parser.add_argument("--db", type=Path, required=True, help="Database path")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output directory")

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    args.output.mkdir(parents=True, exist_ok=True)

    # Get all suppliers with enough contracts
    # Exclude special labels and consolidate case variations
    cursor = conn.execute(
        """
        SELECT
            MAX(supplier_name) as supplier_name,
            COUNT(*) as total,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as total_value,
            COUNT(DISTINCT buyer_name) as buyer_count
        FROM contracts
        WHERE supplier_name IS NOT NULL
          AND UPPER(supplier_name) NOT IN (
              'MULTIPLE SUPPLIERS (FRAMEWORK)',
              'PRE-PROCUREMENT (NO SUPPLIER YET)',
              'NOT SPECIFIED'
          )
          AND UPPER(supplier_name) NOT LIKE '%FRAMEWORK%'
          AND UPPER(supplier_name) NOT LIKE 'PLEASE SEE%'
          AND UPPER(supplier_name) NOT LIKE 'SEE ATTACHED%'
          AND UPPER(supplier_name) NOT LIKE 'VARIOUS%'
          AND LENGTH(supplier_name) > 3
        GROUP BY UPPER(supplier_name)
        HAVING total >= ?
        ORDER BY total_value DESC
        """,
        (MAX_AWARDED_VALUE, MIN_CONTRACTS),
    )
    supplier_rows = cursor.fetchall()

    suppliers = []
    for row in supplier_rows:
        supplier_name = row["supplier_name"]
        slug = generate_supplier_page(conn, supplier_name, args.output)
        suppliers.append(
            (supplier_name, slug, row["total"], row["total_value"], row["buyer_count"])
        )
        print(f"Generated: supplier-{slug}.html ({row['total']} contracts)")

    # Generate index
    generate_supplier_index(suppliers, args.output)

    conn.close()
    print(f"\nGenerated {len(suppliers)} supplier pages")


if __name__ == "__main__":
    main()
