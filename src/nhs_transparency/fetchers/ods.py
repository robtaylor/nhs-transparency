"""
ODS (Organisation Data Service) API fetcher.

Fetches NHS organization data from the NHS Digital Organisation Data Service.
API Documentation: https://digital.nhs.uk/services/organisation-data-service/guidance-for-developers

Key organization roles:
- RO197: NHS Trust
- RO198: NHS Trust Site
- RO318: Integrated Care Board (ICB)
- RO261: NHS England (Commissioning Hub)
- RO98: Primary Care Trust (historical)
- RO107: Primary Care Group (historical)
- RO157: Commissioning Support Unit
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import date

import httpx
from rich.progress import Progress, TaskID

from ..db import get_connection

logger = logging.getLogger(__name__)

ODS_BASE_URL = "https://directory.spineservices.nhs.uk/ORD/2-0-0"

# Organization roles we're interested in
ORG_ROLES = {
    "RO197": "NHS Trust",
    "RO198": "NHS Trust Site",
    "RO318": "Integrated Care Board",
    "RO261": "NHS England Regional",
    "RO157": "Commissioning Support Unit",
    "RO172": "Independent Sector Healthcare Provider",
}


@dataclass
class Organization:
    """Represents an NHS organization from ODS."""

    ods_code: str
    name: str
    org_type: str
    org_subtype: str | None
    status: str
    address_line1: str | None
    address_line2: str | None
    address_line3: str | None
    town: str | None
    county: str | None
    postcode: str | None
    country: str | None
    last_change_date: date | None


class ODSFetcher:
    """Fetches organization data from the ODS API."""

    def __init__(self, db_path=None):
        self.client = httpx.Client(
            base_url=ODS_BASE_URL,
            timeout=30.0,
            headers={"Accept": "application/fhir+json"},
        )
        self.db_path = db_path

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def fetch_organizations_by_role(
        self,
        role_id: str,
        status: str = "Active",
        limit: int | None = None,
    ) -> list[Organization]:
        """
        Fetch organizations with a specific role.

        Args:
            role_id: ODS role code (e.g., "RO197" for NHS Trusts)
            status: Filter by status ("Active", "Inactive", or None for all)
            limit: Maximum number of records to fetch (for testing)

        Returns:
            List of Organization objects
        """
        organizations = []
        offset = 0
        page_size = 1000  # ODS API max

        while True:
            params = {
                "PrimaryRoleId": role_id,
                "Limit": min(page_size, limit - len(organizations)) if limit else page_size,
            }
            # API requires Offset > 0, so only include if we're past the first page
            if offset > 0:
                params["Offset"] = offset
            if status:
                params["Status"] = status

            logger.debug(f"Fetching {role_id} offset={offset}")

            try:
                response = self.client.get("/organisations", params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching organizations: {e}")
                raise

            data = response.json()
            orgs_data = data.get("Organisations", [])

            if not orgs_data:
                break

            for org_data in orgs_data:
                org = self._parse_organization_from_list(org_data, role_id)
                if org:
                    organizations.append(org)

            if limit and len(organizations) >= limit:
                break

            if len(orgs_data) < page_size:
                break

            offset += page_size
            time.sleep(0.1)  # Be nice to the API

        return organizations

    def fetch_organization_details(self, ods_code: str) -> Organization | None:
        """Fetch detailed information for a single organization."""
        try:
            response = self.client.get(f"/organisations/{ods_code}")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Organization not found: {ods_code}")
                return None
            raise

        data = response.json()
        org_data = data.get("Organisation", {})

        # Get primary role
        roles = org_data.get("Roles", {}).get("Role", [])
        if isinstance(roles, dict):
            roles = [roles]
        primary_role = next(
            (r.get("id") for r in roles if r.get("primaryRole", False)),
            roles[0].get("id") if roles else "Unknown",
        )

        return self._parse_organization_detail(data, primary_role)

    def _parse_organization_from_list(self, org_data: dict, role_id: str) -> Organization | None:
        """Parse organization data from list API response (search results)."""
        ods_code = org_data.get("OrgId", "")
        if not ods_code:
            return None

        name = org_data.get("Name", "")
        status = org_data.get("Status", "")
        postcode = org_data.get("PostCode")
        last_change = org_data.get("LastChangeDate")

        # Parse last change date
        last_change_date = None
        if last_change:
            try:
                last_change_date = date.fromisoformat(last_change)
            except ValueError:
                pass

        return Organization(
            ods_code=ods_code,
            name=name,
            org_type=ORG_ROLES.get(role_id, role_id),
            org_subtype=None,
            status=status,
            address_line1=None,  # Not in list response
            address_line2=None,
            address_line3=None,
            town=None,
            county=None,
            postcode=postcode,
            country=None,
            last_change_date=last_change_date,
        )

    def _parse_organization_detail(self, org_data: dict, role_id: str) -> Organization | None:
        """Parse organization data from detail API response (single org lookup)."""
        ods_code = org_data.get("Organisation", {}).get("OrgId", "")
        if not ods_code:
            return None

        org = org_data.get("Organisation", {})
        name = org.get("Name", "")
        status = org.get("Status", "")
        last_change = org.get("LastChangeDate")

        # Get address from GeoLoc
        geo = org.get("GeoLoc", {}).get("Location", {})
        address = {
            "line1": geo.get("AddrLn1"),
            "line2": geo.get("AddrLn2"),
            "line3": geo.get("AddrLn3"),
            "town": geo.get("Town"),
            "county": geo.get("County"),
            "postcode": geo.get("PostCode"),
            "country": geo.get("Country"),
        }

        # Parse last change date
        last_change_date = None
        if last_change:
            try:
                last_change_date = date.fromisoformat(last_change)
            except ValueError:
                pass

        return Organization(
            ods_code=ods_code,
            name=name,
            org_type=ORG_ROLES.get(role_id, role_id),
            org_subtype=None,
            status=status,
            address_line1=address.get("line1"),
            address_line2=address.get("line2"),
            address_line3=address.get("line3"),
            town=address.get("town"),
            county=address.get("county"),
            postcode=address.get("postcode"),
            country=address.get("country"),
            last_change_date=last_change_date,
        )

    def save_organizations(self, organizations: list[Organization], conn: sqlite3.Connection):
        """Save organizations to the database."""
        cursor = conn.cursor()

        for org in organizations:
            cursor.execute(
                """
                INSERT INTO organizations (
                    ods_code, name, org_type, org_subtype, status,
                    address_line1, address_line2, address_line3,
                    town, county, postcode, country,
                    last_change_date, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(ods_code) DO UPDATE SET
                    name = excluded.name,
                    org_type = excluded.org_type,
                    org_subtype = excluded.org_subtype,
                    status = excluded.status,
                    address_line1 = excluded.address_line1,
                    address_line2 = excluded.address_line2,
                    address_line3 = excluded.address_line3,
                    town = excluded.town,
                    county = excluded.county,
                    postcode = excluded.postcode,
                    country = excluded.country,
                    last_change_date = excluded.last_change_date,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    org.ods_code,
                    org.name,
                    org.org_type,
                    org.org_subtype,
                    org.status,
                    org.address_line1,
                    org.address_line2,
                    org.address_line3,
                    org.town,
                    org.county,
                    org.postcode,
                    org.country,
                    org.last_change_date.isoformat() if org.last_change_date else None,
                ),
            )

        conn.commit()

    def fetch_all(
        self,
        roles: list[str] | None = None,
        include_inactive: bool = False,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> dict[str, list[Organization]]:
        """
        Fetch all organizations for specified roles.

        Args:
            roles: List of role IDs to fetch. Defaults to all defined roles.
            include_inactive: Whether to include inactive organizations.
            progress: Rich Progress instance for progress display.
            task_id: Rich task ID for progress updates.

        Returns:
            Dict mapping role IDs to lists of organizations.
        """
        roles = roles or list(ORG_ROLES.keys())
        results = {}

        for role_id in roles:
            role_name = ORG_ROLES.get(role_id, role_id)
            logger.info(f"Fetching {role_name} organizations...")

            if progress and task_id:
                progress.update(task_id, description=f"Fetching {role_name}...")

            active_orgs = self.fetch_organizations_by_role(role_id, status="Active")
            results[role_id] = active_orgs

            if include_inactive:
                inactive_orgs = self.fetch_organizations_by_role(role_id, status="Inactive")
                results[role_id].extend(inactive_orgs)

            logger.info(f"  Found {len(results[role_id])} {role_name} organizations")

            if progress and task_id:
                progress.advance(task_id)

        return results

    def sync_to_database(
        self,
        roles: list[str] | None = None,
        include_inactive: bool = False,
    ) -> dict[str, int]:
        """
        Fetch organizations and save to database.

        Returns:
            Dict mapping role IDs to counts of organizations saved.
        """
        conn = get_connection(self.db_path)

        try:
            results = self.fetch_all(roles, include_inactive)
            counts = {}

            for role_id, orgs in results.items():
                self.save_organizations(orgs, conn)
                counts[role_id] = len(orgs)

            return counts
        finally:
            conn.close()
