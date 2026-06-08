from __future__ import annotations

import streamlit as st

from radigest_ui.cleanup import maybe_cleanup_old_work
from radigest_ui.config import ensure_work_dirs
from radigest_ui.ui_helpers import set_demo_defaults

ensure_work_dirs()
maybe_cleanup_old_work()

st.title("radigest")
st.subheader("Design restriction enzyme pairs without using the command line")

st.write(
    "Upload a reference FASTA or choose a catalog reference, select candidate enzymes, "
    "set sequencing assumptions, and download ranked enzyme-pair design tables."
)

with st.container(border=True):
    st.markdown("#### Start")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Upload my FASTA", type="primary", width="stretch"):
            st.session_state["reference_mode"] = "Upload FASTA"
            st.switch_page("app_pages/design.py")
    with c2:
        if st.button("Use catalog reference", width="stretch"):
            set_demo_defaults(mock=False)
            st.session_state["reference_mode"] = "Catalog reference"
            st.switch_page("app_pages/design.py")
    with c3:
        if st.button("Try UI mock demo", width="stretch"):
            set_demo_defaults(mock=True)
            st.switch_page("app_pages/design.py")

st.info(
    "Uploaded FASTA files are processed on the machine hosting this app. Do not upload "
    "sensitive or unpublished references to a public deployment unless that deployment is under your control."
)
