#!/usr/bin/env python3
"""
Generate an HTML dashboard from the NHS transparency database.

Creates a static HTML page with charts and tables for GitHub Pages.
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Maximum value to include in aggregations (£200M)
# Higher values are often framework ceilings, not actual spend
# Note: Some legitimate large contracts may be excluded, but this gives
# more accurate totals than including framework ceiling values
MAX_AGGREGATION_VALUE = 200_000_000

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NHS Transparency Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .card {{ @apply bg-white rounded-lg shadow-md p-6 mb-6; }}
        .stat-value {{ @apply text-3xl font-bold text-blue-600; }}
        .stat-label {{ @apply text-gray-600 text-sm; }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <header class="bg-blue-900 text-white py-8">
        <div class="container mx-auto px-4">
            <h1 class="text-3xl font-bold">NHS Transparency Dashboard</h1>
            <p class="text-blue-200 mt-2">Tracking IT spending and contracts across the NHS</p>
            <p class="text-blue-300 text-sm mt-1">Last updated: {generated_date}</p>
        </div>
    </header>

    <main class="container mx-auto px-4 py-8">
        <!-- Key Statistics -->
        <section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="card text-center">
                <div class="stat-value">{total_contracts:,}</div>
                <div class="stat-label">Contracts Tracked</div>
            </div>
            <div class="card text-center">
                <div class="stat-value">£{total_contract_value:,.0f}M</div>
                <div class="stat-label">Awarded Contract Value*</div>
            </div>
            <div class="card text-center">
                <div class="stat-value">{unique_buyers:,}</div>
                <div class="stat-label">NHS Buyers</div>
            </div>
            <div class="card text-center">
                <div class="stat-value">{unique_suppliers:,}</div>
                <div class="stat-label">Suppliers</div>
            </div>
        </section>

        <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6 text-sm text-yellow-800">
            <strong>*Note on values:</strong> Contract values are from awarded amounts where available.
            Framework agreements (which set maximum ceilings, not actual spend) are excluded from totals
            when they exceed £200M, as many frameworks are set to high ceiling values that don't reflect
            actual spending. See the Framework Agreements section below for high-value frameworks.
        </div>

        <!-- Top Vendors -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Top Vendors by Contract Value</h2>
            <p class="text-gray-600 mb-4">Largest suppliers by awarded contract value (excludes framework ceilings)</p>
            {vendor_analysis}
        </section>

        <!-- Spending by Year -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Contract Awards by Year</h2>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div style="height: 300px;">
                    <canvas id="yearlySpendChart"></canvas>
                </div>
                <div>
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="border-b">
                                <th class="text-left py-2">Year</th>
                                <th class="text-right py-2">Contracts</th>
                                <th class="text-right py-2">Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {yearly_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- Top Buyers -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Top NHS Buyers by Contract Value</h2>
            <p class="text-gray-500 text-sm mb-3">
                Excludes framework ceiling values over £200M.
                <a href="trusts.html" class="text-blue-600 hover:underline">View all organizations →</a>
            </p>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead>
                        <tr class="border-b">
                            <th class="text-left py-2">Organisation</th>
                            <th class="text-right py-2">Contracts</th>
                            <th class="text-right py-2">Awarded Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {buyer_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Top Suppliers -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Top Suppliers by Contract Value</h2>
            <p class="text-gray-500 text-sm mb-3">Excludes framework ceiling values over £200M</p>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead>
                        <tr class="border-b">
                            <th class="text-left py-2">Supplier</th>
                            <th class="text-right py-2">Contracts</th>
                            <th class="text-right py-2">Awarded Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {supplier_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Recent Large Contracts -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Recent Large Contracts (£10M - £200M)</h2>
            <p class="text-gray-500 text-sm mb-3">Actual contract awards, excluding framework ceilings</p>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b">
                            <th class="text-left py-2">Date</th>
                            <th class="text-left py-2">Buyer</th>
                            <th class="text-left py-2">Supplier</th>
                            <th class="text-left py-2">Title</th>
                            <th class="text-right py-2">Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {large_contracts_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Contract Value Distribution -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Contract Value Distribution</h2>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div style="height: 300px;">
                    <canvas id="valueDistChart"></canvas>
                </div>
                <div>
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="border-b">
                                <th class="text-left py-2">Value Range</th>
                                <th class="text-right py-2">Contracts</th>
                                <th class="text-right py-2">Total Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {value_dist_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- Framework Agreements -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Framework Agreements (High Ceiling Values)</h2>
            <p class="text-gray-600 mb-4">
                Framework agreements set maximum spending limits but don't represent actual spend.
                Individual call-off contracts under these frameworks are tracked separately when published.
            </p>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b bg-gray-50">
                            <th class="text-left py-2">Framework</th>
                            <th class="text-left py-2">Buyer</th>
                            <th class="text-right py-2">Ceiling Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {framework_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Data Sources -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Data Sources</h2>
            <table class="w-full">
                <thead>
                    <tr class="border-b">
                        <th class="text-left py-2">Source</th>
                        <th class="text-right py-2">Records</th>
                        <th class="text-right py-2">Last Updated</th>
                    </tr>
                </thead>
                <tbody>
                    {data_source_rows}
                </tbody>
            </table>
        </section>

        <!-- About -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">About This Project</h2>
            <p class="text-gray-700 mb-4">
                This dashboard tracks NHS IT spending to promote transparency and support
                advocacy for open source and UK-based alternatives to proprietary US software.
            </p>
            <p class="text-gray-700 mb-4">
                Data is collected automatically from Contracts Finder, filtering for awarded
                contracts from NHS organisations.
            </p>
            <p class="text-gray-600 text-sm">
                <a href="https://github.com/robtaylor/nhs-transparency" class="text-blue-600 hover:underline">
                    View source code on GitHub
                </a>
            </p>
        </section>
    </main>

    <footer class="bg-gray-800 text-gray-400 py-6">
        <div class="container mx-auto px-4 text-center">
            <p>NHS Transparency Project - Open Data for Public Good</p>
            <p class="text-sm mt-2">Data is sourced from public government APIs under the Open Government Licence</p>
        </div>
    </footer>

    <script>
        // Yearly spending chart
        const yearlyData = {yearly_json};
        if (yearlyData.labels.length > 0) {{
            new Chart(document.getElementById('yearlySpendChart'), {{
                type: 'bar',
                data: {{
                    labels: yearlyData.labels,
                    datasets: [{{
                        label: 'Contract Value (£M)',
                        data: yearlyData.values,
                        backgroundColor: '#3B82F6'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{
                                callback: function(value) {{
                                    return '£' + value.toLocaleString() + 'M';
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}

        // Value distribution chart
        const valueDistData = {value_dist_json};
        if (valueDistData.labels.length > 0) {{
            new Chart(document.getElementById('valueDistChart'), {{
                type: 'doughnut',
                data: {{
                    labels: valueDistData.labels,
                    datasets: [{{
                        data: valueDistData.counts,
                        backgroundColor: [
                            '#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'right'
                        }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>
"""


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


