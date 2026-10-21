# BPI MVP v1 — research draft

> **Current scope correction:** The MVP must cover the longest reliable historical period, not just 2023–2026. The existing package is an interim snapshot and does not complete the MVP. Historical acquisition, harmonisation and integration are required MVP work, not optional post-MVP backlog. Earlier statements describing the narrowed delivery as the finished MVP are superseded. See [config/delivery_scope.json](config/delivery_scope.json). Current status: **INCOMPLETE_HISTORICAL_MVP**.

## Delivery scope agreed on 21 October 2026

One main organisation-by-quarter dataset, 2023 Q1–2026 Q2. This is a finished **MVP delivery under explicit assumptions**, not a financially certified or complete historical database. Any failed mandatory MVP check means the package is not accepted, even if files were written.

## Working assumptions

- Group banks to the highest dated NIC control parent supported by the available records. Genuinely independent status, institution types and foreign-root scope are not independently certified.
- Use a top-parent consolidated Y-9C report when available; otherwise label bank-only aggregates. Do not add subsidiary core balances to consolidated reports.
- Keep predecessors separate before the official merger date; no retrospective combination. The current graph uses inclusive effective-date boundaries; transaction boundary conflicts remain review cases.
- Exclude unresolved ownership records from main grouping and retain them in evidence. Additionally exclude bank-only groups that could be incomplete because an unresolved member points to them. Withhold matched-bank detail for affected consolidated groups while retaining their reported consolidated financials.
- Withhold every quarterly financial value on rows flagged for uncertain perimeter changes, retaining reported YTD evidence. Never fill missing detailed bank measures or reporting-threshold blanks with zero.
- Quarantine whole organisation-quarter records that fail an exact accounting identity, keeping original values and failed checks in the evidence. Do not repair numbers to make them balance. The main-table test result must be reported separately from the pre-quarantine failures.
- Source-specific loan/equity definitions and bank-only reporting limitations remain labelled; no claim that all financial perimeters are equivalent.
- No requirement to extend earlier than 2023 or fill every detailed bank field in this MVP. Those are backlog items, not hidden completed features.

## Contents

The delivered cohort contains **59,639 organisation-quarter rows and 236 columns**. Of the 59,674 upstream rows, 33 bank-only groups were excluded for possible missing members and two S&T BANCORP quarters (2024 Q2 and Q3) were quarantined for conflicting trading-revenue identities. Their source values are retained without correction. There are 417 unresolved ownership-ledger records outside grouping. 83,825 uncertain quarter-value cells were withheld.

Financial-test coverage: **71,507 PASS, zero FAIL in the main cohort, and 405,605 NOT_TESTABLE**. Most component tests are not testable, so this is limited validation, not a fully validated financial database. The pre-quarantine report includes two failures. The original packaging run passed 44 software tests; the subsequent historical-extension review expands the suite. See README for the current suite count; clean clones can skip optional source-dependent tests.

- `organisation_financials.csv` / `.parquet`: the **one main dataset**, also available in `mvp_v1.duckdb`. Monetary values are USD thousands.
- `data_dictionary.csv`: all columns, source mappings, units and notes. `measure_mapping.json` preserves the active schedule map.
- `financial_tests.csv`: pre-quarantine PASS, FAIL or NOT_TESTABLE_MISSING_INPUT for net interest, complete interest-income/expense component totals, and trading revenue memo-component totals, on YTD and quarter flows. `financial_tests_main.csv` tests the delivered main cohort; `financial_quarantine.csv` retains excluded conflicting rows.
- `exceptions.csv`: unresolved ownership and groups/detail additionally excluded or withheld at MVP packaging.
- `upstream_ownership_ledger.csv` and `upstream_measure_coverage.csv`: original audit evidence. Coverage counts describe the upstream build, not a recalculation after MVP exclusions/flow suppression; the main table and MVP tests reflect the packaged cohort.
- `upstream_release_report.json`: immutable record of the original broader-target release blockers and source provenance.
- `mvp_manifest.json`: frozen scope, transformations, source hash results, counts and accepted limitations.
- `VALIDATION_REPORT.md`: readable MVP result and financial-test coverage.

Empty cells mean unavailable, unreported or withheld; never assume they mean zero. NOT_TESTABLE is not PASS. Passing accounting identities does not establish full filing accuracy or completeness.

## Reproduce from the repository root

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\build_dataset.py --start 20230331 --end 20260630
# Use the completed output directory printed above:
.\.venv\Scripts\python.exe src\release_mvp.py --input outputs\dataset\YOUR_RUN
.\.venv\Scripts\python.exe -m pytest -q --basetemp test_temp_mvp
```

NIC may need normal browser downloads followed by `--browser-source-dir`. Source data are not included in GitHub or the delivery archive. For exact reconstruction, retain the source snapshots and use build_dataset.py's `--offline --source-manifest` replay with the same mapping version before packaging. Packaging checks every referenced source hash.

Every packaging run uses a new directory. Explicit `--output` must name a directory that does not exist. No upstream financial tables are modified. Exit 0 means the scoped MVP checks passed, not financial certification; exit 2 means an MVP check failed. The upstream builder can return exit 2 because the broader, original target remains incomplete; inspect processing_status before packaging.

## Post-MVP backlog

1. Complete detailed bank-report equivalents using verified official sources; raw CDR access is currently blocked in the tested environment.
2. Resolve ownership exceptions, verify institution attributes and foreign ultimate-parent treatment.
3. Independently reconcile selected group/bank values to official filings; broaden financial tests to all relevant schedules.
4. Verify acquisition-quarter income, control-date boundaries, amendments and reporting thresholds.
5. Extend history and maintain period-specific mapping validity; reassess the incomplete September 2026 release before including it.

No new questionnaire is required to use this delivery scope. Material methodological deviations from these assumptions must be documented rather than silently introduced.
