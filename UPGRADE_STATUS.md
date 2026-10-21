# Implementation history

> Target updated 21 October: [REQUIREMENTS.md](REQUIREMENTS.md) supersedes earlier merger-reference proposals. Use dated highest-parent grouping; keep predecessors separate before the official merger date. No retroactive "always merged" history is requested. Existing implementation/results below are not yet the complete new target.

This is a historical change log. [README.md](README.md), [PANEL_STATUS.md](PANEL_STATUS.md) and [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) describe current behaviour.

## Stage 1 — small-quarter proof of concept

Started with a small holding-company and bank sample to verify official source parsing, selected financial mappings, stock versus YTD income conversion, ownership links and CSV/Parquet/DuckDB outputs. Earlier sample counts do not describe the current population.

## Stage 2 — stronger quarterly controls

Added precise integer parsing, raw filing date and identifier checks, FDIC response completeness checks, adjacent-quarter validation, strict missingness, separate loan definitions and deposit contributor/perimeter diagnostics. Core balances of matched subsidiaries are not added to consolidated holder financials.

## Stage 3 — 2023–2025 draft panel

Implemented all 12 quarters, all observed Y-9C filers and bank candidates. The saved source snapshot yields 55,090 raw bank-quarter rows and 13,662 final organisation-quarter rows.

Added dated NIC control-chain ownership review, raw-bank and coverage tables, exception exports, transformation-event classification and potentially affected-quarter review flags.

## Still outstanding

One-quarter download automation was added on 21 October 2026; see [AUTOMATION.md](AUTOMATION.md). Saved-source processing and live FDIC download were verified. Scripted NIC requests remain blocked and require the documented manual fallback.

- Complete institution-type screening and coverage of holder groups without Y-9C observations.
- Independent reference-filing reconciliation and resolution of material ownership/value exceptions.
- Agreed comparable financial/deposit definitions and restatement handling.
- Verified merger lineage and actual merger-adjusted financial histories.
- Earlier history after source/mapping continuity checks.
- A publication release gate; current exports remain REVIEW_REQUIRED.

The workflow and table images now distinguish implemented outputs from planned merger adjustment. Source files and generated financial datasets are excluded from GitHub. See [stakeholder questions](REVIEW_QUESTIONS.md) before approving methodology.
