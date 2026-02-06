# NHS Advocacy Campaign - Technical Tools Specification

## Overview

A suite of tools to automate data collection, organization mapping, and consent management for the NHS IT advocacy campaign.

---

## Tool 1: ODS Organization Fetcher

### Purpose
Retrieve and structure the complete list of NHS organizations from the Organisation Data Service API.

### Data Source
- **API**: https://directory.spineservices.nhs.uk/ORD/2-0-0/
- **Documentation**: https://digital.nhs.uk/services/organisation-data-service/guidance-for-developers

### Functionality
- Fetch all NHS Trusts (role: RO197)
- Fetch all Integrated Care Boards (role: RO318)
- Fetch NHS England organizations
- Store in structured format with:
  - ODS code
  - Organization name
  - Organization type
  - Status (active/inactive)
  - Address
  - Postcode
  - Last updated date

### Output
- SQLite database or JSON files
- CSV export capability

### Technology
- Python with `httpx` or `requests`
- `sqlite3` for storage
- Scheduled refresh capability

---

## Tool 2: Contracts Finder Scraper

### Purpose
Search and extract NHS IT contract awards, focusing on Palantir, TPP, and related suppliers.

### Data Source
- **API**: https://www.contractsfinder.service.gov.uk/apidocumentation/home
- **Search terms**:
  - "Palantir"
  - "Federated Data Platform"
  - "FDP"
  - "TPP"
  - "SystmOne"
  - "NHS data platform"

### Functionality
- Search contracts by supplier name and keywords
- Filter by buyer type (NHS organizations)
- Extract:
  - Contract title
  - Buyer organization
  - Supplier
  - Contract value
  - Award date
  - Contract duration
  - Link to full notice
- Match buyer organizations to ODS codes

### Output
- Database table linking organizations to contracts
- Timeline of contract awards
- Value analysis

### Technology
- Python with `httpx`
- JSON parsing
- Cross-reference with ODS data

---

## Tool 3: Trust Website Leadership Scraper

### Purpose
Extract senior leadership information from NHS Trust websites.

### Approach
This is the most challenging tool due to website variability. Options:

#### Option A: Semi-Automated with LLM Assistance
1. Fetch trust website homepage
2. Find "About Us" / "Our Team" / "Board" pages
3. Use LLM to extract structured data from HTML
4. Human review and correction

#### Option B: Crowdsourced Manual Entry
1. Generate list of trusts needing data
2. Web interface for volunteers to enter leadership data
3. Validation through multiple entries

#### Option C: Hybrid
1. Attempt automated extraction
2. Flag low-confidence results for manual review
3. Learn from corrections

### Data to Extract
- Name
- Job title
- Professional contact (if published)
- Photo URL (for verification)
- Source URL

### Technology
- Python with `httpx` and `beautifulsoup4`
- Optional: `playwright` for JavaScript-rendered pages
- Optional: Claude API for intelligent extraction
- Human review interface (simple web app)

---

## Tool 4: Parliamentary Records Search

### Purpose
Find and index parliamentary activity related to NHS IT contracts.

### Data Sources
- **Hansard API**: https://hansard.parliament.uk/
- **Written Questions**: https://questions-statements.parliament.uk/
- **Select Committee Evidence**: Manual or RSS feeds

### Functionality
- Search for debates mentioning Palantir, FDP, NHS data
- Extract MP/Lord names and positions
- Identify supportive parliamentarians for the campaign
- Track chronology of political engagement

### Output
- Timeline of parliamentary activity
- List of engaged parliamentarians
- Key quotes and positions

### Technology
- Python with `httpx`
- Text search and categorization
- Optional: sentiment/position analysis

---

## Tool 5: Consent Management System

### Purpose
GDPR-compliant management of contacts and their consent status.

### Core Functionality

#### Contact Database
- Name
- Role
- Organization (linked to ODS code)
- Contact method (email, LinkedIn, etc.)
- Source of contact information
- Date added

#### Consent Tracking
- Consent status: not_contacted | pending | opted_in | opted_out
- Date of consent/refusal
- Method of consent (email reply, form, etc.)
- Consent scope (what they agreed to receive)

#### Communication Log
- Date of each communication
- Type (initial outreach, update, etc.)
- Channel used
- Response received

#### Opt-Out Handling
- Immediate removal from active communications
- Retention of minimal record for suppression list
- Automated suppression in any bulk sends

### User Interface
- Web-based dashboard
- Contact search and filtering
- Bulk operations with safeguards
- Export for mail merge (opted-in only)
- Audit log

