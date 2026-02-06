"""
Contracts Finder API client.

Fetches public contract data from the UK Government Contracts Finder.
API Documentation: https://www.contractsfinder.service.gov.uk/apidocumentation/home

IMPORTANT: The Contracts Finder API requires OAuth 2.0 authentication.
You need to register for API access at:
https://www.contractsfinder.service.gov.uk/apidocumentation/registerapplication

For bulk analysis without authentication, consider:
1. Using the "Download all" feature on the website
2. Using the archived data from data.gov.uk

The bulk CSV downloads are available at:
https://www.contractsfinder.service.gov.uk/Search/Results (click "Download results")
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from ..db import get_connection

logger = logging.getLogger(__name__)

CONTRACTS_FINDER_BASE_URL = "https://www.contractsfinder.service.gov.uk/Published"

# Search terms for NHS IT contracts
DEFAULT_SEARCH_TERMS = [
    "Palantir",
    "Federated Data Platform",
    "FDP",
    "TPP",
    "SystmOne",
    "EMIS",
    "Epic",
    "Cerner",
    "electronic patient record",
    "EPR",
    "patient administration system",
    "health data platform",
    "NHS data",
    "clinical information system",
]

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
]


@dataclass
class Contract:
    """Represents a contract from Contracts Finder."""

    external_id: str
    title: str
    description: str | None
    buyer_name: str
    buyer_ods_code: str | None  # We'll try to match this
    supplier_name: str | None
    value_gbp: int | None
    value_low_gbp: int | None
    value_high_gbp: int | None
    award_date: date | None
    start_date: date | None
    end_date: date | None
    notice_url: str | None
    contract_type: str | None
    procurement_route: str | None
    keywords_matched: list[str]


class ContractsFinderFetcher:
    """Fetches contract data from the Contracts Finder API."""

    def __init__(self, db_path=None):
        self.client = httpx.Client(
            base_url=CONTRACTS_FINDER_BASE_URL,
            timeout=60.0,
            headers={"Accept": "application/json"},
        )
        self.db_path = db_path

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def search_notices(
        self,
        search_term: str,
        notice_type: str = "Contract",
        published_from: date | None = None,
        published_to: date | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[dict]:
        """
        Search for contract notices.

        Args:
            search_term: Text to search for
            notice_type: "Contract", "Tender", or "Pipeline"
            published_from: Start date for publication date filter
            published_to: End date for publication date filter
            page: Page number (1-indexed)
            page_size: Results per page (max 100)

        Returns:
            List of notice dictionaries
        """
        # Build search request
        payload = {
            "searchCriteria": {
                "keyword": search_term,
                "types": [notice_type],
            },
            "size": page_size,
            "from": (page - 1) * page_size,
        }

        if published_from:
            payload["searchCriteria"]["publishedFrom"] = published_from.isoformat()
        if published_to:
            payload["searchCriteria"]["publishedTo"] = published_to.isoformat()

        try:
            response = self.client.post("/Notices/OCDS/Search", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error searching contracts: {e}")
            raise

        data = response.json()
        return data.get("results", [])

    def search_all_pages(
        self,
        search_term: str,
        notice_type: str = "Contract",
        published_from: date | None = None,
        max_results: int | None = None,
    ) -> list[dict]:
        """
        Search for all matching notices across pages.

        Args:
            search_term: Text to search for
            notice_type: Type of notice to search
            published_from: Start date filter
            max_results: Maximum total results to fetch

        Returns:
            List of all matching notice dictionaries
        """
        all_results = []
        page = 1
        page_size = 100

        while True:
            results = self.search_notices(
                search_term=search_term,
                notice_type=notice_type,
                published_from=published_from,
                page=page,
                page_size=page_size,
            )

            if not results:
                break

            all_results.extend(results)
            logger.debug(f"Fetched page {page}, total results: {len(all_results)}")

            if max_results and len(all_results) >= max_results:
                all_results = all_results[:max_results]
                break

            if len(results) < page_size:
                break

            page += 1
            time.sleep(0.5)  # Rate limiting

        return all_results

    def is_nhs_buyer(self, buyer_name: str) -> bool:
        """Check if the buyer appears to be an NHS organization."""
        if not buyer_name:
            return False
        buyer_upper = buyer_name.upper()
        return any(kw.upper() in buyer_upper for kw in NHS_BUYER_KEYWORDS)

    def parse_contract(self, notice_data: dict, keywords_matched: list[str]) -> Contract | None:
        """Parse a contract notice into a Contract object."""
        try:
            # OCDS format has nested structure
            releases = notice_data.get("releases", [])
            if not releases:
                return None

            release = releases[0]
            notice_id = release.get("id", "")

            # Get buyer info
            buyer = release.get("buyer", {})
            buyer_name = buyer.get("name", "")

            # Get award/tender info
            awards = release.get("awards", [])
            tender = release.get("tender", {})

            # Title and description
            title = tender.get("title", "")
            description = tender.get("description", "")

            # Supplier (from awards)
            supplier_name = None
            award_date = None
            value_gbp = None

            if awards:
                award = awards[0]
                suppliers = award.get("suppliers", [])
                if suppliers:
                    supplier_name = suppliers[0].get("name")

                award_date_str = award.get("date")
                if award_date_str:
                    try:
                        award_date = datetime.fromisoformat(
                            award_date_str.replace("Z", "+00:00")
                        ).date()
                    except ValueError:
                        pass

                value = award.get("value", {})
                if value.get("amount"):
                    value_gbp = int(value["amount"])

            # Contract period
            period = tender.get("contractPeriod", {})
            start_date = None
            end_date = None

            if period.get("startDate"):
                try:
                    start_date = datetime.fromisoformat(
                        period["startDate"].replace("Z", "+00:00")
                    ).date()
                except ValueError:
                    pass

            if period.get("endDate"):
                try:
                    end_date = datetime.fromisoformat(
                        period["endDate"].replace("Z", "+00:00")
                    ).date()
                except ValueError:
                    pass

            # Value range (from tender)
            value_low = None
            value_high = None
            tender_value = tender.get("value", {})
            if tender_value.get("amount"):
                value_gbp = value_gbp or int(tender_value["amount"])
            tender_min = tender.get("minValue", {})
            tender_max = tender.get("maxValue", {})
            if tender_min.get("amount"):
                value_low = int(tender_min["amount"])
            if tender_max.get("amount"):
                value_high = int(tender_max["amount"])

            # Notice URL
            documents = tender.get("documents", [])
            notice_url = None
            for doc in documents:
                if doc.get("documentType") == "tenderNotice":
                    notice_url = doc.get("url")
                    break

            # Procurement method
            procurement_route = tender.get("procurementMethod")

            return Contract(
                external_id=notice_id,
                title=title,
                description=description[:5000] if description else None,
                buyer_name=buyer_name,
                buyer_ods_code=None,  # To be matched later
                supplier_name=supplier_name,
                value_gbp=value_gbp,
                value_low_gbp=value_low,
                value_high_gbp=value_high,
                award_date=award_date,
                start_date=start_date,
                end_date=end_date,
                notice_url=notice_url,
                contract_type="it",  # We're specifically searching for IT
                procurement_route=procurement_route,
                keywords_matched=keywords_matched,
            )

        except Exception as e:
            logger.warning(f"Failed to parse contract notice: {e}")
            return None

    def fetch_nhs_it_contracts(
        self,
        search_terms: list[str] | None = None,
        published_from: date | None = None,
        nhs_only: bool = True,
    ) -> list[Contract]:
        """
        Fetch NHS IT contracts matching the specified search terms.

        Args:
            search_terms: Terms to search for. Defaults to IT vendor names.
            published_from: Only fetch contracts published after this date.
            nhs_only: Filter to only NHS buyers.

        Returns:
            List of Contract objects.
        """
        terms = search_terms or DEFAULT_SEARCH_TERMS
        all_contracts = {}  # Dedupe by external_id

        for term in terms:
            logger.info(f"Searching for: {term}")
            notices = self.search_all_pages(
                search_term=term,
                notice_type="Contract",
                published_from=published_from,
            )

            for notice in notices:
                contract = self.parse_contract(notice, [term])
                if contract is None:
                    continue

                # Filter to NHS buyers if requested
                if nhs_only and not self.is_nhs_buyer(contract.buyer_name):
                    continue

                # Dedupe and merge keywords
                if contract.external_id in all_contracts:
                    existing = all_contracts[contract.external_id]
                    if term not in existing.keywords_matched:
                        existing.keywords_matched.append(term)
                else:
                    all_contracts[contract.external_id] = contract

            time.sleep(1)  # Be nice between search terms

        return list(all_contracts.values())

    def save_contracts(self, contracts: list[Contract], conn: sqlite3.Connection):
        """Save contracts to the database."""
        import json

        cursor = conn.cursor()

        for contract in contracts:
            cursor.execute(
                """
                INSERT INTO contracts (
                    external_id, source, buyer_ods_code, buyer_name,
                    supplier_name, title, description, contract_type,
                    value_gbp, value_low_gbp, value_high_gbp,
                    award_date, start_date, end_date,
                    procurement_route, notice_url, keywords
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_id) DO UPDATE SET
                    buyer_name = excluded.buyer_name,
                    supplier_name = excluded.supplier_name,
                    title = excluded.title,
                    description = excluded.description,
                    value_gbp = excluded.value_gbp,
                    value_low_gbp = excluded.value_low_gbp,
                    value_high_gbp = excluded.value_high_gbp,
                    award_date = excluded.award_date,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    procurement_route = excluded.procurement_route,
                    notice_url = excluded.notice_url,
                    keywords = excluded.keywords
                """,
                (
                    contract.external_id,
                    "contracts_finder",
                    contract.buyer_ods_code,
                    contract.buyer_name,
                    contract.supplier_name,
                    contract.title,
                    contract.description,
                    contract.contract_type,
                    contract.value_gbp,
                    contract.value_low_gbp,
                    contract.value_high_gbp,
                    contract.award_date.isoformat() if contract.award_date else None,
                    contract.start_date.isoformat() if contract.start_date else None,
                    contract.end_date.isoformat() if contract.end_date else None,
                    contract.procurement_route,
                    contract.notice_url,
                    json.dumps(contract.keywords_matched),
                ),
            )

        conn.commit()

    def sync_to_database(
        self,
        search_terms: list[str] | None = None,
        published_from: date | None = None,
        nhs_only: bool = True,
    ) -> int:
        """
        Fetch contracts and save to database.

        Returns:
            Number of contracts saved.
        """
        conn = get_connection(self.db_path)

        try:
            contracts = self.fetch_nhs_it_contracts(
                search_terms=search_terms,
                published_from=published_from,
                nhs_only=nhs_only,
            )
            self.save_contracts(contracts, conn)
            return len(contracts)
        finally:
            conn.close()


def match_buyer_to_ods(conn: sqlite3.Connection) -> int:
    """
    Attempt to match contract buyers to ODS organization codes.

    Uses fuzzy matching on organization names.

    Returns:
        Number of contracts matched.
    """
    cursor = conn.cursor()

    # Get unmatched contracts
    cursor.execute(
        """
        SELECT id, buyer_name FROM contracts
        WHERE buyer_ods_code IS NULL AND buyer_name IS NOT NULL
        """
    )
    unmatched = cursor.fetchall()

    matched_count = 0

    for contract_id, buyer_name in unmatched:
        # Try exact match first
        cursor.execute(
            "SELECT ods_code FROM organizations WHERE UPPER(name) = UPPER(?)",
            (buyer_name,),
        )
        result = cursor.fetchone()

        if result:
            cursor.execute(
                "UPDATE contracts SET buyer_ods_code = ? WHERE id = ?",
                (result[0], contract_id),
            )
            matched_count += 1
            continue

        # Try partial match (buyer name contains org name or vice versa)
        cursor.execute(
            """
            SELECT ods_code, name FROM organizations
            WHERE UPPER(name) LIKE '%' || UPPER(?) || '%'
               OR UPPER(?) LIKE '%' || UPPER(name) || '%'
            ORDER BY LENGTH(name) DESC
            LIMIT 1
            """,
            (buyer_name, buyer_name),
        )
        result = cursor.fetchone()

        if result:
            cursor.execute(
                "UPDATE contracts SET buyer_ods_code = ? WHERE id = ?",
                (result[0], contract_id),
            )
            matched_count += 1

    conn.commit()
    return matched_count
