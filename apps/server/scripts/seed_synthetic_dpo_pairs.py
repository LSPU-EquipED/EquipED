"""Synthetic DPO dataset generator for local development/testing only.

Creates fake evaluations, agent generations, and reviewer EDIT corrections
for the SME agent, entirely through the same real models and functions the
production evaluation pipeline uses (``resolve_or_reuse_evaluation_snapshots``
for a genuinely hash-signed snapshot, real ORM models for everything else),
so the resulting rows pass through ``export_dpo_package()`` unmodified and
land in ``pairs.jsonl`` in exactly the same shape a real reviewer correction
would.

This does NOT introduce a second DPO format, and it does NOT touch
``export_dpo_package()``, the projectors, or the capability registry --
it only inserts rows those already know how to read.

DEV/TEST ONLY. Every row this script creates is tagged so it can be found
and removed later:
  - Document.title is prefixed with SYNTHETIC_TITLE_PREFIX
  - PreferenceLog.notes is set to SYNTHETIC_NOTE

Run against whatever DATABASE_URL your environment points to -- per this
project's docs that is normally the shared Neon dev database, not a private
one. Clean up with --cleanup when you're done so you don't leave synthetic
evaluations sitting in a shared dev database.

Usage:
    cd apps
    uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs --count 25
    uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs --cleanup
"""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from server.core.config import get_settings
from server.core.database import get_session_factory
from server.db.metadata import import_model_modules
from server.modules.agents.sme.prompt import build_envelope_prompt_and_source
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    LlmRubricGuidanceConfig,
)
from server.modules.rubrics.repository import get_active_form_definition
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.modules.training_data.exporter import export_dpo_package

logger = logging.getLogger(__name__)

AGENT_ID = "sme"
SYNTHETIC_TITLE_PREFIX = "[SYNTHETIC-DPO-TEST] "
SYNTHETIC_NOTE = "synthetic-dpo-seed"
SYNTHETIC_USER_EMAIL = "synthetic-dpo-seed@local.test"
SYNTHETIC_MODEL_NAME = "synthetic-dpo-seed"

# (baseline_score, baseline_reasoning, corrected_score, corrected_reasoning)
# Deliberately different score/reasoning pairs so every generation produces a
# real, non-trivial DPO pair -- the projector skips generations where the
# correction doesn't actually change anything.
_VARIANTS: tuple[tuple[int, str, int, str], ...] = (
    (
        2,
        "Some activities are present but coverage is thin.",
        4,
        "Activities span the full range of stated objectives with clear "
        "alignment to each learning outcome.",
    ),
    (
        1,
        "No measurable content found for this criterion.",
        3,
        "On closer reading, three qualifying instances are present in the "
        "middle section that the original pass missed.",
    ),
    (
        3,
        "Adequate coverage across most of the material.",
        2,
        "Several claimed instances are duplicates of the same activity "
        "restated, so effective coverage is lower than scored.",
    ),
    (
        2,
        "Coverage is inconsistent across sections.",
        4,
        "Every section contains at least one qualifying, well-grounded "
        "instance; coverage is consistent throughout.",
    ),
    (
        4,
        "Excellent, thorough coverage throughout.",
        3,
        "Coverage is good but one late section has no qualifying instance, "
        "so this does not fully meet the top band.",
    ),
)

# A short but structurally realistic stand-in for a real SLM's body text --
# fed through the actual SME prompt builder below so the synthetic prompt
# has the same shape (preamble, criterion block, JSON schema example,
# downsampled source text) as a real evaluation's prompt, not a one-line
# placeholder a trained adapter would never see at real inference time.
_STUB_SLM_SOURCE_TEXT = """
Lesson 3: Cellular Respiration and Energy Transfer

Learning Objectives
By the end of this lesson, students will be able to: (1) describe the
three stages of cellular respiration, (2) explain how ATP is produced and
used as an energy currency, and (3) compare aerobic and anaerobic
respiration in terms of energy yield.

Content
Cellular respiration is the process by which cells break down glucose to
release usable energy. It occurs in three main stages: glycolysis, the
Krebs cycle, and the electron transport chain. Glycolysis takes place in
the cytoplasm and splits one glucose molecule into two pyruvate molecules,
producing a small net gain of ATP. The Krebs cycle, occurring in the
mitochondrial matrix, further breaks down pyruvate and releases carbon
dioxide while generating electron carriers. The electron transport chain,
located in the inner mitochondrial membrane, uses those carriers to
produce the majority of the cell's ATP through oxidative phosphorylation.

Activity 1: Diagram Labeling
Students label a diagram of the mitochondrion, identifying the outer
membrane, inner membrane, matrix, and cristae, and indicate where each
stage of respiration occurs.

Activity 2: Comparison Table
In pairs, students complete a table comparing aerobic respiration and
anaerobic fermentation across energy yield, byproducts, and the organisms
or conditions in which each occurs.

Performance Task(s)
Students design a short experiment measuring the rate of yeast
fermentation under different sugar concentrations, record their
observations, and write a two-paragraph conclusion relating their results
to the concepts covered in this lesson.
""".strip()


