# Dated top-level grouping — first implementation

Implemented 21 October 2026. This is an isolated pilot, not a replacement for the existing panel or a claim that all new requirements are complete.

Run from the repository root with the existing source files:

```powershell
.\.venv\Scripts\python.exe src\top_level.py --period 20241231
```

Outputs go to a unique `outputs/top_level_pilot/<quarter>-<id>/` folder: one main organisation financial table, a supporting ownership ledger, CSV/Parquet/DuckDB, a source-hash summary and REVIEW_REQUIRED marker. Existing panel files are not overwritten.

## Implemented

- Follow dated direct NIC control relationships to the highest reachable root for each bank and Y-9C filer.
- Reject control cycles and multiple active parents rather than choosing a convenient root.
- Flag unresolved FDIC/NIC disagreement; do not call a bank independent when FDIC reports a holder but NIC provides no path.
- Use a Y-9C report only when it belongs to the top root. Never add its subsidiary core balances again.
- Otherwise produce explicitly labelled bank-only aggregates. Independent candidates also fall into this source-basis category; it does not assert a holding company exists.
- Preserve strict missingness and source-specific loan definitions. Detect nested reporting banks and suppress their aggregate stock/deposit sums rather than risk double counting.
- Retain reported Y-9C YTD and derived quarterly income. Bank-only group income is withheld pending membership and acquisition-quarter checks; current-member YTD is separately labelled evidence.
- No retroactive successor roll-up. Quarter-end control dates determine grouping.

## Saved Q4 2024 pilot

The first run produced 4,276 root-quarter rows: 349 top-root consolidated Y-9C reports and 3,927 bank-only/source-basis rows. It identified 17 groups with nested-bank overlap. These counts are provisional, not the approved population. Some roots are foreign or not financial holding companies, and some are holder-only roots with no eligible bank members; institution attributes and coverage still need verification.

The ownership ledger includes unresolved holder-only records as well as banks, so its status totals must not be described as bank counts. Excluded institutions remain in that ledger. Source snapshots may change results.

## Financial mapping work started

`config/schedule_inventory.json` records a small subset checked against the official June 2026 form. It is **not loaded by the financial pipeline** and is not a complete historical map. In particular HI-A item 15 is BHCT3210 on that form, which must not be confused with existing BHCK3210 reporting scope. Full HI, HI-A and HI-B coverage, Call Report equivalents and historical code validity remain outstanding.

Official FDIC documentation confirms bank financial downloads and institution API routes are available, including financial-report downloads back to 1992. This is not proof that every desired field or ownership crosswalk exists throughout that period:
https://www.fdic.gov/bank-data-guide/data-downloads

The existing FDIC financial response already supplies bank CERT/RSSDID and holder RSSDHCR. A separate historical identifier crosswalk has **not yet been verified**. Highest-root grouping here relies on the saved dated NIC graph, not an assumed crosswalk.

## Remaining work

Verify parent attributes and foreign-root scope; resolve multiple parents and effective-date boundary conventions; reconcile bank-only reporting perimeters and missing filers; approve acquisition-quarter flows; complete expanded mappings and official-filing comparisons; integrate snapshot selection and full-panel orchestration; establish actual first/latest source availability. No publication certification is claimed.
