# Current-quarter upgrade

The v2 output is a diagnostic research draft. See `outputs/20241231_v2/`.

Implemented:

- Validate calendar quarter ends and adjacent input periods before processing.
- Validate raw source dates, missing/duplicate identifiers and FDIC downloaded count against `meta.total` before joins.
- Preserve integral values without float precision loss; reject fractional input amounts/IDs.
- Require all BHC deposit components; missing components no longer become zero.
- Label banks with blank/self holders as `standalone_candidate_bank`, pending independent ownership evidence.
- Separate FDIC loans net of allowances (`loans_net_allowances`) from BHC `total_loans` net of unearned income. They are deliberately separate columns until a common definition is verified.
- Aggregate documented FDIC `DEPDOM`, `DEPFOR`, `DEPIDOM`, `DEPNIDOM` across same-quarter subsidiary banks. Preserve contributor counts and missing-field counts. These are stock measures in USD thousands.
- Keep subsidiary-bank deposit sums separate from consolidated Y-9C totals. Record their difference for investigation; do not force equality or invent consolidation eliminations.
- Reconcile domestic deposit components and require bank income cross-check coverage for every selected candidate.
- Export `financials_wide.csv` and Parquet, one row per entity-quarter, plus a separate deposit table and supporting evidence.
- Preserve full FDIC request parameters and file hashes; rename the timestamp to `processed_at_utc` because the original retrieval time is unknown.
- Return CLI exit code 2 for failed financial checks. All outputs carry a `REVIEW_REQUIRED` marker; successful mechanical checks do not authorise publication.
- `--all-bhcs` supports all observed Y-9C filers for this input quarter. This option is not a claim of complete bank/savings-institution population or historical coverage.

## Offline reproduction from the workspace root

```powershell
.\bpi_regulatory_mvp\.venv\Scripts\python.exe .\bpi_regulatory_mvp\src\bpi_pipeline.py --y9-current .\bpi_regulatory_mvp\research\BHCF20241231.ZIP --y9-prior .\bpi_regulatory_mvp\research\BHCF20240930.ZIP --fdic-current .\bpi_regulatory_mvp\research\fdic_extended_20241231.json --fdic-prior .\bpi_regulatory_mvp\research\fdic_20240930.json --output .\bpi_regulatory_mvp\outputs\20241231_v2
.\bpi_regulatory_mvp\.venv\Scripts\python.exe -m pytest -q .\bpi_regulatory_mvp\tests --basetemp .\bpi_regulatory_mvp\test_temp
```

## Remaining work

Independent standalone verification, loan/equity/income definition reconciliation, reference-filing reconciliation, approved deposit consolidation treatment, complete bank/savings coverage, 2023–2025 iteration and verified merger history remain outstanding. Deposit fields here use FDIC's official financials API; direct CDR schedule parsing is not yet implemented. Foreign deposits left blank by a domestic bank remain null, not fabricated zero.

The original README and architecture review describe the first prototype; this status note takes precedence for v2 behaviour.
