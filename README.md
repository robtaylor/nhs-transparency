# NHS Transparency Tools

Tools for analyzing NHS spending, tracking IT contracts, and supporting transparency advocacy.

## Features

- **ODS Fetcher**: Retrieve NHS organization data from the Organisation Data Service API
- **Contracts Finder**: Search and analyze public contract awards
- **Financial Dashboard**: (Coming soon) Analyze trust-level financial data
- **IT Spend Analyzer**: (Coming soon) Track IT spending and vendor relationships
- **PFI Tracker**: (Coming soon) Monitor PFI contract obligations

## Installation

```bash
# Using uv
uv sync

# Or with pip
pip install -e .
```

## Usage

```bash
# Initialize the database
nhs init

# Fetch NHS organizations
nhs fetch organizations

# Fetch IT-related contracts
nhs fetch contracts

# View database statistics
nhs stats

# Query contracts
nhs query contracts --supplier "Palantir"
nhs query contracts --buyer "NHS"

# View spending summary
nhs summary
```

## Data Sources

- [NHS ODS (Organisation Data Service)](https://digital.nhs.uk/services/organisation-data-service)
- [Contracts Finder](https://www.contractsfinder.service.gov.uk/)
- NHS Trust Annual Reports and Accounts
- HM Treasury PFI data

## License

MIT
