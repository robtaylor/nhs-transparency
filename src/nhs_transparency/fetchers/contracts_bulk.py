"""
Contracts Finder bulk CSV data loader.

Downloads and processes bulk CSV exports from data.gov.uk.
These are monthly OCDS flattened CSV files that don't require authentication.

Data source: https://data.gov.uk/search?q=contracts+finder
"""

import csv
import io
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from ..db import get_connection

logger = logging.getLogger(__name__)

# NHS-related buyer keywords for filtering
NHS_BUYER_KEYWORDS = [
    "NHS",
    "National Health Service",
    "Trust",
    "Hospital",
    "Foundation Trust",
    "Integrated Care",
    "ICB",
    "Clinical Commissioning",
    "CCG",
    "Health and Social Care",
    "Department of Health",
    "DHSC",
]


@dataclass
class ContractRecord:
    """Represents a contract from the bulk CSV data."""

    external_id: str
    title: str
    description: str | None
    buyer_name: str
    supplier_name: str | None
    value_gbp: int | None
    award_date: date | None
    start_date: date | None
    end_date: date | None
    notice_url: str | None


class ContractsBulkLoader:
    """Loads contract data from bulk CSV files."""

    def __init__(self, db_path=None):
        self.client = httpx.Client(timeout=120.0, follow_redirects=True)
        self.db_path = db_path

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def is_nhs_buyer(self, buyer_name: str) -> bool:
        """Check if the buyer appears to be an NHS organization."""
        if not buyer_name:
            return False
        buyer_upper = buyer_name.upper()
        return any(kw.upper() in buyer_upper for kw in NHS_BUYER_KEYWORDS)

    def download_csv(self, url: str) -> str:
        """Download a CSV file from URL and return its content."""
        logger.info(f"Downloading: {url}")
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def parse_csv(
        self,
        csv_content: str,
        nhs_only: bool = True,
        keywords: list[str] | None = None,
    ) -> list[ContractRecord]:
        """
        Parse CSV content into ContractRecord objects.

        Args:
            csv_content: Raw CSV text
            nhs_only: If True, only include NHS buyers
            keywords: If provided, only include contracts matching these keywords

        Returns:
            List of ContractRecord objects
        """
        records = []
        reader = csv.DictReader(io.StringIO(csv_content))

        for row in reader:
            # Extract buyer name - column names vary in OCDS CSV
            buyer_name = (
                row.get("buyer/name")
                or row.get("buyer_name")
                or row.get("releases/0/buyer/name")
                or ""
            )

            # Filter by NHS buyer if requested
            if nhs_only and not self.is_nhs_buyer(buyer_name):
                continue

            # Extract title and description
            title = (
                row.get("tender/title")
                or row.get("title")
                or row.get("releases/0/tender/title")
                or ""
            )
            description = (
                row.get("tender/description")
                or row.get("description")
                or row.get("releases/0/tender/description")
            )

            # Filter by keywords if provided
            if keywords:
                text_to_search = f"{title} {description or ''} {buyer_name}".upper()
                if not any(kw.upper() in text_to_search for kw in keywords):
                    continue

            # Extract contract ID
            external_id = row.get("releases/0/id") or row.get("ocid") or row.get("id") or ""
            if not external_id:
                continue

            # Extract supplier
            supplier_name = (
                row.get("awards/0/suppliers/0/name")
                or row.get("supplier_name")
                or row.get("releases/0/awards/0/suppliers/0/name")
            )

            # Extract value
            value_gbp = None
            value_str = (
                row.get("awards/0/value/amount")
                or row.get("tender/value/amount")
                or row.get("releases/0/awards/0/value/amount")
            )
            if value_str:
                try:
                    value_gbp = int(float(value_str))
                except (ValueError, TypeError):
                    pass

            # Extract dates
            award_date = self._parse_date(
                row.get("awards/0/date")
                or row.get("award_date")
                or row.get("releases/0/awards/0/date")
            )
            start_date = self._parse_date(
                row.get("tender/contractPeriod/startDate")
                or row.get("start_date")
                or row.get("releases/0/tender/contractPeriod/startDate")
            )
            end_date = self._parse_date(
                row.get("tender/contractPeriod/endDate")
                or row.get("end_date")
                or row.get("releases/0/tender/contractPeriod/endDate")
            )

            # Extract URL
            notice_url = (
                row.get("tender/documents/0/url")
                or row.get("notice_url")
                or row.get("releases/0/tender/documents/0/url")
            )

            records.append(
                ContractRecord(
                    external_id=external_id,
                    title=title,
                    description=description[:5000] if description else None,
                    buyer_name=buyer_name,
                    supplier_name=supplier_name,
                    value_gbp=value_gbp,
                    award_date=award_date,
                    start_date=start_date,
                    end_date=end_date,
                    notice_url=notice_url,
                )
            )

        return records

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse a date string in various formats."""
        if not date_str:
            return None

        # Try ISO format first
        for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                from datetime import datetime

                return datetime.strptime(
                    date_str[:19], fmt.replace("T%H:%M:%SZ", "").replace("T%H:%M:%S", "")
                ).date()
            except (ValueError, TypeError):
                continue

        # Try just taking the first 10 characters as YYYY-MM-DD
        try:
            return date.fromisoformat(date_str[:10])
        except (ValueError, TypeError):
            return None

    def load_from_file(
        self,
        file_path: Path,
        nhs_only: bool = True,
        keywords: list[str] | None = None,
    ) -> list[ContractRecord]:
        """Load contracts from a local CSV file."""
        logger.info(f"Loading from file: {file_path}")
        with open(file_path) as f:
            content = f.read()
        return self.parse_csv(content, nhs_only=nhs_only, keywords=keywords)

    def load_from_url(
        self,
        url: str,
        nhs_only: bool = True,
        keywords: list[str] | None = None,
    ) -> list[ContractRecord]:
        """Download and load contracts from a CSV URL."""
        content = self.download_csv(url)
        return self.parse_csv(content, nhs_only=nhs_only, keywords=keywords)

    def save_contracts(self, contracts: list[ContractRecord], conn: sqlite3.Connection):
        """Save contracts to the database."""

        cursor = conn.cursor()

        for contract in contracts:
            cursor.execute(
                """
                INSERT INTO contracts (
                    external_id, source, buyer_name,
                    supplier_name, title, description, contract_type,
                    value_gbp, award_date, start_date, end_date, notice_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    contract.external_id,
                    "contracts_finder_bulk",
                    contract.buyer_name,
                    contract.supplier_name,
                    contract.title,
                    contract.description,
                    None,  # contract_type - would need to classify
                    contract.value_gbp,
                    contract.award_date.isoformat() if contract.award_date else None,
                    contract.start_date.isoformat() if contract.start_date else None,
                    contract.end_date.isoformat() if contract.end_date else None,
                    contract.notice_url,
                ),
            )

        conn.commit()

    def sync_from_file(
        self,
        file_path: Path,
        nhs_only: bool = True,
        keywords: list[str] | None = None,
    ) -> int:
        """Load contracts from file and save to database."""
        conn = get_connection(self.db_path)
        try:
            contracts = self.load_from_file(file_path, nhs_only=nhs_only, keywords=keywords)
            self.save_contracts(contracts, conn)
            return len(contracts)
        finally:
            conn.close()
