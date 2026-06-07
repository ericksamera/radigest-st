from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from radigest_ui.runner import expected_outputs, zip_outputs
from radigest_ui.storage import delete_run, load_status, run_dir_for_key
from radigest_ui.tables import first_value, format_float, read_json, read_tsv, truthy_series
from radigest_ui.ui_helpers import active_run_key, log_tail

st.title("Design results")

run_key = active_run_key()
if not run_key:
    st.warning("No run selected.")
    st.page_link("app_pages/design.py", label="Start a design")
    st.stop()

run_dir = run_dir_for_key(run_key)
status_path = run_dir / "status.json"
manifest_path = run_dir / "manifest.json"

if not status_path.exists() or not manifest_path.exists():
    st.error("Run metadata was not found.")
    st.page_link("app_pages/design.py", label="Start a new design")
    st.stop()

status = load_status(run_key)
if status.get("state") != "DONE":
    st.warning(f"Run state is `{status.get('state', 'UNKNOWN')}`.")
    st.page_link("app_pages/processing.py", label="Go to Processing", query_params={"run": run_key})
    st.stop()

outputs = expected_outputs(run_dir)
missing = [name for name, path in outputs.items() if not path.exists()]
if missing:
    st.error(f"Expected outputs are missing: {', '.join(missing)}")
    st.stop()

summary_df = read_tsv(outputs["summary_tsv"])
full_df = read_tsv(outputs["tsv"])
report = read_json(outputs["json"])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

best_pair = ",".join(report.get("summary", {}).get("best_pair", [])) or str(first_value(summary_df, "enzyme_pair"))
feasible_pairs = report.get("summary", {}).get("feasible_pairs")
if feasible_pairs is None and "feasible" in summary_df.columns:
    feasible_pairs = int(truthy_series(summary_df["feasible"]).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Best pair", best_pair)
c2.metric("Feasible pairs", feasible_pairs if feasible_pairs is not None else "NA")
c3.metric("Predicted genome %", format_float(first_value(summary_df, "predicted_pct")))
c4.metric("Predicted depth", format_float(first_value(summary_df, "predicted_depth")))

st.caption(f"Run key: `{run_key}`")
if manifest.get("runner") == "mock":
    st.warning("This is mock output for UI testing. Do not use it for scientific interpretation.")

summary_tab, full_tab, plots_tab, provenance_tab, downloads_tab = st.tabs([
    "Summary table", "Full table", "Quick plots", "Provenance + logs", "Downloads"
])

with summary_tab:
    st.subheader("Compact ranked table")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

with full_tab:
    st.subheader("Full machine-readable table")
    st.dataframe(full_df, use_container_width=True, hide_index=True)

with plots_tab:
    st.subheader("Top-pair diagnostics")
    if not summary_df.empty:
        plot_df = summary_df.head(25).copy()
        if "enzyme_pair" in plot_df.columns:
            plot_df = plot_df.set_index("enzyme_pair")
        numeric_candidates = [c for c in ["predicted_pct", "predicted_depth", "fit_score", "weighted_fragments"] if c in plot_df.columns]
        if numeric_candidates:
            selected = st.selectbox("Metric", numeric_candidates, index=0)
            chart_df = pd.to_numeric(plot_df[selected], errors="coerce").dropna()
            st.bar_chart(chart_df)
        else:
            st.info("No recognized numeric summary columns were available for plotting.")
    else:
        st.info("The summary table is empty.")

with provenance_tab:
    st.subheader("Design report JSON")
    st.json(report, expanded=False)

    with st.expander("Manifest"):
        st.json(manifest, expanded=False)

    stderr = log_tail(run_dir / "stderr.txt")
    stdout = log_tail(run_dir / "stdout.txt")
    with st.expander("stderr log", expanded=bool(stderr)):
        st.code(stderr or "No stderr captured.", language="text")
    with st.expander("stdout log"):
        st.code(stdout or "No stdout captured.", language="text")

with downloads_tab:
    st.subheader("Download outputs")
    st.download_button(
        "Download compact summary TSV",
        data=outputs["summary_tsv"].read_bytes(),
        file_name="design.summary.tsv",
        mime="text/tab-separated-values",
        use_container_width=True,
    )
    st.download_button(
        "Download full TSV",
        data=outputs["tsv"].read_bytes(),
        file_name="design.tsv",
        mime="text/tab-separated-values",
        use_container_width=True,
    )
    st.download_button(
        "Download JSON report",
        data=outputs["json"].read_bytes(),
        file_name="design.json",
        mime="application/json",
        use_container_width=True,
    )
    st.download_button(
        "Download all outputs as ZIP",
        data=zip_outputs(run_dir),
        file_name=f"radigest_design_{run_key[:12]}.zip",
        mime="application/zip",
        use_container_width=True,
    )

st.divider()
left, right = st.columns([1, 1])
with left:
    st.page_link("app_pages/design.py", label="Start another design")
with right:
    if st.button("Clear this run from local cache", type="secondary"):
        delete_run(run_key)
        if st.session_state.get("current_run_key") == run_key:
            del st.session_state["current_run_key"]
        st.switch_page("app_pages/design.py")
