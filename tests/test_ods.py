"""Tests for ODS fetcher."""

from nhs_transparency.fetchers.ods import ODSFetcher, Organization


class TestODSFetcher:
    """Tests for the ODS API fetcher."""

    def test_parse_organization_from_list(self):
        """Test parsing organization from list API response."""
        fetcher = ODSFetcher()

        org_data = {
            "Name": "MANCHESTER UNIVERSITY NHS FOUNDATION TRUST",
            "OrgId": "R0A",
            "Status": "Active",
            "PostCode": "M13 9WL",
            "LastChangeDate": "2023-11-14",
            "PrimaryRoleId": "RO197",
        }

        org = fetcher._parse_organization_from_list(org_data, "RO197")

        assert org is not None
        assert org.ods_code == "R0A"
        assert org.name == "MANCHESTER UNIVERSITY NHS FOUNDATION TRUST"
        assert org.status == "Active"
        assert org.postcode == "M13 9WL"
        assert org.org_type == "NHS Trust"

    def test_parse_organization_missing_code(self):
        """Test that organizations without ODS code are rejected."""
        fetcher = ODSFetcher()

        org_data = {
            "Name": "Test Org",
            "Status": "Active",
        }

        org = fetcher._parse_organization_from_list(org_data, "RO197")
        assert org is None

    def test_is_nhs_buyer_keywords(self):
        """Test NHS buyer detection."""
        from nhs_transparency.fetchers.contracts_bulk import ContractsBulkLoader

        loader = ContractsBulkLoader()

        assert loader.is_nhs_buyer("NHS England")
        assert loader.is_nhs_buyer("Manchester University NHS Foundation Trust")
        assert loader.is_nhs_buyer("Guy's and St Thomas' NHS Foundation Trust")
        assert loader.is_nhs_buyer("NHS Digital")
        assert loader.is_nhs_buyer("Department of Health and Social Care")

        assert not loader.is_nhs_buyer("Acme Corporation")
        assert not loader.is_nhs_buyer("Ministry of Defence")
        assert not loader.is_nhs_buyer("")


class TestDatabase:
    """Tests for database operations."""

    def test_init_db(self, tmp_path):
        """Test database initialization."""
        from nhs_transparency.db import get_db_stats, init_db

        db_path = tmp_path / "test.db"
        init_db(db_path)

        assert db_path.exists()

        stats = get_db_stats(db_path)
        assert "organizations" in stats
        assert "contracts" in stats
        assert stats["organizations"] == 0

    def test_save_organizations(self, tmp_path):
        """Test saving organizations to database."""
        from datetime import date

        from nhs_transparency.db import get_connection, init_db
        from nhs_transparency.fetchers.ods import ODSFetcher

        db_path = tmp_path / "test.db"
        init_db(db_path)

        fetcher = ODSFetcher(db_path)
        conn = get_connection(db_path)

        orgs = [
            Organization(
                ods_code="R0A",
                name="Test Trust",
                org_type="NHS Trust",
                org_subtype=None,
                status="Active",
                address_line1=None,
                address_line2=None,
                address_line3=None,
                town=None,
                county=None,
                postcode="M13 9WL",
                country=None,
                last_change_date=date(2023, 11, 14),
            ),
        ]

        fetcher.save_organizations(orgs, conn)

        cursor = conn.execute("SELECT * FROM organizations WHERE ods_code = 'R0A'")
        row = cursor.fetchone()

        assert row is not None
        assert row["name"] == "Test Trust"
        assert row["status"] == "Active"

        conn.close()
