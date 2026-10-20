# BPI regulatory-data research pipeline

Python tools for preparing public US holding-company and bank regulatory data for stress-test research, using DuckDB, Parquet and CSV. This is a research prototype developed for the BPI use case; it does not imply BPI affiliation or approval.

**Status: REVIEW_REQUIRED.** A draft covers all 12 quarters of 2023–2025. Full-population financial checks have unresolved failures. Complete merger-adjusted histories have **not** been produced. Passing software tests does not certify the financial dataset.

## Current delivery

The last completed local run retained:

| Result | Observations |
|---|---:|
| FDIC bank-quarter records in the raw-bank table | 55,090 |
| Organisation-quarter rows after the NIC ownership review filter | 13,662 |
| Duplicate organisation-quarter keys in that table | 0 |
| FDIC holder observations corroborated in NIC control chains | 45,649 |
| Blank-holder observations with a NIC control parent | 326 |
| FDIC/NIC holder disagreements | 37 |
| Missing financial measure values in the pre-review measures table | 1,618 |
| Negative stock values flagged in that measures table | 30 |
| NIC transformation records dated within 2023–2025 | 1,350 |

These are results from the saved local source snapshot, not guarantees for a fresh download. Regulatory amendments and source refreshes can change them. Negative equity can be a valid filing value.

**GitHub contains the code, documentation, tests and illustrative workflow images. Downloaded source files, generated datasets, DuckDB databases and the Python environment are excluded.** Repository links cannot provide the locally generated CSV files.

## Workflow

1. Read each quarter's official NIC holding-company ZIP and obtain FDIC financials.
2. Identify Y-9C observations through populated `BHCK2170`; validate source dates, record identifiers and FDIC response completeness.
3. Retain all observed Y-9C filers in panel mode. Match banks to holders using the same quarter's FDIC `RSSDHCR`.
4. Use consolidated Y-9C financials for those holders. Keep subsidiary banks in the ownership and raw-bank tables rather than adding their core balances again.
5. Aggregate selected bank deposit categories separately, preserving contributor counts, missingness and differences from consolidated deposits.
6. Convert YTD income to quarterly income, run checks and export quarterly tables.
7. Combine quarters, audit ownership against dated NIC control chains and generate the reviewed organisation table plus exception reports.
8. Record NIC transformation events and flag potentially affected quarters for merger research.

The workflow images distinguish the implemented draft from planned merger adjustments. The output-table image uses illustrative figures, not source observations.

## Coverage and ownership rules

The NIC files mix Y-9C, Y-9LP and Y-9SP fields. The current filter uses populated Y-9C assets; it does not independently classify each filer as a BHC, SLHC or IHC. The internal label `consolidated_BHC` should therefore be read as a holding-company filing label.

A bank with a blank, zero or self-referential FDIC holder initially becomes a `standalone_candidate_bank`. The reviewed table retains that bank only if the dated NIC direct-control graph yields no control ancestor. Absence of a NIC edge is not independent proof of standalone status or comprehensive source coverage. Historical institution-type screening, including foreign branches, remains outstanding.

The full run also retains **40,430 bank-quarter records whose reported holder has no selected Y-9C row**. They remain in `bank_raw` and the coverage ledger, but are not included as standalone banks in the main organisation table. Small holders outside Y-9C scope are one possible explanation; this has not been established for every record. Bank-only aggregates for those groups are not yet implemented.

Consequently, the main table is **not yet a complete analytical population of every bank and savings institution**. Its duplicate-key check also does not establish that every possible ownership or consolidation overlap has been resolved.

## Measures and definitions

All monetary values are **USD thousands**. Stocks are quarter-end balances.

