from __future__ import annotations

import streamlit as st

from radigest_ui.binaries import BinaryNotFoundError, radigest_design_binary
from radigest_ui.config import WORK_DIR, ensure_work_dirs
from radigest_ui.ui_helpers import set_demo_defaults

ensure_work_dirs()

st.title("radigest")
st.subheader("Design restriction enzyme pairs without using the command line")

st.write(
    "This app wraps `radigest-design`: upload a reference FASTA, choose candidate enzymes "
    "and sequencing assumptions, then download the ranked enzyme-pair design tables."
)

with st.container(border=True):
    st.markdown("#### Binary status")
    try:
        info = radigest_design_binary()
        st.success(f"Found `radigest-design`: `{info.path}`")
        st.caption(f"Version response: `{info.version}`")
    except BinaryNotFoundError as exc:
        st.warning(str(exc))
        st.caption(
            "You can still test the UI by enabling mock mode on the Design page."
        )

with st.container(border=True):
    st.markdown("#### Start")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Upload my FASTA", type="primary", use_container_width=True):
            st.session_state["reference_mode"] = "Upload FASTA"
            st.switch_page("app_pages/design.py")
    with c2:
        if st.button("Use bundled toy FASTA", use_container_width=True):
            set_demo_defaults(mock=False)
            st.switch_page("app_pages/design.py")
    with c3:
        if st.button("Try UI mock demo", use_container_width=True):
            set_demo_defaults(mock=True)
            st.switch_page("app_pages/design.py")

st.markdown("#### What the app saves")
st.write(
    "Runs are cached under `.radigest_work/` by a manifest hash. If a user submits the same "
    "FASTA hash, enzyme list, and design parameters again, the Processing page reuses the "
    "existing outputs instead of re-running the binary."
)

st.code(str(WORK_DIR), language="text")

st.info(
    "Uploaded FASTA files are processed on the machine hosting this app. Do not upload "
    "sensitive or unpublished references to a public deployment unless that deployment is under your control."
)
