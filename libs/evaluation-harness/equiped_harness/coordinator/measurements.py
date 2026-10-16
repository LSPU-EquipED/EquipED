"""Validate source references and deterministically score current measurements."""

from __future__ import annotations

from typing import Any

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
from equiped_harness.coordinator.catalog import CatalogItem
from equiped_harness.coordinator.objective_gauging import ObjectiveSource
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.result_contracts import CriterionScore
from equiped_harness.strategies.calculators import score_count, score_ratio


def _ensure_source_ids(
    ids: Any, allowed: set[str], *, max_items: int = 64
) -> tuple[str, ...]:
    if (
        not isinstance(ids, list)
        or len(ids) > max_items
        or any(not isinstance(i, str) for i in ids)
    ):
        raise AgentExecutionError("Current Coordinator source references are invalid")
    if len(ids) != len(set(ids)) or any(i not in allowed for i in ids):
        raise AgentExecutionError(
            "Current Coordinator source references are unknown or duplicated"
        )
    return tuple(ids)


def _status(row: dict[str, Any], *, allows_absent: bool = False) -> str:
    if set(row) - {
        "status",
        "score",
        "evidence_id",
        "instance_ids",
        "unit_ids",
        "qualifying_unit_ids",
    }:
        raise AgentExecutionError("Current Coordinator response contains extra fields")
    status = row.get("status")
    if status == "insufficient":
        raise AgentExecutionError("Current Coordinator task is insufficient")
    if status not in {"supported", "absent"} or (
        status == "absent" and not allows_absent
    ):
        raise AgentExecutionError("Current Coordinator response has invalid status")
    return status


def _make_guidance(
    c: CriterionDefinition, row: dict[str, Any], catalog: dict[str, CatalogItem]
) -> tuple[CriterionScore, dict[str, Any]]:
    status = _status(
        row,
        allows_absent="absent" in getattr(c.strategy_config, "guidance", "").casefold(),
    )
    if set(row) != {"status", "score", "evidence_id"}:
        raise AgentExecutionError("Guidance row has invalid fields")
    score = row.get("score")
    if type(score) is not int or not 1 <= score <= 4:
        raise AgentExecutionError("Guidance score must be an integer from 1 to 4")
    evidence_id = row.get("evidence_id")
    if evidence_id is not None and (
        not isinstance(evidence_id, str)
        or evidence_id not in catalog
        or catalog[evidence_id].source != "slm"
    ):
        raise AgentExecutionError("Guidance evidence_id is not an SLM source ID")
    if status == "supported" and evidence_id is None:
        raise AgentExecutionError("Supported guidance requires one evidence_id")
    if status == "absent" and evidence_id is not None:
        raise AgentExecutionError("Absent guidance cannot carry evidence")
    fact = {
        "kind": "guidance",
        "status": status,
        "score": score,
        "evidence_id": evidence_id,
    }
    evidence = (catalog[evidence_id].text,) if evidence_id else ()
    justification = f"{c.title}: {status} evidence; deterministic score {score}/4."
    return CriterionScore(
        c.criterion_code, c.title, score, justification, evidence=evidence
    ), fact


def _make_count(
    c: CriterionDefinition, row: dict[str, Any], catalog: dict[str, CatalogItem]
) -> tuple[CriterionScore, dict[str, Any]]:
    if set(row) != {"status", "instance_ids"}:
        raise AgentExecutionError("Count row has invalid fields")
    status = _status(row, allows_absent=True)
    ids = _ensure_source_ids(row.get("instance_ids"), set(catalog), max_items=100)
    if any(catalog[i].source != "slm" for i in ids):
        raise AgentExecutionError("Count evidence must use SLM source IDs")
    if status == "supported" and not ids:
        raise AgentExecutionError("Supported count requires evidence instances")
    if status == "absent" and ids:
        raise AgentExecutionError("Absent count cannot carry instances")
    cfg = c.strategy_config
    assert isinstance(cfg, CountBandConfig)
    count = len(ids)
    score = score_count(
        cfg,
        GroundedInstanceMeasurement(
            instances=tuple(GroundedInstance(excerpt=catalog[i].text) for i in ids)
        ),
    ).score
    fact = {
        "kind": "count",
        "status": status,
        "instance_ids": list(ids),
        "count": count,
        "thresholds": [cfg.threshold_4, cfg.threshold_3, cfg.threshold_2],
    }
    evidence = tuple(catalog[i].text for i in ids[:8])
    justification = (
        f"{c.title}: {count} distinct instance(s); deterministic score {score}."
    )
    return CriterionScore(
        c.criterion_code, c.title, score, justification, evidence=evidence
    ), fact


