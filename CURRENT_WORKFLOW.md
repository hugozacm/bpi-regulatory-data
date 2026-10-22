# Current workflow — available-data frontend pilot

## Scope

The active classroom pilot covers inclusive **2023 Q1–2026 Q2**, 236 columns and CSV delivery. Historical expansion remains a separate incomplete programme. No retrospective always-merged series or certified full-population coverage is claimed.

## End-to-end

1. The public Site submits exactly the selected start/end quarter-end dates to the restricted local API.
2. The worker checks saved official source hashes and reuses snapshots. Missing required sources are acquired when accessible; browser challenges require normal manual intervention.
3. Read Y-9C and FDIC Call Report-derived data. Verify quarter/identifier keys and complete FDIC response counts.
4. Resolve dated NIC control roots; use consolidated Y-9C core figures without adding subsidiary balances again. Keep labelled bank-only aggregates; unresolved ownership is recorded, not declared independent.
5. Preserve bank deposit detail separately. Stocks stay at quarter-end; compatible adjacent YTD values produce quarterly flows.
6. Apply `CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1`: retain original computed rows/checks, withhold flagged quarterly flows, quarantine rows with accounting failures, and recheck the delivered cohort. Reject duplicate keys and removal of an entire requested quarter.
7. Export all 236 columns and separate validation, quarantine, coverage, ownership and provenance evidence. Missing checks are NOT_TESTABLE, not PASS.
8. The Site loads the completed job and downloads a checksum-verified CSV using resumable pieces.

## Evidence files

`organisation_financials.csv` is the delivered cohort. `raw_organisation_financials.csv` preserves pre-gate calculations, `validation_input.csv` preserves original checks, `validation.csv` checks delivered rows, and `financial_quarantine.csv` records excluded rows. Original regulatory inputs remain immutable hash-addressed snapshots.

`measure_coverage.csv` describes upstream mapping availability, not post-suppression cell counts. `measure_dictionary.json` preserves the schedule mapping specification; `output_dictionary.json` documents every output column. `period_coverage.csv` identifies delivered/missing quarters and missing-prior/detailed-schedule limitations. `release_report.json` contains policy version, quality counts, sources and blockers.

The frozen published fallback remains separate. It additionally applies ownership-completeness exclusions and bank-detail suppression. Its older counts must not be presented as the latest on-demand result.

## Operation and limitations

See [CONNECTED_FRONTEND.md](CONNECTED_FRONTEND.md) for launch, reconnect, bounded status recovery, API routes and limits. The computer/tunnel must remain running. Public job limits are shared. Available quarters can be delivered partially; missing shared ownership/event inputs or no usable quarters still blocks the result rather than guessing.

Institution classification, domestic-versus-global root selection, missing detailed bank equivalents, source amendments and independent filing reconciliation require further work. Passing tests or accounting identities is not financial certification. Predecessors remain separate before official effective merger dates.

Historical acquisition/staging tools are documented in [HISTORICAL_EXTENSION.md](HISTORICAL_EXTENSION.md). Their raw archives do not establish integrated analytical coverage.

## Automatic reconnection — 22 October 2026

Run `Start BPI.cmd` after restarting the laptop. The launcher privately registers its current temporary HTTPS origin at the existing Site. The browser reads the non-cacheable connection record on load and during health checks; no address copying or republication is required. The processor remains local and must stay awake. See CONNECTED_FRONTEND.md for the owner-only registration credential and setup limits. Dataset preparation and the 236-column output are unchanged.
