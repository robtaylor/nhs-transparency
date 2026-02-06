"""Command-line interface for NHS Transparency tools."""

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import db
from .fetchers.contracts_finder import match_buyer_to_ods
from .fetchers.ods import ORG_ROLES, ODSFetcher

console = Console()


def setup_logging(verbose: bool):
    """Configure logging with rich output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to database file",
)
@click.pass_context
def main(ctx, verbose: bool, db_path: Path | None):
    """NHS Transparency Tools - Financial analysis and advocacy support."""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path


@main.command()
@click.pass_context
def init(ctx):
    """Initialize the database."""
    db_path = ctx.obj.get("db_path")
    db.init_db(db_path)
    console.print("[green]Database initialized successfully[/green]")


@main.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    db_path = ctx.obj.get("db_path")

    try:
        statistics = db.get_db_stats(db_path)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("Run 'nhs init' to create the database first.")
        return

    table = Table(title="Database Statistics")
    table.add_column("Table", style="cyan")
    table.add_column("Records", justify="right", style="green")

    for table_name, count in statistics.items():
        table.add_row(table_name, str(count))

    console.print(table)


@main.group()
def fetch():
    """Fetch data from external sources."""
    pass


@fetch.command("organizations")
@click.option(
    "--roles",
    "-r",
    multiple=True,
    help="Specific roles to fetch (e.g., RO197 for NHS Trusts)",
)
@click.option("--include-inactive", is_flag=True, help="Include inactive organizations")
@click.pass_context
def fetch_organizations(ctx, roles: tuple[str], include_inactive: bool):
    """Fetch NHS organizations from ODS."""
    db_path = ctx.obj.get("db_path")

    # Initialize database if needed
    db.init_db(db_path)

    roles_list = list(roles) if roles else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching organizations...", total=len(roles_list or ORG_ROLES))

        with ODSFetcher(db_path) as fetcher:
            results = fetcher.fetch_all(
                roles=roles_list,
                include_inactive=include_inactive,
                progress=progress,
                task_id=task,
            )

            # Save to database
            conn = db.get_connection(db_path)
            try:
                for _role_id, orgs in results.items():
                    fetcher.save_organizations(orgs, conn)
            finally:
                conn.close()

    # Print summary
    table = Table(title="Organizations Fetched")
    table.add_column("Role", style="cyan")
    table.add_column("Type", style="white")
    table.add_column("Count", justify="right", style="green")

    for role_id, orgs in results.items():
        role_name = ORG_ROLES.get(role_id, role_id)
        table.add_row(role_id, role_name, str(len(orgs)))

    console.print(table)
    console.print(f"[green]Total: {sum(len(o) for o in results.values())} organizations[/green]")


@fetch.command("contracts")
@click.option(
    "--file",
    "-f",
    "csv_file",
    type=click.Path(exists=True, path_type=Path),
    help="Load contracts from a CSV file (bulk download from data.gov.uk)",
)
@click.option(
    "--terms",
    "-t",
    multiple=True,
    help="Filter by keywords (in title/description/buyer)",
)
@click.option("--all-buyers", is_flag=True, help="Include non-NHS buyers")
@click.pass_context
def fetch_contracts(ctx, csv_file: Path | None, terms: tuple[str], all_buyers: bool):
    """Load contracts from Contracts Finder bulk CSV data.

    The Contracts Finder API requires authentication. For bulk analysis,
    download CSV files from data.gov.uk:

    https://data.gov.uk/search?q=contracts+finder

    Then load them with: nhs fetch contracts --file notices.csv
    """
    from .fetchers.contracts_bulk import ContractsBulkLoader

    db_path = ctx.obj.get("db_path")

    if not csv_file:
        console.print("[yellow]No CSV file specified.[/yellow]")
        console.print()
        console.print("The Contracts Finder API requires OAuth authentication.")
        console.print("For bulk analysis, download CSV files from:")
        console.print("[cyan]https://data.gov.uk/search?q=contracts+finder[/cyan]")
        console.print()
        console.print("Then load them with:")
        console.print("[green]nhs fetch contracts --file notices.csv[/green]")
        return

    # Initialize database if needed
    db.init_db(db_path)

    terms_list = list(terms) if terms else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Loading from {csv_file.name}...", total=None)

        with ContractsBulkLoader(db_path) as loader:
            count = loader.sync_from_file(
                csv_file,
                nhs_only=not all_buyers,
                keywords=terms_list,
            )

    console.print(f"[green]Loaded {count} contracts[/green]")

    # Try to match to ODS codes
    if count > 0:
        conn = db.get_connection(db_path)
        try:
            matched = match_buyer_to_ods(conn)
            console.print(f"[green]Matched {matched} contracts to ODS organizations[/green]")
        finally:
            conn.close()


@fetch.command("known-contracts")
@click.pass_context
def fetch_known_contracts(ctx):
    """Load known major NHS IT contracts.

    These are high-profile contracts that we track explicitly,
    like the Palantir Federated Data Platform contract.
    """
    from .fetchers.known_contracts import get_known_contracts

    db_path = ctx.obj.get("db_path")
    db.init_db(db_path)

    conn = db.get_connection(db_path)
    cursor = conn.cursor()

    contracts = get_known_contracts()
    loaded = 0

    for contract in contracts:
        cursor.execute(
            """
            INSERT INTO contracts (
                external_id, source, buyer_name, supplier_name,
                title, description, value_gbp,
                award_date, start_date, end_date, notice_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(external_id) DO UPDATE SET
                buyer_name = excluded.buyer_name,
                supplier_name = excluded.supplier_name,
                title = excluded.title,
                description = excluded.description,
                value_gbp = excluded.value_gbp,
                award_date = excluded.award_date,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                notice_url = excluded.notice_url
            """,
            (
                contract["notice_id"],
                "known_contracts",
                contract["buyer"],
                contract["supplier"],
                contract["title"],
                contract["description"],
                contract["value_gbp"],
                contract["award_date"],
                contract["start_date"],
                contract["end_date"],
                f"https://www.contractsfinder.service.gov.uk/notice/{contract['notice_id']}",
            ),
        )
        loaded += 1

    conn.commit()
    conn.close()

    console.print(f"[green]Loaded {loaded} known contracts[/green]")
    for contract in contracts:
        console.print(f"  - {contract['title']} ({contract['supplier']}): £{contract['value_gbp']:,}")


@main.group()
def query():
    """Query the database."""
    pass


@query.command("contracts")
@click.option("--supplier", "-s", help="Filter by supplier name (partial match)")
@click.option("--buyer", "-b", help="Filter by buyer name (partial match)")
@click.option("--limit", "-n", default=20, help="Maximum results to show")
@click.pass_context
def query_contracts(ctx, supplier: str | None, buyer: str | None, limit: int):
    """List contracts in the database."""
    db_path = ctx.obj.get("db_path")
    conn = db.get_connection(db_path)

    query = "SELECT * FROM contracts WHERE 1=1"
    params = []

    if supplier:
        query += " AND UPPER(supplier_name) LIKE UPPER(?)"
        params.append(f"%{supplier}%")

    if buyer:
        query += " AND (UPPER(buyer_name) LIKE UPPER(?) OR buyer_ods_code = ?)"
        params.append(f"%{buyer}%")
        params.append(buyer.upper())

    query += " ORDER BY award_date DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        console.print("[yellow]No contracts found[/yellow]")
        return

    table = Table(title=f"Contracts (showing {len(rows)})")
    table.add_column("Date", style="cyan")
    table.add_column("Buyer", style="white", max_width=30)
    table.add_column("Supplier", style="green", max_width=20)
    table.add_column("Value", justify="right", style="yellow")
    table.add_column("Title", max_width=40)

    for row in rows:
        value = f"£{row['value_gbp']:,}" if row["value_gbp"] else "-"
        award_date = row["award_date"] or "-"
        table.add_row(
            str(award_date),
            row["buyer_name"][:30] if row["buyer_name"] else "-",
            row["supplier_name"][:20] if row["supplier_name"] else "-",
            value,
            row["title"][:40] if row["title"] else "-",
        )

    console.print(table)


@query.command("organizations")
@click.option("--type", "-t", "org_type", help="Filter by organization type")
@click.option("--search", "-s", help="Search by name (partial match)")
@click.option("--limit", "-n", default=20, help="Maximum results to show")
@click.pass_context
def query_organizations(ctx, org_type: str | None, search: str | None, limit: int):
    """List organizations in the database."""
    db_path = ctx.obj.get("db_path")
    conn = db.get_connection(db_path)

    query = "SELECT * FROM organizations WHERE 1=1"
    params = []

    if org_type:
        query += " AND UPPER(org_type) LIKE UPPER(?)"
        params.append(f"%{org_type}%")

    if search:
        query += " AND UPPER(name) LIKE UPPER(?)"
        params.append(f"%{search}%")

    query += " ORDER BY name LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        console.print("[yellow]No organizations found[/yellow]")
        return

    table = Table(title=f"Organizations (showing {len(rows)})")
    table.add_column("ODS Code", style="cyan")
    table.add_column("Name", style="white", max_width=40)
    table.add_column("Type", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Postcode", style="white")

    for row in rows:
        table.add_row(
            row["ods_code"],
            row["name"][:40] if row["name"] else "-",
            row["org_type"] or "-",
            row["status"] or "-",
            row["postcode"] or "-",
        )

    console.print(table)


@main.command()
@click.pass_context
def summary(ctx):
    """Show a summary of NHS IT spending data."""
    db_path = ctx.obj.get("db_path")
    conn = db.get_connection(db_path)

    # Get top suppliers by contract count and value
    cursor = conn.execute(
        """
        SELECT
            supplier_name,
            COUNT(*) as contract_count,
            SUM(COALESCE(value_gbp, 0)) as total_value
        FROM contracts
        WHERE supplier_name IS NOT NULL
        GROUP BY supplier_name
        ORDER BY total_value DESC
        LIMIT 15
        """
    )
    suppliers = cursor.fetchall()

    if suppliers:
        table = Table(title="Top Suppliers by Total Contract Value")
        table.add_column("Supplier", style="cyan")
        table.add_column("Contracts", justify="right", style="white")
        table.add_column("Total Value", justify="right", style="green")

        for row in suppliers:
            value = f"£{row['total_value']:,}" if row["total_value"] else "-"
            table.add_row(
                row["supplier_name"][:40] if row["supplier_name"] else "-",
                str(row["contract_count"]),
                value,
            )

        console.print(table)
    else:
        console.print(
            "[yellow]No contract data available. Run 'nhs fetch contracts' first.[/yellow]"
        )

    conn.close()


if __name__ == "__main__":
    main()
