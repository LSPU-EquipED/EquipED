"""One-off migration: convert SME's 10 criteria from count_band/ratio_band to
llm_rubric_guidance, with qualitative (non-numeric) score-level descriptors.

Rationale: SME's calculator-based criteria never had the LLM output a score
directly, so a plain reviewer score correction had no field to attach to for
DPO purposes (see docs/superpowers/specs -- this reverts SME to the same
LLM-direct scoring shape ITSO already uses). Numeric percentage/count
thresholds are replaced with qualitative bands (e.g. "most" instead of
"80%") because several of these criteria measure an open-ended, self-defined
set (topics, tasks, sections) where the percentage was never a hard fact to
begin with -- see the design discussion for the full reasoning. A-02/A-03/
A-04 (closed, named category counts) are intentionally converted too, per
explicit decision, even though their original counts were genuinely
checkable facts.

Uses the existing rubric authoring workflow (draft -> edit -> publish ->
activate) rather than mutating the DB directly, so validation, versioning,
and the publish/activate invariants all still apply. See
_qualitative_rewrites.py for the shared rewrite table and migration runner
(SME's and Coordinator's OP/A criteria share identical scoring rules).

Usage (from repo root):

    uv run --project server python -m server.scripts.convert_sme_to_llm_rubric_guidance
"""

from __future__ import annotations

import logging

from server.core.database import get_session_factory

from ._qualitative_rewrites import OP_A_QUALITATIVE_REWRITES, run_qualitative_conversion

logger = logging.getLogger(__name__)

AGENT_ID = "sme"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        run_qualitative_conversion(session, AGENT_ID, OP_A_QUALITATIVE_REWRITES)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
