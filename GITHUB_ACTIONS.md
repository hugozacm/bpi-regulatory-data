# On-demand processing without an always-on server

> Historical or alternate implementation guide. For the active public pilot, controls, quality gate and current run commands, use [README.md](README.md), [CONNECTED_FRONTEND.md](CONNECTED_FRONTEND.md) and [CURRENT_WORKFLOW.md](CURRENT_WORKFLOW.md). Counts and disconnected-hosting statements below describe that earlier stage, not the live Site.

Status: workflow and bounded runner prepared locally; not yet published or cloud-tested.
This replaces neither historical harmonisation nor financial approval.

## Before enabling

1. Publish the current source, tests, config and `.github/workflows/regulatory-data.yml` to the repository's default branch. Git write authentication is required; the previous push was blocked.
2. Check GitHub Billing → Actions allowance and budgets. Use a zero-spend budget with **Stop usage when budget limit is reached** where available, or keep paid overage disabled. Do not assume timeout/retention makes execution free. Standard public-repository runners and private-repository allowances have different billing rules.
3. Only after confirming spending controls, set repository Actions variable `REGDATA_ACTIONS_ENABLED=true`. Until then the processing job is skipped.
4. Actions → Prepare regulatory research draft → Run workflow → choose From/To year and quarter. Download the run artifact within one day. No schedule or push trigger is installed.

## What runs

Validate inputs → download missing official sources → highest dated ownership grouping → stock/YTD-flow processing → validation → CSV/Parquet research draft plus coverage, ownership and validation tables, release report and output hashes.

Maximum four quarters, one active job, 20-minute processing timeout inside a 25-minute job. No source cache, paid runner, cloud database, repository write or automatic publication. Artifact data cap: 25 MiB plus small job metadata. The upstream draft can contain accounting failures and unresolved groups: inspect the validation and release report before use. Completion means **COMPLETED_REVIEW_REQUIRED**, never financial approval or historical MVP completion.

NIC/FFIEC blocking may prevent unattended acquisition. No CAPTCHA bypass is implemented; a failed source produces a failed job/report, not fabricated data. This initial cloud runner does not import browser-downloaded source files. Raw source archives are not uploaded and disappear with the runner; download receipts/hashes in the release report identify them but are not a substitute for retaining source bytes for exact reproduction.

The integrated financial mappings currently accept 2023 Q1–2026 Q2. Earlier requests fail explicitly. The required longer history remains unfinished; `history_sources.py` and `build_historical.py` remain separate local acquisition/staging tools, not harmonised historical output.

The public demo still shows its saved snapshot. It cannot anonymously trigger Actions and does not update itself from these artifacts. An authorised GitHub operator runs jobs; never put a GitHub token in frontend code. A reviewed-publication step is still needed.

## Local validation without downloads

PowerShell, from the project directory:

```powershell
$env:FROM_YEAR='2024'
$env:FROM_QUARTER='1'
$env:TO_YEAR='2024'
$env:TO_QUARTER='1'
.\.venv\Scripts\python.exe src/run_actions_job.py --validate-only
.\.venv\Scripts\python.exe -m pytest -q tests/test_actions_job.py
```

Omit `--validate-only` to attempt real acquisition and processing locally. Artifacts go to a unique `outputs/actions/<id>` directory.

Official references: [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [budgets](https://docs.github.com/en/billing/how-tos/set-up-budgets), [manual workflows](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow), [artifact retention](https://github.com/actions/upload-artifact).