def generate_html_report(db_path: Path, output_path: Path) -> None:
    """Generate an HTML dashboard from the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Basic statistics - exclude very high values (framework ceilings)
    cursor = conn.execute(
        """
        SELECT COUNT(*), SUM(COALESCE(value_gbp, 0))
        FROM contracts
        WHERE value_gbp IS NULL OR value_gbp <= ?
        """,
        (MAX_AGGREGATION_VALUE,),
    )
    row = cursor.fetchone()
    total_contracts = row[0]
    total_contract_value = (row[1] or 0) / 1_000_000

    cursor = conn.execute("SELECT COUNT(DISTINCT buyer_name) FROM contracts")
    unique_buyers = cursor.fetchone()[0]

    cursor = conn.execute(
        "SELECT COUNT(DISTINCT supplier_name) FROM contracts WHERE supplier_name IS NOT NULL"
    )
    unique_suppliers = cursor.fetchone()[0]

    # Top vendors by contract value (dynamic, not hardcoded)
    # Exclude special labels and bad data entries
    # Group by case-insensitive name to consolidate duplicates like "AbbVie Ltd" / "ABBVIE LTD"
    cursor = conn.execute(
        """
        SELECT
            MAX(supplier_name) as supplier_name,
            COUNT(*) as contract_count,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as total_value
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
        HAVING total_value > 0
        ORDER BY total_value DESC
        LIMIT 5
        """,
        (MAX_AGGREGATION_VALUE,),
    )
    top_vendors = cursor.fetchall()

    vendor_cards = []
    for row in top_vendors:
        supplier = row["supplier_name"]
        # Truncate long names
        display_name = (supplier[:25] + "...") if len(supplier) > 25 else supplier
        value = format_value(row["total_value"])
        vendor_cards.append(f"""
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h3 class="font-semibold text-lg text-blue-800" title="{supplier}">{display_name}</h3>
                <p class="text-gray-700 mt-2">{row["contract_count"]} contracts</p>
                <p class="text-blue-600 font-bold text-xl">{value}</p>
            </div>
        """)

    vendor_analysis = f'<div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">{"".join(vendor_cards)}</div>'

    # Yearly spending - exclude very high values
    cursor = conn.execute(
        """
        SELECT
            strftime('%Y', award_date) as year,
            COUNT(*) as contracts,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) / 1000000.0 as value_millions
        FROM contracts
        WHERE award_date IS NOT NULL
        GROUP BY year
        ORDER BY year
    """,
        (MAX_AGGREGATION_VALUE,),
    )
    yearly_data = cursor.fetchall()

    yearly_rows = ""
    yearly_labels = []
    yearly_values = []
    for row in yearly_data:
        yearly_rows += f'<tr class="border-b"><td class="py-1">{row["year"]}</td><td class="text-right py-1">{row["contracts"]:,}</td><td class="text-right py-1">£{row["value_millions"]:,.1f}M</td></tr>'
        yearly_labels.append(row["year"])
        yearly_values.append(round(row["value_millions"], 1))

    yearly_json = json.dumps({"labels": yearly_labels, "values": yearly_values})

    # Top buyers - exclude very high values
    cursor = conn.execute(
        """
        SELECT
            buyer_name,
            COUNT(*) as contract_count,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as total_value
        FROM contracts
        GROUP BY buyer_name
        ORDER BY total_value DESC
        LIMIT 15
    """,
        (MAX_AGGREGATION_VALUE,),
    )
    buyers = cursor.fetchall()

    buyer_rows = ""
    for row in buyers:
        value = format_value(row["total_value"])
        # Truncate long names
        name = row["buyer_name"][:60] + "..." if len(row["buyer_name"]) > 60 else row["buyer_name"]
        buyer_rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2">{name}</td>
                <td class="text-right py-2">{row["contract_count"]}</td>
                <td class="text-right py-2 font-semibold">{value}</td>
            </tr>
        """

    # Top suppliers - exclude very high values, group case-insensitively
    cursor = conn.execute(
        """
        SELECT
            MAX(supplier_name) as supplier_name,
            COUNT(*) as contract_count,
            SUM(CASE WHEN value_gbp <= ? THEN COALESCE(value_gbp, 0) ELSE 0 END) as total_value
        FROM contracts
        WHERE supplier_name IS NOT NULL
        GROUP BY UPPER(supplier_name)
        ORDER BY total_value DESC
        LIMIT 15
    """,
        (MAX_AGGREGATION_VALUE,),
    )
    suppliers = cursor.fetchall()

    supplier_rows = ""
    for row in suppliers:
        value = format_value(row["total_value"])
        name = (
            row["supplier_name"][:50] + "..."
            if len(row["supplier_name"]) > 50
            else row["supplier_name"]
        )
        supplier_rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2">{name}</td>
                <td class="text-right py-2">{row["contract_count"]}</td>
                <td class="text-right py-2 font-semibold">{value}</td>
            </tr>
        """

    # Recent large contracts - only include reasonable values
    cursor = conn.execute(
        """
        SELECT
            award_date,
            buyer_name,
            supplier_name,
            title,
            value_gbp,
            notice_url
        FROM contracts
        WHERE value_gbp >= 10000000 AND value_gbp <= ?
        ORDER BY award_date DESC
        LIMIT 20
    """,
        (MAX_AGGREGATION_VALUE,),
    )
    large_contracts = cursor.fetchall()

    large_contracts_rows = ""
    for row in large_contracts:
        value = format_value(row["value_gbp"])
        buyer = (
            row["buyer_name"][:30] + "..."
            if len(row["buyer_name"] or "") > 30
            else (row["buyer_name"] or "Unknown")
        )
        supplier = (
            row["supplier_name"][:30] + "..."
            if len(row["supplier_name"] or "") > 30
            else (row["supplier_name"] or "Not specified")
        )
        title = (
            row["title"][:50] + "..."
            if len(row["title"] or "") > 50
            else (row["title"] or "Unknown")
        )
        date = row["award_date"][:10] if row["award_date"] else "Unknown"

        if row["notice_url"]:
            title_html = f'<a href="{row["notice_url"]}" class="text-blue-600 hover:underline" target="_blank">{title}</a>'
        else:
            title_html = title

        large_contracts_rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2">{date}</td>
                <td class="py-2">{buyer}</td>
                <td class="py-2">{supplier}</td>
                <td class="py-2">{title_html}</td>
                <td class="text-right py-2 font-semibold">{value}</td>
            </tr>
        """

    if not large_contracts_rows:
        large_contracts_rows = '<tr><td colspan="5" class="py-4 text-center text-gray-500">No contracts between £10M and £200M found</td></tr>'

    # Framework agreements (high ceiling values)
    cursor = conn.execute(
        """
        SELECT
            title,
            buyer_name,
            value_gbp,
            notice_url
        FROM contracts
        WHERE value_gbp > ?
        ORDER BY value_gbp DESC
        LIMIT 15
    """,
        (MAX_AGGREGATION_VALUE,),
    )
    frameworks = cursor.fetchall()

    framework_rows = ""
    for row in frameworks:
        value = format_value(row["value_gbp"])
        buyer = (
            row["buyer_name"][:40] + "..."
            if len(row["buyer_name"] or "") > 40
            else (row["buyer_name"] or "Unknown")
        )
        title = (
            row["title"][:60] + "..."
            if len(row["title"] or "") > 60
            else (row["title"] or "Unknown")
        )

        if row["notice_url"]:
            title_html = f'<a href="{row["notice_url"]}" class="text-blue-600 hover:underline" target="_blank">{title}</a>'
        else:
            title_html = title

        framework_rows += f"""
            <tr class="border-b hover:bg-gray-50">
                <td class="py-2">{title_html}</td>
                <td class="py-2">{buyer}</td>
                <td class="text-right py-2 text-gray-500">{value}</td>
            </tr>
        """

    if not framework_rows:
        framework_rows = '<tr><td colspan="3" class="py-4 text-center text-gray-500">No high-value contracts over £200M found</td></tr>'

    # Contract value distribution - only include reasonable values
    value_ranges = [
        ("Under £100K", 0, 100_000),
        ("£100K - £1M", 100_000, 1_000_000),
        ("£1M - £10M", 1_000_000, 10_000_000),
        ("£10M - £100M", 10_000_000, 100_000_000),
        ("£100M - £200M", 100_000_000, MAX_AGGREGATION_VALUE),
    ]

    value_dist_rows = ""
    value_dist_labels = []
    value_dist_counts = []

    for label, min_val, max_val in value_ranges:
        cursor = conn.execute(
            "SELECT COUNT(*), SUM(COALESCE(value_gbp, 0)) FROM contracts WHERE value_gbp >= ? AND value_gbp < ?",
            (min_val, max_val),
        )
        row = cursor.fetchone()
        count = row[0]
        total = row[1] or 0

        if count > 0:
            value_dist_rows += f'<tr class="border-b"><td class="py-1">{label}</td><td class="text-right py-1">{count:,}</td><td class="text-right py-1">{format_value(total)}</td></tr>'
            value_dist_labels.append(label)
            value_dist_counts.append(count)

    value_dist_json = json.dumps({"labels": value_dist_labels, "counts": value_dist_counts})

    # Data sources
    data_source_rows = ""

    cursor = conn.execute("SELECT COUNT(*), MAX(updated_at) FROM organizations")
    row = cursor.fetchone()
    data_source_rows += f'<tr class="border-b"><td class="py-2">NHS ODS (Organizations)</td><td class="text-right py-2">{row[0]:,}</td><td class="text-right py-2">{row[1] or "N/A"}</td></tr>'

    cursor = conn.execute("SELECT COUNT(*), MAX(created_at) FROM contracts")
    row = cursor.fetchone()
    data_source_rows += f'<tr class="border-b"><td class="py-2">Contracts Finder</td><td class="text-right py-2">{row[0]:,}</td><td class="text-right py-2">{row[1] or "N/A"}</td></tr>'

    conn.close()

    # Generate HTML
    html = HTML_TEMPLATE.format(
        generated_date=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        total_contracts=total_contracts,
        total_contract_value=total_contract_value,
        unique_buyers=unique_buyers,
        unique_suppliers=unique_suppliers,
        vendor_analysis=vendor_analysis,
        yearly_rows=yearly_rows,
        yearly_json=yearly_json,
        buyer_rows=buyer_rows,
        supplier_rows=supplier_rows,
        large_contracts_rows=large_contracts_rows,
        framework_rows=framework_rows,
        value_dist_rows=value_dist_rows,
        value_dist_json=value_dist_json,
        data_source_rows=data_source_rows,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    print(f"HTML report generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate NHS transparency HTML dashboard")
    parser.add_argument("--db", type=Path, required=True, help="Database path")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output HTML path")

    args = parser.parse_args()
    generate_html_report(args.db, args.output)


if __name__ == "__main__":
    main()
