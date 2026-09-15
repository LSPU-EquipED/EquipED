"""One-off migration: convert Coordinator's 9 OP/A criteria from
count_band/ratio_band to llm_rubric_guidance, with qualitative (non-numeric)
score-level descriptors -- mirrors the SME conversion (see
convert_sme_to_llm_rubric_guidance.py) since Coordinator "judges each
criterion the same way the Subject Matter Expert does" for these 9
criteria (identical scoring rules in seed_rubrics.py).

A-05 is intentionally left untouched: it uses the unrelated
curriculum_alignment strategy (required by COORDINATOR_MANIFEST_V2),
not count_band/ratio_band, and is out of scope for this conversion.

Uses the existing rubric authoring workflow (draft -> edit -> publish ->
activate) rather than mutating the DB directly. See
_qualitative_rewrites.py for the shared rewrite table and migration
runner.

Usage (from repo root):

    uv run --project server python -m \
        server.scripts.convert_coordinator_to_llm_rubric_guidance
"""

from __future__ import annotations

import logging

from server.core.database import get_session_factory

from ._qualitative_rewrites import OP_A_QUALITATIVE_REWRITES, run_qualitative_conversion

logger = logging.getLogger(__name__)

AGENT_ID = "coordinator"

# Everything except A-05 (curriculum_alignment -- out of scope here).
_COORDINATOR_REWRITES = {
    code: rewrite
    for code, rewrite in OP_A_QUALITATIVE_REWRITES.items()
    if code != "A-05"
}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        run_qualitative_conversion(session, AGENT_ID, _COORDINATOR_REWRITES)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
