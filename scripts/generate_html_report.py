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
        <section class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div class="card text-center">
                <div class="stat-value">{total_organizations:,}</div>
                <div class="stat-label">NHS Organizations</div>
            </div>
            <div class="card text-center">
                <div class="stat-value">{total_trusts:,}</div>
                <div class="stat-label">NHS Trusts</div>
            </div>
            <div class="card text-center">
                <div class="stat-value">{total_contracts:,}</div>
                <div class="stat-label">IT Contracts Tracked</div>
            </div>
            <div class="card text-center">
                <div class="stat-value">£{total_contract_value:,.0f}M</div>
                <div class="stat-label">Total Contract Value</div>
            </div>
        </section>

        <!-- Organization Types -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">NHS Organizations by Type</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <canvas id="orgTypeChart"></canvas>
                </div>
                <div>
                    <table class="w-full">
                        <thead>
                            <tr class="border-b">
                                <th class="text-left py-2">Type</th>
                                <th class="text-right py-2">Count</th>
                            </tr>
                        </thead>
                        <tbody>
                            {org_type_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- Supplier Analysis -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Top IT Suppliers by Contract Value</h2>
            {supplier_section}
        </section>

        <!-- Key Vendors -->
        <section class="card">
            <h2 class="text-xl font-semibold mb-4">Key Vendor Analysis</h2>
            <p class="text-gray-600 mb-4">Focus areas: Palantir (Federated Data Platform), TPP (SystmOne), EMIS</p>
            {vendor_analysis}
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
                Data is collected automatically from public sources including the NHS Organisation
                Data Service and Contracts Finder.
            </p>
            <p class="text-gray-600 text-sm">
                <a href="https://github.com/your-org/nhs-transparency" class="text-blue-600 hover:underline">
                    View source code on GitHub
                </a>
            </p>
        </section>
    </main>

    <footer class="bg-gray-800 text-gray-400 py-6">
        <div class="container mx-auto px-4 text-center">
            <p>NHS Transparency Project - Open Data for Public Good</p>
            <p class="text-sm mt-2">Data is sourced from public government APIs and is provided under the Open Government Licence</p>
        </div>
    </footer>

    <script>
        // Organization type chart
        const orgTypeData = {org_type_json};
        if (orgTypeData.labels.length > 0) {{
            new Chart(document.getElementById('orgTypeChart'), {{
                type: 'doughnut',
                data: {{
                    labels: orgTypeData.labels,
                    datasets: [{{
                        data: orgTypeData.values,
                        backgroundColor: [
                            '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            position: 'bottom'
                        }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>
"""


def generate_html_report(db_path: Path, output_path: Path) -> None:
    """Generate an HTML dashboard from the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Gather statistics
    cursor = conn.execute("SELECT COUNT(*) FROM organizations WHERE status = 'Active'")
    total_organizations = cursor.fetchone()[0]

    cursor = conn.execute(
        "SELECT COUNT(*) FROM organizations WHERE org_type = 'NHS Trust' AND status = 'Active'"
    )
    total_trusts = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*), SUM(COALESCE(value_gbp, 0)) FROM contracts")
    row = cursor.fetchone()
    total_contracts = row[0]
    total_contract_value = (row[1] or 0) / 1_000_000  # Convert to millions

    # Organization types
    cursor = conn.execute("""
        SELECT org_type, COUNT(*) as count
        FROM organizations
        WHERE status = 'Active'
        GROUP BY org_type
        ORDER BY count DESC
        LIMIT 6
    """)
    org_types = cursor.fetchall()

    org_type_rows = ""
    org_type_labels = []
    org_type_values = []
    for row in org_types:
        org_type_rows += f'<tr class="border-b"><td class="py-2">{row["org_type"]}</td><td class="text-right py-2">{row["count"]:,}</td></tr>'
        org_type_labels.append(row["org_type"])
        org_type_values.append(row["count"])

    org_type_json = json.dumps({"labels": org_type_labels, "values": org_type_values})

    # Supplier section
    if total_contracts > 0:
        cursor = conn.execute("""
            SELECT
                supplier_name,
                COUNT(*) as contract_count,
                SUM(COALESCE(value_gbp, 0)) as total_value
            FROM contracts
            WHERE supplier_name IS NOT NULL
            GROUP BY supplier_name
            ORDER BY total_value DESC
            LIMIT 10
        """)
        suppliers = cursor.fetchall()

        supplier_rows = ""
        for row in suppliers:
            value = f"£{row['total_value']:,}" if row["total_value"] else "Unknown"
            supplier_rows += f"""
                <tr class="border-b">
                    <td class="py-2">{row["supplier_name"]}</td>
                    <td class="text-right py-2">{row["contract_count"]}</td>
                    <td class="text-right py-2">{value}</td>
                </tr>
            """

        supplier_section = f"""
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
        """
    else:
        supplier_section = '<p class="text-gray-500">No contract data loaded yet. Run the data collection workflow.</p>'

    # Vendor analysis
    key_vendors = ["Palantir", "TPP", "EMIS", "Cerner", "Epic"]
    vendor_cards = []
    for vendor in key_vendors:
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as contract_count,
                SUM(COALESCE(value_gbp, 0)) as total_value
            FROM contracts
            WHERE UPPER(supplier_name) LIKE UPPER(?)
               OR UPPER(title) LIKE UPPER(?)
        """,
            (f"%{vendor}%", f"%{vendor}%"),
        )
        result = cursor.fetchone()

        if result["contract_count"] > 0:
            value = f"£{result['total_value']:,}" if result["total_value"] else "Unknown"
            vendor_cards.append(f"""
                <div class="bg-gray-50 rounded-lg p-4">
                    <h3 class="font-semibold text-lg">{vendor}</h3>
                    <p class="text-gray-600">{result["contract_count"]} contracts</p>
                    <p class="text-blue-600 font-semibold">{value}</p>
                </div>
            """)
        else:
            vendor_cards.append(f"""
                <div class="bg-gray-50 rounded-lg p-4">
                    <h3 class="font-semibold text-lg">{vendor}</h3>
                    <p class="text-gray-400">No contracts found</p>
                </div>
            """)

    vendor_analysis = (
        f'<div class="grid grid-cols-1 md:grid-cols-5 gap-4">{"".join(vendor_cards)}</div>'
    )

    # Data sources
    data_source_rows = ""

    cursor = conn.execute("SELECT COUNT(*), MAX(updated_at) FROM organizations")
    row = cursor.fetchone()
    data_source_rows += f'<tr class="border-b"><td class="py-2">NHS ODS</td><td class="text-right py-2">{row[0]:,}</td><td class="text-right py-2">{row[1] or "N/A"}</td></tr>'

    cursor = conn.execute("SELECT COUNT(*), MAX(created_at) FROM contracts")
    row = cursor.fetchone()
    data_source_rows += f'<tr class="border-b"><td class="py-2">Contracts Finder</td><td class="text-right py-2">{row[0]:,}</td><td class="text-right py-2">{row[1] or "N/A"}</td></tr>'

    cursor = conn.execute("SELECT COUNT(*), MAX(created_at) FROM trust_financials")
    row = cursor.fetchone()
    data_source_rows += f'<tr class="border-b"><td class="py-2">Trust Financials</td><td class="text-right py-2">{row[0]:,}</td><td class="text-right py-2">{row[1] or "N/A"}</td></tr>'

    cursor = conn.execute("SELECT COUNT(*), MAX(created_at) FROM pfi_contracts")
    row = cursor.fetchone()
    data_source_rows += f'<tr><td class="py-2">PFI Contracts</td><td class="text-right py-2">{row[0]:,}</td><td class="text-right py-2">{row[1] or "N/A"}</td></tr>'

    conn.close()

    # Generate HTML
    html = HTML_TEMPLATE.format(
        generated_date=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        total_organizations=total_organizations,
        total_trusts=total_trusts,
        total_contracts=total_contracts,
        total_contract_value=total_contract_value,
        org_type_rows=org_type_rows,
        org_type_json=org_type_json,
        supplier_section=supplier_section,
        vendor_analysis=vendor_analysis,
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
