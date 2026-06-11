from __future__ import annotations

from typing import Any

REFERENCE_CATALOG: dict[str, dict[str, Any]] = {
    "toy": {
        "label": "Toy demo reference",
        "description": "Small bundled FASTA for testing the Streamlit UI.",
        "local_path": "examples/toy.fa",
        "expected_sha256": None,
        "max_bytes": None,
    },
    # Add deployment-specific public references here, for example:
    # "arabidopsis_tair10": {
    #     "label": "Arabidopsis thaliana TAIR10",
    #     "description": "Curated public reference genome.",
    #     "url": "https://example.org/Arabidopsis_thaliana.TAIR10.dna.toplevel.fa.gz",
    #     "expected_sha256": "optional-known-sha256",
    #     "max_bytes": 2_000_000_000,
    # },
}


def catalog_labels() -> dict[str, str]:
    return {
        key: str(entry.get("label", key)) for key, entry in REFERENCE_CATALOG.items()
    }
