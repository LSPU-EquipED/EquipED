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

DEV/TEST/LOCAL ONLY. Every row this script creates is tagged with a run-id
so it can be found and removed later:
  - Document.title includes SYNTHETIC_TITLE_PREFIX and the run-id
  - PreferenceLog.notes includes the run-id

Run against whatever DATABASE_URL your environment points to -- per this
project's docs that is normally the shared Neon dev database, not a private
one. Clean up with --cleanup when you're done so you don't leave synthetic
evaluations sitting in a shared dev database.

Usage:
    cd apps
    # Against local/test database:
    uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
        --count 25 --confirm SEED --confirm-target LOCAL
    uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
        --cleanup --run-id <UUID> --confirm CLEANUP --confirm-target LOCAL

    # Against allowlisted remote dev database (fingerprint):
    export SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS="<fingerprint>"
    uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
        --count 25 --confirm SEED --confirm-target "<fingerprint>"
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import logging
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, unquote_plus, urlparse

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

ALLOWED_ENVIRONMENTS: frozenset[str] = frozenset({"development", "test", "local"})
PRODUCTION_ENVIRONMENTS: frozenset[str] = frozenset({"production", "prod"})
CONFIRM_SEED_KEYWORD = "SEED"
CONFIRM_CLEANUP_KEYWORD = "CLEANUP"

AGENT_ID = "sme"
SYNTHETIC_TITLE_PREFIX = "[SYNTHETIC-DPO-TEST] "
SYNTHETIC_NOTE_PREFIX = "synthetic-dpo-seed"
SYNTHETIC_NOTE = SYNTHETIC_NOTE_PREFIX
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


def _format_note(run_id: uuid.UUID) -> str:
    return f"{SYNTHETIC_NOTE_PREFIX}:{run_id}"


def _format_title(run_id: uuid.UUID, index: int) -> str:
    return f"{SYNTHETIC_TITLE_PREFIX}[run:{run_id}] SLM {index + 1}"


# Query parameters that can change where libpq connects.  Query keys are
# decoded and case-folded before checking, so spelling/encoding tricks cannot
# turn a local-looking authority into a remote connection.
_ROUTING_QUERY_KEYS = frozenset(
    {
        "host",
        "hostaddr",
        "port",
        "dbname",
        "database",
        "service",
        "servicefile",
        # These can select among multiple hosts or otherwise alter routing.
        "target_session_attrs",
        "load_balance_hosts",
    }
)


def _has_routing_query_override(database_url: str) -> bool:
    """Return whether the URL contains a libpq connection-routing override."""
    parsed = urlparse(database_url)
    return any(
        unquote_plus(key).strip().casefold() in _ROUTING_QUERY_KEYS
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
    )


