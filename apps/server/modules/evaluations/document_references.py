"""Thin read-only interface from document lifecycle into evaluation jobs.

The documents syllabus service needs to know whether a
reference document is still referenced by evaluation job(s) before it can
be deleted. This module owns that query so the documents module never has
to reach into ``evaluations.models`` directly, keeping the module boundary
expressed as an explicit service interface.
"""

from __future__ import annotations

from typing import Any

from .models import EvaluationJob

__all__ = ["count_document_references"]


def count_document_references(document_id, db: Any | None = None) -> int:
    """Return how many evaluation jobs reference ``document_id``.

    A document is referenced when it is attached to a job as either the
    ``syllabus_id`` or the ``curriculum_id``. The caller uses this as the
    delete-lock gate: a non-zero result means the document must be kept.
    """
    if db is None:
        return 0
    return (
        db.query(EvaluationJob)
        .filter(
            (EvaluationJob.document_id == document_id)
            | (EvaluationJob.syllabus_id == document_id)
            | (EvaluationJob.curriculum_id == document_id)
        )
        .count()
    )
