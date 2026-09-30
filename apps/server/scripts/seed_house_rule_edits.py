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

import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

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
