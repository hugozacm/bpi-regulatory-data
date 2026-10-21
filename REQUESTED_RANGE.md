# Requested-range execution: actual implementation

Reusable modern builds must carry `CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1`, as
well as matching mapping/source hashes. Legacy pre-gate outputs are not reused;
they must be rebuilt. This alternate runner still treats partial modern builds
conservatively; the active public pilot has its own explicit partial-delivery path.

## Historical financial pilot now implemented: March 2001

`python src/request_dataset.py --start 20010331 --end 20010331` now invokes `build_legacy_quarter.py` after acquiring the official holding-company file. Bank financial data come from the official FDIC API for the same reporting date, rather than unnecessarily downloading an additional SAS bank archive. Use `--offline` to reproduce from existing snapshots. Other historical periods still lack verified mappings and remain explicitly blocked; the March 2001 mapping is never extrapolated.

Verified output: **4,571 rows, 236 columns, zero duplicate organisation-quarter keys, 1,676 net-interest identities tested with zero failures**. Sources include 9,940 bank records and 2,196 holder identity records; only 1,819 holder records have observed consolidated Y-9C assets. Parent-only LP/SP amounts are never substituted for consolidated finance. The main output has 1,676 consolidated-holder rows and 2,895 bank-only aggregate rows. These are partial coverage counts, not the complete population: 102 ownership links are unresolved and 3,611 candidate groups are quarantined because their highest domestic root is not verified. No zero-filling or missing-parent-as-independent shortcut was used.

The mapping config `config/legacy_20010331.json` cites the official March 2001 form and applies only to that date. It maps assets, equity, deposit components and six income totals; detailed unverified columns remain blank. Quarter income is Q1 YTD without division by four, but is withheld for affected merger/control-change groups. Bank-only income remains withheld pending perimeter reconciliation. Historical accounting definitions (including extraordinary items) are not claimed fully comparable to current reports. The output includes a 236-row dictionary, coverage table, dated ownership ledger, quarantine and validation CSVs, plus source receipts/hashes in the release report.

Local trial output: `outputs/requests/20010331-20010331/organisation_financials.csv`; detailed evidence: `outputs/legacy_financials/20261021T181341Z-19527492`. Request status is **PARTIAL_REVIEW_REQUIRED**, not historical MVP complete. Regression suite after the historical build integration: **101 passed, 1 optional test skipped**. Website-triggered processing remains unconnected; this step did not change or publish the site.

Run from the project directory:

```powershell
.\.venv\Scripts\python.exe src/request_dataset.py --start 20010331 --end 20010331
.\.venv\Scripts\python.exe src/request_dataset.py --start 20240331 --end 20240331 --offline
```

Dates are inclusive quarter ends. Outputs and live local progress are in `outputs/requests/<start>-<end>/status.json`; per-quarter logs are alongside it. Only requested historical archives are downloaded. The modern financial builder also acquires a preceding quarter when required for YTD differences. Verified downloaded bytes are reused. Use `--refresh` to request current official bytes and rebuild; previous hash snapshots remain audit evidence rather than being the active selected version. The command does not poll for amendments automatically.

Supported financial quarters run independently and contribute to one CSV. Missing/blocked quarters do not discard successful quarters. A completed compatible single-quarter build can be reused only while its mapping hash and referenced source-file hashes match. Old historical archives are acquired but remain explicitly blocked from financial output until their mappings and dated grouping are implemented. A raw download is not an organisation-quarter dataset.

States: RUNNING, DOWNLOADING, PROCESSING, COMPLETED_REVIEW_REQUIRED, BLOCKED_SOURCE_ACQUISITION, BLOCKED_HISTORICAL_MAPPING, PARTIAL_REVIEW_REQUIRED, BLOCKED and FAILED. Exit 0 means the entire requested range processed as a review draft; exit 2 means partial/blocked/failed. A green result does not certify financial correctness.

Verified 21 October 2026: bank and holding-company archives for 2001 Q1 acquired from literal official Chicago Fed links, with SHA-256 receipts. The holding-company CSV includes an all-dashes separator row; parser now skips only full-width all-dashes rows and retains strict validation for actual records. Recent-quarter request produced the 2024 Q1 CSV from a compatible cached build (4,335 rows). Historical financial harmonisation remains unfinished.

This command is local. The public website does not start it, display this status live, or acquire older years yet. Public request queuing and secure transport to the local processor are not implemented. The public export has separately been expanded to all 236 columns of the existing snapshot; this does not complete historical coverage.

Historical acquisition rerun: both 2001 Q1 archives now pass acquisition checks. The holding-company parser staged 1,691,574 nonmissing reported field values with zero parsing errors at `outputs/history/20261021T175102Z-0f2d0079`. That is raw staging, not harmonised organisation-quarter output. Regression suite: 97 passed, 1 optional test skipped.
