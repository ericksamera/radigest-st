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
    st.session_state["reference_mode"] = "Use bundled toy FASTA"
    st.session_state["enzyme_text"] = "EcoRI,MseI,PstI,ApeKI,NlaIII,MspI"
    st.session_state["target_genome_pct"] = 45.833333
    st.session_state["coverage_tolerance_pct"] = 1.0
    st.session_state["desired_depth"] = 10.0
    st.session_state["samples"] = 1
    st.session_state["read_layout"] = "pe"
    st.session_state["read_length"] = 150
    st.session_state["budget_mode"] = "Flowcell / run total"
    st.session_state["flowcell_read_pairs"] = "1000"
    st.session_state["lane_read_pairs"] = "300M"
    st.session_state["lanes"] = 1
    st.session_state["usable_read_fraction"] = 1.0
    st.session_state["min_bp"] = 1
    st.session_state["max_bp"] = 100
    st.session_state["score_min_bp"] = 1
    st.session_state["score_max_bp"] = 100
    st.session_state["size_model"] = "hard"
    st.session_state["size_mean_bp"] = 275.0
    st.session_state["size_sd_bp"] = 85.0
    st.session_state["size_edge_sd_bp"] = 25.0
    st.session_state["jobs"] = 1
    st.session_state["build_workers"] = 2
    st.session_state["threads"] = 2
    st.session_state["use_mock_runner"] = mock
