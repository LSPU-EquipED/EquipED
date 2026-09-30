"""House-rule DPO corrections on REAL SME evaluations (adapter validation).

Teaches one invented, easy-to-measure rule to an SME adapter: for each *edited*
criterion the score is raised by 1 (capped at 4); every other criterion is a
*control* and is never corrected. The script reads the stored answers of real,
COMPLETED SME evaluations and, only with explicit confirmation, inserts small
score-only ``PreferenceLog`` corrections. The existing exporter turns those into
DPO pairs, so the exporter, projectors and training flow are unchanged.

It never modifies evaluations, generations, documents or snapshots. Every row it
writes is tagged ``house-rule-seed:<run-id>`` and can be removed with --cleanup.

DEV/TEST/LOCAL ONLY. The adapter trained on these corrections teaches an INVENTED
rule: it is a validation artifact and must never be published.

Usage (from apps/):
    # 1. Read-only report (the default):
    uv run --project server python -m server.scripts.seed_house_rule_edits \
        --train-evaluations-file train_ids.txt \
        --reference-evaluations-file heldout_ids.txt --verify-export \
        --report-csv expected_scores.csv

    # 2. Write the corrections (both flags are required):
    uv run --project server python -m server.scripts.seed_house_rule_edits \
        --train-evaluations-file train_ids.txt \
        --reference-evaluations-file heldout_ids.txt --verify-export \
        --confirm SEED --confirm-target <LOCAL or fingerprint>

    # 3. Remove them when the validation is done:
    uv run --project server python -m server.scripts.seed_house_rule_edits \
        --cleanup --run-id <UUID> --confirm CLEANUP --confirm-target <T>
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.contracts import LlmRubricGuidanceConfig
from server.modules.rubrics.snapshot_contracts import SnapshotIntegrityError
from server.modules.rubrics.snapshots import load_verified_agent_snapshot
from server.modules.synthesis.models import AgentGeneration

AGENT_ID = "sme"
RUN_NOTE_PREFIX = "house-rule-seed"
HOUSE_USER_EMAIL = "house-rule-seed@local.test"
DEFAULT_EDIT_CRITERIA = ("OP-01", "OP-03", "OP-05", "A-01", "A-03", "A-05")
# The Colab notebook trains with max_prompt_length = 1536 tokens.
PROMPT_TOKEN_LIMIT = 1536
CHARS_PER_TOKEN = 4
CONTRACT_KEY = "criterion_measurements.v1"
CONTRACT_VERSION = 1

Group = Literal["train", "reference"]
Role = Literal["edited", "control"]


class IneligibleRunError(Exception):
    """The run cannot proceed; nothing was written."""


def _as_score(value: object) -> int | None:
    """A valid 1-4 integer score, else None. Booleans and strings are invalid."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    else:
        return None
    return number if 1 <= number <= 4 else None


def apply_rule(score: object) -> tuple[int | None, str | None]:
    """The house rule: (new_score, skip_reason). Raise by 1, capped at 4."""
    current = _as_score(score)
    if current is None:
        return None, "invalid_score"
    if current >= 4:
        return None, "already_max"
    return current + 1, None


def is_score_shaped(measurement: dict[str, Any]) -> bool:
    """True only for an llm_rubric_guidance measurement (same test as the
    projector's private helper; a test pins that they agree)."""
    return (
        "score" in measurement
        and "instances" not in measurement
        and "total_units" not in measurement
    )


def base_reference(scores: Sequence[int]) -> int:
    """Mean of an SLM's runs, rounded half up (2.5 -> 3)."""
    return int(sum(scores) / len(scores) + 0.5)


def expected_score(role: Role, reference: int) -> int:
    """What the adapter should score if it learned the rule."""
    return min(4, reference + 1) if role == "edited" else reference


