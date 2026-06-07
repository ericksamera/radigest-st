from __future__ import annotations


import streamlit as st

from radigest_ui.binaries import BinaryNotFoundError, radigest_design_binary
from radigest_ui.config import EXAMPLES_DIR, ensure_work_dirs
from radigest_ui.hashing import normalize_enzymes
from radigest_ui.storage import (
    prepare_design_run,
    register_existing_fasta,
    save_uploaded_fasta,
)

ensure_work_dirs()

st.title("Design enzyme pairs")
st.write(
    "Enter the experimental design target. The app will run `radigest-design` and cache the output by manifest hash."
)

reference_options = ["Upload FASTA", "Use bundled toy FASTA"]
reference_default = st.session_state.get("reference_mode", "Upload FASTA")
reference_index = (
    reference_options.index(reference_default)
    if reference_default in reference_options
    else 0
)

with st.form("design_form"):
    st.markdown("### 1. Reference")
    reference_mode = st.radio(
        "Reference source",
        reference_options,
        index=reference_index,
        horizontal=True,
        key="reference_mode",
    )

    uploaded = None
    if reference_mode == "Upload FASTA":
        uploaded = st.file_uploader(
            "Reference FASTA", type=["fa", "fasta", "fna", "gz"], key="uploaded_fasta"
        )
    else:
        st.caption(f"Using `{EXAMPLES_DIR / 'toy.fa'}`")

    st.markdown("### 2. Candidate enzymes")
    enzyme_text = st.text_area(
        "Candidate enzymes",
        value=st.session_state.get("enzyme_text", "EcoRI,MseI,PstI,ApeKI,NlaIII,MspI"),
        help="Comma, space, or newline separated. Use `all` to ask radigest-design to screen all bundled enzymes.",
        key="enzyme_text",
    )

    normalized_enzymes = normalize_enzymes(enzyme_text)
    if normalized_enzymes == ["all"]:
        st.caption(
            "Special mode: `all` candidate enzymes will be passed directly to radigest-design."
        )
    else:
        st.caption(f"Parsed {len(normalized_enzymes)} unique candidate enzymes.")

    st.markdown("### 3. Design target")
    c1, c2, c3 = st.columns(3)
    with c1:
        target_genome_pct = st.number_input(
            "Target genome %",
            min_value=0.001,
            value=float(st.session_state.get("target_genome_pct", 2.5)),
            step=0.1,
            key="target_genome_pct",
        )
    with c2:
        desired_depth = st.number_input(
            "Desired mean locus depth",
            min_value=0.1,
            value=float(st.session_state.get("desired_depth", 10.0)),
            step=1.0,
            key="desired_depth",
        )
    with c3:
        samples = st.number_input(
            "Samples",
            min_value=1,
            value=int(st.session_state.get("samples", 96)),
            step=1,
            key="samples",
        )

    st.markdown("### 4. Sequencing budget")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        read_layout = st.selectbox(
            "Read layout",
            ["pe", "se"],
            index=0 if st.session_state.get("read_layout", "pe") == "pe" else 1,
            key="read_layout",
        )
    with c2:
        read_length = st.number_input(
            "Read length bp",
            min_value=1,
            value=int(st.session_state.get("read_length", 150)),
            step=1,
            key="read_length",
        )
    with c3:
        budget_options = ["Flowcell / run total", "Lane count"]
        budget_default = st.session_state.get("budget_mode", "Flowcell / run total")
        budget_mode_label = st.selectbox(
            "Budget mode",
            budget_options,
            index=(
                budget_options.index(budget_default)
                if budget_default in budget_options
                else 0
            ),
            key="budget_mode",
        )
    with c4:
        usable_read_fraction = st.number_input(
            "Usable read fraction",
            min_value=0.001,
            max_value=1.0,
            value=float(st.session_state.get("usable_read_fraction", 0.85)),
            step=0.05,
            key="usable_read_fraction",
        )

    if budget_mode_label == "Flowcell / run total":
        flowcell_read_pairs = st.text_input(
            "Total read pairs for run / flowcell",
            value=st.session_state.get("flowcell_read_pairs", "300M"),
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
                value=st.session_state.get("lane_read_pairs", "300M"),
                help="Examples: 50M, 300M, 1.2G, 1000000",
                key="lane_read_pairs",
            )
        with c2:
            lanes = st.number_input(
                "Lanes",
                min_value=1,
                value=int(st.session_state.get("lanes", 1)),
                step=1,
                key="lanes",
            )
        flowcell_read_pairs = st.session_state.get("flowcell_read_pairs", "300M")

    with st.expander("Advanced design, digest, and runtime settings", expanded=False):
        st.markdown("#### Coverage denominator")
        c1, c2 = st.columns(2)
        with c1:
            denominator = st.selectbox(
                "Denominator", ["non-n", "all"], index=0, key="denominator"
            )
        with c2:
            genome_bases = st.text_input(
                "Explicit genome bases",
                value=st.session_state.get("genome_bases", ""),
                help="Optional. Leave blank to let radigest-design count FASTA bases.",
                key="genome_bases",
            )

        st.markdown("#### Size selection")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            min_bp = st.number_input(
                "Hard min bp",
                min_value=0,
                value=int(st.session_state.get("min_bp", 300)),
                step=1,
                key="min_bp",
            )
        with c2:
            max_bp = st.number_input(
                "Hard max bp",
                min_value=1,
                value=int(st.session_state.get("max_bp", 600)),
                step=1,
                key="max_bp",
            )
        with c3:
            score_min_bp = st.number_input(
                "Score min bp",
                min_value=0,
                value=int(st.session_state.get("score_min_bp", 1)),
                step=1,
                key="score_min_bp",
            )
        with c4:
            score_max_bp = st.number_input(
                "Score max bp",
                min_value=1,
                value=int(st.session_state.get("score_max_bp", 2000)),
                step=1,
                key="score_max_bp",
            )

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            size_model_options = ["normal", "hard", "triangular", "soft-window"]
            default_size_model = st.session_state.get("size_model", "normal")
            size_model = st.selectbox(
                "Size model",
                size_model_options,
                index=(
                    size_model_options.index(default_size_model)
                    if default_size_model in size_model_options
                    else 0
                ),
                key="size_model",
            )
        with c2:
            size_mean_bp = st.number_input(
                "Size mean bp",
                value=float(st.session_state.get("size_mean_bp", 275.0)),
                step=1.0,
                key="size_mean_bp",
            )
        with c3:
            size_sd_bp = st.number_input(
                "Size SD bp",
                min_value=0.001,
                value=float(st.session_state.get("size_sd_bp", 85.0)),
                step=1.0,
                key="size_sd_bp",
            )
        with c4:
            size_edge_sd_bp = st.number_input(
                "Size edge SD bp",
                min_value=0.001,
                value=float(st.session_state.get("size_edge_sd_bp", 25.0)),
                step=1.0,
                key="size_edge_sd_bp",
            )

        st.markdown("#### Digest behavior")
        c1, c2, c3 = st.columns(3)
        with c1:
            allow_same = st.toggle(
                "Allow same-enzyme adjacencies",
                value=bool(st.session_state.get("allow_same", False)),
                key="allow_same",
            )
        with c2:
            include_ends = st.toggle(
                "Include terminal fragments",
                value=bool(st.session_state.get("include_ends", False)),
                key="include_ends",
            )
        with c3:
            strict_cuts = st.toggle(
                "Require explicit cut sites",
                value=bool(st.session_state.get("strict_cuts", False)),
                key="strict_cuts",
            )

        st.markdown("#### Objective and scoring weights")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            objective_options = [
                "balanced",
                "closest-coverage",
                "depth-first",
                "feasible-lowest-coverage",
                "max-depth",
            ]
            default_objective = st.session_state.get("objective", "balanced")
            objective = st.selectbox(
                "Objective",
                objective_options,
                index=(
                    objective_options.index(default_objective)
                    if default_objective in objective_options
                    else 0
                ),
                key="objective",
            )
        with c2:
            coverage_tolerance_pct = st.number_input(
                "Coverage tolerance pct-points",
                min_value=0.0,
                value=float(st.session_state.get("coverage_tolerance_pct", 0.25)),
                step=0.05,
                key="coverage_tolerance_pct",
            )
        with c3:
            weight_coverage = st.number_input(
                "Weight coverage",
                min_value=0.0,
                value=float(st.session_state.get("weight_coverage", 1.0)),
                step=0.1,
                key="weight_coverage",
            )
        with c4:
            weight_depth = st.number_input(
                "Weight depth",
                min_value=0.0,
                value=float(st.session_state.get("weight_depth", 2.0)),
                step=0.1,
                key="weight_depth",
            )
        with c5:
            weight_overcoverage = st.number_input(
                "Weight overcoverage",
                min_value=0.0,
                value=float(st.session_state.get("weight_overcoverage", 0.5)),
                step=0.1,
                key="weight_overcoverage",
            )
        weight_insert = st.number_input(
            "Weight insert",
            min_value=0.0,
            value=float(st.session_state.get("weight_insert", 0.25)),
            step=0.1,
            key="weight_insert",
        )

        st.markdown("#### Runtime")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            jobs = st.number_input(
                "Jobs",
                min_value=1,
                value=int(st.session_state.get("jobs", 2)),
                step=1,
                key="jobs",
            )
        with c2:
            build_workers = st.number_input(
                "Build workers",
                min_value=1,
                value=int(st.session_state.get("build_workers", 2)),
                step=1,
                key="build_workers",
            )
        with c3:
            threads = st.number_input(
                "Threads",
                min_value=1,
                value=int(st.session_state.get("threads", 2)),
                step=1,
                key="threads",
            )
        with c4:
            max_pairs = st.number_input(
                "Max pairs",
                min_value=0,
                value=int(st.session_state.get("max_pairs", 0)),
                step=1,
                key="max_pairs",
            )
        with c5:
            top = st.number_input(
                "Report top N",
                min_value=0,
                value=int(st.session_state.get("top", 0)),
                step=1,
                key="top",
            )

        use_mock_runner = st.toggle(
            "Use mock runner for UI testing",
            value=bool(st.session_state.get("use_mock_runner", False)),
            help="Writes mock design outputs without executing radigest-design. Do not use mock output scientifically.",
            key="use_mock_runner",
        )

    submitted = st.form_submit_button("Run design", type="primary")

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
            fasta_meta = register_existing_fasta(EXAMPLES_DIR / "toy.fa")

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
        st.switch_page("app_pages/processing.py", query_params={"run": run_key})
    except BinaryNotFoundError as exc:
        st.error(str(exc))
        st.info(
            "Enable mock runner to test the UI without a binary, or copy `radigest-design` into `bin/`."
        )
    except (
        Exception
    ) as exc:  # Streamlit-friendly guard for bad local files or parameters.
        st.error(f"Could not prepare run: {exc}")