def _make_ratio(
    c: CriterionDefinition, row: dict[str, Any], catalog: dict[str, CatalogItem]
) -> tuple[CriterionScore, dict[str, Any]]:
    if set(row) != {"status", "unit_ids", "qualifying_unit_ids"}:
        raise AgentExecutionError("Ratio row has invalid fields")
    status = _status(row, allows_absent=True)
    units = _ensure_source_ids(row.get("unit_ids"), set(catalog), max_items=200)
    qualifying = _ensure_source_ids(
        row.get("qualifying_unit_ids"), set(units), max_items=200
    )
    if any(catalog[i].source != "slm" for i in units):
        raise AgentExecutionError("Ratio units must use SLM source IDs")
    if status == "supported" and not units:
        raise AgentExecutionError("Supported ratio requires measurable units")
    if status == "absent" and (units or qualifying):
        raise AgentExecutionError("Absent ratio cannot carry units")
    cfg = c.strategy_config
    assert isinstance(cfg, RatioBandConfig)
    score = score_ratio(
        cfg,
        QualifyingUnitsMeasurement(
            total_units=tuple(
                GroundedUnit(unit_id=i, evidence=catalog[i].text) for i in units
            ),
            qualifying_unit_ids=qualifying,
            has_measurable_content=bool(units),
        ),
    ).score
    fact = {
        "kind": "ratio",
        "status": status,
        "unit_ids": list(units),
        "qualifying_unit_ids": list(qualifying),
        "total": len(units),
        "qualifying": len(qualifying),
        "thresholds": [cfg.threshold_4, cfg.threshold_3, cfg.threshold_2],
        **(
            {"short_sample": cfg.short_sample.model_dump(mode="json")}
            if cfg.short_sample is not None
            else {}
        ),
    }
    evidence = tuple(catalog[i].text for i in units[:8])
    justification = (
        f"{c.title}: {len(qualifying)}/{len(units)} qualifying unit(s); "
        f"deterministic score {score}."
    )
    return CriterionScore(
        c.criterion_code, c.title, score, justification, evidence=evidence
    ), fact


def _score_ordinary(
    criterion: CriterionDefinition,
    row: dict[str, Any],
    catalog: dict[str, CatalogItem],
) -> tuple[CriterionScore, dict[str, Any]]:
    """Use the same strategy dispatch for response validation and scoring."""
    config = criterion.strategy_config
    if isinstance(config, LlmRubricGuidanceConfig):
        return _make_guidance(criterion, row, catalog)
    if isinstance(config, CountBandConfig):
        return _make_count(criterion, row, catalog)
    if isinstance(config, RatioBandConfig):
        return _make_ratio(criterion, row, catalog)
    raise AgentExecutionError("Unsupported current Coordinator strategy")


def _validate_objective(
    data: dict[str, Any],
    inventory: ObjectiveSource,
    catalog: dict[str, CatalogItem],
    *,
    dimension: str,
) -> list[dict[str, Any]]:
    rows = data["results"]
    if len(rows) != len(inventory.objectives):
        raise AgentExecutionError(
            "Objective task must include every objective exactly once"
        )
    expected = {o.objective_id for o in inventory.objectives}
    seen: set[str] = set()
    allowed = {k for k, v in catalog.items() if v.source == dimension}
    validated: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"objective_id", "source_ids"}:
            raise AgentExecutionError("Objective row has invalid fields")
        oid = row.get("objective_id")
        if not isinstance(oid, str) or oid not in expected or oid in seen:
            raise AgentExecutionError("Objective task has unknown or duplicate IDs")
        seen.add(oid)
        ids = _ensure_source_ids(row.get("source_ids"), allowed, max_items=2)
        if dimension == "assessment":
            objective_text = next(
                o.text for o in inventory.objectives if o.objective_id == oid
            )
            normalized_objective = " ".join(objective_text.split()).casefold()
            if any(
                normalized_objective in " ".join(catalog[i].text.split()).casefold()
                for i in ids
            ):
                raise AgentExecutionError(
                    "Objective self-quotation is not assessment evidence"
                )
        validated.append({"objective_id": oid, "source_ids": list(ids)})
    if seen != expected:
        raise AgentExecutionError("Objective task is missing an objective")
    by_id = {r["objective_id"]: r for r in validated}
    return [by_id[o.objective_id] for o in inventory.objectives]
