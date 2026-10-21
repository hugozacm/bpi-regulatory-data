# Current architecture — stakeholder walkthrough

> Historical or alternate implementation guide. For the active public pilot, controls, quality gate and current run commands, use [README.md](README.md), [CONNECTED_FRONTEND.md](CONNECTED_FRONTEND.md) and [CURRENT_WORKFLOW.md](CURRENT_WORKFLOW.md). Counts and disconnected-hosting statements below describe that earlier stage, not the live Site.

> Historical/pilot document: retained for audit, not the current implementation contract. Use [CURRENT_WORKFLOW.md](CURRENT_WORKFLOW.md), [MVP_V1.md](MVP_V1.md), [HISTORICAL_EXTENSION.md](HISTORICAL_EXTENSION.md) and [REQUIREMENTS.md](REQUIREMENTS.md) for current scope. Any fixed December 2025 merger-reference proposal below is withdrawn; predecessors remain separate before official mergers.

**New integrated entry point:** `src/build_dataset.py` uses snapshot acquisition, `top_level.py` grouping, the active `config/expanded_measures.json`, and combined financial/coverage/validation exports. See [DATASET_RELEASE.md](DATASET_RELEASE.md). Earlier stage descriptions below are retained but are not the complete integrated architecture.

> Target updated 21 October: [REQUIREMENTS.md](REQUIREMENTS.md) supersedes earlier merger-reference proposals. Use dated highest-parent grouping; keep predecessors separate before the official merger date. No retroactive "always merged" history is requested. Existing implementation/results below are not yet the complete new target.

For the distinction between one-quarter automation and the filtered full panel, see [CURRENT_WORKFLOW.md](CURRENT_WORKFLOW.md). Automated refreshes do not automatically refresh the existing full panel.

Status: REVIEW_REQUIRED. This describes the implemented 2023–2025 draft, not a certified or merger-adjusted dataset.

## Simple workflow

Official NIC Y-9C ZIPs + FDIC selected financial fields
→ quarterly source/date/completeness checks
→ same-quarter bank-to-holder matching
→ consolidated holder financials + candidate standalone bank financials
→ separate matched-bank deposit sums + quarterly income conversion
→ combine all 12 quarters
→ dated NIC control-chain audit and candidate-bank exclusions
→ organisation table + raw banks + validation and source evidence.

In a parallel review branch, NIC transformation records produce merger-event classifications and potentially affected-quarter flags. They do not change historical financial values.

## What each programme does

| Programme | Implemented responsibility |
|---|---|
| `src/run_workflow.py` | One-quarter source acquisition, immutable snapshots, blocked-download reporting, financial run and separate NIC audit; see AUTOMATION.md |
| `src/bpi_pipeline.py` | Parse a quarter, select Y-9C filers, match FDIC banks, prepare stocks/flows and deposit sums, export checks and provenance |
| `src/build_panel.py` | Process 12 quarters and assemble intermediate CSV, Parquet and DuckDB tables |
| `src/history_audit.py` | Read dated NIC control relationships and transformation events; classify events conservatively |
| `src/review_panel.py` | Audit ownership, remove candidate banks with NIC parents, export the main draft and review evidence |

Run commands and required source filenames are in [README.md](README.md). The measure map documents mappings implemented directly in Python.

## Main output structure

`organisation_financials`: one row per organisation and quarter.

- Identity: entity key, name, entity level and report date.
- Core values: assets, source-specific loans, deposits, equity, YTD income and quarterly income.
- Deposit detail: matched-bank total, domestic, foreign, domestic interest-bearing and noninterest-bearing deposits, bank count and difference from core deposits.
- Release status: REVIEW_REQUIRED.

Amounts are USD thousands. BHC loans (`BHCK2122`, net of unearned income) and bank loans (`LNLSNET`, net of allowances) occupy different columns: they are not equivalent definitions. Candidate banks use their own deposits in the columns prefixed `bank_subsidiary_`.

Supporting tables retain raw banks, intermediate financials, ownership links, NIC audit results, validation, missing/negative-value exceptions, merger events and source provenance. `processed_at_utc` is a processing time, not an inferred download time.

## Inclusion and double-counting logic

Use Y-9C consolidated balances for selected holders; do not add their bank subsidiaries' core balances again. Deposit detail is a separately labelled bank-perimeter aggregate, not an addition to consolidated deposits.

Blank/zero/self FDIC holders initially create standalone candidates. The final filter retains these only when the dated NIC control graph finds no parent; this is not proof of standalone status.

The saved run contains 13,662 organisation-quarter rows and 55,090 raw bank-quarter rows. It removes 326 candidate observations with NIC parents. Another 40,430 bank-quarter observations have a reported holder without a selected Y-9C row: retained as raw evidence but excluded from the main table. Bank-only group aggregates remain unimplemented.

## Stocks, flows and missingness

Stocks use quarter-end balances. Q1 income equals YTD; Q2–Q4 income is current YTD minus adjacent prior-quarter YTD. Missing prior values remain missing. FDIC quarterly income is cross-checked. Merger effects, restatements and perimeter changes are not automatically repaired.

Missing deposit contributors remain missing; they are not turned into zero. Domestic interest-bearing plus noninterest-bearing deposits are checked against domestic deposits. Consolidated-versus-bank-sum differences are exposed for review, not eliminated mechanically.

## Validation is not a release gate

The full population has unresolved checks. The single-quarter CLI returns exit code 2 on failed financial checks, but the panel builder continues and retains diagnostics. A completed export is not publication approval.

The saved intermediate measures contain 1,618 missing values and 30 negative stock flags; negative equity can be genuine. These counts are not a count of errors in the final filtered table. No duplicate organisation-quarter keys were found, but this does not prove every ownership overlap has been resolved.

## Merger adjustment — planned, not produced

Current outputs contain 1,350 dated NIC transformation records and 103 potentially affected holding-company quarter flags. No event is automatically approved to rewrite history.

Provisional reference date: 31 December 2025. Predecessor lineage, deal scope, legal versus consolidation dates, partial transfers, failures, accounting and merger-quarter income must be agreed and verified before constructing an adjusted history.

See [review questions](REVIEW_QUESTIONS.md), [panel status](PANEL_STATUS.md), and the two PNGs in `review_images/`. PNG figures are illustrative, not extracted financial observations.
