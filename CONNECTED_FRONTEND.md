# Connected frontend — current operation

The public ChatGPT Site uses a restricted Windows-local Python processor through temporary HTTPS. Current selectable scope is **2023 Q1–2026 Q2**; no earlier-year availability is claimed.

## Using the Site

1. Open **Workspace** and choose inclusive From/To quarters.
2. Press **Prepare dataset**. Status follows queued, source checks/acquisition, processing, validation and export.
3. When ready, press **Download full CSV**: all institutions in the delivered cohort and all 236 columns.
4. Expand **Preview & supporting reports** for delivered validation, original-input validation, quarantined rows, period coverage, measure coverage, the complete 236-column dictionary and source provenance.
5. **Download available snapshot** downloads existing published data for the selected period, without a new build. Its row count may differ because it is a separate frozen cohort.

No institution, basis or column filters are required. Refresh is not required between builds.

## Quality and interpretation

New builds use `CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1`. Uncertain quarterly flows are withheld; stocks and reported YTD evidence remain. Input and delivered-row checks use the broader component identities. Failed rows are quarantined, not corrected. The result displays input failures, quarantine count, withheld values, delivered failures and NOT_TESTABLE counts separately.

Old jobs do not acquire this policy retroactively. Their Site result is labelled legacy; prepare a new build to apply the gate. All results remain research drafts. Passing accounting identities does not prove complete ownership, full-population coverage or financial accuracy. Frozen publication also has additional ownership-completeness rules; do not assume identical cohorts.

## Download and refresh behaviour

All job CSV downloads—including validation, input validation, quarantine, period coverage and measure coverage—transfer in 1 MiB pieces with up to three attempts per piece. The browser verifies the full byte count and SHA-256 before saving one CSV. A retry retains completed pieces in tab memory; the same report button resumes that report without rebuilding. Only one CSV transfer runs at a time. Build/reconnect controls are guarded during transfers and preview loading, and filenames retain the original job's dates.

Refreshing restarts an incomplete transfer, but session storage restores the job status/result in the same tab. A `?job=<32-hex-id>` link can reopen an existing result on the configured processor. Job IDs are public-source result references, not authentication. Sources and results remain on the local processor.

## Start and reconnect

```powershell
.\.venv\Scripts\python.exe src/start_frontend_pilot.py
```

The launcher verifies the pinned official Cloudflare executable hash, starts the processor if absent and creates a temporary tunnel. It prints owned process IDs and the HTTPS address. Keep the computer awake, connected, and both processes running. There is no startup service, paid hosting or uptime guarantee.

After a tunnel restart, paste the new address under **Methodology → Reconnect the temporary processor**. Do not enter credentials. Stop only verified owned processes after confirming no build is active. Windows Python redirectors may create a serving child process.

Logs: `outputs/pilot_runtime/`. Private job records/logs: `outputs/public_jobs/`. Do not expose a project-directory file server.

## Restricted API contract

| Route | Purpose |
|---|---|
| GET /pilot/health | Connectivity, active-job indicator, supported bounds |
| POST /pilot/jobs | Exactly start/end quarter-end strings; submit bounded job |
| GET /pilot/jobs/{id} | Actual status, events and quality counts |
| GET /pilot/jobs/{id}/dataset | Paged preview of delivered rows |
| GET /pilot/jobs/{id}/result-manifest?file=KIND | Byte count, part count and SHA-256; default KIND=result |
| GET /pilot/jobs/{id}/result-part?file=KIND&index=N | One bounded piece; KIND is an allowlisted CSV artifact, never a path |
| GET /pilot/jobs/{id}/result | Legacy whole-CSV route |
| GET /pilot/jobs/{id}/validation | Delivered-row checks |
| GET /pilot/jobs/{id}/validation-input | Original-row checks and failure evidence |
| GET /pilot/jobs/{id}/quarantine | Rows excluded from delivery |
| GET /pilot/jobs/{id}/periods | Requested/delivered/missing-quarter CSV with reasons |
| GET /pilot/jobs/{id}/coverage | Upstream mapping availability |
| GET /pilot/jobs/{id}/dictionary | All actual output columns, units, source fields, calculations and missingness |
| GET /pilot/jobs/{id}/provenance | Sanitised source receipts and quality summary |

## Limits and security

One active build, one waiting slot; 60-second submission interval, 10 jobs per UTC day, maximum 14 quarters, 30-minute build limit and minimum disk-space check. Requests use fixed argument arrays, never user-selected commands or filesystem paths.

CORS/origin checks are not authentication. Anonymous public requests are intentional; limits are shared by everyone. Operator routes, raw archives, private logs and arbitrary files are not served. Interrupted work is marked INTERRUPTED on restart. No browser credentials are required.

The processor indicator refreshes every 30 seconds. Status requests never overlap. Temporary failures back off at 2, 4, 8, 16 and 30 seconds, then pause after six failed attempts. HTTP 400/401/403/404/410/422 errors stop immediately; 408/429/5xx may retry. **Resume status checks** explicitly restarts a paused transient-error poll, without submitting a duplicate job. Health checks do not re-enable an active build button. These are bounded reconnection attempts, not an uptime guarantee.

Partial jobs end as **COMPLETED_PARTIAL_REVIEW_REQUIRED**, with requested/delivered/missing periods and downloadable period coverage. Missing current financial inputs omit the affected quarter. Missing prior inputs retain available stocks/YTD but withhold quarter flows; missing expanded bank schedules fall back to available core inputs with a limitation flag. Missing shared ownership/event data or no usable quarter still blocks safely. No source or value is fabricated.

The dictionary endpoint also builds a complete dictionary for older jobs from their original saved mapping and actual CSV header. New builds save output_dictionary.json. Large static snapshot downloads use a separate export path, not built-result resumable transfers.

## Verification

21 October 2026 quality-policy replay: job `95852a83053440a2a82b1bdc4171fd75`
is an operator-run offline replay, not a website-submitted job. It uses the same
41 source receipts as legacy job `72ed20e582cd463aa2e846e52b878409`, covering
2023 Q1–2026 Q1. Results: 55,626 delivered rows, 236 columns; 78,612 uncertain
quarterly values withheld; two input failures and two rows quarantined; zero
delivered-row failures, 67,003 PASS and 378,005 NOT_TESTABLE. Unresolved ownership:
388 records. Regression check: 109 passed, one optional skipped.

Regression command: `python -m pytest -q tests --basetemp=test_temp_review`. See the latest test result rather than historical counts. Full-size CSV transfer previously verified 55,628 rows, 236 columns and 32,397,413 bytes with a matching checksum; that count belongs to the legacy pre-gate build, not the revised cleaned cohort.
