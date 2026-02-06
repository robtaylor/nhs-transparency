#!/usr/bin/env python3
"""
Generate a markdown report from the NHS transparency database.

Produces summary statistics and highlights for advocacy purposes.
"""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


def generate_report(db_path: Path, output_path: Path) -> None:
    """Generate a markdown report from the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    report_lines = [
        "# NHS Transparency Report",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
    ]

    # Organization statistics
    report_lines.extend(
        [
            "## NHS Organizations",
            "",
        ]
    )

    cursor = conn.execute("""
        SELECT org_type, COUNT(*) as count
        FROM organizations
        WHERE status = 'Active'
        GROUP BY org_type
        ORDER BY count DESC
    """)
    org_stats = cursor.fetchall()

    report_lines.append("| Organization Type | Count |")
    report_lines.append("|-------------------|-------|")
    total_orgs = 0
    for row in org_stats:
        report_lines.append(f"| {row['org_type']} | {row['count']:,} |")
        total_orgs += row["count"]
    report_lines.append(f"| **Total** | **{total_orgs:,}** |")
    report_lines.append("")

    # Contract statistics
    cursor = conn.execute("SELECT COUNT(*) FROM contracts")
    contract_count = cursor.fetchone()[0]

    if contract_count > 0:
        report_lines.extend(
            [
                "## IT Contracts",
                "",
            ]
        )

        # Top suppliers by value
        cursor = conn.execute("""
            SELECT
                supplier_name,
                COUNT(*) as contract_count,
                SUM(COALESCE(value_gbp, 0)) as total_value
            FROM contracts
            WHERE supplier_name IS NOT NULL
            GROUP BY supplier_name
            ORDER BY total_value DESC
            LIMIT 20
        """)
        suppliers = cursor.fetchall()

        if suppliers:
            report_lines.append("### Top Suppliers by Contract Value")
            report_lines.append("")
            report_lines.append("| Supplier | Contracts | Total Value |")
            report_lines.append("|----------|-----------|-------------|")
            for row in suppliers:
                value = f"£{row['total_value']:,}" if row["total_value"] else "Unknown"
                report_lines.append(
                    f"| {row['supplier_name']} | {row['contract_count']} | {value} |"
                )
            report_lines.append("")

        # Key vendors of interest
        report_lines.append("### Key Vendors Analysis")
        report_lines.append("")

        key_vendors = ["Palantir", "TPP", "EMIS", "Cerner", "Epic"]
        for vendor in key_vendors:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as contract_count,
                    SUM(COALESCE(value_gbp, 0)) as total_value,
                    MIN(award_date) as earliest,
                    MAX(award_date) as latest
                FROM contracts
                WHERE UPPER(supplier_name) LIKE UPPER(?)
                   OR UPPER(title) LIKE UPPER(?)
            """,
                (f"%{vendor}%", f"%{vendor}%"),
            )
            result = cursor.fetchone()

            if result["contract_count"] > 0:
                report_lines.append(f"**{vendor}**")
                report_lines.append(f"- Contracts: {result['contract_count']}")
                if result["total_value"]:
                    report_lines.append(f"- Total value: £{result['total_value']:,}")
                if result["earliest"]:
                    report_lines.append(f"- Date range: {result['earliest']} to {result['latest']}")
                report_lines.append("")

        # Recent large contracts
        cursor = conn.execute("""
            SELECT
                title,
                buyer_name,
                supplier_name,
                value_gbp,
                award_date
            FROM contracts
            WHERE value_gbp > 1000000
            ORDER BY award_date DESC
            LIMIT 10
        """)
        large_contracts = cursor.fetchall()

        if large_contracts:
            report_lines.append("### Recent Large Contracts (>£1M)")
            report_lines.append("")
            for row in large_contracts:
                report_lines.append(f"- **{row['title'][:80]}**")
                report_lines.append(f"  - Buyer: {row['buyer_name']}")
                report_lines.append(f"  - Supplier: {row['supplier_name'] or 'Unknown'}")
                report_lines.append(f"  - Value: £{row['value_gbp']:,}")
                report_lines.append(f"  - Date: {row['award_date']}")
                report_lines.append("")

    else:
        report_lines.extend(
            [
                "## IT Contracts",
                "",
                "*No contract data loaded yet. Run data collection workflow.*",
                "",
            ]
        )

    # Trust financials
    cursor = conn.execute("SELECT COUNT(*) FROM trust_financials")
    financials_count = cursor.fetchone()[0]

    if financials_count > 0:
        report_lines.extend(
            [
                "## Trust Financial Data",
                "",
            ]
        )

        cursor = conn.execute("""
            SELECT
                financial_year,
                COUNT(*) as trust_count,
                SUM(staff_costs_agency) as total_agency_spend,
                AVG(staff_costs_agency * 100.0 / NULLIF(staff_costs_total, 0)) as avg_agency_pct
            FROM trust_financials
            GROUP BY financial_year
            ORDER BY financial_year DESC
        """)
        for row in cursor.fetchall():
            report_lines.append(f"### {row['financial_year']}")
            report_lines.append(f"- Trusts with data: {row['trust_count']}")
            if row["total_agency_spend"]:
                report_lines.append(f"- Total agency spend: £{row['total_agency_spend']:,}k")
            if row["avg_agency_pct"]:
                report_lines.append(
                    f"- Average agency spend: {row['avg_agency_pct']:.1f}% of staff costs"
                )
            report_lines.append("")
    else:
        report_lines.extend(
            [
                "## Trust Financial Data",
                "",
                "*No financial data loaded yet.*",
                "",
            ]
        )

    # PFI data
    cursor = conn.execute("SELECT COUNT(*) FROM pfi_contracts")
    pfi_count = cursor.fetchone()[0]

    if pfi_count > 0:
        report_lines.extend(
            [
                "## PFI Contracts",
                "",
            ]
        )

        cursor = conn.execute("""
            SELECT
                COUNT(*) as contract_count,
                SUM(capital_value_gbp) as total_capital,
                MIN(contract_end_date) as earliest_end,
                MAX(contract_end_date) as latest_end
            FROM pfi_contracts
        """)
        result = cursor.fetchone()
        report_lines.append(f"- Total PFI contracts: {result['contract_count']}")
        if result["total_capital"]:
            report_lines.append(f"- Total capital value: £{result['total_capital']:,}")
        report_lines.append(
            f"- Contract end dates: {result['earliest_end']} to {result['latest_end']}"
        )
        report_lines.append("")

        # Highest burden trusts
        cursor = conn.execute("""
            SELECT
                o.name as trust_name,
                p.unitary_charge_gbp
            FROM pfi_payments p
            JOIN pfi_contracts c ON p.pfi_contract_id = c.id
            JOIN organizations o ON c.ods_code = o.ods_code
            WHERE p.financial_year = (SELECT MAX(financial_year) FROM pfi_payments)
            ORDER BY p.unitary_charge_gbp DESC
            LIMIT 10
        """)
        high_pfi = cursor.fetchall()

        if high_pfi:
            report_lines.append("### Highest PFI Payments (Latest Year)")
            report_lines.append("")
            report_lines.append("| Trust | Annual Payment |")
            report_lines.append("|-------|----------------|")
            for row in high_pfi:
                report_lines.append(f"| {row['trust_name']} | £{row['unitary_charge_gbp']:,}k |")
            report_lines.append("")
    else:
        report_lines.extend(
            [
                "## PFI Contracts",
                "",
                "*No PFI data loaded yet.*",
                "",
            ]
        )

    # Data freshness
    report_lines.extend(
        [
            "## Data Sources",
            "",
            "| Source | Records | Last Updated |",
            "|--------|---------|--------------|",
        ]
    )

    cursor = conn.execute("SELECT COUNT(*), MAX(updated_at) FROM organizations")
    row = cursor.fetchone()
    report_lines.append(f"| NHS ODS Organizations | {row[0]:,} | {row[1] or 'N/A'} |")

    cursor = conn.execute("SELECT COUNT(*), MAX(created_at) FROM contracts")
    row = cursor.fetchone()
    report_lines.append(f"| Contracts Finder | {row[0]:,} | {row[1] or 'N/A'} |")

    cursor = conn.execute("SELECT COUNT(*), MAX(created_at) FROM trust_financials")
    row = cursor.fetchone()
    report_lines.append(f"| Trust Financials | {row[0]:,} | {row[1] or 'N/A'} |")

    cursor = conn.execute("SELECT COUNT(*), MAX(created_at) FROM pfi_contracts")
    row = cursor.fetchone()
    report_lines.append(f"| PFI Contracts | {row[0]:,} | {row[1] or 'N/A'} |")

    report_lines.append("")

    # Footer
    report_lines.extend(
        [
            "---",
            "",
            "*This report is generated automatically by the NHS Transparency project.*",
            "",
            "For more information, see: https://github.com/your-org/nhs-transparency",
        ]
    )

    conn.close()

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines))
    print(f"Report generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate NHS transparency report")
    parser.add_argument("--db", type=Path, required=True, help="Database path")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output markdown path")

    args = parser.parse_args()
    generate_report(args.db, args.output)


if __name__ == "__main__":
    main()
