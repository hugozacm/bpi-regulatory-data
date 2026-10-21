# Agreed direction — 21 October 2026

This records Hugo's instructions in this chat. It is not a claim of separate Laura/BPI approval, complete implementation or financial certification. It supersedes earlier proposed fixed-reference, retroactively combined merger histories.

## Output and grouping

- Deliver one main organisation-by-quarter dataset. Supporting source, mapping, ownership and validation evidence remains available separately for audit, not as competing financial datasets.
- Roll each bank up through the dated ownership hierarchy to its highest holding-company level, not only its immediate parent.
- Retain genuinely independent banks as their own organisations.
- Use a top-level consolidated Y-9C report when available. Do not add subsidiary core balances already included in that report.
- If no suitable consolidated report exists, construct a separately labelled bank-only group aggregate from the member banks. It is not equivalent to consolidated holding-company accounts and may omit nonbank activities or consolidation eliminations.
- Preserve separately labelled bank-perimeter deposit detail alongside consolidated measures. Do not add it to consolidated deposits.

## Dates and mergers

- Extend backwards as far as reliable official online data and verified mappings allow, through the latest available reporting quarter.
- Determine actual earliest/latest availability from sources; neither has yet been established by this requirements update. Existing validated financial inputs cover 2023–2025.
- Before the official merger date, predecessor organisations remain separate. Following the effective date, apply the relevant successor ownership.
- Do not rewrite pre-merger history as if the organisations had always been combined. The old provisional 31 December 2025 merger reference date is withdrawn.
- Quarter-end membership follows dated ownership. Preserve reported consolidated income; do not mechanically add predecessor YTD income. Acquisition-quarter flows, partial purchases, failures and differing ownership/consolidation dates require evidenced treatment and review flags, not invented allocations.

## Identifiers

Check official FDIC identifier/crosswalk sources and their historical coverage. FDIC certificate numbers and RSSD IDs are different keys. Existing inputs include CERT, bank RSSDID and holder RSSDHCR; an identifier crosswalk alone does not prove historical highest-parent ownership. Combine identifier evidence with dated NIC control relationships. Availability of a separate historical FDIC crosswalk is not yet verified.

## Expanded financial scope

Use the supplied June 2026 FR Y-9C filing as the requested reference. Verify actual field codes, definitions, availability and reporting frequency against official forms/instructions for each historical period.

- HI: interest income items; interest expense items; net interest income; provision for credit losses; noninterest income; noninterest expense; net income; all trading-revenue memo items; realised gains/losses in items 6.a and 6.b.
- HI-A: total holding-company equity capital and other comprehensive income.
- HI-B: provisionally Part I, items 1–9, including subitems and both charge-off and recovery columns. This interpretation is a working assumption, not an explicit confirmation that Part II is excluded.
- Keep existing assets, loans and deposit measures unless deliberately replaced by verified definitions.
- Find equivalent Call Report measures for bank-only groups; do not assume codes or definitions match Y-9C.
- Preserve original YTD flows and calculate quarterly flows only where reporting frequency and adjacent filings permit. Do not difference equity or other stock balances. Beginning balances, ending balances and movements require distinct treatment.
- Reporting-threshold exclusions, discontinued fields and unavailable quarters remain missing with explanatory flags, never fabricated zeros.
- Retain source-specific loan definitions until harmonisation is verified.

Reference filing (not successfully retrieved in the earlier web check):
https://www.ffiec.gov/npw/FinancialReport/ReturnFinancialReportPDF?rpt=FRY9C&id=1039502&dt=20260630

Official June 2026 blank form inspected as fallback:
https://www.federalreserve.gov/apps/reportingforms/Download/DownloadAttachment?guid=649467b7-df0a-4b1a-8f75-9a75c70962b5

## Validation and delivery

Initial working benchmark: official source filings and internal accounting identities. No numerical tolerance or reviewer sign-off is invented. Record differences, reporting scope and missingness; retain REVIEW_REQUIRED until acceptance checks are agreed and satisfied.

Implementation order:
1. Verify identifier-source availability and build a versioned financial-field inventory.
2. Implement dated top-level ownership and clearly labelled bank-only aggregates, with overlap/cycle/ambiguous-parent checks.
3. Implement and reconcile the expanded measures for one quarter and its preceding quarter.
4. Integrate the snapshot downloader with the reviewed panel; retain a clear browser-import handoff.
5. Establish actual source endpoints/history and extend with period-specific mapping and validation.

## Implementation boundary today

Update: an integrated 2023–2025 build with highest-parent grouping and 106 mapped schedule fields is implemented. See [DATASET_RELEASE.md](DATASET_RELEASE.md) for actual results and release blockers. Detailed bank equivalents, full history, reporting eligibility, independent financial validation and complete ownership resolution remain unfinished. The paragraph below records the earlier boundary, not the current feature inventory.

The current code has selected core measures, same-quarter FDIC holder links, a dated NIC audit, a 2023–2025 draft and one-quarter source acquisition/import. It does not yet implement all top-level aggregation rules, bank-only groups, the expanded schedule inventory or the full requested history. This document changes the requirements, not financial outputs.
