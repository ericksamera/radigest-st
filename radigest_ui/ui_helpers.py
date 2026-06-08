from __future__ import annotations

from pathlib import Path
import json

import streamlit as st


def active_run_key() -> str | None:
    run_key = st.query_params.get("run")
    if run_key:
        st.session_state["current_run_key"] = run_key
        return run_key
    return st.session_state.get("current_run_key")


def log_tail(path: Path, max_chars: int = 8000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def load_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def set_demo_defaults(mock: bool = False) -> None:
    st.session_state["reference_mode"] = "Catalog reference"
    st.session_state["primary_enzymes"] = ["EcoRI", "PstI", "ApeKI"]
    st.session_state["secondary_enzymes"] = ["MseI", "MspI", "NlaIII"]
    st.session_state["use_all_enzymes"] = False
    st.session_state["target_genome_pct"] = 1.0
    st.session_state["coverage_tolerance_pct"] = 0.25
    st.session_state["desired_depth"] = 10.0
    st.session_state["samples"] = 37
    st.session_state["read_layout"] = "pe"
    st.session_state["read_length"] = 300
    st.session_state["budget_mode"] = "Flowcell / run total"
    st.session_state["flowcell_read_pairs"] = "50M"
    st.session_state["lane_read_pairs"] = "300M"
    st.session_state["lanes"] = 1
    st.session_state["usable_read_fraction"] = 1.0
    st.session_state["min_bp"] = 200
    st.session_state["max_bp"] = 400
    st.session_state["score_min_bp"] = 1
    st.session_state["score_max_bp"] = 2000
    st.session_state["size_model"] = "soft-window"
    st.session_state["size_mean_bp"] = 275.0
    st.session_state["size_sd_bp"] = 85.0
    st.session_state["size_edge_sd_bp"] = 50.0
    st.session_state["jobs"] = 1
    st.session_state["build_workers"] = 2
    st.session_state["threads"] = 2
    st.session_state["use_mock_runner"] = mock