### Technology
- Python backend (FastAPI or Flask)
- SQLite or PostgreSQL database
- Simple frontend (htmx or React)
- Authentication for campaign staff

---

## Tool 6: Outreach Template System

### Purpose
Generate personalized outreach messages while maintaining consistency.

### Functionality
- Template library for different scenarios:
  - Initial contact
  - Follow-up
  - Post-opt-in welcome
  - Update newsletters
- Variable substitution (name, organization, contract status)
- A/B testing capability
- Response tracking integration

### Technology
- Jinja2 templates
- Markdown with HTML rendering
- Integration with consent management system

---

## Tool 7: Alternatives Documentation Generator

### Purpose
Generate tailored briefing documents based on organization's current situation.

### Document Types
- Executive summary (1 page)
- Technical comparison
- Cost analysis
- Case studies from trusts using alternatives
- Legal/data sovereignty briefing

### Personalization
- Reference organization's current contracts
- Comparable trusts that chose alternatives
- Relevant parliamentary activity in their region

### Technology
- Markdown templates
- PDF generation (WeasyPrint or similar)
- Data integration from other tools

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Collection                          │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  ODS Fetcher    │ Contracts       │ Trust Website    │ Hansard  │
│                 │ Finder Scraper  │ Scraper          │ Search   │
└────────┬────────┴────────┬────────┴────────┬─────────┴────┬─────┘
         │                 │                 │              │
         ▼                 ▼                 ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Central Database                            │
│  - Organizations (from ODS)                                     │
│  - Contracts (from Contracts Finder)                            │
│  - People (from trust websites, manual entry)                   │
│  - Parliamentary activity                                       │
│  - Consent records                                              │
│  - Communication logs                                           │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Consent Management UI                        │
│  - Contact management                                           │
│  - Outreach tracking                                            │
│  - Opt-in/opt-out handling                                      │
│  - Document generation                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Priority

### Phase 1: Foundation (Week 1-2)
1. **ODS Fetcher** - straightforward API, gives us the organization backbone
2. **Database schema** - design central data model
3. **Basic consent management** - even a spreadsheet to start

### Phase 2: Intelligence (Week 3-4)
4. **Contracts Finder Scraper** - understand current contract landscape
5. **Parliamentary Search** - identify political allies and context

### Phase 3: Scale (Week 5-6)
6. **Trust Website Scraper** - the hard part, identify actual people
7. **Consent Management UI** - proper tooling as list grows

### Phase 4: Outreach (Week 7+)
8. **Outreach Templates** - standardized communications
9. **Documentation Generator** - personalized briefings

---

## Technology Stack Recommendation

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Best library ecosystem for scraping/data |
| HTTP Client | httpx | Modern, async-capable |
| HTML Parsing | beautifulsoup4 + lxml | Robust, well-documented |
| Database | SQLite (dev) → PostgreSQL (prod) | Simple start, scales later |
| Web Framework | FastAPI | Modern, async, good for APIs |
| Frontend | htmx + Tailwind | Simple, minimal JS complexity |
| Task Queue | None initially → Redis + Celery | Add when needed for scheduled jobs |
| Deployment | Docker + fly.io or Railway | Simple, cheap hosting |

---

## Data Model (Draft)

