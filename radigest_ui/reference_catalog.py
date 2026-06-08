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
    "oncorhynchus_nerka_uvic2.0": {
        "label": "Oncorhynchus nerka (sockeye salmon) reference genome.",
        "description": "Curated public reference genome.",
        "url": "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/034/236/695/GCF_034236695.1_Oner_Uvic_2.0/GCF_034236695.1_Oner_Uvic_2.0_genomic.fna.gz",
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
