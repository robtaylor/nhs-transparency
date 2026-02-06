# NHS IT Advocacy Campaign Plan

## Objective

Build an opt-in contact list of NHS IT decision makers who want to be informed about open source and UK-based alternatives to proprietary US software (specifically Palantir's Federated Data Platform and TPP's systems) currently being deployed across the NHS.

---

## Phase 1: Identify Relevant Roles

### Trust Level (~220 NHS Trusts)
- Chief Information Officers (CIOs) / Chief Technology Officers (CTOs)
- Chief Clinical Information Officers (CCIOs)
- Chief Digital Officers (CDOs)
- Board members with digital/IT portfolio (often a Non-Executive Director)
- Procurement directors (for contract decisions)

### Integrated Care Board Level (42 ICBs)
- ICB Digital Leads
- ICB Chief Information Officers

### National Level
- NHS England Transformation Directorate leadership
- NHSE Chief Data & Analytics Officer's team

---

## Phase 2: Public Data Sources

### Structured/Scrapeable Sources

| Source | URL | Data Available |
|--------|-----|----------------|
| NHS ODS (Organisation Data Service) | https://digital.nhs.uk/services/organisation-data-service | Machine-readable list of all NHS organizations |
| Contracts Finder | https://www.contractsfinder.service.gov.uk/ | Contract awards searchable by supplier |
| Find a Tender | https://www.find-tender.service.gov.uk/ | Above-threshold procurement notices |
| NHS Trust Websites | Various | Board and senior leadership teams |
| FOI Disclosure Logs | Various trust websites | IT/data contract information |

### Semi-Structured Sources

| Source | Description |
|--------|-------------|
| Parliamentary Records (Hansard) | Debates, written questions, select committee evidence |
| NHS Trust Board Papers | Minutes of meetings where FDP adoption was discussed |
| ICB Board Papers | Similar transparency requirements to trusts |

### Professional Networks

| Source | Description |
|--------|-------------|
| CCIO Network / Digital Health Networks | Professional community of NHS digital leaders |
| BCS Health & Care | Professional body with NHS IT membership |
| Digital Health (digitalhealthnet.com) | Trade publication with CIO/CCIO profiles |

### Existing Campaign Infrastructure

| Organization | Focus | URL |
|--------------|-------|-----|
| Foxglove | Legal challenges to FDP | https://foxglove.org.uk |
| medConfidential | NHS data privacy | https://medconfidential.org |
| openDemocracy | Investigative journalism | https://opendemocracy.net |

---

## Phase 3: Data Collection Approach

### Step 1: Organizational Data (Non-Personal)
1. Retrieve full list of NHS trusts and ICBs from ODS API
2. Cross-reference with Contracts Finder for Palantir/FDP and TPP contracts
3. Categorize organizations by status:
   - Adopted FDP
   - Considering FDP
   - Rejected/not adopted
   - Unknown

### Step 2: Identify Role Holders
4. For each organization, find CIO/CCIO/CDO from public leadership pages
5. Record: Name, Role, Organization, Public Contact Method (if available)

### Step 3: Consent-First Contact
6. Reach out through professional channels explaining the campaign
7. Ask for explicit opt-in to receive information
8. Only add consenting individuals to the active contact list

---

## Phase 4: Alternatives Material to Prepare

### Open Source / UK-Based Alternatives

| Solution | Description | NHS Adoption |
|----------|-------------|--------------|
| OpenEHR | Open standard for health records, UK-developed | Several trusts |
| Better (better.care) | Slovenian company using openEHR | Some NHS deployments |
| NHS-developed open source | Various projects from NHS Digital | Varies |

### Key Arguments to Document

- **Cost comparisons**: FDP contract value vs. open source alternatives
- **Data sovereignty**: CLOUD Act implications of US company holding NHS data
- **Clinical safety**: DCB0129/DCB0160 compliance of alternatives
- **Interoperability**: OpenEHR vs proprietary formats
- **Long-term vendor lock-in risks**

---

## Phase 5: GDPR Compliance

### Lawful Basis
- Legitimate interest for contacting public officials in professional capacity about matters within their remit

### Required Documentation
- [ ] Legitimate Interest Assessment (LIA)
- [ ] Privacy Notice
- [ ] Data retention policy
- [ ] Subject access request process

### Principles
- **Consent tracking**: Record when and how consent was given
- **Right to object**: Trivially easy opt-out mechanism
- **Data minimization**: Only name, role, organization, professional contact method
- **Security**: Appropriate protection for stored data

---

## Technical Tools Required

See: `tools-specification.md` (to be created)

---

## Timeline

| Phase | Activities | Dependencies |
|-------|------------|--------------|
| 1 | Set up data collection infrastructure | None |
| 2 | Collect organizational data from ODS and Contracts Finder | Phase 1 |
| 3 | Identify decision makers at each organization | Phase 2 |
| 4 | Prepare alternatives documentation | Can run in parallel |
| 5 | Begin consent-first outreach | Phases 3 & 4 |
| 6 | Ongoing: maintain list, send updates | Phase 5 |

---

## Success Metrics

- Number of organizations mapped
- Number of decision makers identified
- Opt-in rate from outreach
- Engagement with alternatives information
- Any policy changes or contract reconsiderations influenced
