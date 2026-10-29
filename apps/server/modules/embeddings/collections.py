"""Collection names and source-to-collection routing for embeddings."""

from __future__ import annotations

import hashlib
from typing import Final

COL_REFERENCE_ALL: Final[str] = "col_reference_all"
COL_POLICY_ALL: Final[str] = "col_policy_all"
COL_RUBRIC_SME: Final[str] = "col_rubric_sme"
COL_RUBRIC_COORDINATOR: Final[str] = "col_rubric_coordinator"
COL_RUBRIC_GAD: Final[str] = "col_rubric_gad"
COL_RUBRIC_ITSO: Final[str] = "col_rubric_itso"
COL_SLM_ALL: Final[str] = "col_slm_all"
COL_SLM_PREFIX: Final[str] = "col_slm_all_"

SOURCE_TYPE_TO_COLLECTION: Final[dict[str, str]] = {
    "syllabus": COL_REFERENCE_ALL,
    "curriculum": COL_REFERENCE_ALL,
    "policy": COL_POLICY_ALL,
    "rubric_sme": COL_RUBRIC_SME,
    "rubric_coord": COL_RUBRIC_COORDINATOR,
    "rubric_gad": COL_RUBRIC_GAD,
    "rubric_itso": COL_RUBRIC_ITSO,
    "slm": COL_SLM_ALL,
}


def resolve_collection_name(source_type: str) -> str:
    """Resolve target Chroma collection from a document source type."""

    try:
        return SOURCE_TYPE_TO_COLLECTION[source_type]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported source_type for embeddings: {source_type}"
        ) from exc


def resolve_slm_collection_name(model_id: str, dimension: int) -> str:
    """Return a stable SLM collection name isolated by model and vector width."""
    if not model_id or dimension <= 0:
        raise ValueError("SLM model ID and positive embedding dimension are required")
    key = hashlib.sha256(f"{model_id}|{dimension}".encode()).hexdigest()[:16]
    return f"{COL_SLM_PREFIX}{key}"


__all__ = [
    "COL_REFERENCE_ALL",
    "COL_POLICY_ALL",
    "COL_RUBRIC_SME",
    "COL_RUBRIC_COORDINATOR",
    "COL_RUBRIC_GAD",
    "COL_RUBRIC_ITSO",
    "COL_SLM_ALL",
    "COL_SLM_PREFIX",
    "SOURCE_TYPE_TO_COLLECTION",
    "resolve_collection_name",
    "resolve_slm_collection_name",
]
