#!/usr/bin/env python3
"""
Generate individual trust detail pages showing contract breakdowns.

Creates a page for each NHS trust/buyer with significant contract activity,
clearly separating awarded contracts from framework ceiling values.
"""

import argparse
import re
import sqlite3
from pathlib import Path

# Maximum value considered as "awarded" vs "framework ceiling"
MAX_AWARDED_VALUE = 200_000_000

# Minimum contracts to generate a detail page
MIN_CONTRACTS = 5


def slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    # Remove special characters, convert to lowercase, replace spaces with hyphens
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:80]  # Limit length


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


TRUST_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{trust_name} - NHS Transparency</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .card {{ @apply bg-white rounded-lg shadow-md p-6 mb-6; }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <header class="bg-blue-900 text-white py-6">
        <div class="container mx-auto px-4">
            <a href="index.html" class="text-blue-300 hover:text-white text-sm">← Back to Dashboard</a>
            <h1 class="text-2xl font-bold mt-2">{trust_name}</h1>
            <p class="text-blue-200 mt-1">Contract Analysis</p>
        </div>
    </header>

    <main class="container mx-auto px-4 py-8">
        <!-- Summary Stats -->
        <section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="card text-center">
                <div class="text-3xl font-bold text-blue-600">{total_contracts}</div>
                <div class="text-gray-600 text-sm">Total Contracts</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-green-600">{awarded_value}</div>
                <div class="text-gray-600 text-sm">Awarded Value</div>
                <div class="text-gray-400 text-xs mt-1">{awarded_count} contracts</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-orange-500">{ceiling_value}</div>
                <div class="text-gray-600 text-sm">Framework Ceilings</div>
                <div class="text-gray-400 text-xs mt-1">{ceiling_count} frameworks</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-purple-600">{unique_suppliers}</div>
                <div class="text-gray-600 text-sm">Unique Suppliers</div>
            </div>
        </section>

        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-sm text-blue-800">
            <strong>Understanding this data:</strong> "Awarded Value" shows actual contract awards.
            "Framework Ceilings" shows maximum potential spend under framework agreements -
            actual spending under these frameworks is typically much lower and happens via call-off contracts.
        </div>

        <!-- Awarded Contracts -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4 text-green-700">
                Awarded Contracts
                <span class="text-gray-500 font-normal text-sm ml-2">(Actual spending)</span>
            </h2>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b bg-gray-50">
                            <th class="text-left py-2 px-2">Date</th>
                            <th class="text-left py-2 px-2">Supplier</th>
                            <th class="text-left py-2 px-2">Title</th>
                            <th class="text-right py-2 px-2">Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {awarded_rows}
                    </tbody>
                </table>
            </div>
            {awarded_pagination}
        </section>

        <!-- Framework Agreements -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4 text-orange-600">
                Framework Agreements
                <span class="text-gray-500 font-normal text-sm ml-2">(Ceiling values - not actual spend)</span>
            </h2>
            <p class="text-gray-600 mb-4 text-sm">
                These are maximum spending limits under framework agreements.
                Individual call-off contracts are tracked separately when published.
            </p>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b bg-orange-50">
                            <th class="text-left py-2 px-2">Date</th>
                            <th class="text-left py-2 px-2">Framework</th>
                            <th class="text-right py-2 px-2">Ceiling Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {ceiling_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Top Suppliers -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Top Suppliers by Awarded Value</h2>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead>
                        <tr class="border-b">
                            <th class="text-left py-2">Supplier</th>
                            <th class="text-right py-2">Contracts</th>
                            <th class="text-right py-2">Total Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {supplier_rows}
                    </tbody>
                </table>
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


def generate_trust_page(conn: sqlite3.Connection, buyer_name: str, output_dir: Path) -> str:
    """Generate a detail page for a specific trust."""
    cursor = conn.cursor()

    # Get summary stats
    cursor.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN value_gbp <= ? THEN 1 ELSE 0 END) as awarded_count,
            SUM(CASE WHEN value_gbp > ? THEN 1 ELSE 0 END) as ceiling_count,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as awarded_value,
            SUM(CASE WHEN value_gbp > ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as ceiling_value,
            COUNT(DISTINCT supplier_name) as unique_suppliers
        FROM contracts
        WHERE buyer_name = ?
        """,
        (MAX_AWARDED_VALUE, MAX_AWARDED_VALUE, MAX_AWARDED_VALUE, MAX_AWARDED_VALUE, buyer_name),
    )
    stats = cursor.fetchone()

    # Get awarded contracts (up to 50 most recent)
    cursor.execute(
        """
        SELECT award_date, supplier_name, title, value_gbp, notice_url
        FROM contracts
        WHERE buyer_name = ? AND value_gbp <= ?
        ORDER BY award_date DESC, value_gbp DESC
        LIMIT 50
        """,
        (buyer_name, MAX_AWARDED_VALUE),
    )
    awarded_contracts = cursor.fetchall()

    awarded_rows = ""
    for row in awarded_contracts:
        date = row[0][:10] if row[0] else "Unknown"
        supplier = (row[1][:40] + "...") if row[1] and len(row[1]) > 40 else (row[1] or "Not specified")
        title = (row[2][:50] + "...") if row[2] and len(row[2]) > 50 else (row[2] or "Unknown")
        value = format_value(row[3])

        if row[4]:
            title_html = f'<a href="{row[4]}" class="text-blue-600 hover:underline" target="_blank">{title}</a>'
        else:
            title_html = title

        awarded_rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2 px-2">{date}</td>
                <td class="py-2 px-2">{supplier}</td>
                <td class="py-2 px-2">{title_html}</td>
                <td class="text-right py-2 px-2 font-semibold text-green-700">{value}</td>
            </tr>
        """

    if not awarded_rows:
        awarded_rows = '<tr><td colspan="4" class="py-4 text-center text-gray-500">No awarded contracts found</td></tr>'

    # Pagination note if there are more
    awarded_pagination = ""
    if stats[1] > 50:
        awarded_pagination = f'<p class="text-gray-500 text-sm mt-4">Showing 50 of {stats[1]} awarded contracts</p>'

    # Get framework agreements (ceiling values)
    cursor.execute(
        """
        SELECT award_date, title, value_gbp, notice_url
        FROM contracts
        WHERE buyer_name = ? AND value_gbp > ?
        ORDER BY value_gbp DESC
        """,
        (buyer_name, MAX_AWARDED_VALUE),
    )
    ceiling_contracts = cursor.fetchall()

    ceiling_rows = ""
    for row in ceiling_contracts:
        date = row[0][:10] if row[0] else "Unknown"
        title = (row[1][:70] + "...") if row[1] and len(row[1]) > 70 else (row[1] or "Unknown")
        value = format_value(row[2])

        if row[3]:
            title_html = f'<a href="{row[3]}" class="text-blue-600 hover:underline" target="_blank">{title}</a>'
        else:
            title_html = title

        ceiling_rows += f"""
            <tr class="border-b hover:bg-orange-50">
                <td class="py-2 px-2">{date}</td>
                <td class="py-2 px-2">{title_html}</td>
                <td class="text-right py-2 px-2 font-semibold text-orange-600">{value}</td>
            </tr>
        """

    if not ceiling_rows:
        ceiling_rows = '<tr><td colspan="3" class="py-4 text-center text-gray-500">No framework agreements over £200M</td></tr>'

    # Get top suppliers - group case-insensitively
    cursor.execute(
        """
        SELECT
            MAX(supplier_name) as supplier_name,
            COUNT(*) as contract_count,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as total_value
        FROM contracts
        WHERE buyer_name = ? AND supplier_name IS NOT NULL
        GROUP BY UPPER(supplier_name)
        ORDER BY total_value DESC
        LIMIT 10
        """,
        (MAX_AWARDED_VALUE, buyer_name),
    )
    suppliers = cursor.fetchall()

    supplier_rows = ""
    for row in suppliers:
        name = (row[0][:50] + "...") if len(row[0]) > 50 else row[0]
        value = format_value(row[2])
        supplier_rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2">{name}</td>
                <td class="text-right py-2">{row[1]}</td>
                <td class="text-right py-2 font-semibold">{value}</td>
            </tr>
        """

    if not supplier_rows:
        supplier_rows = '<tr><td colspan="3" class="py-4 text-center text-gray-500">No supplier data available</td></tr>'

    # Generate HTML
    slug = slugify(buyer_name)
    html = TRUST_PAGE_TEMPLATE.format(
        trust_name=buyer_name,
        total_contracts=stats[0],
        awarded_count=stats[1],
        awarded_value=format_value(stats[3]),
        ceiling_count=stats[2],
        ceiling_value=format_value(stats[4]),
        unique_suppliers=stats[5],
        awarded_rows=awarded_rows,
        awarded_pagination=awarded_pagination,
        ceiling_rows=ceiling_rows,
        supplier_rows=supplier_rows,
    )

    # Write file
    output_path = output_dir / f"trust-{slug}.html"
    output_path.write_text(html)

    return slug


def generate_trust_index(trusts: list[tuple], output_dir: Path) -> None:
    """Generate an index page listing all trusts."""
    rows = ""
    for name, slug, total, awarded_val, ceiling_val in trusts:
        display_name = (name[:60] + "...") if len(name) > 60 else name
        rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2">
                    <a href="trust-{slug}.html" class="text-blue-600 hover:underline">{display_name}</a>
                </td>
                <td class="text-right py-2">{total}</td>
                <td class="text-right py-2 text-green-700">{format_value(awarded_val)}</td>
                <td class="text-right py-2 text-orange-600">{format_value(ceiling_val)}</td>
            </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NHS Trusts - NHS Transparency</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <header class="bg-blue-900 text-white py-6">
        <div class="container mx-auto px-4">
            <a href="index.html" class="text-blue-300 hover:text-white text-sm">← Back to Dashboard</a>
            <h1 class="text-2xl font-bold mt-2">NHS Trust Contract Analysis</h1>
            <p class="text-blue-200 mt-1">Drill down into individual organizations</p>
        </div>
    </header>

    <main class="container mx-auto px-4 py-8">
        <div class="bg-white rounded-lg shadow-md p-6">
            <p class="text-gray-600 mb-4">
                Select an organization to see detailed contract breakdown, including the distinction
                between awarded contract values and framework ceiling values.
            </p>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead>
                        <tr class="border-b bg-gray-50">
                            <th class="text-left py-2">Organization</th>
                            <th class="text-right py-2">Contracts</th>
                            <th class="text-right py-2">Awarded Value</th>
                            <th class="text-right py-2">Framework Ceilings</th>
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

    output_path = output_dir / "trusts.html"
    output_path.write_text(html)
    print(f"Generated trust index: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate NHS trust detail pages")
    parser.add_argument("--db", type=Path, required=True, help="Database path")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output directory")

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    args.output.mkdir(parents=True, exist_ok=True)

    # Get all buyers with enough contracts
    cursor = conn.execute(
        """
        SELECT
            buyer_name,
            COUNT(*) as total,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as awarded_value,
            SUM(CASE WHEN value_gbp > ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as ceiling_value
        FROM contracts
        GROUP BY buyer_name
        HAVING total >= ?
        ORDER BY total DESC
        """,
        (MAX_AWARDED_VALUE, MAX_AWARDED_VALUE, MIN_CONTRACTS),
    )
    buyers = cursor.fetchall()

    trusts = []
    for row in buyers:
        buyer_name = row["buyer_name"]
        slug = generate_trust_page(conn, buyer_name, args.output)
        trusts.append((buyer_name, slug, row["total"], row["awarded_value"], row["ceiling_value"]))
        print(f"Generated: trust-{slug}.html ({row['total']} contracts)")

    # Generate index
    generate_trust_index(trusts, args.output)

    conn.close()
    print(f"\nGenerated {len(trusts)} trust pages")


if __name__ == "__main__":
    main()
