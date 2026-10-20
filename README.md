# BPI regulatory-data MVP

**Historical panel:** see [PANEL_STATUS.md](PANEL_STATUS.md) for the twelve-quarter 2023–2025 research draft, full bank coverage ledger, ownership audit and outstanding merger work.

**Updated implementation:** see [UPGRADE_STATUS.md](UPGRADE_STATUS.md) for v2 behaviour and reproduction commands. Outputs now include detailed deposit aggregation, a wide table, stricter input checks and explicit review status. Blank-holder banks are candidates pending independent verification; source-specific loan definitions use separate columns.

This is a deliberately small, reproducible prototype for preparing public US bank regulatory data for stress-test research. It combines consolidated holding-company FR Y-9C data with bank-level Call Report data, creates CSV/Parquet/DuckDB outputs, converts cumulative income to a true single-quarter flow, and prevents double counting between a BHC and its insured-bank subsidiaries.

## What works now

- One verified end-to-end target quarter: **2024-12-31**, with **2024-09-30** as the required prior quarter.
- Five consolidated BHCs chosen from valid FR Y-9C filers that have same-quarter FDIC ownership matches.
- Three large standalone insured banks with complete selected measures, selected only where the same-quarter `RSSDHCR` is blank/zero or self-referential.
- Assets, loans, deposits, total equity, YTD net income and single-quarter net income.
- Period-aware ownership links using FDIC's quarter-end `RSSDHCR` and `NAMEHCR` fields.
- Source-file hashes, field-level source variables, validation results, CSV, Parquet and DuckDB.

## Official source formats verified

1. **NIC / FR Y-9C holding-company download.** The NIC page says quarterly ZIPs contain caret-delimited text, one row per institution, and mix FR Y-9C, Y-9LP and Y-9SP variables. The pipeline includes only rows with populated `BHCK2170`, an observable FR Y-9C field. Official page: <https://www.ffiec.gov/npw/FinancialReport/FinancialDataDownload>
2. **FDIC BankFind Suite API.** `/banks/financials` returns JSON or CSV without a paid API. This MVP requests documented financial and identifier fields and retains the raw JSON response. Documentation: <https://api.fdic.gov/banks/docs/>
3. **Measure definitions.** The mappings are recorded in `config/measure_map.csv`. Federal Reserve MDRM confirms, among others, `BHCK2170` total assets, `BHCK2122` total loans and leases net of unearned income, `BHCK3210` total equity capital and `BHCK4340` net income. FR Y-9C deposits are the sum of domestic and foreign, noninterest- and interest-bearing components. FDIC `LNLSNET` is retained under the common research label `total_loans`, but its source-specific definition remains visible in the mapping and provenance rather than being claimed as perfectly identical to `BHCK2122`.

All monetary values are **USD thousands**, matching the regulatory sources.

## Reproduce

The NIC site may challenge scripted downloads, so download these two files from the official page and place them in `research/`:

- `BHCF20241231.ZIP`
- `BHCF20240930.ZIP`

Then, from this directory in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\bpi_pipeline.py `
  --period 20241231 `
  --prior-period 20240930 `
  --y9-current research\BHCF20241231.ZIP `
  --y9-prior research\BHCF20240930.ZIP `
  --output outputs\20241231
.\.venv\Scripts\python.exe -m pytest -q
```

For a fully offline rerun, add `--fdic-current research\fdic_20241231.json --fdic-prior research\fdic_20240930.json`.

## Stock versus flow logic

- Assets, loans, deposits and equity are quarter-end **stocks** and are used directly.
- FR Y-9C `BHCK4340` is a calendar-year-to-date **flow**. For Q2-Q4, the pipeline subtracts the preceding quarter's YTD value; Q1 is used directly. If the prior filing is missing, the quarterly value remains null rather than being guessed.
- FDIC `NETINC` is kept as YTD and documented `NETINCQ` is used for the quarter. The validation report checks `NETINCQ == current NETINC - prior NETINC` for the selected standalone banks.

## No-double-counting rule

The analytical entity table contains consolidated BHC rows and truly standalone bank rows. Banks whose same-quarter `RSSDHCR` matches a selected BHC are written to `ownership.csv` for traceability but are deliberately excluded as separate analytical entities. This avoids adding consolidated BHC assets to subsidiary-bank assets.

## Outputs

- `institutions.*`: analytical entities and identifiers.
- `measures.*`: tidy measures with source variable and stock/flow status.
- `ownership.*`: subsidiary-bank-to-top-holder matches for the report date.
- `validation.*`: executable QA checks.
- `provenance.*`: official URLs, local input names and SHA-256 hashes.
- `bpi_mvp.duckdb`: the same five tables in DuckDB.
- `run_summary.json`: concise machine-readable run result.

## Limitations and next steps

- This is one quarter, not yet the requested 2023-2025 panel. The code accepts other adjacent quarter pairs, but historical field continuity needs a period-by-period mapping review before claiming coverage.
- `RSSDHCR` is a quarter-end regulatory high-holder field. It is period-aware for the chosen quarter but is not a full ownership graph, ownership percentage, or legal-control history.
- The output does not sum bank subsidiaries into a BHC; it relies on the already consolidated FR Y-9C. It also does not reconcile every nonbank subsidiary or intercompany elimination.
- No merger adjustment is claimed. The current NIC bulk structure download contains ownership history and transformations, but this MVP does not yet ingest a dated historical snapshot sufficient to reconstruct pre-merger comparables.
- The sample selection is mechanical (largest eligible entities), not a statement about BPI membership or stress-test coverage.
- Regulatory filings can be amended. Re-running may change values; provenance hashes make that visible.

Next: extend the date loop to 2023-2025, add versioned period-valid measure mappings, ingest NIC relationship/transformation history, and add amendment-aware snapshots before any merger-adjusted research series is published.
