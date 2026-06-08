from __future__ import annotations

import streamlit as st

from radigest_ui.binaries import BinaryNotFoundError, radigest_design_binary
from radigest_ui.config import ensure_work_dirs
from radigest_ui.hashing import normalize_enzymes
from radigest_ui.reference_catalog import REFERENCE_CATALOG, catalog_labels
from radigest_ui.reference_sources import (
    reference_cache_path,
    resolve_catalog_reference,
)
from radigest_ui.runner import run_or_reuse
from radigest_ui.storage import prepare_design_run, save_uploaded_fasta
from radigest_ui.ui_helpers import log_tail

ensure_work_dirs()

PRIMARY_ENZYME_OPTIONS = [
    "EcoRI",
    "PstI",
    "ApeKI",
    "SbfI",
    "NsiI",
    "NlaIII",
    "HindIII",
]
SECONDARY_ENZYME_OPTIONS = [
    "MseI",
    "MspI",
    "NlaIII",
    "MluCI",
    "BfaI",
    "CviQI",
    "DpnII",
    "Sau3AI",
]
DEFAULT_PRIMARY_ENZYMES = ["EcoRI", "PstI", "ApeKI"]
DEFAULT_SECONDARY_ENZYMES = ["MseI", "MspI", "NlaIII"]

DEFAULT_WIDGET_STATE = {
    "reference_mode": "Catalog reference",
    "primary_enzymes": DEFAULT_PRIMARY_ENZYMES,
    "secondary_enzymes": DEFAULT_SECONDARY_ENZYMES,
    "use_all_enzymes": False,
    "target_genome_pct": 1.0,
    "coverage_tolerance_pct": 0.25,
    "desired_depth": 10.0,
    "samples": 37,
    "read_layout": "pe",
    "read_length": 300,
    "budget_mode": "Flowcell / run total",
    "flowcell_read_pairs": "50M",
    "lane_read_pairs": "300M",
    "lanes": 1,
    "usable_read_fraction": 0.85,
    "denominator": "non-n",
    "genome_bases": "",
    "min_bp": 200,
    "max_bp": 400,
    "score_min_bp": 1,
    "score_max_bp": 2000,
    "size_model": "soft-window",
    "size_mean_bp": 275.0,
    "size_sd_bp": 85.0,
    "size_edge_sd_bp": 50.0,
    "allow_same": False,
    "include_ends": False,
    "strict_cuts": False,
    "objective": "balanced",
    "weight_coverage": 1.0,
    "weight_depth": 2.0,
    "weight_overcoverage": 0.5,
    "weight_insert": 0.25,
    "jobs": 2,
    "build_workers": 2,
    "threads": 2,
    "max_pairs": 0,
    "top": 0,
    "use_mock_runner": False,
}


