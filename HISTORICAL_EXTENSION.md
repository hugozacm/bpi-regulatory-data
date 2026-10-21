# Historical extension — acquisition and raw staging, not a harmonised release

> **Current scope correction:** The MVP must cover the longest reliable historical period, not just 2023–2026. The existing package is an interim snapshot and does not complete the MVP. Historical acquisition, harmonisation and integration are required MVP work, not optional post-MVP backlog. Earlier statements describing the narrowed delivery as the finished MVP are superseded. See [config/delivery_scope.json](config/delivery_scope.json). Current status: **INCOMPLETE_HISTORICAL_MVP**.

## Historical processing implemented

`src/build_historical.py` now processes downloaded holding-company CSV archives into a long-format reported-value dataset, available as CSV, Parquet and DuckDB. It defaults to requesting 1986 Q3–2026 Q2 and explicitly lists missing quarters. It validates identifiers, dates, duplicate records, column shape and source hashes before accepting a quarter. Values and original field codes remain strings: no modern mapping, ownership or stock/flow interpretation is imposed on older filings.

```powershell
.\.venv\Scripts\python.exe src\build_historical.py --start 19860930 --end 20260630
```

Outputs are under a new `outputs/history/` run directory, with `history_report.json` recording actual loaded periods, errors, provenance and remaining gaps. This staging dataset includes reported holding-company archive records; it does not claim every record is a Y-9C filer. It is not interchangeable with the main organisation-quarter table.

The initial real-data staging run loaded 1986 Q3 with 636,409 non-missing reported values. These are field-value observations, not institutions. Exit 0 means available selected files processed without errors, not that the requested range is complete. Check `requested_coverage_complete` and `missing_requested_periods`; `historical_harmonisation_complete` and `financially_certified` remain false. The inventory hash records the exact manifest bytes read, even when downloads subsequently update the manifest.

The user requested the longest available history on 21 October 2026. Frozen MVP v1 remains unchanged. Historical archives are collected separately and must not be interpreted as an already harmonised panel.

## Official archive coverage discovered

| Family | Literal published links found | Coverage |
|---|---:|---|
| Bank financial archives | 140 | 1976 Q1–2010 Q4 |
| Holding-company archives | 139 | 1986 Q3–2021 Q1 |

Sources: [Chicago Fed bank files 1976–2000](https://www.chicagofed.org/banking/financial-institution-reports/commercial-bank-data-complete-1976-2000), [2001–2010](https://www.chicagofed.org/banking/financial-institution-reports/commercial-bank-data-complete-2001-2010), and [holding-company files](https://www.chicagofed.org/banking/financial-institution-reports/bhc-data).

These ranges describe discovered archive links, not guaranteed availability of every modern measure. The holding-company links inspected deliver CSV even where the label/prose refers to ZIP. The initial 1986 Q3 CSV passed identifier, date and record-shape checks. Bank archives are ZIP containers; container validation alone does not validate the SAS financial records inside.

## Reproduce collection

From the project directory, after installing requirements:

```powershell
.\.venv\Scripts\python.exe src\history_sources.py
.\.venv\Scripts\python.exe src\history_sources.py --download
.\.venv\Scripts\python.exe -m pytest -q
```

Discovery uses actual official page links rather than guessed historical URLs. The downloader resumes hash-verified snapshots and records failures without fabricating missing quarters. Review `research/history/chicago_manifest.json` for the actual current downloaded count, errors, source URLs, timestamps, hashes and format inventories. Raw data are excluded from Git.

## Remaining gates before harmonised historical output

1. Finish acquisition and inspect all missing/failed quarters. Obtain the 2021 Q2–2022 Q4 holding-company bridge from NIC, and bank financial data after 2010 from FDIC/FFIEC sources.
2. Parse historical bank SAS XPORT records and verify historical identifiers and report populations. Do not assume that modern identifier fields or financial codes existed throughout the archive.
3. Establish dated mappings for each requested measure, including changes in units, definitions and reporting requirements. Explicitly flag unavailable or non-comparable measures.
4. Verify dated highest-parent ownership. Keep predecessors separate before official mergers; do not impose current ownership on earlier dates. Exclude unresolved grouping rather than double count.
5. Convert YTD flows only with compatible preceding-quarter data and a verified reporting perimeter. Stocks remain quarter-end balances.
6. Run financial, coverage, uniqueness and provenance checks before exporting a separate historical research draft. The current integrated build deliberately retains its 2023–2026 mapping-date guard.

The existing MVP remains the usable scoped delivery. Historical source collection does not expand its validated coverage automatically.
