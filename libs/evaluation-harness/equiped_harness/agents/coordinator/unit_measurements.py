"""Ground and score occurrence-level Coordinator count and ratio rows."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from equiped_harness.agents.coordinator.catalog import CatalogItem
from equiped_harness.agents.coordinator.measurements import _score_ordinary
from equiped_harness.contracts import (
    CountBandConfig,
    CriterionDefinition,
    GroundedInstance,
    GroundedInstanceMeasurement,
    GroundedUnit,
    LlmRubricGuidanceConfig,
    QualifyingUnitsMeasurement,
    RatioBandConfig,
)
from equiped_harness.contracts.results import CriterionScore
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.strategies.calculators import score_count, score_ratio

UNIT_POLICIES: dict[str, dict[str, Any]] = {
    "OP-01": {
        "kind": "ratio",
        "categories": ("topic_transition",),
        "distinct_types": False,
        "label": "topic transitions",
    },
    "OP-02": {
        "kind": "count",
        "categories": ("interactive_task",),
        "distinct_types": False,
        "label": "interactive tasks",
    },
    "OP-03": {
        "kind": "ratio",
        "categories": ("student_task",),
        "distinct_types": False,
        "label": "student tasks",
    },
    "OP-04": {
        "kind": "ratio",
        "categories": ("instructional_section",),
        "distinct_types": False,
        "label": "instructional sections",
    },
    "OP-05": {
        "kind": "count",
        "categories": ("enhancement_activity",),
        "distinct_types": False,
        "label": "enhancement activities",
    },
    "A-01": {
        "kind": "ratio",
        "categories": ("student_task",),
        "distinct_types": False,
        "label": "student tasks",
    },
    "A-02": {
        "kind": "count",
        "categories": (
            "objective_test",
            "written_response",
            "reflection",
            "performance_task",
            "project",
            "oral_assessment",
            "self_assessment",
        ),
        "distinct_types": True,
        "label": "assessment types",
    },
    "A-03": {
        "kind": "count",
        "categories": (
            "checkpoint",
            "self_assessment",
            "reflection_record",
            "cumulative_tracker",
        ),
        "distinct_types": False,
        "label": "progress monitoring activities",
    },
    "A-04": {
        "kind": "count",
        "categories": ("answer_key", "rubric", "remediation", "positive_reinforcement"),
        "distinct_types": True,
        "label": "support types",
    },
}

_ITEM_KEYS = {"source_id", "quote", "category", "qualifies", "reason"}
_CANONICAL_KEYS = _ITEM_KEYS | {"item_id", "start", "end"}


def unit_policy(criterion_code: str) -> dict[str, Any]:
    try:
        return UNIT_POLICIES[criterion_code]
    except KeyError as exc:
        raise AgentExecutionError("Unknown Coordinator unit criterion") from exc


def _normalized_with_offsets(text: str) -> tuple[str, list[int], list[int]]:
    chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for match in re.finditer(r"\S+", text):
        if chars:
            chars.append(" ")
            starts.append(match.start() - 1)
            ends.append(match.start())
        for index in range(match.start(), match.end()):
            chars.append(text[index])
            starts.append(index)
            ends.append(index + 1)
    return "".join(chars), starts, ends


def _ground(
    quote: str, source_id: str, catalog: dict[str, CatalogItem]
) -> tuple[str, int, int, str]:
    target = " ".join(quote.split())
    if not target:
        raise AgentExecutionError("Occurrence quote is empty")
    hits: dict[tuple[str, int, int], str] = {}
    entry = catalog.get(source_id)
    if entry is None or entry.source != "slm":
        raise AgentExecutionError("Occurrence source_id is not an SLM packet source")
    normalized, starts, ends = _normalized_with_offsets(entry.text)
    cursor = 0
    while (pos := normalized.find(target, cursor)) >= 0:
        endpos = pos + len(target)
        start = entry.start + starts[pos]
        end = entry.start + ends[endpos - 1]
        hits[(source_id, start, end)] = entry.text[starts[pos] : ends[endpos - 1]]
        cursor = pos + 1
    spans = {(start, end) for _, start, end in hits}
    if len(spans) != 1:
        raise AgentExecutionError(
            "Occurrence quote is absent or ambiguous in SLM source"
        )
    start, end = next(iter(spans))
    source_id = next(sid for sid, a, b in hits if (a, b) == (start, end))
    return source_id, start, end, hits[(source_id, start, end)]


def _canonical_item(
    item: dict[str, Any], policy: dict[str, Any], catalog: dict[str, CatalogItem]
) -> dict[str, Any]:
    if not isinstance(item, dict) or set(item) not in (_ITEM_KEYS, _CANONICAL_KEYS):
        raise AgentExecutionError("Occurrence item has invalid fields")
    if not isinstance(item["source_id"], str) or item["source_id"] not in catalog:
        raise AgentExecutionError("Occurrence source_id is not in the packet catalog")
    if (
        not isinstance(item["quote"], str)
        or not item["quote"]
        or len(item["quote"]) > 700
    ):
        raise AgentExecutionError("Occurrence quote is invalid")
    if (
        not isinstance(item["category"], str)
        or item["category"] not in policy["categories"]
    ):
        raise AgentExecutionError("Occurrence category is not allowed for criterion")
    if type(item["qualifies"]) is not bool:
        raise AgentExecutionError("Occurrence qualifies must be a boolean")
    if (
        not isinstance(item["reason"], str)
        or not item["reason"].strip()
        or len(item["reason"]) > 500
    ):
        raise AgentExecutionError("Occurrence reason is invalid")
    source_id, start, end, original_quote = _ground(
        item["quote"], item["source_id"], catalog
    )
    if item["source_id"] != source_id:
        raise AgentExecutionError("Occurrence source_id does not match grounded quote")
    item_id = (
        "unit-"
        + hashlib.sha256(f"slm|{start}|{end}|{item['category']}".encode()).hexdigest()[
            :16
        ]
    )
    result = {key: item[key] for key in _ITEM_KEYS}
    result["quote"] = original_quote
    result.update(item_id=item_id, start=start, end=end)
    if "item_id" in item and (item["item_id"], item["start"], item["end"]) != (
        item_id,
        start,
        end,
    ):
        raise AgentExecutionError("Persisted occurrence identity does not match source")
    return result


def validate_unit_row(
    criterion: CriterionDefinition,
    row: dict[str, Any],
    catalog: dict[str, CatalogItem],
    *,
    max_items: int = 100,
) -> dict[str, Any]:
    policy = unit_policy(criterion.criterion_code)
    config = criterion.strategy_config
    if (policy["kind"] == "count" and not isinstance(config, CountBandConfig)) or (
        policy["kind"] == "ratio" and not isinstance(config, RatioBandConfig)
    ):
        raise AgentExecutionError("Coordinator unit criterion has unsupported strategy")
    if (
        not isinstance(row, dict)
        or set(row) != {"status", "items"}
        or not isinstance(row.get("status"), str)
        or row.get("status") not in {"supported", "absent"}
    ):
        raise AgentExecutionError("Occurrence row has invalid fields or status")
    items = row["items"]
    if not isinstance(items, list) or len(items) > max_items:
        raise AgentExecutionError("Occurrence packet exceeds item limit")
    if row["status"] == "absent" and items:
        raise AgentExecutionError("Absent occurrence row cannot carry items")
    if row["status"] == "supported" and not items:
        raise AgentExecutionError("Supported occurrence row requires items")
    grounded = [_canonical_item(item, policy, catalog) for item in items]
    dedup: dict[tuple[int, int, str], dict[str, Any]] = {}
    classifications: dict[tuple[int, int], tuple[str, bool]] = {}
    for item in grounded:
        span = (item["start"], item["end"])
        classification = (item["category"], item["qualifies"])
        if span in classifications and classifications[span] != classification:
            raise AgentExecutionError("Occurrence has conflicting classifications")
        classifications[span] = classification
        dedup[(item["start"], item["end"], item["category"])] = item
    return {"status": row["status"], "items": list(dedup.values())}


def _metric_items(
    criterion: CriterionDefinition, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    counted = [i for i in items if i["qualifies"]]
    if UNIT_POLICIES[criterion.criterion_code]["distinct_types"]:
        return list({i["category"]: i for i in counted}.values())
    return counted


def score_unit_row(
    criterion: CriterionDefinition, row: dict[str, Any], catalog: dict[str, CatalogItem]
) -> tuple[CriterionScore, dict[str, Any]]:
    if isinstance(criterion.strategy_config, LlmRubricGuidanceConfig):
        return _score_ordinary(criterion, row, catalog)
    persisted_merged = (
        isinstance(row, dict)
        and isinstance(row.get("items"), list)
        and len(row["items"]) > 100
        and all(
            isinstance(item, dict) and _CANONICAL_KEYS <= set(item)
            for item in row["items"]
        )
    )
    canonical = validate_unit_row(
        criterion, row, catalog, max_items=200 if persisted_merged else 100
    )
    policy = unit_policy(criterion.criterion_code)
    items = canonical["items"]
    measured = items if policy["kind"] == "ratio" else _metric_items(criterion, items)
    config = criterion.strategy_config
    if isinstance(config, CountBandConfig):
        instances = tuple(GroundedInstance(excerpt=i["quote"]) for i in measured)
        # The standalone measurement contract caps model-produced instances at
        # 100. Merged, independently bounded packets may contain up to 200.
        measurement = GroundedInstanceMeasurement.model_construct(instances=instances)
        result = score_count(
            config,
            measurement,
        )
        metrics: dict[str, Any] = {"count": result.count}
    elif isinstance(config, RatioBandConfig) and config.mode == "coverage_percentage":
        qualifying = [i for i in measured if i["qualifies"]]
        result = score_ratio(
            config,
            QualifyingUnitsMeasurement(
                total_units=tuple(
                    GroundedUnit(unit_id=i["item_id"], evidence=i["quote"])
                    for i in measured
                ),
                qualifying_unit_ids=tuple(i["item_id"] for i in qualifying),
                has_measurable_content=bool(measured),
            ),
        )
        metrics = {"total": len(measured), "qualifying": len(qualifying)}
    else:
        raise AgentExecutionError("Unsupported Coordinator unit scoring mode")
    score = result.score
    fact = {
        "kind": policy["kind"],
        "status": canonical["status"],
        "items": items,
        **metrics,
        "unit_label": policy["label"],
        "instance_ids": [i["item_id"] for i in measured],
        "unit_ids": [i["item_id"] for i in measured],
        "qualifying_unit_ids": [i["item_id"] for i in measured if i["qualifies"]],
        "scoring_config": config.model_dump(mode="json"),
    }
    evidence = tuple(i["quote"] for i in items[:8])
    return CriterionScore(
        criterion.criterion_code,
        criterion.title,
        score,
        f"{criterion.title}: "
        f"{metrics.get('count', metrics.get('qualifying', 0))} "
        f"{policy['label']}; deterministic score {score}.",
        evidence=evidence,
    ), fact


def combine_unit_rows(
    criterion: CriterionDefinition,
    rows: list[dict[str, Any]],
    catalog: dict[str, CatalogItem],
) -> dict[str, Any]:
    unit_policy(criterion.criterion_code)
    merged: dict[tuple[int, int, str], dict[str, Any]] = {}
    statuses: list[str] = []
    for row in rows:
        canonical = validate_unit_row(criterion, row, catalog)
        statuses.append(canonical["status"])
        for item in canonical["items"]:
            key = (item["start"], item["end"], item["category"])
            previous = merged.get(key)
            if previous and previous["qualifies"] != item["qualifies"]:
                raise AgentExecutionError(
                    "Occurrence has conflicting classifications across packets"
                )
            merged[key] = item
    if len(merged) > 200:
        raise AgentExecutionError("Merged occurrence rows exceed item limit")
    items = list(merged.values())
    if not items:
        return {"status": "absent", "items": []}
    return {"status": "supported", "items": items}
