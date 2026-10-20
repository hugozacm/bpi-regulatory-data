# Stakeholder review — 21 October 2026

Purpose: agree the population, definitions and acceptance rules before extending or using the draft for research.

## Six decisions to ask for

1. **Which institutions belong in the dataset?** All US BHCs and savings holding companies, banks and savings institutions? Include foreign-owned groups, US intermediate holders or foreign branches? How should nested holders be handled?
2. **What do we do when a bank has a holder but no Y-9C observation?** Should we create a separately labelled bank-only group aggregate? The saved run has 40,430 such bank-quarter records outside the main table; bank aggregates are not equivalent to full consolidated holder accounts.
3. **Which exact financial and deposit definitions are required?** Loans before or after allowances? Which equity/income scope? Are domestic/foreign and interest/noninterest deposits enough, or are demand, savings, time and insured/uninsured splits required?
4. **How far back is useful, and how should breaks be treated?** Minimum start date? Prefer a longer series with documented definition/coverage breaks or a shorter comparable panel? Which amendment vintage should be retained?
5. **How should merger-adjusted history be constructed?** Confirm or change the provisional 31 December 2025 reference. Which predecessors belong to each surviving group? How should partial acquisitions, failures, multiple successors, intercompany balances and acquisition-quarter income be handled?
6. **What makes the dataset acceptable?** Which reference filings or existing dataset should we reconcile to? What tolerances and missingness are acceptable? Which ownership disagreements or other checks must block release, and who approves them?

## Technical work planned for 21 October

After the methodology discussion, start source-download automation:

- Provide one command to download missing official sources, process available quarters and produce a validation/review report.
- Keep the existing automated FDIC downloads; add NIC financial and structure downloads where the official endpoints permit them.
- If NIC requires a browser challenge, report the manual step clearly; do not bypass it or silently continue with missing sources.
- Preserve original source snapshots, record URLs, file hashes and actual retrieval times for new downloads, and avoid overwriting earlier snapshots.
- Check download completeness and expected formats; report failed downloads explicitly.
- Test with a small quarter first. Keep financial approval and merger-methodology decisions separate from successful automation.

This is planned work, not an implemented feature or a scheduled automatic run.

## Bring to the meeting

- [Current workflow PNG](review_images/workflow.png) and [illustrative output structure](review_images/output_tables_example.png).
- One actual holding-company example, one candidate standalone bank and one merger-event review example from local outputs.
- [Current results and limitations](PANEL_STATUS.md).

The image figures are illustrative. Actual local exports are not in GitHub. Do not present a merger-event example as an implemented merger-adjusted financial history.

## Current evidence to explain

- 12 quarters, 2023–2025; 13,662 organisation-quarter draft rows.
- 55,090 raw bank-quarter rows retained, including excluded coverage cases.
- 37 FDIC/NIC holder disagreements; 326 blank-holder candidates excluded after NIC review.
- 1,618 missing measures and 30 negative-stock flags in intermediate tables; negative equity is not automatically erroneous.
- No merger-adjusted history, no complete historical population claim and no publication approval.

Record each answer, owner and follow-up before changing the methodology.
