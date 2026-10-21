# 2023–2025 panel — current delivery

One-quarter source-download automation was added on 21 October 2026. See [AUTOMATION.md](AUTOMATION.md) for its separate test results and limitations. This did not rebuild or approve the full panel described below.

All twelve quarterly NIC holding-company ZIPs and FDIC selected-field financial responses have been downloaded from their official sources and processed. The default output is a research draft, with exceptions retained.

## Results

- 55,090 bank-quarter observations retained in `bank_raw`.
- 13,662 organisation-quarter rows after excluding 326 blank-holder candidates with a NIC control parent.
- 379–390 observed Y-9C filers per quarter; reporting types are not yet independently classified as BHC versus SLHC/IHC.
- No duplicate organisation-quarter keys in the combined analytical table.
- 45,649 FDIC holder observations corroborated in dated NIC control chains.
- 37 FDIC/NIC holder disagreements and 326 blank-holder observations with a NIC parent require review.
- 9,078 bank-quarter observations have no control parent found in NIC. This is a provisional standalone-candidate classification, not independent proof of institutional status or complete NIC coverage.
- 1,618 missing financial measure values and 30 negative stock values retained as exceptions. Negative equity, in particular, can be a real filing value and is not automatically a data error.
- 1,350 NIC transformation rows fall within 2023–2025. They are classified for review, not automatically approved for adjustment.

## Open the output

`outputs/panel_2023_2025/organisation_financials.csv` is the main wide research table. It includes core financials plus separately labelled subsidiary-bank deposit sums. All amounts are USD thousands.

The same folder contains:

- `bank_raw.csv`: every downloaded bank financial row, including banks whose holder does not file Y-9C.
- `bank_coverage.csv`: each bank's original FDIC-based inclusion classification.
- `ownership_audit.csv`: independent dated NIC control-chain checks; this refines the original coverage classification.
- `value_exceptions.csv`: missing values and negative stocks for review.
- `merger_events.csv`: official NIC events, source definition and review status.
- `merger_quarter_review.csv`: potentially affected holding-company flow observations.
- `deposits.csv`: deposit categories, contributor counts, missingness and differences from consolidated totals.
- `validation.csv`, `provenance.csv`, `quarter_summary.json`, `review_summary.json`.
- `panel.duckdb` and matching Parquet files.

## What prevents research release

The full-population validation checks do not all pass. This is explicitly recorded, rather than hidden by retaining only complete institutions.

40,430 bank-quarter observations have a reported holder without a selected Y-9C row. Many may have small holding companies outside Y-9C reporting scope; these remain in `bank_raw` and the coverage ledger, but are not silently relabelled standalone or combined into invented Y-9C financials. A bank-only aggregate for such groups is a distinct methodology still to implement.

Other outstanding work: exclude/classify foreign branches and other reporting types using verified historical institution attributes; reconcile source-specific loans, equity and income; reconcile subsidiary deposit perimeters and intercompany eliminations; assess prior-period restatements; compare selected amounts with reference filings.

## Merger adjustment status

No complete merger-adjusted panel is claimed. The verified NIC transformation code 1 can include purchase-and-assumption transactions and multiple successors. Accounting method 2 does not combine historical income automatically. Legal transformation dates can differ from economic consolidation dates. Each candidate needs scope, date and accounting checks before summing predecessor histories. Partial asset transfers, splits and failures are explicitly flagged. The fixed reference date remains provisionally 31 December 2025.

Official definitions: https://www.ffiec.gov/npw/StaticData/DataDownload/NPW%20Data%20Dictionary.pdf

## Reproduce from the cloned repository root

First complete the environment and source-file setup in [README.md](README.md).

```powershell
.\.venv\Scripts\python.exe src\build_panel.py
.\.venv\Scripts\python.exe src\review_panel.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp test_temp_verify
```

The builder reuses local files, downloading absent FDIC quarters. Official NIC ZIPs must be present in `research/` because their scripted endpoints may show browser challenges. NIC relationship and transformation ZIPs are also required for review. The NIC ZIP hashes and FDIC request metadata are retained; original browser download timestamps are not reconstructed.
