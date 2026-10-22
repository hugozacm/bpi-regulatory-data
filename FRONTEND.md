# Frontend — current public interface

The existing public [Site](https://bpi-regulatory-research-hugo.amusedvine18.chatgpt.site/) is the active interface. It has Workspace, Fed scenarios and Methodology views. Choose quarters, prepare a dataset, and download all 236 columns. There are no institution/basis/column filters.

The interface uses BPI's official website logo reference, observed purple/orange palette, Roboto body text and Barlow Semi Condensed headings. It is explicitly a classroom prototype, not an official BPI service or endorsement. Logo and fonts are external dependencies with font fallbacks.

## Source and publication

Public source: `frontend/executive.html`, `executive.js`, `recovery.js`, `executive.css`, `bpi-brand.css`, `processor-config.json`. Recovery refreshes health every 30 seconds and pauses status polling after bounded transient retries or an immediate permanent error. Partial outputs and missing periods are explicitly labelled; dictionary downloads explain all 236 columns.

`src/build_public_demo.py` generates `public_demo/dist/`. It retains the existing identity in `public_demo/.openai/hosting.json`. Use the Sites source helper to synchronise, package and publish that exact source state; do not create another Site.

Evidence defaults to the latest saved build carrying the cautious quality policy,
not a fixed workstation-specific run ID. Use `--evidence-report PATH` to select
another completed or explicitly partial build report. A frozen dataset is still
required for the published fallback; GitHub intentionally excludes those data.

```powershell
.\.venv\Scripts\python.exe src/build_public_demo.py
node --check frontend/executive.js
```

The published fallback is a frozen 14-quarter snapshot, partitioned into content-hashed quarter assets. New job results load through the restricted live API without republishing. Regenerating static assets alone does not update completed job data or the public Site.

## Processing and evidence

[CONNECTED_FRONTEND.md](CONNECTED_FRONTEND.md) defines the current controls, endpoint contract, free-local-runtime requirements and reconnect/download behaviour.

The result distinguishes input accounting failures, quarantined rows, uncertain quarterly values withheld, delivered-row failures and NOT_TESTABLE checks. Legacy jobs show a warning instead of claiming the revised cleaning policy. Supporting reports preserve exceptions. CSV exports contain all columns; the five-row preview shows only selected summary measures.

Official 2026 Fed macro charts are a separate context view, not a bank stress-loss model or forecast.

## Alternate interfaces

`frontend/index.html`, `app.js`, `style.css`, `backend.js`, `processor.js` and `fed.js` support earlier/local interfaces. They are not loaded by the public executive interface. `src/serve_frontend.py` serves the read-only localhost explorer on port 8765; do not expose it publicly.

The operator API on port 8767, Streamlit interface, Lovable experiment, Render notes and disabled-by-default GitHub Actions workflow are not the current public execution path. Their documents are historical/alternate guides, not the live feature inventory.

## Automatic connection discovery — 22 October 2026

The existing Site now has a small Worker with an R2 `BUCKET` binding. Public exported assets are served from its `assets/` prefix; one private-write connection record backs the non-cacheable `/processor-config.json`. No extra Site, paid hosting account or financial-data rebuild is required. The registered address is public, but updates require the owner launcher credential. See CONNECTED_FRONTEND.md.

Publication: open the existing Site source with the Sites helper, run `python src/build_public_demo.py`, then `python src/build_connection_site.py`, package/save/deploy that exact source, and run `python src/upload_site_assets.py` to upload the allowlisted public export. Run `Start BPI.cmd` to register a healthy processor. Preserve `.openai/hosting.json` identity and `r2: "BUCKET"`; do not restore `static` or overwrite the live registry with a generated config file. The export remains a staging directory, not a file server for the repository.
