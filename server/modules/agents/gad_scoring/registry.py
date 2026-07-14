"""Registry, validation, and rendering for code-scored GAD criteria."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError
from .female_male_count import (
    CRITERION_ID as BALANCE_ID,
)
from .female_male_count import (
    CRITERION_TITLE as BALANCE_TITLE,
)
from .female_male_count import (
    GAD_ROW_2_PROMPT,
    score_representation_balance,
)
from .life_experiences import (
    CRITERION_ID as LIFE_ID,
)
from .life_experiences import (
    CRITERION_TITLE as LIFE_TITLE,
)
from .life_experiences import (
    GAD_ROW_4_PROMPT,
    score_life_experience_instances,
)
from .peace_and_equality import (
    CRITERION_ID as PEACE_ID,
)
from .peace_and_equality import (
    CRITERION_TITLE as PEACE_TITLE,
)
from .peace_and_equality import (
    GAD_ROW_5_PROMPT,
    score_peace_equality_instances,
)
from .potential import (
    CRITERION_ID as POTENTIAL_ID,
)
from .potential import (
    CRITERION_TITLE as POTENTIAL_TITLE,
)
from .potential import (
    GAD_ROW_3_PROMPT,
    score_respect_potential_instances,
)
from .stereotypes import (
    CRITERION_ID as STEREOTYPE_ID,
)
from .stereotypes import (
    CRITERION_TITLE as STEREOTYPE_TITLE,
)
from .stereotypes import (
    GAD_ROW_1_PROMPT,
    score_stereotype_instances,
)


@dataclass(frozen=True, slots=True)
class CriterionDefinition:
    criterion_id: str
    title: str
    prompt: str
    score: Callable[..., int]
    balance: bool = False


CRITERIA: tuple[CriterionDefinition, ...] = (
    CriterionDefinition(
        STEREOTYPE_ID,
        STEREOTYPE_TITLE,
        GAD_ROW_1_PROMPT,
        score_stereotype_instances,
    ),
    CriterionDefinition(
        BALANCE_ID,
        BALANCE_TITLE,
        GAD_ROW_2_PROMPT,
        score_representation_balance,
        balance=True,
    ),
    CriterionDefinition(
        POTENTIAL_ID,
        POTENTIAL_TITLE,
        GAD_ROW_3_PROMPT,
        score_respect_potential_instances,
    ),
    CriterionDefinition(
        LIFE_ID,
        LIFE_TITLE,
        GAD_ROW_4_PROMPT,
        score_life_experience_instances,
    ),
    CriterionDefinition(
        PEACE_ID,
        PEACE_TITLE,
        GAD_ROW_5_PROMPT,
        score_peace_equality_instances,
    ),
)

REGISTERED_CODES: frozenset[str] = frozenset(
    definition.criterion_id for definition in CRITERIA
)


def build_prompt(
    definition: CriterionDefinition,
    chunks: list[dict[str, Any]],
) -> str:
    return json.dumps(
        {
            "agent": "gad",
            "criterion_id": definition.criterion_id,
            "document_chunks": chunks,
            "instructions": [definition.prompt],
        },
        ensure_ascii=False,
    )


def parse_payload(raw_response: str, criterion_id: str) -> dict[str, Any]:
    if not isinstance(raw_response, str):
        raise AgentExecutionError(
            f"GAD criterion {criterion_id} returned a non-string response"
        )
    payload = raw_response.strip()
    fenced = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$",
        payload,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        payload = fenced.group(1).strip()
    elif not payload.startswith("{"):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AgentExecutionError(
            f"GAD criterion {criterion_id} returned invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise AgentExecutionError(
            f"GAD criterion {criterion_id} returned an invalid response"
        )
    return parsed


def _non_negative_int(value: Any, field: str, criterion_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AgentExecutionError(
            f"GAD criterion {criterion_id} returned invalid {field}"
        )
    return value


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _grounded_instances(
    payload: dict[str, Any],
    chunk_infos: list[dict[str, Any]],
    criterion_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    raw_instances = payload.get("instances", [])
    if not isinstance(raw_instances, list):
        raise AgentExecutionError(
            f"GAD criterion {criterion_id} returned invalid instances"
        )

    normalized_chunks = [
        (
            str(chunk.get("chunk_id", "")),
            _normalized(str(chunk.get("text", ""))),
        )
        for chunk in chunk_infos
    ]
    seen: set[str] = set()
    evidence: list[str] = []
    chunk_ids: list[str] = []
    ungrounded = 0

    for instance in raw_instances:
        if not isinstance(instance, dict):
            ungrounded += 1
            continue
        excerpt = str(instance.get("excerpt", "")).strip()
        normalized_excerpt = _normalized(excerpt)
        if not normalized_excerpt or normalized_excerpt in seen:
            continue
        matching_ids = [
            chunk_id
            for chunk_id, chunk_text in normalized_chunks
            if normalized_excerpt in chunk_text
        ]
        if not matching_ids:
            ungrounded += 1
            continue
        seen.add(normalized_excerpt)
        evidence.append(excerpt)
        for chunk_id in matching_ids:
            if chunk_id and chunk_id not in chunk_ids:
                chunk_ids.append(chunk_id)

    return tuple(evidence), tuple(chunk_ids), ungrounded


def build_score(
    definition: CriterionDefinition,
    payload: dict[str, Any],
    chunk_infos: list[dict[str, Any]],
) -> CriterionScore:
    summary = payload.get("summary", "")
    if not isinstance(summary, str) or not summary.strip():
        raise AgentExecutionError(
            f"GAD criterion {definition.criterion_id} returned invalid summary"
        )
    summary = summary.strip()

    if definition.balance:
        female_count = _non_negative_int(
            payload.get("female_count"), "female_count", definition.criterion_id
        )
        male_count = _non_negative_int(
            payload.get("male_count"), "male_count", definition.criterion_id
        )
        band = definition.score(female_count, male_count)
        difference = abs(female_count - male_count)
        justification = (
            f"Female representations: {female_count}; male representations: "
            f"{male_count}; absolute difference: {difference}. {summary}"
        )
        evidence: tuple[str, ...] = ()
        chunk_ids: tuple[str, ...] = ()
    else:
        claimed_count = _non_negative_int(
            payload.get("instance_count"),
            "instance_count",
            definition.criterion_id,
        )
        evidence, chunk_ids, ungrounded = _grounded_instances(
            payload, chunk_infos, definition.criterion_id
        )
        grounded_count = len(evidence)
        band = definition.score(grounded_count)
        justification = (
            f"Grounded unique instances: {grounded_count} "
            f"(model reported {claimed_count}; {ungrounded} unsupported "
            f"or invalid instance(s) excluded). {summary}"
        )

    return CriterionScore(
        criterion_id=definition.criterion_id,
        criterion_title=definition.title,
        score=band,
        justification=justification,
        chunk_ids=chunk_ids,
        evidence=evidence,
    )


__all__ = [
    "CRITERIA",
    "REGISTERED_CODES",
    "CriterionDefinition",
    "build_prompt",
    "build_score",
    "parse_payload",
]
