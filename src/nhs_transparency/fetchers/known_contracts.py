"""
Known major NHS IT contracts to track.

These are high-profile contracts that we want to ensure are captured,
fetched directly by their Contracts Finder notice IDs.
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