def _get_prompt_budget() -> int:
    settings = get_settings()
    return int(getattr(settings, "sme_total_prompt_budget_chars", 15000))


def _get_or_create_synthetic_user(session: Session) -> User:
    existing = session.query(User).filter_by(email=SYNTHETIC_USER_EMAIL).one_or_none()
    if existing is not None:
        return existing
    user = create_user(
        session,
        name="Synthetic DPO Seed",
        email=SYNTHETIC_USER_EMAIL,
        password=uuid.uuid4().hex,
        role=UserRole.FACULTY,
    )
    session.flush()
    return user


def _llm_rubric_guidance_criteria(session: Session) -> list[CriterionDefinition]:
    """Return every active SME llm_rubric_guidance CriterionDefinition, so
    synthetic prompts/responses target real, currently-active criteria
    instead of hardcoded codes that might not exist in this database."""
    form = get_active_form_definition(session, AGENT_ID)
    if form is None:
        raise RuntimeError(
            f"No active/published rubric found for agent '{AGENT_ID}' -- "
            "cannot generate synthetic corrections against it."
        )
    criteria: list[CriterionDefinition] = [
        criterion
        for domain in form.domains
        for criterion in domain.criteria
        if isinstance(criterion.strategy_config, LlmRubricGuidanceConfig)
    ]
    if not criteria:
        raise RuntimeError(
            f"Agent '{AGENT_ID}' has no active llm_rubric_guidance criteria -- "
            "cannot generate score-edit synthetic corrections."
        )
    return criteria


def generate(session: Session, count: int) -> list[uuid.UUID]:
    """Create `count` synthetic evaluations + SME generations + EDIT
    corrections. Returns the list of evaluation_ids created."""
    user = _get_or_create_synthetic_user(session)
    criteria = _llm_rubric_guidance_criteria(session)
    prompt_budget = _get_prompt_budget()

    evaluation_ids: list[uuid.UUID] = []

    for i in range(count):
        criterion = criteria[i % len(criteria)]
        criterion_code, criterion_title = criterion.criterion_code, criterion.title
        baseline_score, baseline_reasoning, corrected_score, corrected_reasoning = (
            _VARIANTS[i % len(_VARIANTS)]
        )

        # The real SME prompt builder -- same preamble/criterion-block/JSON
        # schema/downsampled-source shape a real evaluation's prompt has,
        # not a hand-written placeholder. canonical_source_text is a fake
        # SLM excerpt (_STUB_SLM_SOURCE_TEXT); everything around it is the
        # actual production prompt-construction code, unmodified.
        prompt, _source_packet = build_envelope_prompt_and_source(
            (criterion,),
            canonical_source_text=_STUB_SLM_SOURCE_TEXT,
            prompt_budget=prompt_budget,
        )
        prompt_text = prompt.render_flat()

        document_id = uuid.uuid4()
        document = Document(
            document_id=document_id,
            title=f"{SYNTHETIC_TITLE_PREFIX}SLM {i + 1}",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
        session.add(document)

        evaluation_id = uuid.uuid4()
        job = EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            submitted_by=user.user_id,
            status="COMPLETED",
            target_agent=AGENT_ID,
        )
        session.add(job)
        session.flush()

        # Genuine, hash-signed snapshot of whatever SME rubric is actually
        # active right now -- never hand-crafted, so the exporter's
        # integrity check (load_verified_agent_snapshot) passes honestly.
        resolve_or_reuse_evaluation_snapshots(session, evaluation_id, (AGENT_ID,))

        agent_result_id = uuid.uuid4()
        session.add(
            AgentResult(
                agent_result_id=agent_result_id,
                evaluation_id=evaluation_id,
                document_id=document_id,
                agent_name=AGENT_ID,
                model_name=SYNTHETIC_MODEL_NAME,
                success=True,
                envelope_status={"envelope_0": "ok"},
            )
        )
        session.flush()

        orig_response = {
            "summary": f"Synthetic SME evaluation {i + 1}.",
            "criterion_measurements": [
                {
                    "criterion_id": criterion_code,
                    "criterion_title": criterion_title,
                    "score": baseline_score,
                    "reasoning": baseline_reasoning,
                }
            ],
        }
        session.add(
            AgentGeneration(
                generation_id=uuid.uuid4(),
                agent_result_id=agent_result_id,
                evaluation_id=evaluation_id,
                document_id=document_id,
                agent_id=AGENT_ID,
                unit_key="envelope_0",
                criterion_ids=[criterion_code],
                prompt_text=prompt_text,
                response_text=json.dumps(orig_response, ensure_ascii=False),
                response_json=orig_response,
                response_contract_key="criterion_measurements.v1",
                response_contract_version=1,
                model_name=SYNTHETIC_MODEL_NAME,
                envelope_status="ok",
                prompt_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                response_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            )
        )

        session.add(
            PreferenceLog(
                evaluation_id=evaluation_id,
                user_id=user.user_id,
                agent_name=AGENT_ID,
                criterion_id=criterion_code,
                action="EDIT",
                edited_json={
                    "score": corrected_score,
                    "justification": corrected_reasoning,
                },
                notes=SYNTHETIC_NOTE,
            )
        )

        evaluation_ids.append(evaluation_id)

    session.commit()
    return evaluation_ids


