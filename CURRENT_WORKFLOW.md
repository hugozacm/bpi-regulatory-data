# What the workflow does now

**Implementation update:** [DATASET_RELEASE.md](DATASET_RELEASE.md) describes the new integrated `build_dataset.py` command. It supersedes the two-path description below for the new dataset; older tools/results remain documented for audit. The integrated build is still release-blocked, not a final approved dataset.

> Target updated 21 October: [REQUIREMENTS.md](REQUIREMENTS.md) supersedes earlier merger-reference proposals. Use dated highest-parent grouping; keep predecessors separate before the official merger date. No retroactive "always merged" history is requested. Existing implementation/results below are not yet the complete new target.
Updated 21 October 2026. Checked against the current code; this documentation update does not rerun or approve the data.

## Two paths, not one fully integrated command

| Path | What it does | What it does not do |
|---|---|---|
| One-quarter automation: `src/run_workflow.py` | Prepare source snapshots, process one quarter, produce financial tables and a separate NIC ownership audit | Does not build the 12-quarter panel or apply the NIC audit as a financial-row filter |
| Full panel: `src/build_panel.py` then `src/review_panel.py` | Combine 2023–2025 and produce `organisation_financials` with the NIC ownership filter and coverage/exception tables | Does not use the new automation's snapshot receipts or create merger-adjusted history |

The full-panel scripts still read expected filenames directly from `research/`. A refresh through the one-quarter command does not automatically refresh the existing full panel.

## One-quarter command: actual sequence

1. **Choose a calendar quarter.** Default: 31 December 2024. Q2–Q4 also need the immediately preceding quarter for income. Q1 does not need prior-year financials.
2. **Find the sources.** Use a validated automated-download receipt when present; otherwise use the expected local file. Download missing sources unless `--offline` is selected. `--refresh` requests new copies rather than overwriting original files.
3. **Check inputs.** Verify dates, identifiers, expected columns and FDIC response completeness. Reject invalid ZIP/CSV/JSON content. Any blocked required source prevents financial processing.
4. **Preserve source evidence.** Keep hash-addressed copies, source URLs/parameters and a per-run manifest. Record retrieval time for new downloads; imported legacy files have unknown retrieval time.
5. **Build financials.** Select observed Y-9C filers; link banks using same-quarter FDIC holder identifiers. Use consolidated holder core balances, not those balances plus subsidiaries again. Blank/zero/self-holder banks remain standalone candidates.
6. **Prepare measures.** Assets, loans, deposits and equity are quarter-end stocks. Income is Q1 YTD directly, otherwise current YTD minus prior-quarter YTD. BHC loans net of unearned income and bank loans net of allowances remain different columns.
7. **Add deposit detail separately.** Aggregate matched-bank total/domestic/foreign/domestic-interest/domestic-noninterest deposits. Preserve missing contributors and differences from consolidated deposits; do not add the deposit sum to core deposits.
8. **Audit ownership separately.** Read dated NIC relationships and write bank ownership checks. Record transformation-event review classifications for the existing fixed 2023–2025 event window. This audit does not remove rows from the quarter's financial tables.
9. **Export diagnostics.** A unique run directory contains financial CSV/Parquet/DuckDB files, ownership evidence, readable and JSON workflow reports, and REVIEW_REQUIRED markers.

Financial-check failures retain diagnostic outputs and return exit 2. Missing/invalid sources or processing failure return exit 1. Exit 0 is not research approval. Download-only mode skips financial processing.

## Where downloads stand

Live FDIC downloading succeeded in the last test. NIC financial and structure requests were blocked; the command reports the manual browser-download step. It does not bypass challenges. Current NIC downloads are publications with dated history, not vintage archives.

See [AUTOMATION.md](AUTOMATION.md) for commands, source-cache precedence, outputs and verified results.

## Existing full-panel path

The panel builder processes all twelve 2023–2025 quarters and assembles intermediate tables. The review script retains raw banks, audits dated control chains, excludes standalone candidates with NIC parents, and writes the reviewed organisation table plus coverage, exceptions and merger-quarter flags.

The saved panel has 13,662 organisation-quarter rows and 55,090 raw bank-quarter rows. Another 40,430 bank-quarter observations have a reported holder without a selected Y-9C observation: they are retained in raw data, not included in the main organisation table or converted into bank-only group aggregates.

These are earlier saved-run counts, not newly recomputed totals. See [PANEL_STATUS.md](PANEL_STATUS.md).

## What is still not finished

- Fully unattended NIC downloads and a single snapshot-based command for the complete panel.
- Complete institution classification/coverage and bank-only holder groups without Y-9C observations.
- Resolution of ownership disagreements, missing values and financial validation failures.
- Independent reconciliation to agreed reference filings and stakeholder-approved financial definitions.
- Merger-adjusted financial history. Events and flags are evidence for review, not adjusted values.
- Historical extension before 2023 and a publication approval gate.

The merger reference date remains provisionally 31 December 2025. Partial acquisitions, failed-bank purchases, accounting differences and missing historical data still require agreed treatment.
