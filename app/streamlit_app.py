"""Local analyst interface for the scoped BPI regulatory-data research MVP."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "outputs" / "dataset"
RELEASE_ROOT = ROOT / "outputs" / "mvp_v1"
QUARTERS = [f"{year}{month}"+day for year in range(2023, 2027)
            for month, day in (("03", "31"), ("06", "30"), ("09", "30"), ("12", "31"))
            if f"{year}{month}{day}" <= "20260630"]


def directories(base: Path, marker: str) -> list[Path]:
    if not base.is_dir():
        return []
    return sorted((p for p in base.iterdir() if p.is_dir() and (p / marker).is_file()),
                  key=lambda p: p.name, reverse=True)


def run_script(script: str, arguments: list[str]) -> tuple[int, str]:
    command = [sys.executable, str(ROOT / "src" / script), *arguments]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                timeout=60 * 60 * 2, check=False)
    except subprocess.TimeoutExpired:
        return 124, "The process exceeded the two-hour limit. Inspect the output directory."
    except OSError as exc:
        return 1, f"Unable to start process: {exc}"
    return result.returncode, (result.stdout + "\n" + result.stderr)[-20000:]


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        st.error(f"Cannot read {path.name}: {exc}")
        return {}


st.set_page_config(page_title="BPI Regulatory Data | Research MVP", page_icon="🏦", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1160px; padding-top: 2rem;}
div[data-testid="stMetric"] {background: #f5f7fa; border: 1px solid #e5e9ef;
  border-radius: 12px; padding: 14px 18px;}
.stButton > button[kind="primary"] {font-weight: 650;}
</style>""", unsafe_allow_html=True)
st.title("Regulatory Data · Research MVP")
st.caption("Independent research prototype · Not affiliated with or approved by BPI")
st.warning("Research draft only. Passing scoped checks does not certify financial completeness or accuracy.")
releases = directories(RELEASE_ROOT, "mvp_manifest.json")
builds = directories(DATASET_ROOT, "release_report.json")
overview_a, overview_b, overview_c = st.columns(3)
overview_a.metric("Available releases", len(releases))
overview_b.metric("Upstream builds", len(builds))
overview_c.metric("Delivery status", "Research draft" if releases else "Not generated")
st.caption("Workflow: Acquire sources → Build dataset → Validate → Deliver files")
generate, validate, deliver = st.tabs(["01 · Generate dataset", "02 · Validation results", "03 · Download results"])

with generate:
    st.subheader("Build the regulatory dataset")
    st.write("Official FDIC and NIC source snapshots are required. Some NIC ZIP files may need "
             "to be downloaded through a browser and placed in a local folder.")
    c1, c2 = st.columns(2)
    with c1:
        start = st.selectbox("Start quarter", QUARTERS, index=0,
                             format_func=lambda q: f"{q[:4]} Q{(int(q[4:6])-1)//3+1}")
    with c2:
        end = st.selectbox("End quarter", QUARTERS, index=len(QUARTERS)-1,
                           format_func=lambda q: f"{q[:4]} Q{(int(q[4:6])-1)//3+1}")
    source_folder = st.text_input("Optional folder containing browser-downloaded NIC ZIPs",
                                  placeholder=r"C:\Users\...\Downloads\NIC")
    offline = st.checkbox("Use existing cached sources only (offline)", value=False)
    if st.button("Build dataset", type="primary", disabled=start > end):
        args = ["--start", start, "--end", end]
        if offline:
            args.append("--offline")
        if source_folder.strip():
            source = Path(source_folder.strip()).expanduser()
            if not source.is_dir():
                st.error("The NIC source folder does not exist on this computer.")
                st.stop()
            args += ["--browser-source-dir", str(source)]
        with st.spinner("Running the regulatory data pipeline. This may take several minutes..."):
            status, output = run_script("build_dataset.py", args)
        st.code(output or "(No process output)", language="text")
        if status == 0:
            st.success("Builder finished. Review its release report before packaging.")
        else:
            st.warning(f"Builder returned exit code {status}. This may reflect broader-target "
                       "review blockers or missing inputs; inspect processing_status and source_errors.")
    builds = directories(DATASET_ROOT, "release_report.json")
    if builds:
        chosen = st.selectbox("Completed upstream build to package", builds,
                              format_func=lambda p: p.name)
        upstream = load_json(chosen / "release_report.json")
        st.write("Processing status:", upstream.get("processing_status", "Unknown"))
        if upstream.get("source_errors"):
            st.error("Source acquisition errors prevent packaging.")
            st.json(upstream["source_errors"])
        ready = upstream.get("processing_status") == "COMPLETED" and not upstream.get("source_errors")
        if st.button("Package scoped MVP research draft", disabled=not ready):
            with st.spinner("Checking source hashes, quarantining conflicts and packaging..."):
                status, output = run_script("release_mvp.py", ["--input", str(chosen)])
            st.code(output or "(No process output)", language="text")
            if status == 0:
                st.success("MVP packaging completed. Open Download results.")
            else:
                st.error(f"Packaging failed (exit {status}); do not deliver this release.")
    else:
        st.info("No upstream build found. Run the builder or copy an existing build to outputs/dataset.")

releases = directories(RELEASE_ROOT, "mvp_manifest.json")
with validate:
    st.subheader("Release validation")
    if not releases:
        st.info("No packaged MVP release is available on this computer.")
    else:
        selected = st.selectbox("Research draft release", releases, key="validation_release",
                                format_func=lambda p: p.name)
        manifest = load_json(selected / "mvp_manifest.json")
        st.caption("Release manifest · full audit details available below")
        with st.expander("View complete release manifest"):
            st.json(manifest)
        report = selected / "VALIDATION_REPORT.md"
        if report.is_file():
            st.markdown(report.read_text(encoding="utf-8"))
        else:
            st.warning("Validation report is missing.")
        exceptions = selected / "exceptions.csv"
        if exceptions.is_file():
            st.download_button("Download exceptions CSV", exceptions.read_bytes(),
                               file_name="exceptions.csv", mime="text/csv")

with deliver:
    st.subheader("Download the research dataset")
    if not releases:
        st.info("First generate and package a dataset.")
    else:
        selected = st.selectbox("Packaged release", releases, key="download_release",
                                format_func=lambda p: p.name)
        st.info("Financial figures are in USD thousands. Blank values must not be interpreted as zero.")
        st.markdown("**Deliverable package**")
        st.caption("Share the dictionary, validation report and exceptions alongside the dataset.")
        for filename, mime in (
            ("organisation_financials.csv", "text/csv"),
            ("organisation_financials.parquet", "application/octet-stream"),
            ("data_dictionary.csv", "text/csv"),
            ("VALIDATION_REPORT.md", "text/markdown"),
            ("mvp_manifest.json", "application/json"),
        ):
            path = selected / filename
            if path.is_file():
                st.download_button(f"Download {filename}", path.read_bytes(),
                                   file_name=filename, mime=mime, key=filename)
            else:
                st.warning(f"Missing expected deliverable: {filename}")
        st.caption("Keep the manifest, dictionary, validation report and exceptions alongside "
                   "the financial dataset when sharing it with analysts.")
