# Provisional assumptions — confirm before research release

These are working choices, not stakeholder-approved methodology. See [REVIEW_QUESTIONS.md](REVIEW_QUESTIONS.md) for the meeting checklist.

| Topic | Current implementation / assumption | Decision still needed |
|---|---|---|
| Period | Draft covers 2023–2025, all 12 quarters | Minimum start date; acceptable historical breaks |
| Holding companies | Populated Y-9C assets identify observed filers; internal label consolidated_BHC | Verified BHC/SLHC/IHC and foreign-owned scope |
| Standalone banks | FDIC blank/zero/self holder, then no dated NIC control parent found | Independent institution-type and standalone verification |
| Holders without Y-9C | Banks retained in raw data, excluded from the main table | Whether/how to publish bank-only group aggregates |
| Core consolidation | Use consolidated Y-9C; do not add matched subsidiary core balances | Review remaining overlaps and out-of-scope entities |
| Deposits | Separate matched-bank sums: total/domestic/foreign/domestic interest and noninterest | Required additional categories and consolidation treatment |
| Loans | BHC net-unearned and bank net-allowance measures stay separate | Comparable definition or explicitly separate series |
| Stocks and flows | Quarter-end stocks; Q1 YTD, later quarters adjacent YTD differences | Restatements, reporting-perimeter changes and merger-quarter income |
| Missing values | Preserve nulls; never infer missing deposit detail as zero | Acceptance thresholds and remediation |
| Merger reference | Provisionally 31 December 2025 | Confirm reference population and full versus partial deal rules |
| Merger adjustment | Events and quarter flags only; no adjusted financial history | Verified lineage, economic dates, accounting and eliminations |
| Source vintage | Saved current publications with dated history, not vintage archives | Snapshot/amendment policy for reproducible research |
| Approval | Every output remains REVIEW_REQUIRED | Benchmark, tolerance, reviewer and release-blocking checks |

No absence of an ownership record proves independence. No transformation code alone proves a fully additive merger. No successful programme run or passing software test certifies the financial panel.