def cleanup(session: Session) -> tuple[int, int]:
    """Delete the reachable part of every synthetic row this script created.

    ``evaluation_form_snapshots`` rows are permanently immutable at the DB
    level (``trg_evaluation_form_snapshots_immutable``, a BEFORE UPDATE OR
    DELETE trigger added in migration 20260829_0004 that unconditionally
    raises) -- this is a deliberate audit guarantee for every evaluation,
    real or synthetic, not something this script works around. Because
    ``EvaluationJob``/``Document`` are referenced by that immutable snapshot
    row's FK, they cannot be deleted either.

    What this DOES delete: ``PreferenceLog``, ``AgentGeneration``,
    ``AgentResult`` -- removing these means the synthetic evaluation can
    never again produce a DPO pair (no generation, no correction), so it is
    inert for every purpose this generator exists for.

    What it leaves behind: ``Document``/``EvaluationJob``/
    ``EvaluationFormSnapshot`` rows, still tagged with SYNTHETIC_TITLE_PREFIX
    for later identification, exactly like a real evaluation's snapshot
    would remain forever.

    Returns (documents_found, documents_left_in_place) -- both counts are
    the same number, since none can be removed; the tuple shape makes that
    explicit at the call site rather than implying a full deletion happened.
    """
    documents = (
        session.query(Document)
        .filter(Document.title.like(f"{SYNTHETIC_TITLE_PREFIX}%"))
        .all()
    )
    document_ids = [d.document_id for d in documents]
    if not document_ids:
        return (0, 0)

    jobs = (
        session.query(EvaluationJob)
        .filter(EvaluationJob.document_id.in_(document_ids))
        .all()
    )
    evaluation_ids = [j.evaluation_id for j in jobs]

    if evaluation_ids:
        session.query(PreferenceLog).filter(
            PreferenceLog.evaluation_id.in_(evaluation_ids)
        ).delete(synchronize_session=False)
        session.query(AgentGeneration).filter(
            AgentGeneration.evaluation_id.in_(evaluation_ids)
        ).delete(synchronize_session=False)
        session.query(AgentResult).filter(
            AgentResult.evaluation_id.in_(evaluation_ids)
        ).delete(synchronize_session=False)

    session.commit()
    return (len(document_ids), len(document_ids))


def main() -> None:
    # Must run before any session flush: registers every ORM model module
    # (e.g. admin.models' PromptVersion) so FK string references resolve.
    import_model_modules()

    parser = argparse.ArgumentParser(
        description=(
            "Generate (or clean up) synthetic SME DPO score-edit corrections "
            "for local pipeline testing. DEV/TEST ONLY."
        )
    )
    parser.add_argument(
        "--count",
        type=int,
        default=25,
        help="Number of synthetic corrections to generate (default: 25).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help=(
            "Delete all previously generated synthetic rows instead of "
            "creating new ones."
        ),
    )
    parser.add_argument(
        "--verify-export",
        action="store_true",
        help=(
            "After generating, run export_dpo_package() in dry-run mode and "
            "print the resulting pair count as a sanity check."
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    session = get_session_factory()()
    try:
        if args.cleanup:
            found, left_in_place = cleanup(session)
            if found == 0:
                logger.info("Nothing to clean up: no synthetic rows found.")
            else:
                logger.info(
                    "Cleanup complete: removed PreferenceLog/AgentGeneration/"
                    "AgentResult rows for %d synthetic evaluation(s) -- they "
                    "can no longer produce a DPO pair. %d Document/"
                    "EvaluationJob/EvaluationFormSnapshot row(s) remain "
                    "(the DB permanently forbids deleting evaluation form "
                    "snapshots, for any evaluation) but stay tagged with "
                    "'%s' and are otherwise inert.",
                    found,
                    left_in_place,
                    SYNTHETIC_TITLE_PREFIX.strip(),
                )
            return

        evaluation_ids = generate(session, args.count)
        logger.info(
            "Generated %d synthetic SME corrections tagged '%s' / notes='%s'.",
            len(evaluation_ids),
            SYNTHETIC_TITLE_PREFIX.strip(),
            SYNTHETIC_NOTE,
        )

        if args.verify_export:
            with tempfile.TemporaryDirectory() as tmp:
                manifest = export_dpo_package(
                    session=session,
                    agent_id=AGENT_ID,
                    output_dir=Path(tmp) / "package",
                    dry_run=True,
                )
            logger.info(
                "Verification export (dry-run): %d pair(s) exportable for agent '%s' "
                "(includes any pre-existing real pairs already in this database).",
                manifest.pair_count,
                AGENT_ID,
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