| Output | Holding-company source | Bank source / treatment |
|---|---|---|
| `total_assets` | `BHCK2170` | `ASSET` |
| `total_loans` | `BHCK2122`: loans and leases net of unearned income | Not populated from FDIC net loans |
| `loans_net_allowances` | Not populated from the BHC loan field | `LNLSNET`: separate source-specific measure |
| `total_equity` | `BHCK3210` | `EQ`; reporting perimeter requires review |
| `total_deposits` | Sum of `BHDM6631`, `BHDM6636`, `BHFN6631`, `BHFN6636` | `DEP` |
| `net_income_ytd` | `BHCK4340` | `NETINC` |
| `net_income_quarter` | Q1: YTD directly; Q2–Q4: current YTD minus adjacent prior-quarter YTD | `NETINCQ`, cross-checked against the YTD calculation |

Missing BHC deposit components produce a missing total. A missing prior income value produces missing quarterly income. The program checks adjacent calendar quarters; it does not automatically repair amendments, perimeter changes or merger-quarter income.

The deposit table separately aggregates `DEP`, `DEPDOM`, `DEPFOR`, `DEPIDOM` and `DEPNIDOM`: total, domestic, foreign, domestic interest-bearing and domestic noninterest-bearing deposits. A missing contributor value is not silently converted to zero. Domestic interest-bearing plus noninterest-bearing deposits are checked against domestic deposits.

Subsidiary sums cover the matched FDIC reporting banks. They can differ from consolidated Y-9C deposits because of reporting scope and consolidation effects. The difference is exported, not forced to zero. Additional categories such as demand, savings and time deposits are not implemented.

See [config/measure_map.csv](config/measure_map.csv). It documents the mappings; Python currently implements them directly, so both must remain aligned.

## Official sources