```sql
-- Organizations from ODS
CREATE TABLE organizations (
    ods_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    org_type TEXT,  -- trust, icb, etc.
    status TEXT,    -- active, inactive
    address TEXT,
    postcode TEXT,
    website_url TEXT,
    last_ods_update DATE,
    last_scraped DATE
);

-- Contracts from Contracts Finder
CREATE TABLE contracts (
    id INTEGER PRIMARY KEY,
    cf_id TEXT UNIQUE,  -- Contracts Finder ID
    title TEXT,
    buyer_ods_code TEXT REFERENCES organizations(ods_code),
    supplier TEXT,
    value_gbp INTEGER,
    award_date DATE,
    end_date DATE,
    notice_url TEXT,
    keywords TEXT,  -- JSON array of matched search terms
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- People identified at organizations
CREATE TABLE people (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT,
    org_ods_code TEXT REFERENCES organizations(ods_code),
    contact_method TEXT,  -- email, linkedin URL, etc.
    source_url TEXT,      -- where we found this info
    confidence TEXT,      -- high, medium, low
    last_verified DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Consent tracking
CREATE TABLE consent (
    id INTEGER PRIMARY KEY,
    person_id INTEGER REFERENCES people(id),
    status TEXT NOT NULL,  -- not_contacted, pending, opted_in, opted_out
    consent_date DATE,
    consent_method TEXT,   -- email_reply, form, verbal
    consent_scope TEXT,    -- JSON: what they agreed to
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Communication log
CREATE TABLE communications (
    id INTEGER PRIMARY KEY,
    person_id INTEGER REFERENCES people(id),
    direction TEXT,    -- outbound, inbound
    channel TEXT,      -- email, linkedin, phone
    comm_type TEXT,    -- initial_outreach, follow_up, update
    content_summary TEXT,
    sent_at TIMESTAMP,
    response_received BOOLEAN DEFAULT FALSE,
    response_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Parliamentary activity
CREATE TABLE parliamentary (
    id INTEGER PRIMARY KEY,
    source TEXT,       -- hansard, written_question, committee
    date DATE,
    speaker TEXT,      -- MP/Lord name
    party TEXT,
    constituency TEXT,
    title TEXT,
    content TEXT,
    url TEXT,
    relevance_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

# Part 2: NHS Financial Transparency Tools

## Overview

Tools to analyze NHS spending patterns, identify systemic inefficiencies, and provide public transparency on how NHS money is spent.

---

## Tool F1: Trust Financial Dashboard

### Purpose
Aggregate and visualize trust-level financial data to enable comparison and identify spending patterns.

### Data Sources

| Source | URL | Format | Update Frequency |
|--------|-----|--------|------------------|
| Trust Annual Reports & Accounts | Individual trust websites | PDF | Annual (July-Aug) |
| NHS England Consolidated Accounts | england.nhs.uk | PDF/Excel | Annual |
| NHS Provider Accounts (NHSE) | england.nhs.uk/publication | Excel | Annual |
| Reference Cost Collection | england.nhs.uk | Excel | Annual |
| ERIC (Estates Returns) | digital.nhs.uk | CSV | Annual |

### Key Metrics to Extract

**From Annual Accounts:**
- Total operating expenditure
- Staff costs (broken down by category)
- Purchase of healthcare from non-NHS bodies
- Supplies and services - clinical
- Supplies and services - general
- Premises costs
- Depreciation and amortization
- Clinical negligence costs
- Agency and contract staff costs
- Consultancy costs

**Derived Metrics:**
- Cost per weighted activity unit (WAU)
- Agency spend as % of total staff costs
- Admin costs as % of total expenditure
- Year-on-year growth rates
- Deviation from peer group average

### Functionality

1. **PDF Extraction Pipeline**
   - Download annual reports from trust websites
   - Extract financial tables using `pdfplumber` or `camelot`
   - Map to standardized schema
   - Flag extraction confidence levels
   - Queue low-confidence extractions for manual review

2. **Normalization Layer**
   - Map trust-specific account codes to standard categories
   - Adjust for trust size (beds, staff, activity)
   - Handle merged/split trusts over time
   - Inflation adjustment for multi-year comparison

3. **Peer Grouping**
   - Group by trust type (acute, mental health, community, ambulance)
   - Group by size bands
   - Group by region
   - Group by teaching status

4. **Dashboard Interface**
   - Trust search and selection
   - Side-by-side comparison of 2-5 trusts
   - Time series charts (5-10 year trends)
   - Peer percentile indicators
   - Drill-down to line-item detail
   - Export to CSV/Excel

### Technical Challenges

| Challenge | Mitigation |
|-----------|------------|
| PDF table extraction accuracy | Multiple extraction methods, confidence scoring, manual verification sample |
| Account code variation | Mapping table maintained manually, LLM-assisted categorization |
| Trust reorganizations | Track successor organizations, handle partial-year accounts |
| Data freshness | Clear "as of" dates, automated staleness alerts |

### Technology
- Python with `pdfplumber`, `camelot-py`, `tabula-py`
- `pandas` for data manipulation
- SQLite/PostgreSQL for storage
- FastAPI backend
- Chart.js or Plotly for visualization
- htmx + Tailwind frontend

---

## Tool F4: IT Spend Analyzer

### Purpose
Specifically track IT and digital spending across NHS organizations to understand the true cost of technology choices.

### Why This Matters
- Palantir FDP contract reportedly worth £330m+ over multiple years
- TPP (SystmOne) and EMIS dominate primary care
- Hidden costs: integration, training, data migration, vendor lock-in
- Opportunity cost: what could be built with open source investment

### Data Sources

| Source | What It Provides |
|--------|------------------|
| Contracts Finder | IT contract awards over £10k/£25k |
| Trust Annual Accounts | Total IT/digital spend line (sometimes) |
| FOI Requests | Detailed IT supplier breakdown |
| Digital Health Intelligence | Market research (some free data) |
| NHSE Digital Maturity Assessment | Self-reported digital capabilities |
| Tech UK NHS IT Suppliers | Industry association data |

### Metrics to Track

**Contract-Level:**
- Supplier name (normalized)
- Contract value (total and annual)
- Contract duration
- Contract type (EPR, PAS, data platform, infrastructure, etc.)
- Renewal/extension history
- Procurement route (framework, open tender, single source)

**Organization-Level:**
- Total IT spend
- IT spend as % of total expenditure
- Supplier concentration (how many vendors)
- Open source vs. proprietary ratio
- Integration costs (connecting systems)
- Legacy system maintenance costs

**Market-Level:**
- Supplier market share by trust count
- Supplier market share by contract value
- Geographic concentration
- Contract win/loss trends
- Price variation for similar solutions

### Functionality

1. **Contract Aggregation**
   - Pull from Contracts Finder API (IT-related keywords)
   - Parse FOI disclosures from trusts
   - Normalize supplier names (e.g., "TPP", "TPP Ltd", "The Phoenix Partnership" → "TPP")
   - Categorize contract types

2. **Supplier Intelligence**
   - Company profiles (from Companies House)
   - Contract history across NHS
   - Parent company tracking (for acquisitions)
   - Geographic footprint

3. **Cost Analysis**
   - Price benchmarking (what do similar trusts pay for similar systems?)
   - Total cost of ownership estimates
   - Integration cost tracking
   - Failed project/write-off identification

4. **Visualization**
   - Supplier market share pie/treemap
   - Geographic heatmap of supplier penetration
   - Contract timeline (start/end dates, renewals)
   - Price comparison scatter plots
   - Trend lines over time

### Specific Palantir/FDP Tracking
- Which trusts have signed FDP agreements
- Contract values where disclosed
- Implementation timeline
- Comparison with trusts using alternatives
- Parliamentary/media coverage correlation

### Technology
- Shared infrastructure with advocacy tools
- Contracts Finder API integration
- Companies House API for supplier data
- Network visualization (supplier relationships)

---

## Tool F5: PFI Payment Tracker

### Purpose
Track the ongoing cost burden of Private Finance Initiative contracts across NHS trusts.

### Background
- PFI was used to build many NHS hospitals from 1990s-2010s
- Trusts pay annual "unitary charges" for 25-30 years
- Some deals are very poor value - trusts pay 5-10x construction cost
- PFI debt contributes to trust deficits
- Trusts can't easily exit these contracts
- Some PFI companies have gone bankrupt (Carillion), complicating matters

### Data Sources

| Source | What It Provides |
|--------|------------------|
| Trust Annual Accounts | PFI/LIFT obligations note (required disclosure) |
| HM Treasury PFI Data | Central register of PFI projects |
| NAO Reports | Analysis of PFI value and problems |
| Infrastructure & Projects Authority | Current project status |
| FOI Requests | Detailed payment schedules |

### Metrics to Track

**Per-Contract:**
- Original capital value
- Total payments to date
- Remaining payments (net present value)
- Annual unitary charge
- Contract end date
- Special purpose vehicle (SPV) ownership
- Service provider details

**Per-Trust:**
- Number of PFI schemes
- Total annual PFI payments
- PFI as % of operating expenditure
- PFI as % of estate costs
- Comparison with non-PFI trusts of similar size

**National:**
- Total NHS PFI debt outstanding
- Annual NHS PFI payments
- Contracts ending in next 5/10/15 years
- Buyout feasibility analysis

### Functionality

1. **PFI Data Extraction**
   - Parse "Private Finance Initiative" note from annual accounts
   - Extract payment schedules (years 1-5, 6-10, 11-15, etc.)
   - Track changes year-over-year
   - Handle refinancing and modifications

2. **Comparative Analysis**
   - PFI vs. non-PFI trusts with similar estate
   - Calculate implied interest rates
   - Estimate "excess" payments over public borrowing alternative

3. **Contract Timeline**
   - Countdown to contract end
   - Handback condition requirements
   - Asset lifecycle considerations

4. **Visualization**
   - Map of PFI hospitals with contract details
   - Trust-level PFI burden ranking
   - Payment schedule charts
   - Cumulative payment visualizations

### Policy Relevance
- Identifies trusts most burdened by PFI
- Informs potential buyout/refinancing decisions
- Highlights when contracts end (asset handback)
- Quantifies the true cost of PFI to NHS

### Technology
- PDF extraction from annual accounts
- HM Treasury data integration
- Time-value-of-money calculations
- Map visualization (Leaflet.js or similar)

---

## Extended Data Model

Adding to the existing schema:

```sql
-- Trust financial data (annual)
CREATE TABLE trust_financials (
    id INTEGER PRIMARY KEY,
    ods_code TEXT REFERENCES organizations(ods_code),
    financial_year TEXT,  -- e.g., "2023-24"

    -- High-level figures (£000s)
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
    it_costs INTEGER,  -- if separately disclosed

    -- Metadata
    source_url TEXT,
    extraction_confidence TEXT,  -- high, medium, low
    manually_verified BOOLEAN DEFAULT FALSE,
    extracted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- IT contracts
CREATE TABLE it_contracts (
    id INTEGER PRIMARY KEY,
    cf_id TEXT,  -- Contracts Finder ID if applicable
    buyer_ods_code TEXT REFERENCES organizations(ods_code),
    supplier_id INTEGER REFERENCES suppliers(id),

    title TEXT,
    contract_type TEXT,  -- epr, pas, data_platform, infrastructure, etc.

    total_value_gbp INTEGER,
    annual_value_gbp INTEGER,
    start_date DATE,
    end_date DATE,

    procurement_route TEXT,  -- framework, open_tender, single_source
    framework_name TEXT,  -- e.g., "G-Cloud 13", "Health Systems Support Framework"

    source_url TEXT,
    source_type TEXT,  -- contracts_finder, foi, annual_report, news

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- IT suppliers (normalized)
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT UNIQUE,
    aliases TEXT,  -- JSON array of alternative names
    companies_house_number TEXT,
    parent_company TEXT,
    headquarters_country TEXT,
    website TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PFI contracts
CREATE TABLE pfi_contracts (
    id INTEGER PRIMARY KEY,
    ods_code TEXT REFERENCES organizations(ods_code),
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

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PFI annual payments
CREATE TABLE pfi_payments (
    id INTEGER PRIMARY KEY,
    pfi_contract_id INTEGER REFERENCES pfi_contracts(id),
    financial_year TEXT,

    unitary_charge_gbp INTEGER,
    service_element_gbp INTEGER,
    capital_element_gbp INTEGER,
    interest_element_gbp INTEGER,

    -- Future obligations snapshot
    remaining_years_1_5 INTEGER,
    remaining_years_6_10 INTEGER,
    remaining_years_11_15 INTEGER,
    remaining_years_16_plus INTEGER,

    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Updated Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Data Collection Layer                          │
├───────────┬───────────┬───────────┬───────────┬───────────┬─────────────┤
│    ODS    │ Contracts │  Trust    │  Annual   │    HM     │  Companies  │
│  Fetcher  │  Finder   │ Websites  │ Accounts  │ Treasury  │   House     │
│           │           │           │  (PDFs)   │   PFI     │             │
└─────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┴──────┬──────┘
      │           │           │           │           │            │
      ▼           ▼           ▼           ▼           ▼            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Central Database                                 │
│  Organizations │ Contracts │ Financials │ IT Spend │ PFI │ Suppliers   │
└─────────────────────────────────────────────────────────────────────────┘
      │
      ├──────────────────────────┬──────────────────────────┐
      ▼                          ▼                          ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Trust Financial │    │  IT Spend       │    │  PFI Payment    │
│ Dashboard       │    │  Analyzer       │    │  Tracker        │
│                 │    │                 │    │                 │
│ - Compare trusts│    │ - Supplier mkt  │    │ - Contract map  │
│ - Trend analysis│    │ - Price bench   │    │ - Burden ranking│
│ - Peer groups   │    │ - Palantir/TPP  │    │ - End dates     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## Implementation Priority (Revised)

### Phase 1: Foundation
1. ODS Fetcher (organization backbone)
2. Database schema (expanded for financials)
3. Contracts Finder integration

### Phase 2: Financial Intelligence
4. **Trust Financial Dashboard** - annual accounts extraction
5. **IT Spend Analyzer** - contract aggregation
6. **PFI Payment Tracker** - PFI data extraction

### Phase 3: Advocacy Tools
7. Consent management system
8. Trust website scraper (contacts)
9. Parliamentary search

### Phase 4: Public Interface
10. Public dashboard for transparency
11. API for journalists/researchers
12. Automated reporting

---

## Next Steps

1. Set up project repository with Python/uv
2. Implement ODS Fetcher as first tool
3. Design and create database schema
4. Build Contracts Finder integration
5. Prototype PDF extraction for annual accounts
6. Iterate from there based on data quality and needs