def _dedupe_enzymes(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        enzyme = value.strip()
        if not enzyme or enzyme in seen:
            continue
        seen.add(enzyme)
        out.append(enzyme)
    return out


@st.dialog("Running design", width="medium", dismissible=False)
def run_design_dialog(run_key: str) -> None:
    st.caption(f"Run key: `{run_key}`")
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
    stderr = log_tail(result.run_dir / "stderr.txt")
    stdout = log_tail(result.run_dir / "stdout.txt")
    if stderr:
        st.subheader("stderr tail")
        st.code(stderr, language="text")
    if stdout:
        with st.expander("stdout tail"):
            st.code(stdout, language="text")
    if st.button("Return to design", width="stretch"):
        st.rerun()


for key, default in DEFAULT_WIDGET_STATE.items():
    st.session_state.setdefault(key, default)

st.title("Design enzyme pairs")
st.write(
    "Enter the experimental design target. The app will run `radigest-design` and cache the output by manifest hash."
)

reference_options = ["Catalog reference", "Upload FASTA"]
reference_labels = catalog_labels()
reference_ids = list(reference_labels)
if not reference_ids:
    st.error("No catalog references are configured.")
    st.stop()

first_reference_label = reference_labels[reference_ids[0]]
if st.session_state.get("selected_reference_label") not in set(
    reference_labels.values()
):
    st.session_state["selected_reference_label"] = first_reference_label

st.markdown("### 1. Reference")
reference_mode = st.radio(
    "Reference source",
    reference_options,
    horizontal=True,
    key="reference_mode",
)

uploaded = None
selected_reference_id = reference_ids[0]
if reference_mode == "Catalog reference":
    selected_reference_label = st.selectbox(
        "Reference preset",
        [reference_labels[key] for key in reference_ids],
        key="selected_reference_label",
    )
    selected_reference_id = next(
        key
        for key, label in reference_labels.items()
        if label == selected_reference_label
    )
    entry = REFERENCE_CATALOG[selected_reference_id]
    if entry.get("description"):
        st.caption(entry["description"])
    if entry.get("local_path"):
        st.caption(f"Bundled reference: `{entry['local_path']}`")
    elif entry.get("url"):
        st.caption(
            f"Cached download target: `{reference_cache_path(selected_reference_id, entry)}`"
        )
else:
    uploaded = st.file_uploader(
        "Reference FASTA", type=["fa", "fasta", "fna", "gz"], key="uploaded_fasta"
    )

st.markdown("### 2. Candidate enzymes")
use_all_enzymes = st.toggle(
    "Screen all bundled enzymes",
    help="Passes `all` directly to radigest-design instead of a selected enzyme list.",
    key="use_all_enzymes",
)

enzyme_col1, enzyme_col2 = st.columns(2)
with enzyme_col1:
    primary_enzymes = st.multiselect(
        "Rare / anchoring enzymes",
        PRIMARY_ENZYME_OPTIONS,
        key="primary_enzymes",
        help="Select or type additional enzymes for the lower-cut-frequency side of the screen.",
        accept_new_options=True,
        placeholder="Choose or add enzymes",
        disabled=use_all_enzymes,
    )
with enzyme_col2:
    secondary_enzymes = st.multiselect(
        "Frequent / secondary enzymes",
        SECONDARY_ENZYME_OPTIONS,
        key="secondary_enzymes",
        help="Select or type additional enzymes for the higher-cut-frequency side of the screen.",
        accept_new_options=True,
        placeholder="Choose or add enzymes",
        disabled=use_all_enzymes,
    )

if use_all_enzymes:
    enzyme_text = "all"
    normalized_enzymes = ["all"]
    st.caption(
        "Special mode: `all` candidate enzymes will be passed directly to radigest-design."
    )
else:
    selected_enzymes = _dedupe_enzymes(primary_enzymes + secondary_enzymes)
    enzyme_text = "\n".join(selected_enzymes)
    normalized_enzymes = normalize_enzymes(enzyme_text)
    if normalized_enzymes:
        st.caption(
            f"Parsed {len(normalized_enzymes)} unique candidate enzymes: "
            + ", ".join(normalized_enzymes)
        )
    else:
        st.warning(
            "Select at least two candidate enzymes, or enable all bundled enzymes."
        )

st.markdown("### 3. Design target")
c1, c2, c3 = st.columns(3)
with c1:
    target_genome_pct = st.number_input(
        "Target genome %",
        min_value=0.001,
        step=0.1,
        key="target_genome_pct",
    )
with c2:
    desired_depth = st.number_input(
        "Desired mean locus depth",
        min_value=0.1,
        step=1.0,
        key="desired_depth",
    )
with c3:
    samples = st.number_input(
        "Samples",
        min_value=1,
        step=1,
        key="samples",
    )

st.markdown("### 4. Sequencing budget")
c1, c2, c3, c4 = st.columns(4)
with c1:
    read_layout = st.selectbox(
        "Read layout",
        ["pe", "se"],
        key="read_layout",
    )
with c2:
    read_length = st.number_input(
        "Read length bp",
        min_value=1,
        step=1,
        key="read_length",
    )
with c3:
    budget_mode_label = st.selectbox(
        "Budget mode",
        ["Flowcell / run total", "Lane count"],
        key="budget_mode",
    )
with c4:
    usable_read_fraction = st.number_input(
        "Usable read fraction",
        min_value=0.001,
        max_value=1.0,
        step=0.05,
        key="usable_read_fraction",
    )

if budget_mode_label == "Flowcell / run total":
    flowcell_read_pairs = st.text_input(
        "Total read pairs for run / flowcell",
        help="Examples: 50M, 300M, 1.2G, 1000000",
        key="flowcell_read_pairs",
    )
    lane_read_pairs = st.session_state.get("lane_read_pairs", "300M")
    lanes = int(st.session_state.get("lanes", 1))
else:
    c1, c2 = st.columns(2)
    with c1:
        lane_read_pairs = st.text_input(
            "Read pairs per lane",
            help="Examples: 50M, 300M, 1.2G, 1000000",
            key="lane_read_pairs",
        )
    with c2:
        lanes = st.number_input(
            "Lanes",
            min_value=1,
            step=1,
            key="lanes",
        )
    flowcell_read_pairs = st.session_state.get("flowcell_read_pairs", "50M")

with st.expander("Advanced design, digest, and runtime settings", expanded=False):
    st.markdown("#### Coverage denominator")
    c1, c2 = st.columns(2)
    with c1:
        denominator = st.selectbox("Denominator", ["non-n", "all"], key="denominator")
    with c2:
        genome_bases = st.text_input(
            "Explicit genome bases",
            help="Optional. Leave blank to let radigest-design count FASTA bases.",
            key="genome_bases",
        )

    st.markdown("#### Size selection")
    size_model = st.selectbox(
        "Size model",
        ["normal", "hard", "triangular", "soft-window"],
        key="size_model",
    )
    c1, c2 = st.columns(2)
    with c1:
        min_bp = st.number_input(
            "Hard min bp",
            min_value=0,
            step=1,
            key="min_bp",
        )
    with c2:
        max_bp = st.number_input(
            "Hard max bp",
            min_value=1,
            step=1,
            key="max_bp",
        )

    if size_model == "hard":
        score_min_bp = int(min_bp)
        score_max_bp = int(max_bp)
        size_mean_bp = float(st.session_state.get("size_mean_bp", 275.0))
        size_sd_bp = float(st.session_state.get("size_sd_bp", 85.0))
        size_edge_sd_bp = float(st.session_state.get("size_edge_sd_bp", 50.0))
        st.caption("Hard model uses only the hard insert-size window.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            score_min_bp = st.number_input(
                "Score min bp",
                min_value=0,
                step=1,
                key="score_min_bp",
            )
        with c2:
            score_max_bp = st.number_input(
                "Score max bp",
                min_value=1,
                step=1,
                key="score_max_bp",
            )

        if size_model == "normal":
            c1, c2 = st.columns(2)
            with c1:
                size_mean_bp = st.number_input(
                    "Size mean bp",
                    step=1.0,
                    key="size_mean_bp",
                )
            with c2:
                size_sd_bp = st.number_input(
                    "Size SD bp",
                    min_value=0.001,
                    step=1.0,
                    key="size_sd_bp",
                )
            size_edge_sd_bp = float(st.session_state.get("size_edge_sd_bp", 50.0))
        elif size_model == "triangular":
            size_mean_bp = st.number_input(
                "Size mean bp",
                step=1.0,
                key="size_mean_bp",
            )
            size_sd_bp = float(st.session_state.get("size_sd_bp", 85.0))
            size_edge_sd_bp = float(st.session_state.get("size_edge_sd_bp", 50.0))
        else:  # soft-window
            size_edge_sd_bp = st.number_input(
                "Size edge SD bp",
                min_value=0.001,
                step=1.0,
                key="size_edge_sd_bp",
            )
            size_mean_bp = float(st.session_state.get("size_mean_bp", 275.0))
            size_sd_bp = float(st.session_state.get("size_sd_bp", 85.0))

    st.markdown("#### Digest behavior")
    c1, c2, c3 = st.columns(3)
    with c1:
        allow_same = st.toggle("Allow same-enzyme adjacencies", key="allow_same")
    with c2:
        include_ends = st.toggle("Include terminal fragments", key="include_ends")
    with c3:
        strict_cuts = st.toggle("Require explicit cut sites", key="strict_cuts")

    st.markdown("#### Objective and scoring weights")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        objective = st.selectbox(
            "Objective",
            [
                "balanced",
                "closest-coverage",
                "depth-first",
                "feasible-lowest-coverage",
                "max-depth",
            ],
            key="objective",
        )
    with c2:
        coverage_tolerance_pct = st.number_input(
            "Coverage tolerance pct-points",
            min_value=0.0,
            step=0.05,
            key="coverage_tolerance_pct",
        )
    with c3:
        weight_coverage = st.number_input(
            "Weight coverage",
            min_value=0.0,
            step=0.1,
            key="weight_coverage",
        )
    with c4:
        weight_depth = st.number_input(
            "Weight depth",
            min_value=0.0,
            step=0.1,
            key="weight_depth",
        )
    with c5:
        weight_overcoverage = st.number_input(
            "Weight overcoverage",
            min_value=0.0,
            step=0.1,
            key="weight_overcoverage",
        )
    weight_insert = st.number_input(
        "Weight insert",
        min_value=0.0,
        step=0.1,
        key="weight_insert",
    )

    st.markdown("#### Runtime")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        jobs = st.number_input("Jobs", min_value=1, step=1, key="jobs")
    with c2:
        build_workers = st.number_input(
            "Build workers", min_value=1, step=1, key="build_workers"
        )
    with c3:
        threads = st.number_input("Threads", min_value=1, step=1, key="threads")
    with c4:
        max_pairs = st.number_input("Max pairs", min_value=0, step=1, key="max_pairs")
    with c5:
        top = st.number_input("Report top N", min_value=0, step=1, key="top")

    use_mock_runner = st.toggle(
        "Use mock runner for UI testing",
        help="Writes mock design outputs without executing radigest-design. Do not use mock output scientifically.",
        key="use_mock_runner",
    )

submitted = st.button("Run design", type="primary", width="stretch")

if submitted:
    try:
        if normalized_enzymes != ["all"] and len(normalized_enzymes) < 2:
            st.error("Provide at least two candidate enzymes, or use `all`.")
            st.stop()

        if reference_mode == "Upload FASTA":
            if uploaded is None:
                st.error("Upload a FASTA file first.")
                st.stop()
            fasta_meta = save_uploaded_fasta(uploaded)
        else:
            with st.spinner("Preparing cached reference"):
                fasta_meta = resolve_catalog_reference(selected_reference_id)

        params = {
            "target_genome_pct": float(target_genome_pct),
            "coverage_tolerance_pct": float(coverage_tolerance_pct),
            "desired_depth": float(desired_depth),
            "samples": int(samples),
            "read_layout": read_layout,
            "read_length": int(read_length),
            "budget_mode": (
                "flowcell" if budget_mode_label == "Flowcell / run total" else "lane"
            ),
            "flowcell_read_pairs": str(flowcell_read_pairs),
            "lane_read_pairs": str(lane_read_pairs),
            "lanes": int(lanes),
            "usable_read_fraction": float(usable_read_fraction),
            "denominator": denominator,
            "genome_bases": str(genome_bases).strip(),
            "min_bp": int(min_bp),
            "max_bp": int(max_bp),
            "score_min_bp": int(score_min_bp),
            "score_max_bp": int(score_max_bp),
            "size_model": size_model,
            "size_mean_bp": float(size_mean_bp),
            "size_sd_bp": float(size_sd_bp),
            "size_edge_sd_bp": float(size_edge_sd_bp),
            "allow_same": bool(allow_same),
            "include_ends": bool(include_ends),
            "strict_cuts": bool(strict_cuts),
            "objective": objective,
            "weight_coverage": float(weight_coverage),
            "weight_depth": float(weight_depth),
            "weight_overcoverage": float(weight_overcoverage),
            "weight_insert": float(weight_insert),
            "jobs": int(jobs),
            "build_workers": int(build_workers),
            "threads": int(threads),
            "max_pairs": int(max_pairs),
            "top": int(top),
        }

        if params["max_bp"] < params["min_bp"]:
            st.error("Hard max bp must be >= hard min bp.")
            st.stop()
        if params["score_max_bp"] < params["score_min_bp"]:
            st.error("Score max bp must be >= score min bp.")
            st.stop()

        if use_mock_runner:
            binary_version = "mock"
        else:
            binary_version = radigest_design_binary().version

        run_key = prepare_design_run(
            fasta=fasta_meta,
            enzyme_text=enzyme_text,
            params=params,
            binary_version=binary_version,
            mock_mode=bool(use_mock_runner),
        )
        st.session_state["current_run_key"] = run_key
        run_design_dialog(run_key)
    except BinaryNotFoundError as exc:
        st.error(str(exc))
        st.info(
            "Enable mock runner to test the UI without a binary, or copy `radigest-design` into `bin/`."
        )
    except (
        Exception
    ) as exc:  # Streamlit-friendly guard for bad local files or parameters.
        st.error(f"Could not prepare run: {exc}")
