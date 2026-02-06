"""
Known major NHS IT contracts to track.

These are high-profile contracts that we want to ensure are captured,
fetched directly by their Contracts Finder notice IDs.

HOW TO FIND NEW CONTRACTS:
1. Go to https://www.contractsfinder.service.gov.uk/Search/Results
2. Set filters:
   - Notice status: Closed (uncheck Open)
   - Procurement stage: Awarded contract
   - Keywords: e.g., "NHS England", "Palantir", "TPP", "EMIS"
3. Find the contract and copy its notice ID from the URL
4. Add it to KNOWN_CONTRACTS below

The CSV export from Contracts Finder is broken (ignores filters),
so we must track major contracts explicitly by their notice IDs.
"""

# Major NHS IT contracts with their Contracts Finder notice IDs
KNOWN_CONTRACTS = [
    {
        "notice_id": "2e8c61c0-faab-4f99-ae69-b00df6bae165",
        "title": "Federated Data Platform and Associated Services (FDP-AS)",
        "buyer": "NHS England",
        "supplier": "Palantir Technologies UK, Ltd.",
        "value_gbp": 330_000_000,  # Full contract value
        "award_date": "2023-11-22",
        "start_date": "2023-11-22",
        "end_date": "2027-02-15",
        "description": "Cloud-based Software as a Service (SaaS) platform for NHS data sharing and analytics. Consortium includes Accenture, PWC, Carnall Farrar and NECS.",
        "tags": ["palantir", "fdp", "data-platform", "analytics"],
    },
    # Add more known contracts here as we discover them
    # TPP SystmOne contracts, EMIS contracts, etc.
]


def get_known_contracts():
    """Return list of known major contracts."""
    return KNOWN_CONTRACTS
