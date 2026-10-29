"""Reconstruct bounded evidence packets for historical Coordinator results.

Ranking is prepared by the authorized caller. This module performs no storage
or model I/O. Counts and ratios visit every original measurement unit; retrieval
order can never remove a unit from a scoring denominator.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from equiped_harness.agents.coordinator.catalog import CatalogItem
from equiped_harness.agents.coordinator.task_prompts import _Task
from equiped_harness.contracts import LlmRubricGuidanceConfig
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.runtime.source_retrieval import (
    SLM_RETRIEVAL_CONTRACT,
    SLM_SOURCE_SPAN_CHARS,
    source_hash,
)

_MAX_SOURCE_CHARS = 8_000
_MAX_OBJECTIVE_CHARS = 2_000
_MAX_OBJECTIVES = 8
_MAX_PACKET_TASKS = 256


def validate_retrieval(
    value: Any,
    *,
    document_id: Any,
    canonical: str,
    criterion_codes: set[str],
) -> dict[str, Any]:
    """Bind rankings to this document, exact source version and rubric."""
    expected_keys = {
        "contract",
        "document_id",
        "source_hash",
        "embedding_model",
        "rankings",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_keys
        or value.get("contract") != SLM_RETRIEVAL_CONTRACT
        or value.get("document_id") != str(document_id)
        or value.get("source_hash") != source_hash(canonical)
        or not isinstance(value.get("embedding_model"), str)
        or not value["embedding_model"].strip()
        or not isinstance(value.get("rankings"), Mapping)
    ):
        raise AgentExecutionError("Coordinator source retrieval identity is invalid")
    rankings = value["rankings"]
    if set(rankings) != criterion_codes - {"A-05"}:
        raise AgentExecutionError("Coordinator source retrieval rubric is incomplete")
    allowed = {
        f"slm-{index + 1:04d}"
        for index in range(
            (len(canonical) + SLM_SOURCE_SPAN_CHARS - 1) // SLM_SOURCE_SPAN_CHARS
        )
    }
    for ranking in rankings.values():
        if (
            not isinstance(ranking, (list, tuple))
            or any(not isinstance(key, str) for key in ranking)
            or len(ranking) != len(allowed)
            or set(ranking) != allowed
        ):
            raise AgentExecutionError(
                "Coordinator source retrieval coverage is invalid"
            )
    return {**value, "rankings": {k: list(v) for k, v in rankings.items()}}


@dataclass(frozen=True, slots=True)
class PacketTask:
    task: _Task
    logical_id: str
    source_ids: tuple[str, ...]
    objective_ids: tuple[str, ...]


def _source_groups(
    items: list[CatalogItem], max_source_chars: int = _MAX_SOURCE_CHARS
) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    current: list[str] = []
    size = 0
    for item in items:
        if current and size + len(item.text) > max_source_chars:
            groups.append(tuple(current))
            current, size = [], 0
        current.append(item.source_id)
        size += len(item.text)
    if current:
        groups.append(tuple(current))
    return groups


def _objective_groups(
    objectives: tuple[dict[str, str], ...], max_objectives: int = _MAX_OBJECTIVES
):
    groups: list[tuple[dict[str, str], ...]] = []
    current: list[dict[str, str]] = []
    size = 0
    for objective in objectives:
        length = len(objective["text"])
        if current and (
            len(current) == max_objectives or size + length > _MAX_OBJECTIVE_CHARS
        ):
            groups.append(tuple(current))
            current, size = [], 0
        current.append(objective)
        size += length
    if current:
        groups.append(tuple(current))
    return groups


def build_packet_tasks(
    specs: list[tuple[str, str, tuple[Any, ...]]],
    catalog: dict[str, CatalogItem],
    objectives: tuple[dict[str, str], ...],
    retrieval: dict[str, Any],
    *,
    prompt_budget: int = 16_000,
    repair_reserve: int = 1_200,
    prompt_factory: Any,
    max_objectives: int = _MAX_OBJECTIVES,
    max_source_chars: int = _MAX_SOURCE_CHARS,
) -> tuple[list[PacketTask], dict[str, Any]]:
    """Plan complete source passes; guidance alone may use retrieved passages."""
    planned: list[PacketTask] = []
    coverage: dict[str, Any] = {}
    for logical_id, kind, criteria in specs:
        namespace = {
            "ordinary": "slm",
            "objective": "assessment",
            "curriculum": "curriculum",
        }[kind]
        items = [item for item in catalog.values() if item.source == namespace]
        item_positions = {item.source_id: i for i, item in enumerate(items)}

        def boundary_context(group: tuple[str, ...]) -> dict[str, str]:
            if not group:
                return {}
            first, last = item_positions[group[0]], item_positions[group[-1]]
            return {
                "before": items[first - 1].text[-240:] if first else "",
                "after": items[last + 1].text[:240] if last + 1 < len(items) else "",
            }

        groups = _source_groups(items, max_source_chars)
        # Even an empty source must explicitly map every objective to no support.
        if not groups:
            groups = [()]
        mode = "complete"
        if kind == "ordinary":
            ranking = retrieval["rankings"][criteria[0].criterion_code]
            positions = {key: index for index, key in enumerate(ranking)}
            groups.sort(key=lambda group: min(positions[key] for key in group))
            if isinstance(criteria[0].strategy_config, LlmRubricGuidanceConfig):
                groups = groups[:1]
                mode = "retrieved"
        objective_groups = (
            [()]
            if kind == "ordinary"
            else _objective_groups(objectives, max_objectives)
        )
        pending = [
            (group, objective_group)
            for objective_group in objective_groups
            for group in groups
        ]
        packets = []
        while pending:
            group, objective_group = pending.pop(0)
            probe = prompt_factory(
                f"{logical_id}.part-999",
                criteria,
                {key: catalog[key] for key in group},
                kind=kind,
                objectives=objective_group,
                packet_scope=mode,
                boundary_context=boundary_context(group),
            )
            if len(probe) + repair_reserve <= prompt_budget:
                packets.append((group, objective_group))
            elif len(group) > 1:
                middle = len(group) // 2
                pending[:0] = [
                    (group[:middle], objective_group),
                    (group[middle:], objective_group),
                ]
            elif len(objective_group) > 1:
                middle = len(objective_group) // 2
                pending[:0] = [
                    (group, objective_group[:middle]),
                    (group, objective_group[middle:]),
                ]
            else:
                raise AgentExecutionError(
                    "Coordinator source unit cannot fit the bounded prompt budget"
                )
        if mode == "retrieved" and len(packets) > 1:
            # Guidance has no count/ratio denominator. Use one candidate packet
            # and explicitly retain its limited source coverage in the audit.
            packets = packets[:1]
        task_ids: list[str] = []
        for index, (group, objective_group) in enumerate(packets, 1):
            task_id = f"{logical_id}.part-{index:03d}"
            subset = {key: catalog[key] for key in group}
            prompt = prompt_factory(
                task_id,
                criteria,
                subset,
                kind=kind,
                objectives=objective_group,
                packet_scope=mode,
                boundary_context=boundary_context(group),
            )
            planned.append(
                PacketTask(
                    _Task(task_id, kind, criteria, prompt),
                    logical_id,
                    group,
                    tuple(o["objective_id"] for o in objective_group),
                )
            )
            task_ids.append(task_id)
        coverage[logical_id] = {
            "mode": mode,
            "source_ids": [item.source_id for item in items],
            "objective_ids": []
            if kind == "ordinary"
            else [o["objective_id"] for o in objectives],
            "task_ids": task_ids,
        }
    if len(planned) > _MAX_PACKET_TASKS:
        raise AgentExecutionError("Coordinator bounded evidence task capacity exceeded")
    return planned, coverage


def combine_rows(kind: str, rows: list[Any]) -> list[dict[str, Any]]:
    """Combine validated disjoint measurements without counting overlap twice."""
    if kind != "ordinary":
        merged: dict[str, list[str]] = {}
        for batch in rows:
            for row in batch:
                ids = merged.setdefault(row["objective_id"], [])
                for key in row["source_ids"]:
                    if key not in ids and len(ids) < 2:
                        ids.append(key)
        return [{"objective_id": key, "source_ids": ids} for key, ids in merged.items()]
    first = rows[0][0]
    if "evidence_id" in first:
        if len(rows) != 1:
            raise AgentExecutionError("Guidance retrieval requires one bounded packet")
        return [dict(first)]
    keys = (
        ("instance_ids",)
        if "instance_ids" in first
        else ("unit_ids", "qualifying_unit_ids")
    )
    combined = {
        key: list(dict.fromkeys(value for batch in rows for value in batch[0][key]))
        for key in keys
    }
    return [{"status": "supported" if combined[keys[0]] else "absent", **combined}]
