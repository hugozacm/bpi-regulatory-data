# Local Streamlit interface (MVP)

The UI is a thin wrapper around the existing integrated data builder and MVP packager. It does not modify financial calculations, claim BPI approval, or perform financial analysis.

## Windows setup

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

Open the localhost URL printed by Streamlit (usually http://localhost:8501).

## Workflow

1. In **Generate dataset**, choose the start and end quarter. For the agreed MVP v1, use **2023 Q1 to 2026 Q2**.
2. Optionally supply a directory containing official NIC ZIPs downloaded through a browser. The UI does not bypass source access controls.
3. Run the integrated builder. Inspect its release report. The builder may return exit code 2 for broader research blockers even when processing_status is COMPLETED.
4. Select a completed upstream build and package it using the existing release_mvp.py. **The scoped release packager requires the exact agreed 2023 Q1–2026 Q2 coverage**; a different period cannot be packaged with that script.
5. Read **Validation results**, then download the main dataset, dictionary, report and manifest under **Download results**.

Generated data and official source snapshots remain local and are excluded from GitHub. A clean clone will not contain a release until source files have been acquired and the pipeline has been run. Streamlit's download buttons load files into server memory, so large Parquet files may require substantial RAM.

## Limitations

This is an initial interface implementation, not yet independently executed or end-to-end tested. Financial outputs remain a **research draft**, not independently certified. The existing release process may quarantine records and withhold uncertain quarterly values; see MVP_V1.md. Do not interpret blank values as zero. Do not share the local Streamlit server publicly without authentication and security review.
