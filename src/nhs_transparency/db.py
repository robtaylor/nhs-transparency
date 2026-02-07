"""Database schema and connection management."""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "nhs.db"

SCHEMA = """
-- Organizations from ODS
CREATE TABLE IF NOT EXISTS organizations (
    ods_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    org_type TEXT,
    org_subtype TEXT,
    status TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    address_line3 TEXT,
    town TEXT,
    county TEXT,
    postcode TEXT,
    country TEXT,
    website_url TEXT,
    last_change_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- IT suppliers (normalized)
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT UNIQUE NOT NULL,
    aliases TEXT,  -- JSON array
    companies_house_number TEXT,
    parent_company TEXT,
    headquarters_country TEXT,
    website TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Contracts from Contracts Finder and other sources
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY,
    external_id TEXT UNIQUE,  -- Contracts Finder ID or other source ID
    source TEXT NOT NULL,  -- contracts_finder, foi, annual_report, etc.

    buyer_ods_code TEXT REFERENCES organizations(ods_code),
    buyer_name TEXT,  -- fallback if no ODS match

    supplier_id INTEGER REFERENCES suppliers(id),
    supplier_name TEXT,  -- original name before normalization

    title TEXT,
    description TEXT,
    contract_type TEXT,  -- it, clinical, estates, etc.

    value_gbp INTEGER,
    value_low_gbp INTEGER,  -- for ranges
    value_high_gbp INTEGER,

    award_date DATE,
    start_date DATE,
    end_date DATE,

    procurement_route TEXT,
    framework_name TEXT,

    notice_url TEXT,

    -- Additional metadata
    cpv_codes TEXT,  -- JSON array of CPV classification codes
    published_date DATE,
    supplier_address TEXT,
    is_sme BOOLEAN,
    is_vcse BOOLEAN,
    status TEXT,  -- awarded, closed, etc.
    location TEXT,  -- geographic area
    suitable_for_sme BOOLEAN,
    suitable_for_vcse BOOLEAN,

    keywords TEXT,  -- JSON array of matched search terms

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trust financial data (annual)
CREATE TABLE IF NOT EXISTS trust_financials (
    id INTEGER PRIMARY KEY,
    ods_code TEXT NOT NULL REFERENCES organizations(ods_code),
    financial_year TEXT NOT NULL,  -- e.g., "2023-24"

    -- High-level figures (stored in £000s)
    total_operating_expenditure INTEGER,
    total_operating_income INTEGER,
    surplus_deficit INTEGER,

    -- Staff costs breakdown
    staff_costs_total INTEGER,
    staff_costs_permanent INTEGER,
    staff_costs_agency INTEGER,
    staff_costs_bank INTEGER,

    -- Other key lines
    supplies_clinical INTEGER,
    supplies_general INTEGER,
    premises_costs INTEGER,
    depreciation INTEGER,
    clinical_negligence INTEGER,
    consultancy_costs INTEGER,
    it_costs INTEGER,

    -- Metadata
    source_url TEXT,
    extraction_method TEXT,  -- manual, pdfplumber, camelot, etc.
    extraction_confidence TEXT,  -- high, medium, low
    manually_verified INTEGER DEFAULT 0,
    verified_by TEXT,
    verified_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(ods_code, financial_year)
);

-- PFI contracts
CREATE TABLE IF NOT EXISTS pfi_contracts (
    id INTEGER PRIMARY KEY,
    ods_code TEXT NOT NULL REFERENCES organizations(ods_code),
    scheme_name TEXT,

    -- Original deal
    capital_value_gbp INTEGER,
    contract_start_date DATE,
    contract_end_date DATE,
    contract_duration_years INTEGER,

    -- SPV details
    spv_name TEXT,
    spv_companies_house TEXT,
    current_equity_holder TEXT,

    -- HM Treasury reference
    hmt_project_id TEXT,

    source_url TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PFI annual payments
CREATE TABLE IF NOT EXISTS pfi_payments (
    id INTEGER PRIMARY KEY,
    pfi_contract_id INTEGER NOT NULL REFERENCES pfi_contracts(id),
    financial_year TEXT NOT NULL,

    unitary_charge_gbp INTEGER,
    service_element_gbp INTEGER,
    capital_element_gbp INTEGER,
    interest_element_gbp INTEGER,

    -- Future obligations snapshot (£000s)
    remaining_years_1_5 INTEGER,
    remaining_years_6_10 INTEGER,
    remaining_years_11_15 INTEGER,
    remaining_years_16_20 INTEGER,
    remaining_years_21_plus INTEGER,

    source_url TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(pfi_contract_id, financial_year)
);

-- Parliamentary activity
CREATE TABLE IF NOT EXISTS parliamentary (
    id INTEGER PRIMARY KEY,
    external_id TEXT UNIQUE,
    source TEXT NOT NULL,  -- hansard_debate, hansard_wms, written_question, committee

    date DATE,
    house TEXT,  -- commons, lords

    speaker_name TEXT,
    speaker_party TEXT,
    speaker_constituency TEXT,
    speaker_member_id TEXT,  -- parliament.uk member ID

    title TEXT,
    content TEXT,
    url TEXT,

    -- Search matching
    search_terms_matched TEXT,  -- JSON array
    relevance_score REAL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_organizations_type ON organizations(org_type);
CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);
CREATE INDEX IF NOT EXISTS idx_contracts_buyer ON contracts(buyer_ods_code);
CREATE INDEX IF NOT EXISTS idx_contracts_supplier ON contracts(supplier_id);
CREATE INDEX IF NOT EXISTS idx_contracts_award_date ON contracts(award_date);
CREATE INDEX IF NOT EXISTS idx_financials_ods ON trust_financials(ods_code);
CREATE INDEX IF NOT EXISTS idx_financials_year ON trust_financials(financial_year);
CREATE INDEX IF NOT EXISTS idx_pfi_ods ON pfi_contracts(ods_code);
CREATE INDEX IF NOT EXISTS idx_parliamentary_date ON parliamentary(date);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection, creating the database if needed."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Initialize the database schema."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_db_stats(db_path: Path | None = None) -> dict:
    """Get counts of records in each table."""
    conn = get_connection(db_path)
    tables = [
        "organizations",
        "suppliers",
        "contracts",
        "trust_financials",
        "pfi_contracts",
        "pfi_payments",
        "parliamentary",
    ]
    stats = {}
    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        stats[table] = cursor.fetchone()[0]
    conn.close()
    return stats