def compute_target_fingerprint(database_url: str) -> str:
    """Compute an unforgeable SHA256 fingerprint for a database target.

    Fingerprints the normalized host:port/path without embedding credentials or secrets.
    """
    parsed = urlparse(database_url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if not port and (
        scheme == "postgresql"
        or scheme.startswith("postgresql+")
        or scheme.startswith("postgres+")
    ):
        port = 5432
    path = parsed.path.rstrip("/")
    normalized = f"{host}:{port}{path}" if port else f"{host}{path}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_local_or_test_target(database_url: str) -> bool:
    """Check if database_url points to a known local/test database.

    Allows SQLite file/memory targets and loopback/local/test network hosts.
    Fails closed on any remote target.
    """
    parsed = urlparse(database_url)
    scheme = (parsed.scheme or "").lower()
    if _has_routing_query_override(database_url):
        return False
    if scheme == "sqlite":
        return True

    host = (parsed.hostname or "").lower().strip()
    if not host:
        return False
    if host in {"localhost", "testserver", "test", "local", "127.0.0.1", "::1"}:
        return True
    if host.endswith(".local") or host.endswith(".test"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback
    except ValueError:
        pass
    return False


def validate_database_target(
    database_url: str | None = None,
    allowed_fingerprints: frozenset[str] | set[str] | tuple[str, ...] | None = None,
) -> str:
    """Validate that configured DATABASE_URL is safe for synthetic seeder operations.

    Refuses targets based on actual configured DATABASE_URL, not APP_ENV alone.
    Fails closed:
      1. Refuses empty or unconfigured DATABASE_URL.
      2. Automatically permits local/test allowlisted targets (sqlite, localhost).
      3. For non-local targets (e.g. shared dev Neon), requires target's SHA256
         fingerprint to be explicitly in allowed_fingerprints or the env var
         SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS.

    Returns the computed target fingerprint.
    """
    if database_url is None:
        settings = get_settings()
        database_url = getattr(settings, "database_url", None)

    if not database_url or not database_url.strip():
        raise PermissionError(
            "Synthetic seeder refused: DATABASE_URL is empty or not configured."
        )

    url_str = database_url.strip()
    if _has_routing_query_override(url_str):
        raise PermissionError(
            "Synthetic seeder refused: DATABASE_URL contains a connection-routing "
            "query override; use the URL authority and remove host/hostaddr/port/"
            "database/service overrides."
        )
    fingerprint = compute_target_fingerprint(url_str)

    if is_local_or_test_target(url_str):
        return fingerprint

    if allowed_fingerprints is None:
        env_fps = os.getenv("SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS", "")
        allowed_fps_set = {
            part.strip().lower() for part in env_fps.split(",") if part.strip()
        }
    else:
        allowed_fps_set = {
            fp.strip().lower() for fp in allowed_fingerprints if fp.strip()
        }

    if fingerprint.lower() in allowed_fps_set:
        return fingerprint

    parsed = urlparse(url_str)
    target_port = parsed.port or "default"
    masked = f"{parsed.scheme}://{parsed.hostname}:{target_port}{parsed.path}"
    raise PermissionError(
        f"Synthetic seeder refused unsafe database target '{masked}'. "
        f"Target host is not on the local/test allowlist, and target fingerprint "
        f"'{fingerprint}' is not in SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS. "
        "To allow this specific dev database, configure its fingerprint in "
        "SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS without embedding credentials."
    )


def validate_environment(env: str | None = None) -> str:
    """Validate that the script is running in an allowed environment.

    Always rejects production environments and any environment not explicitly
    in {'development', 'test', 'local'}.
    """
    if env is None:
        settings = get_settings()
        env = getattr(settings, "environment", "")

    normalized = (env or "").strip().lower()

    if (
        not normalized
        or normalized in PRODUCTION_ENVIRONMENTS
        or normalized not in ALLOWED_ENVIRONMENTS
    ):
        allowed_list = sorted(ALLOWED_ENVIRONMENTS)
        raise PermissionError(
            f"Synthetic seeder is strictly restricted to {allowed_list} environments. "
            f"Execution refused in environment '{env}'."
        )
    return normalized


def generate(
    session: Session, count: int, *, run_id: uuid.UUID | None = None
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Create `count` synthetic evaluations + SME generations + EDIT
    corrections tagged with `run_id`.

    Returns (run_id, list_of_evaluation_ids).
    """
    if count <= 0:
        raise ValueError(f"Count must be a positive integer, got {count}.")

    if run_id is None:
        run_id = uuid.uuid4()

    user = _get_or_create_synthetic_user(session)
    criteria = _llm_rubric_guidance_criteria(session)
    prompt_budget = _get_prompt_budget()

    note_tag = _format_note(run_id)
    evaluation_ids: list[uuid.UUID] = []

    try:
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
                title=_format_title(run_id, i),
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
            resp_text = json.dumps(orig_response, ensure_ascii=False)
            prompt_sha = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
            resp_sha = hashlib.sha256(resp_text.encode("utf-8")).hexdigest()

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
                    response_text=resp_text,
                    response_json=orig_response,
                    response_contract_key="criterion_measurements.v1",
                    response_contract_version=1,
                    model_name=SYNTHETIC_MODEL_NAME,
                    envelope_status="ok",
                    prompt_sha256=prompt_sha,
                    response_sha256=resp_sha,
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
                    notes=note_tag,
                )
            )

            evaluation_ids.append(evaluation_id)

        session.commit()
        return run_id, evaluation_ids
    except Exception:
        session.rollback()
        raise


def cleanup(session: Session, *, run_id: uuid.UUID | str) -> tuple[int, int]:
    """Delete the reachable part of synthetic rows for an exact run_id.

    Requires strict conjunction across:
      - Exact run_id matching in Document.title and PreferenceLog.notes
      - Dedicated synthetic user ownership (User.email == SYNTHETIC_USER_EMAIL)
      - Agent SME ownership (target_agent == AGENT_ID, agent_name/agent_id == AGENT_ID)
      - Synthetic model name (SYNTHETIC_MODEL_NAME)
      - Title prefix (SYNTHETIC_TITLE_PREFIX) and Note prefix (SYNTHETIC_NOTE_PREFIX)

    Fails closed and rolls back on any ambiguity or inconsistency across linked
    entities.

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
    and run-id for audit trail and later identification.

    Returns (documents_found, documents_left_in_place).
    """
    if isinstance(run_id, str):
        try:
            parsed_run_id = uuid.UUID(run_id)
        except ValueError as err:
            raise ValueError(f"Invalid UUID run_id format: '{run_id}'") from err
    elif isinstance(run_id, uuid.UUID):
        parsed_run_id = run_id
    else:
        raise ValueError(
            f"run_id must be a UUID or valid UUID string, got {type(run_id)}"
        )

    run_id_str = str(parsed_run_id)
    expected_note = _format_note(parsed_run_id)
    title_pattern = f"{SYNTHETIC_TITLE_PREFIX}[run:{run_id_str}]%"

    user = session.query(User).filter_by(email=SYNTHETIC_USER_EMAIL).one_or_none()
    if user is None:
        # If synthetic user is missing, no valid synthetic run for that user exists
        return (0, 0)

    try:
        # 1. Candidate Documents: must match title prefix, run-id in title, and user
        candidate_docs = (
            session.query(Document)
            .filter(
                Document.title.like(title_pattern),
                Document.uploaded_by == user.user_id,
            )
            .all()
        )
        if not candidate_docs:
            return (0, 0)

        doc_ids = [d.document_id for d in candidate_docs]

        # 2. EvaluationJobs: every job for a candidate document must satisfy the
        # ownership conjunction; do not hide a foreign job by filtering it out.
        all_jobs = (
            session.query(EvaluationJob)
            .filter(EvaluationJob.document_id.in_(doc_ids))
            .all()
        )
        if len(all_jobs) != len(candidate_docs) or any(
            job.submitted_by != user.user_id or job.target_agent != AGENT_ID
            for job in all_jobs
        ):
            raise RuntimeError(
                f"Ambiguity detected: found {len(candidate_docs)} document(s) matching "
                f"run_id {run_id_str} but {len(all_jobs)} strictly owned evaluation "
                "job(s). Cleanup aborted and rolled back."
            )
        job_eval_ids = {j.evaluation_id for j in all_jobs}

        # 3. Verify AgentResults conjunction:
        # Belongs to job_eval_ids, document in doc_ids, SME agent, synthetic model
        agent_results = (
            session.query(AgentResult)
            .filter(AgentResult.evaluation_id.in_(job_eval_ids))
            .all()
        )
        if len(agent_results) != len(job_eval_ids):
            raise RuntimeError(
                "Ambiguity detected in AgentResult: each owned evaluation must have "
                "exactly one result. Cleanup aborted and rolled back."
            )
        for ar in agent_results:
            if (
                ar.document_id not in set(doc_ids)
                or ar.agent_name != AGENT_ID
                or ar.model_name != SYNTHETIC_MODEL_NAME
            ):
                raise RuntimeError(
                    f"Ambiguity detected in AgentResult {ar.agent_result_id}: "
                    "entity attributes do not strictly match synthetic conjunction "
                    f"requirements (document={ar.document_id}, agent={ar.agent_name}, "
                    f"model={ar.model_name}). Cleanup aborted and rolled back."
                )

        # 4. Verify AgentGenerations conjunction:
        # Belongs to job_eval_ids, document in doc_ids, SME agent, synthetic model
        agent_generations = (
            session.query(AgentGeneration)
            .filter(AgentGeneration.evaluation_id.in_(job_eval_ids))
            .all()
        )
        if len(agent_generations) != len(job_eval_ids):
            raise RuntimeError(
                "Ambiguity detected in AgentGeneration: each owned evaluation must "
                "have exactly one generation. Cleanup aborted and rolled back."
            )
        for ag in agent_generations:
            if (
                ag.document_id not in set(doc_ids)
                or ag.agent_id != AGENT_ID
                or ag.model_name != SYNTHETIC_MODEL_NAME
            ):
                raise RuntimeError(
                    f"Ambiguity detected in AgentGeneration {ag.generation_id}: "
                    "entity attributes do not strictly match synthetic conjunction "
                    f"requirements (document={ag.document_id}, agent={ag.agent_id}, "
                    f"model={ag.model_name}). Cleanup aborted and rolled back."
                )

        # 5. Verify PreferenceLogs conjunction:
        # Belongs to job_eval_ids, synthetic user, SME agent, exact expected note
        pref_logs = (
            session.query(PreferenceLog)
            .filter(PreferenceLog.evaluation_id.in_(job_eval_ids))
            .all()
        )
        if len(pref_logs) != len(job_eval_ids):
            raise RuntimeError(
                "Ambiguity detected in PreferenceLog: each owned evaluation must "
                "have exactly one correction. Cleanup aborted and rolled back."
            )
        for pl in pref_logs:
            if (
                pl.user_id != user.user_id
                or pl.agent_name != AGENT_ID
                or pl.notes != expected_note
            ):
                raise RuntimeError(
                    f"Ambiguity detected in PreferenceLog {pl.log_id}: "
                    "entity attributes do not strictly match synthetic conjunction "
                    f"requirements (user={pl.user_id}, agent={pl.agent_name}, "
                    f"notes={pl.notes}). Cleanup aborted and rolled back."
                )

        # Fail closed if any PreferenceLog exists with note outside matching jobs
        foreign_logs = (
            session.query(PreferenceLog)
            .filter(
                PreferenceLog.notes == expected_note,
                ~PreferenceLog.evaluation_id.in_(job_eval_ids),
            )
            .all()
        )
        if foreign_logs:
            raise RuntimeError(
                f"Ambiguity detected: found {len(foreign_logs)} PreferenceLog(s) "
                f"with run note '{expected_note}' attached to unexpected "
                "evaluation job(s). Cleanup aborted and rolled back."
            )

        # Proceed with deletions for the validated entities
        if job_eval_ids:
            session.query(PreferenceLog).filter(
                PreferenceLog.evaluation_id.in_(job_eval_ids)
            ).delete(synchronize_session=False)
            session.query(AgentGeneration).filter(
                AgentGeneration.evaluation_id.in_(job_eval_ids)
            ).delete(synchronize_session=False)
            session.query(AgentResult).filter(
                AgentResult.evaluation_id.in_(job_eval_ids)
            ).delete(synchronize_session=False)

        session.commit()
        return (len(candidate_docs), len(candidate_docs))
    except Exception:
        session.rollback()
        raise


def main() -> None:
    # Must run before any session flush: registers every ORM model module
    # (e.g. admin.models' PromptVersion) so FK string references resolve.
    import_model_modules()

    parser = argparse.ArgumentParser(
        description=(
            "Generate (or clean up) synthetic SME DPO score-edit corrections "
            "for local pipeline testing. DEV/TEST/LOCAL ONLY."
        )
    )
    parser.add_argument(
        "--count",
        type=int,
        default=25,
        help="Number of synthetic corrections to generate (default: 25).",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help=(
            "UUID string run-id. Optional when generating (auto-generated if omitted); "
            "required when running --cleanup."
        ),
    )
    parser.add_argument(
        "--confirm",
        type=str,
        default=None,
        help=("Confirmation keyword ('SEED' to write pairs, 'CLEANUP' to delete)."),
    )
    parser.add_argument(
        "--confirm-target",
        type=str,
        default=None,
        help="Database target fingerprint or 'LOCAL' for local/test targets.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help=(
            "Delete synthetic rows for a specific --run-id instead of "
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

    # 1. Strict environment check: only development/test/local; always reject production
    current_env = validate_environment()
    logger.info("Synthetic seeder safety verified environment: '%s'.", current_env)

    # 2. Strict DB target check: fail-closed based on actual DATABASE_URL
    target_fingerprint = validate_database_target()
    settings = get_settings()
    configured_db_url = (getattr(settings, "database_url", None) or "").strip()
    is_local = is_local_or_test_target(configured_db_url)
    expected_target_ack = "LOCAL" if is_local else target_fingerprint
    logger.info(
        "Synthetic seeder database target verified (local=%s, fingerprint='%s').",
        is_local,
        target_fingerprint,
    )

    # 3. Strict acknowledgement checks (both environment action and database target)
    if not args.cleanup and args.count <= 0:
        raise ValueError(f"Count must be a positive integer, got {args.count}.")

    if args.cleanup:
        if args.confirm != CONFIRM_CLEANUP_KEYWORD:
            raise PermissionError(
                "Explicit acknowledgement required for cleanup. Please provide "
                f"--confirm {CONFIRM_CLEANUP_KEYWORD}."
            )
        if not args.run_id:
            raise ValueError(
                "Cleanup requires an exact --run-id <UUID> to prevent accidental "
                "global synthetic row deletion."
            )
    else:
        if args.confirm != CONFIRM_SEED_KEYWORD:
            raise PermissionError(
                "Explicit acknowledgement required for seeding writes. Please provide "
                f"--confirm {CONFIRM_SEED_KEYWORD}."
            )

    target_ack = (args.confirm_target or "").strip().lower()
    if not target_ack or target_ack != expected_target_ack.lower():
        raise PermissionError(
            "Explicit acknowledgement required for database target. Please provide "
            f"--confirm-target {expected_target_ack}."
        )

    parsed_run_id: uuid.UUID | None = None
    if args.run_id:
        try:
            parsed_run_id = uuid.UUID(args.run_id)
        except ValueError as err:
            raise ValueError(f"Invalid UUID for --run-id: '{args.run_id}'") from err

    session = get_session_factory()()
    try:
        if args.cleanup:
            assert parsed_run_id is not None
            found, left_in_place = cleanup(session, run_id=parsed_run_id)
            if found == 0:
                logger.info(
                    "Nothing to clean up: no synthetic rows found for run-id %s.",
                    parsed_run_id,
                )
            else:
                logger.info(
                    "Cleanup complete for run-id %s: removed "
                    "PreferenceLog/AgentGeneration/AgentResult rows for %d synthetic "
                    "evaluations -- they can no longer produce a DPO pair. %d Document/"
                    "EvaluationJob/EvaluationFormSnapshot row(s) remain "
                    "(the DB permanently forbids deleting evaluation form "
                    "snapshots, for any evaluation) but stay tagged with "
                    "'%s' and are otherwise inert.",
                    parsed_run_id,
                    found,
                    left_in_place,
                    SYNTHETIC_TITLE_PREFIX.strip(),
                )
            return

        run_id, evaluation_ids = generate(session, args.count, run_id=parsed_run_id)
        logger.info(
            "Generated %d synthetic SME corrections for run-id '%s' tagged '%s' / "
            "notes='%s'.",
            len(evaluation_ids),
            run_id,
            SYNTHETIC_TITLE_PREFIX.strip(),
            _format_note(run_id),
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
