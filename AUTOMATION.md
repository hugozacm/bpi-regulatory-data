# Download-and-run workflow

Implemented 21 October 2026. This first automation runs **one quarter**, including the preceding quarter when needed for income. It produces quarterly intermediate financials and a separate NIC ownership audit, not the final filtered organisation panel. Existing full-panel commands remain available.

## Run from the cloned repository root

After installing README requirements:

```powershell
.\.venv\Scripts\python.exe src\run_workflow.py --period 20241231
```

The command checks for saved sources, downloads missing files, validates them, preserves hash-addressed snapshots, runs the quarter and NIC audit, and writes CSV/Parquet/DuckDB financial tables plus review reports.

```powershell
# Reproduce from saved sources without network requests
.\.venv\Scripts\python.exe src\run_workflow.py --period 20241231 --offline
# Attempt new official downloads without replacing earlier source snapshots
.\.venv\Scripts\python.exe src\run_workflow.py --period 20240331 --refresh --download-only
```

Missing or invalid inputs block processing. Put manually downloaded NIC files in `research/` under the expected filenames, then rerun **without** `--refresh`. A previously validated automated-download receipt takes precedence over a legacy local file. Refresh fetches a new snapshot and advances the receipt; earlier source bytes remain available. Each run records exact snapshot paths and hashes. Receipts are cache pointers, not the permanent provenance record.

## Official downloads and limitations

### Browser fallback update — 21 October

A blocked direct request is not proof of a CAPTCHA. Reports now distinguish `DIRECT_REQUEST_BLOCKED`, `HUMAN_VERIFICATION_INDICATED`, `DOWNLOAD_TIMEOUT` and other source failures. Human-verification detection is a response-text heuristic, not a live browser inspection. Check the actual browser page before asking a person to complete a CAPTCHA.

Browser downloading succeeded for 2025 NIC financial files during a separate interactive check; no CAPTCHA was displayed. Another download attempt timed out. This does not establish that every source downloads unattended.

To import browser downloads, save them with exact expected names in a dedicated folder, then run:

```powershell
.\.venv\Scripts\python.exe src\run_workflow.py --period 20241231 --browser-source-dir C:\BPI-downloads --offline
```

Explicitly supplied files take precedence over old cache receipts, are validated and snapshotted, and remain untouched in the browser folder. Their original retrieval time is unknown rather than inferred. Missing files in that folder fall back to the normal saved-source lookup. Duplicate names such as `BHCF20241231 (1).ZIP` must first be saved/copied under the exact expected name; ambiguous copies are not automatically selected.

The Python command does **not** launch/control a browser or solve CAPTCHAs. The fallback is an explicit browser-download/import handoff, not fully automatic browser acquisition.

- FDIC uses the existing selected-field API, not raw FFIEC CDR schedules. Response totals, bank identifiers, dates and required field keys are checked.
- Y-9 uses the existing NIC financial download route. ZIP/caret content, required fields, dates and selected-filer identifiers are checked.
- NIC structure URLs are discovered only from literal official-page links naming the expected CSV ZIP. No guessed endpoint, CAPTCHA bypass or browser automation is used. JS-only links or a challenge require manual download.
- NIC structure ZIP CRC, required CSV columns and nonempty content are checked; the existing audit applies dated control relationships. Current publications are not vintage snapshots.
- Transient HTTP failures have two bounded retries; access denials are not retried as if they were ordinary server failures. Network requests have connection/read timeouts. This is a sequential small-quarter tool, not a scheduler or bulk-history downloader.
- Download payloads are held in memory; FDIC responses above the 10,000-row request cap fail completeness validation rather than being silently truncated. Pagination is not implemented.
- `retrieved_at_utc` is recorded for newly downloaded files. Legacy browser files have unknown retrieval time, explicitly null. `observed_at_utc` is not substituted for that time.

## Outputs and exit codes

Each run has a new `outputs/automated/<UTC-time>-<unique-id>/` directory; earlier financial runs are not overwritten.

- `workflow_report.json`: source status, provenance, processing status and exit code.
- `workflow_report.md`: short readable review report.
- `<quarter>/`: financial CSV/Parquet tables, `bpi_mvp.duckdb`, validation and provenance.
- `ownership_review/`: separate bank ownership audit, event-review CSV and history summary. This audit does not filter the quarterly financial table. Its existing transformation-event window remains 2023–2025, regardless of the selected financial quarter.
- `REVIEW_REQUIRED.txt`: no publication approval or merger-adjusted-history claim.

Exit 0 means execution completed and financial checks passed, or download-only preparation succeeded. It **never** means research approval. Exit 1 means blocked inputs or processing failure; exit 2 means financial checks failed after diagnostic outputs were retained. The panel builder's existing behaviour is unchanged.

## Verified results — 21 October 2026

- Saved-source Q4 2024 completed: 383 observed Y-9C filers, 770 initial standalone-candidate banks and 435 subsidiary links. NIC separately audited 4,560 bank records: 3,787 confirmed holder chains, 744 with no parent found, 26 missing FDIC holders with NIC parents and 3 disagreements. Quarterly financial validation remains false; exit 2 is expected.
- A live Q1 2024 download-only refresh downloaded and validated FDIC data. NIC financial and both structure downloads were blocked and reported; processing did not run. Fully unattended NIC downloading is **not verified**.

The financial mappings and merger methodology have not changed. Downloaded data and receipts are excluded from GitHub. See README for the complete panel and unresolved coverage issues.