- [NIC holding-company financial downloads](https://www.ffiec.gov/npw/FinancialReport/FinancialDataDownload): quarterly ZIPs containing caret-delimited TXT files.
- [FDIC BankFind API documentation](https://api.fdic.gov/banks/docs/): bank financials and identifiers from the public `/banks/financials` endpoint.
- [NIC structure downloads](https://www.ffiec.gov/npw/FinancialReport/DataDownload/1000): relationships and transformations.
- [NIC structure dictionary](https://www.ffiec.gov/npw/StaticData/DataDownload/NPW%20Data%20Dictionary.pdf) and [Federal Reserve MDRM](https://www.federalreserve.gov/data/mdrm.htm): source definitions.

The bank pipeline uses FDIC's selected financial fields; it does **not** parse raw FFIEC CDR schedule files. It requires no paid API. Current NIC publications contain dated history but are not vintage archives.

## Setup and reproduce

The commands below run from the **cloned repository root**, using Python 3.12 and PowerShell.

```powershell
git clone https://github.com/hugozacm/bpi-regulatory-data.git
cd bpi-regulatory-data
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force research | Out-Null
```

Private-repository Git authentication is required to clone.

### Prepare the source files

Use the official NIC pages above to download and place the following in `research/`:

- `BHCF20230331.ZIP`, `BHCF20230630.ZIP`, `BHCF20230930.ZIP`, `BHCF20231231.ZIP`
- `BHCF20240331.ZIP`, `BHCF20240630.ZIP`, `BHCF20240930.ZIP`, `BHCF20241231.ZIP`
- `BHCF20250331.ZIP`, `BHCF20250630.ZIP`, `BHCF20250930.ZIP`, `BHCF20251231.ZIP`
- `CSV_RELATIONSHIPS.zip` and `CSV_TRANSFORMATIONS.zip` from the **CSV** structure download section.

Do not unzip them. NIC may require an ordinary browser download when its scripted endpoint displays a challenge.

The panel builder downloads missing FDIC responses as `research/fdic_extended_YYYYMMDD.json`. To rerun offline, supply all twelve previously saved responses with those names. Q1 income uses current-year YTD directly, so no 2022 financial input is required for this panel.

### Build and review the panel

```powershell
.\.venv\Scripts\python.exe src\build_panel.py
.\.venv\Scripts\python.exe src\review_panel.py
```

The builder regenerates the output files in `outputs/panel_2023_2025/`. Save a separate snapshot beforehand if you need to preserve an earlier run.

The builder retains quarterly validation failures in its reports and continues assembling the draft. It does **not** turn a completed run into a publication approval. The single-quarter CLI returns exit code 2 on failed financial checks; the panel builder calls its Python function and retains those failure results. Review `validation.csv`, `review_summary.json` and the exception tables before analysis.

### Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp test_temp_verify
```

The last local run passed 15 tests. A fresh clone normally runs 14 and skips the optional real-data integration test because downloaded fixtures are excluded. That test also expects the original `research/fdic_20240930.json` filename alongside the extended Q4 response. Source downloads can be amended, so fixture-dependent checks may change.

Tests cover income conversion, input dates and uniqueness, missingness, precise integer handling, truncated API responses, caret parsing, dated ownership paths and conservative merger-event classification. They are not independent certification of the complete historical financial dataset.

## Output tables

Each listed table is exported to CSV and Parquet and stored in `panel.duckdb`.

| Table | Purpose |
|---|---|
| `organisation_financials` | Main reviewed draft: one row per organisation and quarter, core measures and separately labelled bank deposit aggregates |
| `bank_raw` | All downloaded bank financial records, including banks outside the main analytical table |
| `institutions`, `measures`, `financials_wide` | Intermediate entity and financial tables before the final NIC ownership filter |
| `deposits` | Deposit sums, contributor counts, missingness and differences from core reported deposits |
| `ownership` | FDIC bank-to-Y-9C-holder links |
| `bank_coverage` | Original FDIC-based bank inclusion classification |
| `ownership_audit` | Dated NIC control-chain corroboration and disagreements |
| `validation` | Quarterly mechanical check results; not all pass for the full population |
| `value_exceptions` | Missing measures and negative stock values from the intermediate measures table |
| `merger_events` | Verified source event records and review classifications |
| `merger_quarter_review` | Holding-company observations potentially affected by transformation events |
| `provenance` | Source URLs, file hashes, processing times and FDIC request parameters |

Quarter-specific subfolders also retain their own outputs and `run_summary.json`. The panel folder contains `quarter_summary.json`, `review_summary.json` and a review-required marker. For candidate banks, columns prefixed `bank_subsidiary_` contain the bank's own deposit values; the prefix does not assert that it has subsidiaries.

`processed_at_utc` records processing, not the original download time. Exact reproduction requires the same raw source snapshots; the repository alone does not include them.

## Merger adjustment and remaining work

**No merger-adjusted financial history is currently exported.** The code ingests and classifies transformation records and flags quarters for review. The provisional reference date is 31 December 2025.

A charter-discontinuation code alone does not establish a simple one-buyer, full-entity transfer. Purchase accounting, multiple successors, partial acquisitions, failures and the distinction between legal transformation and economic consolidation dates require verification. Summing predecessors without these checks can double count balances or misstate flows.

Before research release:

- Resolve population coverage, historical institution types and bank-only groups without Y-9C coverage.
- Investigate ownership disagreements and reconcile selected values to official filings.
- Align loan, equity and income definitions and document deposit consolidation treatment.
- Assess missing prior filings, restatements and merger-quarter flow comparability.
- Implement and validate a documented merger-adjustment method and predecessor lineage.
- Extend earlier than 2023 only after verifying historical source and mapping continuity.

[Detailed panel status](PANEL_STATUS.md) · [Provisional assumptions](PROVISIONAL_ASSUMPTIONS.md) · [Stakeholder review questions](REVIEW_QUESTIONS.md)

[Current architecture](ARCHITECTURE_REVIEW.md) describes the implemented workflow. [Implementation history](UPGRADE_STATUS.md) records earlier stages. To regenerate the illustrative PNGs, install the optional Pillow package and run `build_workflow_images.py`; this is not required to run the data pipeline.
