"""Collection names and source-to-collection routing for embeddings."""

from __future__ import annotations

from typing import Final

COL_REFERENCE_ALL: Final[str] = "col_reference_all"
COL_RUBRIC_SME: Final[str] = "col_rubric_sme"
COL_RUBRIC_COORDINATOR: Final[str] = "col_rubric_coordinator"
COL_RUBRIC_GAD: Final[str] = "col_rubric_gad"
COL_RUBRIC_ITSO: Final[str] = "col_rubric_itso"

SOURCE_TYPE_TO_COLLECTION: Final[dict[str, str]] = {
    "syllabus": COL_REFERENCE_ALL,
    "curriculum": COL_REFERENCE_ALL,
    "rubric_sme": COL_RUBRIC_SME,
    "rubric_coord": COL_RUBRIC_COORDINATOR,
    "rubric_gad": COL_RUBRIC_GAD,
    "rubric_itso": COL_RUBRIC_ITSO,
}


def resolve_collection_name(source_type: str) -> str:
    """Resolve target Chroma collection from a document source type."""

    if source_type == "slm":
        raise ValueError(f"Unsupported source_type for embeddings: {source_type}")

    try:
        return SOURCE_TYPE_TO_COLLECTION[source_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported source_type for embeddings: {source_type}") from exc


__all__ = [
    "COL_REFERENCE_ALL",
    "COL_RUBRIC_SME",
    "COL_RUBRIC_COORDINATOR",
    "COL_RUBRIC_GAD",
    "COL_RUBRIC_ITSO",
    "SOURCE_TYPE_TO_COLLECTION",
    "resolve_collection_name",
]