def normalize_codes(raw: Sequence[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in raw:
        code = item.strip().upper()
        if code:
            seen.setdefault(code, None)
    return tuple(seen)


def format_note(run_id: uuid.UUID) -> str:
    return f"{RUN_NOTE_PREFIX}:{run_id}"


@dataclass(frozen=True, slots=True)
class CriterionPlan:
    evaluation_id: uuid.UUID
    generation_id: uuid.UUID
    criterion_code: str
    role: Role
    base_score: int | None
    new_score: int | None
    skip_reason: str | None


@dataclass(frozen=True, slots=True)
class GenerationInfo:
    generation_id: uuid.UUID
    unit_key: str
    prompt_chars: int
    criterion_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationPlan:
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    group: Group
    generations: tuple[GenerationInfo, ...]
    criteria: tuple[CriterionPlan, ...]

    @property
    def writes(self) -> tuple[CriterionPlan, ...]:
        """Corrections to write. Reference (held-out) plans never write."""
        if self.group != "train":
            return ()
        return tuple(c for c in self.criteria if c.new_score is not None)


@dataclass(frozen=True, slots=True)
class RunPlan:
    plans: tuple[EvaluationPlan, ...]
    edit_codes: tuple[str, ...]

    @property
    def writes(self) -> tuple[CriterionPlan, ...]:
        return tuple(c for plan in self.plans for c in plan.writes)

    @property
    def pair_generation_ids(self) -> frozenset[uuid.UUID]:
        """Generations that will produce a DPO pair (>= 1 correction each)."""
        return frozenset(c.generation_id for c in self.writes)

    def skip_counts(self) -> Counter[str]:
        return Counter(
            c.skip_reason for plan in self.plans for c in plan.criteria if c.skip_reason
        )


def _usable_generations(session: Session, evaluation_id: uuid.UUID):
    """SME generations the exporter would use: ok, criterion_measurements.v1."""
    return (
        session.query(AgentGeneration)
        .filter(
            AgentGeneration.evaluation_id == evaluation_id,
            AgentGeneration.agent_id == AGENT_ID,
            AgentGeneration.envelope_status == "ok",
            AgentGeneration.response_contract_key == CONTRACT_KEY,
            AgentGeneration.response_contract_version == CONTRACT_VERSION,
        )
        .order_by(AgentGeneration.unit_key.asc(), AgentGeneration.generation_id.asc())
        .all()
    )


def _measurements(generation: AgentGeneration) -> list[dict[str, Any]]:
    raw = generation.response_json
    if not raw and generation.response_text:
        try:
            raw = json.loads(generation.response_text)
        except (TypeError, ValueError):
            raw = None
    items = raw.get("criterion_measurements") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _measured_codes(measurements: list[dict[str, Any]]) -> list[str]:
    return [
        m["criterion_id"]
        for m in measurements
        if isinstance(m.get("criterion_id"), str) and m["criterion_id"]
    ]


def _existing_log_codes(session: Session, evaluation_id: uuid.UUID) -> set[str]:
    """Criteria that already have ANY preference log for the SME agent."""
    rows = (
        session.query(PreferenceLog.criterion_id)
        .filter(
            PreferenceLog.evaluation_id == evaluation_id,
            func.lower(PreferenceLog.agent_name) == AGENT_ID,
            PreferenceLog.criterion_id.isnot(None),
        )
        .all()
    )
    return {code for (code,) in rows}


def _decide(
    role: Role,
    code: str,
    measurement: dict[str, Any],
    strategy: object,
    existing: set[str],
    duplicated: bool,
) -> tuple[int | None, str | None]:
    """(new_score, skip_reason) for one measured criterion."""
    if role == "control":
        return None, None
    if strategy is None:
        return None, "not_in_snapshot"
    if not isinstance(strategy, LlmRubricGuidanceConfig):
        return None, "not_llm_rubric_guidance"
    if not is_score_shaped(measurement):
        return None, "not_score_shaped"
    if duplicated:
        return None, "criterion_in_multiple_generations"
    if code in existing:
        return None, "existing_log"
    return apply_rule(measurement.get("score"))


def plan_evaluation(
    session: Session,
    evaluation_id: uuid.UUID,
    *,
    group: Group,
    edit_codes: Sequence[str],
) -> EvaluationPlan:
    """Decide what to correct in one evaluation. Fails closed; reads only."""
    job = session.get(EvaluationJob, evaluation_id)
    if job is None:
        raise IneligibleRunError(f"Evaluation {evaluation_id} does not exist.")
    status = str(getattr(job.status, "value", job.status))
    if status != "COMPLETED":
        raise IneligibleRunError(
            f"Evaluation {evaluation_id} is not COMPLETED (status {status})."
        )
    # Only present on the per-agent adapter branch; absent columns mean "no adapter".
    applied = (
        (getattr(job, "adapter_resolution", None) or {}).get(AGENT_ID) or {}
    ).get("applied")
    if applied:
        raise IneligibleRunError(
            f"Evaluation {evaluation_id} was scored with adapter {applied} applied; "
            "the experiment needs base-model answers only."
        )
    generations = _usable_generations(session, evaluation_id)
    if not generations:
        raise IneligibleRunError(
            f"Evaluation {evaluation_id} has no usable SME generation (needs "
            f"envelope_status 'ok' and contract {CONTRACT_KEY} v{CONTRACT_VERSION})."
        )
    try:
        snapshot = load_verified_agent_snapshot(session, evaluation_id, AGENT_ID)
    except SnapshotIntegrityError as exc:
        raise IneligibleRunError(
            f"Evaluation {evaluation_id} has no verified SME form snapshot: {exc}"
        ) from exc
    strategies = {
        criterion.criterion_code: criterion.strategy_config
        for domain in snapshot.snapshot_payload.form.domains
        for criterion in domain.criteria
    }
    existing = _existing_log_codes(session, evaluation_id)
    document = session.get(Document, job.document_id)
    title = (document.title if document is not None else "") or ""
    edit_set = frozenset(edit_codes)

    measured = [(g, _measurements(g)) for g in generations]
    occurrences = Counter(
        code for _, measurements in measured for code in _measured_codes(measurements)
    )
    infos: list[GenerationInfo] = []
    criteria: list[CriterionPlan] = []
    for generation, measurements in measured:
        infos.append(
            GenerationInfo(
                generation_id=generation.generation_id,
                unit_key=generation.unit_key,
                prompt_chars=len(generation.prompt_text or ""),
                criterion_codes=tuple(_measured_codes(measurements)),
            )
        )
        for measurement in measurements:
            code = measurement.get("criterion_id")
            if not isinstance(code, str) or not code:
                continue
            role: Role = "edited" if code in edit_set else "control"
            new_score, skip_reason = _decide(
                role,
                code,
                measurement,
                strategies.get(code),
                existing,
                occurrences[code] > 1,
            )
            criteria.append(
                CriterionPlan(
                    evaluation_id=evaluation_id,
                    generation_id=generation.generation_id,
                    criterion_code=code,
                    role=role,
                    base_score=_as_score(measurement.get("score")),
                    new_score=new_score,
                    skip_reason=skip_reason,
                )
            )
    return EvaluationPlan(
        evaluation_id=evaluation_id,
        document_id=job.document_id,
        document_title=title,
        group=group,
        generations=tuple(infos),
        criteria=tuple(criteria),
    )


def plan_run(
    session: Session,
    *,
    train_ids: Sequence[uuid.UUID],
    reference_ids: Sequence[uuid.UUID],
    edit_codes: Sequence[str],
) -> RunPlan:
    """Plan a whole run. Any problem aborts the run before anything is written."""
    codes = normalize_codes(edit_codes)
    if not codes:
        raise IneligibleRunError("At least one edit criterion is required.")
    all_ids = [*train_ids, *reference_ids]
    if not all_ids:
        raise IneligibleRunError("List at least one evaluation to plan.")
    duplicates = sorted(str(i) for i, n in Counter(all_ids).items() if n > 1)
    if duplicates:
        raise IneligibleRunError(
            "Evaluation id listed more than once (or in both lists): "
            + ", ".join(duplicates)
        )
    plans = [
        plan_evaluation(session, eid, group="train", edit_codes=codes)
        for eid in train_ids
    ] + [
        plan_evaluation(session, eid, group="reference", edit_codes=codes)
        for eid in reference_ids
    ]
    train_documents = {p.document_id for p in plans if p.group == "train"}
    shared = train_documents & {p.document_id for p in plans if p.group == "reference"}
    if shared:
        raise IneligibleRunError(
            "A document is in both the train and the reference list; a held-out SLM "
            "must never be trained on: " + ", ".join(sorted(str(d) for d in shared))
        )
    seen = {c.criterion_code for p in plans for c in p.criteria}
    unknown = [code for code in codes if code not in seen]
    if unknown:
        raise IneligibleRunError(
            "Edit criteria never seen in any listed evaluation: " + ", ".join(unknown)
        )
    return RunPlan(plans=tuple(plans), edit_codes=codes)
