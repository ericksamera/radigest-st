# radigest Streamlit UI

A lightweight multipage Streamlit wrapper for `radigest-design`.

This repo is intentionally thin: Streamlit handles upload, parameter entry, run orchestration, manifest caching, and result display. The Go binary remains the source of truth for digest screening and design scoring.

## Repository layout

```text
streamlit_app.py          multipage router
app_pages/                Home, Design, Processing, Results pages
radigest_ui/              binary discovery, storage, runner, TSV/JSON readers
bin/                      copy radigest binaries here
examples/                 small toy FASTA and enzyme list
.radigest_work/           runtime uploads, manifests, logs, and outputs; gitignored
```

## Required binary

Copy `radigest-design` into `bin/`:

```bash
mkdir -p bin
cp /path/to/radigest-design bin/radigest-design
chmod +x bin/radigest-design
```

You can also point the app at a local binary without copying it:

```bash
RADIGEST_DESIGN_BIN=/absolute/path/to/radigest-design streamlit run streamlit_app.py
```

For Streamlit Community Cloud, `bin/radigest-design` must be a Linux executable. For local macOS testing, use either a macOS build in `bin/` locally or set `RADIGEST_DESIGN_BIN`.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open the app, go to **Design pairs**, select either a catalog reference or upload your own FASTA, and run the design.

## UI mock mode

The Design page includes **Use mock runner**. This writes fake-but-shaped result files so you can test navigation, caching, downloads, and result rendering without a real `radigest-design` binary. Turn it off for real runs.

## Reference catalog

Curated references live in `radigest_ui/reference_catalog.py`. The bundled toy reference is enabled by default. To expose deployment-specific public genomes, add entries with HTTPS URLs:

```python
REFERENCE_CATALOG = {
    "toy": {"label": "Toy demo reference", "local_path": "examples/toy.fa"},
    "my_reference": {
        "label": "My public reference",
        "description": "Short UI description.",
        "url": "https://example.org/reference.fa.gz",
        "expected_sha256": "optional-known-sha256",
        "max_bytes": 2_000_000_000,
    },
}
```

URL references are streamed to disk and cached under `.radigest_work/references/<reference_id>/`. The app passes the cached local FASTA path to `radigest-design`.

## Caching model

The expensive run is cached on disk, not only in Streamlit memory.

Each submitted design creates a stable manifest with:

- `radigest-design` version, or `mock` in mock mode
- FASTA SHA-256 and size
- normalized candidate enzyme list
- target genome percentage and depth
- sequencing budget
- size-selection model
- digest behavior
- performance settings

The app hashes that manifest into a `run_key` and writes:

```text
.radigest_work/
  references/<reference_id>/       shared curated reference downloads
  uploads/<fasta_sha256>/          user-uploaded FASTA copies
  runs/<run_key>/
    manifest.json
    status.json
    stdout.txt
    stderr.txt
    enzymes.txt
    out/
      design.summary.tsv
      design.tsv
      design.json
```

If a later submission produces the same `run_key` and the expected outputs exist, the Processing page skips the binary and sends the user directly to Results.

Streamlit's caches are used only for lightweight app-level work:

- `st.cache_resource`: binary discovery and version check
- `st.cache_data`: parsed TSV and JSON result files
- filesystem cache: actual radigest run outputs

## Useful environment variables

```bash
RADIGEST_DESIGN_BIN=/absolute/path/to/radigest-design
RADIGEST_WORK_DIR=/absolute/path/to/persistent/workdir
RADIGEST_RUN_TIMEOUT_SECONDS=0
RADIGEST_MAX_REFERENCE_DOWNLOAD_BYTES=2147483648
```

`RADIGEST_RUN_TIMEOUT_SECONDS=0` disables the timeout. Set a positive integer to cap single runs. `RADIGEST_MAX_REFERENCE_DOWNLOAD_BYTES` caps curated reference URL downloads unless an individual catalog entry provides `max_bytes`.

## Cleanup policy

The app opportunistically cleans stale local work at startup and on a small fraction of page loads:

- run directories older than 24 hours are deleted
- upload directories older than 24 hours are deleted
- temporary files older than 6 hours are deleted
- curated cached references are preserved

A manual **Clean stale local work now** button is available on the Home page.

## Streamlit Community Cloud notes

Commit the app files and the Linux `bin/radigest-design` binary, then deploy with:

```text
Main file path: streamlit_app.py
```

The public hosted version should be treated as a demo. Uploaded FASTA files are processed on the hosted app instance, are eligible for cleanup after 24 hours, and should not be considered private project storage. For larger genomes or unpublished references, self-host the same app with a persistent `RADIGEST_WORK_DIR` volume.
