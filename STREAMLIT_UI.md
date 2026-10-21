# Streamlit local pilot — 21 October 2026

> Historical or alternate implementation guide. For the active public pilot, controls, quality gate and current run commands, use [README.md](README.md), [CONNECTED_FRONTEND.md](CONNECTED_FRONTEND.md) and [CURRENT_WORKFLOW.md](CURRENT_WORKFLOW.md). Counts and disconnected-hosting statements below describe that earlier stage, not the live Site.

The interface from `feature/streamlit-mvp-ui` has been brought into the current local code without replacing newer historical acquisition, API or Actions modules. The remote branch has not been modified. Its older descriptions of 2023–2026 as the final agreed scope are superseded here: maximum reliable history remains required and unfinished.

## Start

From the project directory in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

Open http://127.0.0.1:8501. This is a local analyst app, not an authenticated public deployment. Do not expose it publicly. Source-folder paths refer to the server's filesystem, not a remote user's computer.

## Trial

Choose 2024 Q1 for both dates; select offline mode to use already saved official snapshots; click Build dataset. Inspect Processing status, source errors and validation. Download the selected-build CSV with its release report and validation/coverage tables. An upstream draft is not the quarantined frozen cohort. The separate interim packager is enabled only for the exact 2023 Q1–2026 Q2 build it supports; selected-quarter drafts do not require it.

The financial mapping bounds remain 2023 Q1–2026 Q2. This is not a completed historical MVP, and passing available checks is not financial certification. Missing cells are not zero. Merger/perimeter uncertainties and unresolved ownership still require review.

## Verified locally

Full local suite with the real-source UI trial enabled: **90 passed**. No cloud workflow was dispatched and no paid service was created.

Streamlit 1.66.0 AppTest exercised initial render, reversed-date rejection, and the actual Build button with real cached 2024 Q1 sources. The resulting build `outputs/dataset/20261021T143212Z-06f3654c` completed with 4,335 organisation-quarter rows, zero duplicate keys, zero failed accounting checks and 29 unresolved ownership records. The selected-build download control was present. These are simulated UI interaction tests, not a manual visual/browser assessment or proof of fresh cloud acquisition.

```powershell
$env:REGDATA_REAL_UI_TEST='1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_streamlit_ui.py --basetemp=test_temp_ui_trial
```

The opt-in real test writes a new build using local sources; ordinary tests skip it. For the full suite, use `tests` explicitly, as ignored output clones can contain duplicate test filenames. Use a fresh workspace-local `--basetemp` on restricted Windows environments.

## Still needed for online testing

Publish the reconciled code after GitHub write authentication is restored; decide the authenticated hosting/execution path; confirm no-spend controls before cloud jobs. Actions and this UI are not connected. The existing public demo remains a separate saved snapshot. Fresh source acquisition may still require browser assistance; this offline test does not resolve that constraint.
