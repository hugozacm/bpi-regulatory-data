# Integrated dataset delivery — 21 October 2026

**Narrowed MVP delivery:** [MVP_V1.md](MVP_V1.md) packages this upstream build under subsequently agreed assumptions. It excludes/withholds specified uncertain data and preserves all audit evidence. The broader-target release status below is unchanged; MVP packaging does not turn an uncertified build into an approved full-history database.

**This is a working integrated research build, not the requested final approved version.** Historical breadth, detailed bank equivalents and independent validation remain incomplete. A completed run returns exit 2 and BLOCKED_REVIEW_REQUIRED rather than silently claiming finality.

## What is implemented

One command acquires/reuses validated source snapshots, groups banks to dated highest control parents, uses a top-parent Y-9C report where present, otherwise labels bank-only aggregates, adds expanded schedules and produces **one main organisation-quarter table**. Supporting ownership, measure-coverage, validation and provenance evidence remains separate.

No pre-merger history is combined retroactively. Direct and indirect nested-bank overlap suppresses risky bank sums. Ambiguous parents, cycles and FDIC/NIC disagreements are kept in the ownership ledger rather than arbitrarily assigned. Candidate independence and institution types are not certified by this graph.

The active `config/expanded_measures.json` contains 106 fields: HI interest-income/expense components, noninterest-income/expense components and totals, net interest income, credit-loss provision, parent net income, realised gains 6.a/6.b, trading memo 9.a–9.g, HI-A equity/OCI, and HI-B Part I subitems 1–9 (item 2 is not applicable), charge-offs and recoveries. Requested HI-B scope remains the documented Part I assumption.

Source forms checked cover 2023, 2024, 2025 and June 2026. The code refuses dates outside 20230331–20260630 until period-specific mappings are added. Historical reporting eligibility is not fully classified. The provision terminology changes across forms; identical codes must not be treated as proof of complete semantic continuity.

Original YTD values and derived quarterly flows are separate. Stocks are not differenced. Size/office thresholds and unavailable values stay null, with measure-coverage counts. The net-interest identity is checked for every complete YTD/quarterly triple; a passing identity is not independent source reconciliation.

Bank-only quarterly mapped totals are calculated only for stable membership without flagged control/transform events, with complete prior inputs. Net income is also checked against each bank's NETINCQ. Current-member YTD evidence is not mislabelled as a historical group YTD series. Holding-company reported YTD differences are preserved with perimeter-review flags, not merger-repaired.

## Reproduce

Install README requirements and run from the cloned repository root:

The default end is now June 2026. For that extension, use `--end 20260630`; the examples below preserve the original twelve-quarter reproducibility check. Supply the new NIC files through `--browser-source-dir` if they are not already snapshotted.

```powershell
# Downloads missing sources and expanded FDIC total fields; NIC may need browser import.
.\.venv\Scripts\python.exe src\build_dataset.py --start 20230331 --end 20251231
# Offline core sources: detailed bank totals may be absent from earlier narrow responses.
.\.venv\Scripts\python.exe src\build_dataset.py --start 20230331 --end 20251231 --offline
# Exact source replay: use a previous run's manifest and retain its immutable snapshots.
.\.venv\Scripts\python.exe src\build_dataset.py --start 20230331 --end 20251231 --offline --source-manifest outputs\dataset\YOUR_RUN\release_report.json
```

`--browser-source-dir` accepts exact-name official downloads. Legacy `research/` files are not overwritten. Each build has a unique directory under `outputs/dataset/`. Expanded FDIC downloads are separate hash-addressed snapshots. Replay checks source and mapping hashes. Processing failures can leave partial diagnostics; only a completed release report establishes completed processing.

Main output: `organisation_financials.csv`, `.parquet` and the corresponding table in `dataset.duckdb`. Monetary fields are USD thousands; the integrated main table uses explicit nullable integer types for financial values. Identifiers, source basis and flags accompany the values.

Evidence: `ownership_ledger`, `measure_coverage`, `validation`, `release_report.json`, `release_report.md`, and REVIEW_REQUIRED marker. The release JSON records source URLs, hashes, parameters and known retrieval times. Inputs, snapshots and generated datasets are excluded from GitHub.

The old `build_panel.py`, `review_panel.py`, `run_workflow.py` and `top_level.py` remain available as legacy/pilot tools. They do not become equivalent to the integrated command merely because their files remain in the repository.

## Concrete results

Latest extension: **14 quarters, 2023 Q1–2026 Q2**, with **59,674 organisation-quarter records**, 236 output columns, 417 unresolved ownership-ledger records, no duplicate keys and zero failures across 62,943 complete net-interest identity checks. These are mechanical checks, not comprehensive financial validation. Detailed-bank unmapped cases remain substantial and are counted in measure_coverage. The current suite passes 41 tests with local source fixtures; clean clones skip source-dependent tests.

NIC browser downloads worked for March, June and September 2026 without a CAPTCHA. March/June contain 387/384 observed Y-9C filers. The September ZIP contains only two, so it is retained as an incomplete-source observation and excluded from the main dataset; the mapping bounds also stop at June. This source availability does not establish complete historical coverage or complete June reporting.

Raw Call Report bulk downloading was checked at https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx. It returned HTTP 403 in the normal in-app browser on this run. No CAPTCHA was displayed there. This blocks verification/acquisition of the detailed raw bank schedules through that path; the builder does not bypass it or invent raw-field mappings.

- Integrated twelve-quarter 2023–2025 run: **51,543 organisation-quarter records**, zero duplicate keys, 360 unresolved ownership-ledger records, zero failures among the net-interest identities checked.
- The live full-period run fetched the expanded FDIC total fields; this is distinct from the initial offline run that used narrower responses.
- A live Q4 2024 run produced 4,276 organisation records; exact source replay also completed.
- FDIC Q1/Q2 2026 sources downloaded, but NIC Q1/Q2 2026 scripted requests were blocked. No claim that June 2026 is the latest available quarter has been established.

Different runs may reflect amendments. Saved report paths and hashes identify the actual source vintage; earlier panel counts refer to a different inclusion method and must not be compared as if they were duplicate runs.

## Why it is not final

1. The requested maximum history/latest available endpoint has not been delivered. Additional NIC sources and older period-specific mappings are needed; no mappings are invented for older forms.
2. Detailed Call Report equivalents for many of the 106 fields remain unmapped. Only verified FDIC total-field candidates are requested; bank columns without a verified equivalent remain missing, not copied from Y-9C codes.
3. Parent/institution attributes, foreign roots, incomplete graph coverage and ambiguous ownership need verified treatment. Bank-only accounts omit nonbank activities and consolidation eliminations.
4. Acquisition-quarter income and changing reporting perimeters need reference-filing checks. Partial transactions and failures are not automatically treated as full additive mergers.
5. Missingness/threshold eligibility, amendments and selected institution values need independent official-filing reconciliation and agreed acceptance tolerances.

The official FDIC financial responses provide CERT, RSSDID and RSSDHCR, and the dated NIC graph provides parent paths. These yield a per-quarter identifier/ownership ledger. A separate comprehensive historical crosswalk download has not been verified and is not assumed necessary or sufficient for ownership history.

## Next source handoff (updated)

The March/June 2026 NIC files have now been downloaded and included in the new build. No user CAPTCHA help was needed. To finish detailed bank equivalents, obtain official raw Call Report tab-delimited bulk ZIPs through the CDR bulk page (or an authorised official alternative). Start with Q4 2024 to verify parsing and mappings, then acquire the full chosen period range. Earlier NIC/Call Report availability and schedule continuity still need investigation; source downloads alone do not fulfil maximum history.
