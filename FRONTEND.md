# Frontend — current public interface

The existing public [Site](https://bpi-regulatory-research-hugo.amusedvine18.chatgpt.site/) is the active interface. It has Workspace, Fed scenarios and Methodology views. Choose quarters, prepare a dataset, and download all 236 columns. There are no institution/basis/column filters.

The data-journey card groups actual API stages into Official filings → Group institutions → Check the data → Download. It does not simulate percentages or elapsed-time savings. Completed results reveal the actual row count, column count and delivered-quarter count; unknown counts remain a dash, and partial results are labelled. A preparation disclosure describes the existing quality policy only for policy-marked results. Financial exceptions, untestable checks and legacy warnings remain visible. The subtle reveal/pulse animations respect reduced-motion preferences. This presentation adds no data sources, financial calculations or API jobs.

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

The existing Site has a small Worker with an R2 `BUCKET` binding. Public assets are checksum-addressed under `blobs/`; immutable manifests under `releases/` define complete versions. Every new saved Worker pins one sealed manifest, so rollback restores its assets as well as its code. The legacy `assets/` prefix is retained only for rollback to pre-migration versions and is no longer overwritten. One separate private-write connection record backs non-cacheable `/processor-config.json`. No extra Site, paid hosting account or financial-data rebuild is required. See CONNECTED_FRONTEND.md.

Publication: open the existing Site source with the Sites helper; run `python src/build_public_demo.py`, then `python src/upload_site_assets.py` to stage and seal a complete checksum-verified release. Failed uploads do not change live assets. Run `python src/build_connection_site.py --release RELEASE_SHA256` using its sealed receipt, then package/save/deploy that exact source with the Sites helper. Do not change the export while staging or packaging. HTML references and frontend JSON reads remain pinned to the same release, even across later deployments. `GET /_release.json` reports the active release. Deploy a previous saved pinned Worker version to roll back; no re-upload is needed. Keep old blobs/manifests for rollback. `--legacy-bridge` is only for the one-time migration (already completed), not normal publication. Preserve Site identity and `r2: "BUCKET"`. The export is not a file server for the repository.
