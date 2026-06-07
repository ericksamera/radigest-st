from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import io
import itertools
import json
import os
from pathlib import Path
import subprocess
import zipfile

from filelock import FileLock

from radigest_ui.binaries import radigest_design_binary
from radigest_ui.config import APP_ROOT, RUNS_DIR, ensure_work_dirs


@dataclass(frozen=True)
class RunResult:
    run_key: str
    run_dir: Path
    state: str
    exit_code: int | None = None
    reused: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timeout_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def expected_outputs(run_dir: Path) -> dict[str, Path]:
    out = run_dir / "out"
    return {
        "summary_tsv": out / "design.summary.tsv",
        "tsv": out / "design.tsv",
        "json": out / "design.json",
    }


def write_status(run_dir: Path, payload: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    tmp = run_dir / "status.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(run_dir / "status.json")


def load_status_file(run_dir: Path) -> dict:
    status_path = run_dir / "status.json"
    if not status_path.exists():
        return {}
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def is_done(run_dir: Path) -> bool:
    status = load_status_file(run_dir)
    if status.get("state") != "DONE":
        return False
    return all(
        path.exists() and path.stat().st_size > 0
        for path in expected_outputs(run_dir).values()
    )


def _enzyme_arg(manifest: dict, run_dir: Path) -> str:
    enzymes = manifest.get("enzymes", [])
    if enzymes == ["all"]:
        return "all"
    return str(run_dir / "enzymes.txt")


def argv_from_manifest(manifest: dict, run_dir: Path) -> list[str]:
    params = manifest["parameters"]
    binary = radigest_design_binary().path
    out_dir = run_dir / "out"

    argv = [
        str(binary),
        "--fasta",
        manifest["fasta_path"],
        "--enzymes",
        _enzyme_arg(manifest, run_dir),
        "--target-genome-pct",
        str(params["target_genome_pct"]),
        "--coverage-tolerance-pct",
        str(params["coverage_tolerance_pct"]),
        "--desired-depth",
        str(params["desired_depth"]),
        "--samples",
        str(params["samples"]),
        "--read-layout",
        params["read_layout"],
        "--read-length",
        str(params["read_length"]),
        "--usable-read-fraction",
        str(params["usable_read_fraction"]),
        "--denominator",
        params["denominator"],
        "--min",
        str(params["min_bp"]),
        "--max",
        str(params["max_bp"]),
        "--score-min",
        str(params["score_min_bp"]),
        "--score-max",
        str(params["score_max_bp"]),
        "--size-model",
        params["size_model"],
        "--size-mean",
        str(params["size_mean_bp"]),
        "--size-sd",
        str(params["size_sd_bp"]),
        "--size-edge-sd",
        str(params["size_edge_sd_bp"]),
        "--objective",
        params["objective"],
        "--weight-coverage",
        str(params["weight_coverage"]),
        "--weight-depth",
        str(params["weight_depth"]),
        "--weight-overcoverage",
        str(params["weight_overcoverage"]),
        "--weight-insert",
        str(params["weight_insert"]),
        "--jobs",
        str(params["jobs"]),
        "--build-workers",
        str(params["build_workers"]),
        "--threads",
        str(params["threads"]),
        "--out-dir",
        str(out_dir),
        "--force",
    ]

    genome_bases = str(params.get("genome_bases", "")).strip()
    if genome_bases:
        argv += ["--genome-bases", genome_bases]

    if params["budget_mode"] == "flowcell":
        argv += ["--flowcell-read-pairs", str(params["flowcell_read_pairs"])]
    else:
        argv += [
            "--lane-read-pairs",
            str(params["lane_read_pairs"]),
            "--lanes",
            str(params["lanes"]),
        ]

    if params.get("allow_same"):
        argv.append("--allow-same")
    if params.get("include_ends"):
        argv.append("--include-ends")
    if params.get("strict_cuts"):
        argv.append("--strict-cuts")
    if int(params.get("max_pairs", 0)) > 0:
        argv += ["--max-pairs", str(params["max_pairs"])]
    if int(params.get("top", 0)) > 0:
        argv += ["--top", str(params["top"])]

    return argv


def run_or_reuse(run_key: str) -> RunResult:
    ensure_work_dirs()
    run_dir = (RUNS_DIR / run_key).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    if is_done(run_dir):
        return RunResult(
            run_key=run_key, run_dir=run_dir, state="DONE", exit_code=0, reused=True
        )

    lock_path = run_dir / "run.lock"
    with FileLock(str(lock_path)):
        if is_done(run_dir):
            return RunResult(
                run_key=run_key, run_dir=run_dir, state="DONE", exit_code=0, reused=True
            )

        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            write_status(
                run_dir,
                {
                    "state": "ERROR",
                    "error": "manifest.json missing",
                    "finished_at": utc_now(),
                },
            )
            return RunResult(
                run_key=run_key, run_dir=run_dir, state="ERROR", exit_code=None
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("runner") == "mock":
            return _run_mock(run_key, run_dir, manifest)

        return _run_radigest_design(run_key, run_dir, manifest)


def _run_radigest_design(run_key: str, run_dir: Path, manifest: dict) -> RunResult:
    argv = argv_from_manifest(manifest, run_dir)
    timeout_raw = os.getenv("RADIGEST_RUN_TIMEOUT_SECONDS", "0").strip()
    timeout = int(timeout_raw) if timeout_raw else 0

    write_status(
        run_dir,
        {
            "state": "RUNNING",
            "run_key": run_key,
            "started_at": utc_now(),
            "argv": argv,
        },
    )

    try:
        proc = subprocess.run(
            argv,
            cwd=str(APP_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout if timeout > 0 else None,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_text = _timeout_output_text(exc.stdout)
        stderr_text = _timeout_output_text(exc.stderr)
        (run_dir / "stdout.txt").write_text(stdout_text, encoding="utf-8")
        (run_dir / "stderr.txt").write_text(
            stderr_text + "\nRun timed out.\n", encoding="utf-8"
        )
        write_status(
            run_dir,
            {
                "state": "ERROR",
                "run_key": run_key,
                "finished_at": utc_now(),
                "exit_code": None,
                "error": f"radigest-design timed out after {timeout} seconds",
                "argv": argv,
            },
        )
        return RunResult(
            run_key=run_key, run_dir=run_dir, state="ERROR", exit_code=None
        )

    (run_dir / "stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")

    if proc.returncode != 0:
        write_status(
            run_dir,
            {
                "state": "ERROR",
                "run_key": run_key,
                "finished_at": utc_now(),
                "exit_code": proc.returncode,
                "stderr_tail": (proc.stderr or "")[-8000:],
                "argv": argv,
            },
        )
        return RunResult(
            run_key=run_key, run_dir=run_dir, state="ERROR", exit_code=proc.returncode
        )

    missing = [
        str(path) for path in expected_outputs(run_dir).values() if not path.exists()
    ]
    if missing:
        write_status(
            run_dir,
            {
                "state": "ERROR",
                "run_key": run_key,
                "finished_at": utc_now(),
                "exit_code": proc.returncode,
                "error": "radigest-design completed but expected outputs were missing",
                "missing_outputs": missing,
                "argv": argv,
            },
        )
        return RunResult(
            run_key=run_key, run_dir=run_dir, state="ERROR", exit_code=proc.returncode
        )

    write_status(
        run_dir,
        {
            "state": "DONE",
            "run_key": run_key,
            "finished_at": utc_now(),
            "exit_code": proc.returncode,
            "outputs": {
                name: str(path) for name, path in expected_outputs(run_dir).items()
            },
            "argv": argv,
        },
    )
    return RunResult(run_key=run_key, run_dir=run_dir, state="DONE", exit_code=0)


def _run_mock(run_key: str, run_dir: Path, manifest: dict) -> RunResult:
    params = manifest["parameters"]
    out_dir = run_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    enzymes = manifest.get("enzymes", [])
    if enzymes == ["all"]:
        enzymes = ["EcoRI", "MseI", "PstI", "MspI", "ApeKI", "NlaIII"]

    pairs = list(itertools.combinations(enzymes, 2)) or [("EcoRI", "MseI")]
    rows = []
    target_pct = float(params["target_genome_pct"])
    target_depth = float(params["desired_depth"])
    read_pairs_total = _mock_total_reads(params)
    samples = max(1, int(params["samples"]))
    read_pairs_per_sample = read_pairs_total / samples

    for i, (a, b) in enumerate(pairs, start=1):
        perturb = (i - 1) * 0.18
        predicted_pct = max(0.001, target_pct * (1 + ((-1) ** i) * 0.04 + perturb / 10))
        weighted_fragments = max(1.0, 1000.0 * predicted_pct + 75 * i)
        predicted_depth = read_pairs_per_sample / weighted_fragments
        pct_error = abs(predicted_pct - target_pct)
        feasible = (
            pct_error <= float(params["coverage_tolerance_pct"])
            and predicted_depth >= target_depth
        )
        loss = pct_error / max(target_pct, 1e-9) + max(
            0, target_depth - predicted_depth
        ) / max(target_depth, 1e-9)
        fit_score = 1 / (1 + loss)
        rows.append(
            {
                "rank": i,
                "enzyme_a": a,
                "enzyme_b": b,
                "enzyme_pair": f"{a},{b}",
                "feasible": str(feasible).lower(),
                "decision_reason": "mock result; replace with real radigest-design for analysis",
                "target_pct": target_pct,
                "predicted_pct": predicted_pct,
                "pct_error": pct_error,
                "target_depth": target_depth,
                "predicted_depth": predicted_depth,
                "read_pairs_per_sample": read_pairs_per_sample,
                "max_samples": max(
                    1, int(read_pairs_total / max(target_depth * weighted_fragments, 1))
                ),
                "weighted_fragments": weighted_fragments,
                "mean_insert_bp": float(params["size_mean_bp"]),
                "insert_status": "mock",
                "fit_score": fit_score,
                "fit_loss": loss,
                "weighted_bases": predicted_pct * 1_000_000,
                "raw_bases_in_window": int(predicted_pct * 900_000),
                "raw_fragments_in_window": int(weighted_fragments * 0.9),
                "records": 1,
                "cached_cut_sites": 42,
                "cache_memory_estimate_bytes": 336,
            }
        )

    rows.sort(key=lambda r: (r["feasible"] != "true", -r["fit_score"]))
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx

    _write_mock_summary_tsv(out_dir / "design.summary.tsv", rows)
    _write_mock_full_tsv(out_dir / "design.tsv", rows, params)

    best = rows[0] if rows else None
    report = {
        "schema_version": 1,
        "radigest_version": "mock",
        "command": ["mock-radigest-design"],
        "input": {
            "fasta": manifest["fasta_path"],
            "denominator": params["denominator"],
            "genome_bases": params.get("genome_bases") or None,
            "reference_bases": {"all_bases": None, "non_n_bases": None},
        },
        "digest_parameters": {
            "min_length": params["min_bp"],
            "max_length": params["max_bp"],
            "score_min": params["score_min_bp"],
            "score_max": params["score_max_bp"],
            "size_model": params["size_model"],
            "size_mean": params["size_mean_bp"],
            "size_sd": params["size_sd_bp"],
            "size_edge_sd": params["size_edge_sd_bp"],
            "allow_same": params["allow_same"],
            "include_ends": params["include_ends"],
            "strict_cuts": params["strict_cuts"],
        },
        "sequencing_budget": {
            "read_layout": params["read_layout"],
            "read_length": params["read_length"],
            "lane_read_pairs": params.get("lane_read_pairs"),
            "lanes": params.get("lanes"),
            "usable_read_fraction": params["usable_read_fraction"],
            "samples": params["samples"],
            "target_mean_locus_depth": params["desired_depth"],
        },
        "design_target": {
            "target_genome_pct": params["target_genome_pct"],
            "coverage_tolerance_pct": params["coverage_tolerance_pct"],
            "objective": params["objective"],
        },
        "outputs": {
            "summary_tsv": str(out_dir / "design.summary.tsv"),
            "tsv": str(out_dir / "design.tsv"),
            "json": str(out_dir / "design.json"),
        },
        "warnings": ["mock runner output; do not use for scientific interpretation"],
        "summary": {
            "candidate_enzymes": len(enzymes),
            "candidate_pairs": len(rows),
            "reported_pairs": len(rows),
            "feasible_pairs": sum(1 for r in rows if r["feasible"] == "true"),
            "best_pair": [best["enzyme_a"], best["enzyme_b"]] if best else [],
        },
        "results": rows,
    }
    (out_dir / "design.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (run_dir / "stdout.txt").write_text("mock runner completed\n", encoding="utf-8")
    (run_dir / "stderr.txt").write_text(
        "mock runner; no radigest-design binary executed\n", encoding="utf-8"
    )

    write_status(
        run_dir,
        {
            "state": "DONE",
            "run_key": run_key,
            "finished_at": utc_now(),
            "exit_code": 0,
            "mock": True,
            "outputs": {
                name: str(path) for name, path in expected_outputs(run_dir).items()
            },
        },
    )
    return RunResult(run_key=run_key, run_dir=run_dir, state="DONE", exit_code=0)


def _mock_total_reads(params: dict) -> float:
    usable = float(params["usable_read_fraction"])
    if params["budget_mode"] == "flowcell":
        return _parse_count(str(params["flowcell_read_pairs"])) * usable
    return _parse_count(str(params["lane_read_pairs"])) * int(params["lanes"]) * usable


def _parse_count(text: str) -> float:
    text = text.strip().replace("_", "")
    if not text:
        return 1.0
    suffix = text[-1].lower()
    mult = {"k": 1e3, "m": 1e6, "g": 1e9, "t": 1e12}.get(suffix, 1.0)
    if mult != 1.0:
        text = text[:-1]
    try:
        value = float(text) * mult
    except ValueError:
        value = 1.0
    return max(value, 1.0)


def _write_mock_summary_tsv(path: Path, rows: list[dict]) -> None:
    fields = [
        "rank",
        "enzyme_pair",
        "feasible",
        "decision_reason",
        "target_pct",
        "predicted_pct",
        "pct_error",
        "target_depth",
        "predicted_depth",
        "read_pairs_per_sample",
        "max_samples",
        "weighted_fragments",
        "mean_insert_bp",
        "insert_status",
        "fit_score",
    ]
    _write_tsv(path, fields, rows)


def _write_mock_full_tsv(path: Path, rows: list[dict], params: dict) -> None:
    fields = [
        "rank",
        "enzyme_a",
        "enzyme_b",
        "feasible",
        "decision_reason",
        "fit_score",
        "fit_loss",
        "target_genome_pct",
        "predicted_weighted_genome_pct",
        "coverage_error_pct_points",
        "coverage_error_rel",
        "overcoverage_rel",
        "undercoverage_rel",
        "target_mean_locus_depth",
        "predicted_mean_locus_depth",
        "depth_margin",
        "depth_shortfall_rel",
        "read_pairs_per_sample",
        "required_pairs_per_sample_full_target",
        "weighted_bases",
        "weighted_fragments",
        "mean_weighted_length",
        "raw_bases_in_window",
        "raw_fragments_in_window",
        "budget_supported_genome_pct",
        "budget_supported_weighted_bases",
        "max_samples_per_lane_full_target",
        "max_samples_total_full_target",
        "lanes_required_full_target",
        "adapter_threshold_bp",
        "overlap_threshold_bp",
        "mean_insert_category",
        "insert_penalty",
        "records",
        "cached_cut_sites",
        "cache_memory_estimate_bytes",
    ]
    converted = []
    for row in rows:
        converted.append(
            {
                **row,
                "target_genome_pct": row["target_pct"],
                "predicted_weighted_genome_pct": row["predicted_pct"],
                "coverage_error_pct_points": row["pct_error"],
                "coverage_error_rel": row["pct_error"] / max(row["target_pct"], 1e-9),
                "overcoverage_rel": max(0.0, row["predicted_pct"] - row["target_pct"])
                / max(row["target_pct"], 1e-9),
                "undercoverage_rel": max(0.0, row["target_pct"] - row["predicted_pct"])
                / max(row["target_pct"], 1e-9),
                "target_mean_locus_depth": row["target_depth"],
                "predicted_mean_locus_depth": row["predicted_depth"],
                "depth_margin": row["predicted_depth"] - row["target_depth"],
                "depth_shortfall_rel": max(
                    0.0, row["target_depth"] - row["predicted_depth"]
                )
                / max(row["target_depth"], 1e-9),
                "required_pairs_per_sample_full_target": row["target_depth"]
                * row["weighted_fragments"],
                "mean_weighted_length": row["mean_insert_bp"],
                "budget_supported_genome_pct": min(
                    row["predicted_pct"],
                    row["predicted_pct"]
                    * row["predicted_depth"]
                    / max(row["target_depth"], 1e-9),
                ),
                "budget_supported_weighted_bases": row["weighted_bases"],
                "max_samples_per_lane_full_target": row["max_samples"],
                "max_samples_total_full_target": row["max_samples"],
                "lanes_required_full_target": 1,
                "adapter_threshold_bp": int(params["read_length"]),
                "overlap_threshold_bp": (
                    int(params["read_length"]) * 2
                    if params["read_layout"] == "pe"
                    else ""
                ),
                "mean_insert_category": "mock",
                "insert_penalty": 0.0,
            }
        )
    _write_tsv(path, fields, converted)


def _write_tsv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def zip_outputs(run_dir: Path) -> bytes:
    outputs = expected_outputs(run_dir)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, path in {
            "manifest.json": run_dir / "manifest.json",
            "status.json": run_dir / "status.json",
            "stdout.txt": run_dir / "stdout.txt",
            "stderr.txt": run_dir / "stderr.txt",
            "design.summary.tsv": outputs["summary_tsv"],
            "design.tsv": outputs["tsv"],
            "design.json": outputs["json"],
        }.items():
            if path.exists():
                zf.write(path, arcname=arcname)
    return buffer.getvalue()
