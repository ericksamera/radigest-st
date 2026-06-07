from __future__ import annotations

import json

import streamlit as st

from radigest_ui.runner import run_or_reuse
from radigest_ui.storage import run_dir_for_key
from radigest_ui.ui_helpers import active_run_key, log_tail

st.title("Processing")

run_key = active_run_key()
if not run_key:
    st.warning("No active run. Start from the Design page.")
    st.page_link("app_pages/design.py", label="Go to Design pairs")
    st.stop()

run_dir = run_dir_for_key(run_key)
manifest_path = run_dir / "manifest.json"
if not manifest_path.exists():
    st.error("Run manifest was not found.")
    st.page_link("app_pages/design.py", label="Start a new design")
    st.stop()

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
st.caption(f"Run key: `{run_key}`")
st.caption(f"Runner: `{manifest.get('runner', 'radigest-design')}`")

with st.status("Running or reusing cached result", expanded=True) as status:
    result = run_or_reuse(run_key)

    if result.state == "DONE":
        if result.reused:
            status.update(label="Cached result found", state="complete")
        else:
            status.update(label="Run complete", state="complete")
        st.session_state["current_run_key"] = run_key
        st.switch_page("app_pages/results.py", query_params={"run": run_key})

    status.update(label="Run failed", state="error")
    st.error("The design run did not complete.")

stderr = log_tail(run_dir / "stderr.txt")
stdout = log_tail(run_dir / "stdout.txt")

if stderr:
    st.subheader("stderr tail")
    st.code(stderr, language="text")
if stdout:
    with st.expander("stdout tail"):
        st.code(stdout, language="text")

st.page_link("app_pages/design.py", label="Return to Design pairs")
