# BPI regulatory-data research MVP

Classroom research prototype; not an official BPI product or financially certified dataset.

## Current product — 21 October 2026

The existing public [BPI-styled workspace](https://bpi-regulatory-research-hugo.amusedvine18.chatgpt.site/) supports **2023 Q1–2026 Q2**, inclusive, and exports **236 columns**. Earlier historical expansion is paused for this frontend pilot, not completed or silently discarded.

**Choose From/To quarters → Prepare dataset → follow actual status → Download full CSV.**

New jobs run on the owner's awake Windows computer through a temporary HTTPS tunnel. They reuse verified sources and attempt missing official downloads. No paid API or hosting is required. CAPTCHA/access restrictions may require manual source acquisition; the code does not bypass them.

**Download available snapshot** is a separate fallback using previously published data for the chosen quarters. It does not run a build. There are no institution, basis or column filters in the public interface.

## Financial delivery policy

New integrated builds apply `CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1`:

- Keep stocks at quarter-end and reported YTD evidence. Withhold all quarterly-flow values flagged for uncertain ownership/reporting perimeter.
- Run net-interest, interest-income components, interest-expense components and trading-revenue component checks for YTD and quarterly values.
- Preserve original-row checks; quarantine institution-quarter rows with failures. Re-run checks on delivered rows. Missing inputs are NOT_TESTABLE, never PASS.
- Reject duplicate keys or a quarantine that removes an entire requested quarter.
- Retain raw rows, quarantine and validation evidence. Do not silently repair reported values.
- Prefer dated top-root Y-9C consolidated figures, do not add subsidiary core balances again, and keep Call Report deposit detail separate.

The published frozen snapshot also has ownership-completeness exclusions and bank-detail suppression. Those additional frozen-release rules are not newly claimed for on-demand builds. Unresolved ownership, institution classification and missing bank-field equivalents remain limitations. Predecessors remain separate before official merger dates; no retrospective always-merged history is claimed.

Old completed jobs are immutable legacy evidence. Their download should not be described as having the new policy; the site labels them and asks for a new build.

## Run locally

Use Python 3.12 from this project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/start_frontend_pilot.py
```

After restarting the laptop, double-click **Start BPI.cmd** in this folder (or run the launcher above). It registers the current connection automatically; no link pasting or republishing is required on the configured laptop. Keep the processor, tunnel and computer running. This is not an automatic Windows startup service. See CONNECTED_FRONTEND.md for owner-key provisioning on a different computer.

Direct build and exact-source replay:

```powershell
.\.venv\Scripts\python.exe src/build_dataset.py --start 20230331 --end 20260331
.\.venv\Scripts\python.exe src/build_dataset.py --start 20230331 --end 20260331 --offline --source-manifest outputs/dataset/YOUR_RUN/release_report.json
.\.venv\Scripts\python.exe -m pytest -q tests --basetemp=test_temp_review
```

Builder exit 2 means review-required research output, not automatic financial approval. Inspect processing_status, source_errors, quality_policy and validation. Available quarters are delivered with an explicit period-coverage report. A missing current source omits that quarter; missing prior inputs withhold quarterly flows. Missing shared ownership/event files still block delivery safely.

## Outputs and evidence

Each build has its own directory under `outputs/dataset/`:

| File | Meaning |
|---|---|
| organisation_financials.csv | Delivered institution-quarter data, 236 columns |
| raw_organisation_financials.csv | Original computed rows before the delivery gate |
| financial_quarantine.csv | Rows excluded for accounting conflicts; empty file retains headers |
| validation_input.csv | Broader checks on original rows, including failures |
| validation.csv | Checks on delivered rows, including NOT_TESTABLE |
| ownership_ledger.csv | Period-specific bank-to-root matching and unresolved records |
| measure_coverage.csv | Acquisition/mapping availability before the delivery gate |
| release_report.json | Source receipts/hashes, policy, counts, blockers |
| measure_dictionary.json | Original 106-field schedule mapping specification |
| output_dictionary.json | Complete 236-column dictionary: metadata, units, source codes, calculation and missingness |
| period_coverage.csv | Requested quarters, delivered/missing status and input limitations |

CSV is the user-facing deliverable; DuckDB/Parquet are reproducible processing artefacts. Monetary values are USD thousands; missing is not zero. Coverage counts describe upstream mappings and must not be read as post-withholding cell counts.

## Documentation and implementation

Use this repository's `main` checkout as the shared source for Codex and GitHub
Desktop. See [GitHub synchronisation](GITHUB_SYNC.md). GitHub push, Site publication
and Python processor restart are separate actions; synchronising code does not
automatically deploy or rebuild financial data.

- [Connected frontend](CONNECTED_FRONTEND.md): current operation, endpoints, downloads and security.
- [Frontend](FRONTEND.md): public source and publication process.
- [Current workflow](CURRENT_WORKFLOW.md): acquisition, grouping, quality gate and outputs.
- [Historical extension](HISTORICAL_EXTENSION.md): separate unfinished historical programme.
- [Frozen MVP v1](MVP_V1.md): earlier frozen delivery, not a new on-demand build.
- `config/delivery_scope.json`: separates the active available-data pilot from the longer historical objective.

Older panel, Streamlit, operator API, Render and GitHub Actions notes describe alternate/earlier implementations, not the active public path. GitHub Actions remains disabled by default. Local raw sources and generated results are excluded from the main repository; publishing the Site does not back up the backend or source cache.
