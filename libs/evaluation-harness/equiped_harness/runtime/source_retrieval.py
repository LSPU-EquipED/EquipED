"""Portable source identity shared by indexing and evidence validation."""

from __future__ import annotations

import hashlib

# Preserve the Coordinator's existing measurement units. Smaller embedding
# chunks point to these spans; changing an encoder must not change score units.
SLM_SOURCE_SPAN_CHARS = 4_000
SLM_RETRIEVAL_CONTRACT = "slm_retrieval.v1"


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
