"""Validate persisted Coordinator packet history against its final bundle."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from equiped_harness.agents.coordinator.catalog import (
    CatalogItem,
)
from equiped_harness.agents.coordinator.catalog import (
    canonical_source as _source_catalog,
)
from equiped_harness.agents.coordinator.context_packets import (
    combine_rows,
    validate_retrieval,
)
from equiped_harness.agents.coordinator.reporting import (
    selected_source_ids,
    unavailable_explanation,
    validate_explanation,
)
from equiped_harness.exceptions import AgentExecutionError


def _fail(message: str) -> None:
    raise ValueError(message)


def _is_ids(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and len(value) == len(set(value))
    )


def _validate_result_row(
    row: Any, kind: str, exposed: set[str], catalog: dict[str, CatalogItem]
) -> None:
    if not isinstance(row, dict):
        _fail("packet result row is invalid")
    if kind == "guidance":
        if (
            set(row) != {"status", "score", "evidence_id"}
            or not isinstance(row.get("status"), str)
            or row["status"] not in {"supported", "absent"}
        ):
            _fail("packet guidance result is invalid")
        if type(row["score"]) is not int or not 1 <= row["score"] <= 4:
            _fail("packet guidance score is invalid")
        evidence_id = row["evidence_id"]
        if evidence_id is not None and (
            not isinstance(evidence_id, str)
            or evidence_id not in exposed
            or catalog[evidence_id].source != "slm"
        ):
            _fail("packet guidance source is outside its packet")
        if (row["status"] == "supported") != (evidence_id is not None):
            _fail("packet guidance status disagrees with its evidence")
    elif kind == "count":
        if (
            set(row) != {"status", "instance_ids"}
            or not isinstance(row.get("status"), str)
            or row["status"] not in {"supported", "absent"}
            or not _is_ids(row.get("instance_ids"))
        ):
            _fail("packet count result is invalid")
        if (
            row["status"] == "supported"
            and not row["instance_ids"]
            or row["status"] == "absent"
            and row["instance_ids"]
        ):
            _fail("packet count status disagrees with its evidence")
        if any(
            key not in exposed or catalog[key].source != "slm"
            for key in row["instance_ids"]
        ):
            _fail("packet count source is outside its packet")
    elif kind == "ratio":
        if (
            set(row) != {"status", "unit_ids", "qualifying_unit_ids"}
            or not isinstance(row.get("status"), str)
            or row["status"] not in {"supported", "absent"}
            or not _is_ids(row.get("unit_ids"))
            or not _is_ids(row.get("qualifying_unit_ids"))
        ):
            _fail("packet ratio result is invalid")
        if not set(row["qualifying_unit_ids"]).issubset(row["unit_ids"]):
            _fail("packet ratio qualifying units are invalid")
        if (
            row["status"] == "supported"
            and not row["unit_ids"]
            or row["status"] == "absent"
            and row["unit_ids"]
        ):
            _fail("packet ratio status disagrees with its evidence")
        if any(
            key not in exposed or catalog[key].source != "slm"
            for key in row["unit_ids"]
        ):
            _fail("packet ratio source is outside its packet")
    else:
        if (
            set(row) != {"objective_id", "source_ids"}
            or not isinstance(row["objective_id"], str)
            or not _is_ids(row["source_ids"])
            or len(row["source_ids"]) > 2
        ):
            _fail("packet objective result is invalid")
        if any(
            key not in exposed
            or catalog[key].source not in {"assessment", "curriculum"}
            for key in row["source_ids"]
        ):
            _fail("packet objective source is outside its packet")


def validate_packet_history(
    result: Any, catalog: dict[str, CatalogItem], bundle: dict[str, Any]
) -> None:
    """Validate source retrieval, packet responses, and their logical aggregates."""
    retrieval = bundle.get("source_retrieval")
    if retrieval is None:
        responses = (getattr(result, "metadata", {}) or {}).get("group_responses", {})
        if isinstance(responses, Mapping) and any(
            isinstance(key, str) and ".part-" in key for key in responses
        ):
            _fail("Coordinator packet execution is missing its retrieval coverage")
        return
    if not isinstance(retrieval, Mapping) or set(retrieval) != {
        "contract",
        "document_id",
        "source_hash",
        "embedding_model",
        "rankings",
        "coverage",
        "packets",
    }:
        _fail("Coordinator packet retrieval history is invalid")
    canonical = _source_catalog(catalog)
    facts = bundle.get("criteria")
    objective = bundle.get("objective")
    curriculum = bundle.get("curriculum")
    if (
        not isinstance(facts, dict)
        or not isinstance(objective, dict)
        or not isinstance(curriculum, dict)
    ):
        _fail("Coordinator packet bundle facts are invalid")
    try:
        validate_retrieval(
            {
                key: retrieval[key]
                for key in (
                    "contract",
                    "document_id",
                    "source_hash",
                    "embedding_model",
                    "rankings",
                )
            },
            document_id=result.document_id,
            canonical=canonical,
            criterion_codes=set(facts) | {"A-05"},
        )
    except (AgentExecutionError, KeyError, TypeError) as exc:
        raise ValueError("Coordinator packet retrieval identity is invalid") from exc

    coverage, packets = retrieval.get("coverage"), retrieval.get("packets")
    metadata = result.metadata if isinstance(result.metadata, dict) else {}
    responses, statuses = (
        metadata.get("group_responses"),
        metadata.get("envelope_status"),
    )
    if (
        not isinstance(coverage, Mapping)
        or not isinstance(packets, Mapping)
        or not isinstance(responses, Mapping)
        or not isinstance(statuses, Mapping)
    ):
        _fail("Coordinator packet history is incomplete")
    logical_ids = {f"ordinary-{cid}" for cid in facts}
    if objective.get("assessment_available") is True:
        logical_ids.add("objective-assessment")
    logical_ids.add("curriculum")
    if set(coverage) != logical_ids:
        _fail("Coordinator packet logical coverage is invalid")
    packet_ids = set(packets)
    if (
        not packet_ids
        or not packet_ids.issubset(responses)
        or not logical_ids.issubset(responses)
    ):
        _fail("Coordinator packet responses are missing")
    if not packet_ids.issubset(statuses) or not logical_ids.issubset(statuses):
        _fail("Coordinator packet statuses are missing")
    inventory_ids = set(responses) - packet_ids - logical_ids - {"__current_bundle__"}
    if set(statuses) != packet_ids | logical_ids | inventory_ids | {
        "__current_bundle__"
    }:
        _fail("Coordinator packet history task set is invalid")
    if any(not re.fullmatch(r"inventory-\d{3}-\d", key) for key in inventory_ids):
        _fail("Coordinator packet history contains an unknown task")
    if statuses.get("__current_bundle__") != "ok":
        _fail("Coordinator packet bundle status is invalid")
    generations = getattr(result, "generations", ())
    if generations:
        inventory_generations = {
            generation.unit_key: generation
            for generation in generations
            if re.fullmatch(r"inventory-\d{3}-\d", getattr(generation, "unit_key", ""))
        }
        captured = {
            generation.unit_key: generation.response_json
            for generation in generations
            if getattr(generation, "unit_key", None) in packet_ids
        }
        if set(captured) != packet_ids or any(
            captured[task_id] != responses[task_id]
            or next(
                generation.envelope_status
                for generation in generations
                if generation.unit_key == task_id
            )
            != statuses[task_id]
            for task_id in packet_ids
        ):
            _fail("Coordinator packet response differs from its captured generation")
        if {generation.unit_key for generation in generations} != (
            packet_ids | inventory_ids
        ):
            _fail("Coordinator captured generation task set is invalid")
        if set(inventory_generations) != inventory_ids or any(
            inventory_generations[key].response_json != responses[key]
            or inventory_generations[key].envelope_status != statuses[key]
            for key in inventory_ids
        ):
            _fail("Coordinator inventory response differs from its captured generation")
    for key in inventory_ids:
        response, status = responses[key], statuses[key]
        if (
            not isinstance(response, Mapping)
            or set(response) != {"results"}
            or not isinstance(response["results"], list)
            or not response["results"]
            or any(
                not isinstance(label, str)
                or label not in {"objective", "continuation", "assessment", "other"}
                for label in response["results"]
            )
            or not isinstance(status, str)
            or status not in {"ok", "repaired"}
        ):
            _fail("Coordinator inventory history is invalid")

    packets_by_logical: dict[str, list[str]] = {logical: [] for logical in logical_ids}
    for task_id, packet in packets.items():
        if (
            not isinstance(task_id, str)
            or not isinstance(packet, Mapping)
            or set(packet) != {"logical_id", "source_ids", "objective_ids"}
        ):
            _fail("Coordinator packet descriptor is invalid")
        logical = packet["logical_id"]
        if (
            logical not in logical_ids
            or not _is_ids(packet["source_ids"])
            or not _is_ids(packet["objective_ids"])
        ):
            _fail("Coordinator packet descriptor is invalid")
        if any(key not in catalog for key in packet["source_ids"]):
            _fail("Coordinator packet contains an unknown source")
        packets_by_logical[logical].append(task_id)

    facts_by_logical: dict[str, tuple[str, dict[str, Any]]] = {
        f"ordinary-{cid}": (fact["kind"], fact)
        for cid, fact in facts.items()
        if isinstance(fact, dict)
    }
    facts_by_logical["objective-assessment"] = ("objective", objective)
    facts_by_logical["curriculum"] = ("curriculum", curriculum)
    for logical in logical_ids:
        plan = coverage[logical]
        kind, fact = facts_by_logical[logical]
        namespace = {
            "guidance": "slm",
            "count": "slm",
            "ratio": "slm",
            "objective": "assessment",
            "curriculum": "curriculum",
        }[kind]
        if not isinstance(plan, Mapping) or set(plan) != {
            "mode",
            "source_ids",
            "objective_ids",
            "task_ids",
        }:
            _fail("Coordinator packet coverage descriptor is invalid")
        if (
            plan.get("mode") not in {"complete", "retrieved"}
            or not _is_ids(plan.get("source_ids"))
            or not _is_ids(plan.get("objective_ids"))
            or not _is_ids(plan.get("task_ids"))
        ):
            _fail("Coordinator packet coverage descriptor is invalid")
        if plan["mode"] != ("retrieved" if kind == "guidance" else "complete"):
            _fail("Coordinator count and coverage tasks require a complete source pass")
        expected_sources = {
            key for key, item in catalog.items() if item.source == namespace
        }
        if set(plan["source_ids"]) != expected_sources:
            _fail("Coordinator packet namespace coverage is invalid")
        expected_objectives = (
            set()
            if kind in {"guidance", "count", "ratio"}
            else {
                row["objective_id"]
                for row in objective.get("rows", [])
                if isinstance(row, dict)
            }
        )
        if set(plan["objective_ids"]) != expected_objectives or set(
            plan["task_ids"]
        ) != set(packets_by_logical[logical]):
            _fail("Coordinator packet objective coverage is invalid")
        actual_tasks = packets_by_logical[logical]
        if not actual_tasks:
            _fail("Coordinator packet task is missing")
        visited_pairs: Counter[tuple[str | None, str]] = Counter()
        source_visits: list[str] = []
        batches: list[list[dict[str, Any]]] = []
        fallback = False
        for task_id in actual_tasks:
            packet = packets[task_id]
            source_ids, objective_ids = packet["source_ids"], packet["objective_ids"]
            if any(catalog[key].source != namespace for key in source_ids):
                _fail("Coordinator packet source namespace is invalid")
            if not set(source_ids).issubset(expected_sources) or not set(
                objective_ids
            ).issubset(expected_objectives):
                _fail("Coordinator packet scope is invalid")
            for source_id in source_ids or [None]:
                for objective_id in objective_ids:
                    visited_pairs[(source_id, objective_id)] += 1
            source_visits.extend(source_ids)
            response = responses[task_id]
            if (
                not isinstance(response, Mapping)
                or set(response) != {"results", "explanation"}
                or not isinstance(response["results"], list)
            ):
                _fail("Coordinator packet response is invalid")
            rows = response["results"]
            if kind in {"guidance", "count", "ratio"} and len(rows) != 1:
                _fail("Coordinator packet result count is invalid")
            if kind in {"objective", "curriculum"}:
                if (
                    len(rows) != len(objective_ids)
                    or [
                        row.get("objective_id") for row in rows if isinstance(row, dict)
                    ]
                    != objective_ids
                ):
                    _fail("Coordinator packet objective rows are incomplete")
            for row in rows:
                _validate_result_row(row, kind, set(source_ids), catalog)
            if kind in {"objective", "curriculum"} and {
                row["objective_id"] for row in rows
            } != set(objective_ids):
                _fail("Coordinator packet objective rows are incomplete")
            status = statuses[task_id]
            if not isinstance(status, str) or status not in {
                "ok",
                "repaired",
                "fallback",
            }:
                _fail("Coordinator packet status is invalid")
            fallback = fallback or status == "fallback"
            selected = set()
            if kind in {"guidance", "count", "ratio"}:
                row = rows[0]
                selected = (
                    {row["evidence_id"]}
                    if kind == "guidance" and row["evidence_id"]
                    else set(row.get("instance_ids", row.get("unit_ids", [])))
                )
            else:
                selected = {key for row in rows for key in row["source_ids"]}
            explanation = response["explanation"]
            if status == "fallback":
                if explanation != unavailable_explanation():
                    _fail("Coordinator packet fallback explanation is invalid")
            else:
                try:
                    normalized = validate_explanation(explanation, catalog, selected)
                    if normalized != explanation:
                        _fail(
                            "stored packet quotations must retain "
                            "the original source text"
                        )
                except (ValueError, TypeError, KeyError) as exc:
                    raise ValueError(
                        "Coordinator packet explanation is invalid"
                    ) from exc
            batches.append(rows)
        if kind in {"guidance", "count", "ratio"}:
            if plan["mode"] == "complete" and Counter(source_visits) != Counter(
                plan["source_ids"]
            ):
                _fail("Coordinator packet source pass is incomplete")
            if plan["mode"] == "retrieved" and (
                len(actual_tasks) != 1
                or not set(source_visits).issubset(expected_sources)
            ):
                _fail("Coordinator retrieved packet coverage is invalid")
        else:
            expected_pairs = Counter(
                (source_id, objective_id)
                for source_id in plan["source_ids"] or [None]
                for objective_id in plan["objective_ids"]
            )
            if visited_pairs != expected_pairs:
                _fail("Coordinator packet source and objective passes are incomplete")
        try:
            merged = combine_rows(
                "ordinary" if kind in {"guidance", "count", "ratio"} else kind, batches
            )
        except (AgentExecutionError, KeyError, IndexError, TypeError) as exc:
            raise ValueError("Coordinator packet aggregation is invalid") from exc
        aggregate = responses.get(logical)
        if (
            not isinstance(aggregate, Mapping)
            or set(aggregate) != {"results", "explanation"}
            or aggregate["results"] != merged
        ):
            _fail("Coordinator packet aggregate does not match its batches")
        aggregate_status = statuses[logical]
        if (
            not isinstance(aggregate_status, str)
            or aggregate_status not in {"ok", "fallback"}
            or (fallback and aggregate_status != "fallback")
        ):
            _fail("Coordinator packet aggregate status is invalid")
        if aggregate_status == "fallback":
            cid = (
                logical.removeprefix("ordinary-")
                if logical.startswith("ordinary-")
                else "A-05"
                if logical == "objective-assessment"
                else "C-01"
            )
            if cid not in bundle.get("reasoning_unavailable", []):
                _fail("Coordinator packet fallback was dropped")
        elif (
            logical.removeprefix("ordinary-") in bundle.get("reasoning_unavailable", [])
            or (
                logical == "objective-assessment"
                and "A-05" in bundle.get("reasoning_unavailable", [])
            )
            or (
                logical == "curriculum"
                and "C-01" in bundle.get("reasoning_unavailable", [])
            )
        ):
            _fail("Coordinator unavailable reasoning marker was dropped")
        if kind in {"guidance", "count", "ratio"}:
            final = fact
            expected_row = {
                "guidance": {
                    "status": final.get("status"),
                    "score": final.get("score"),
                    "evidence_id": final.get("evidence_id"),
                },
                "count": {
                    "status": final.get("status"),
                    "instance_ids": final.get("instance_ids"),
                },
                "ratio": {
                    "status": final.get("status"),
                    "unit_ids": final.get("unit_ids"),
                    "qualifying_unit_ids": final.get("qualifying_unit_ids"),
                },
            }[kind]
            if merged != [expected_row]:
                _fail("Coordinator packet aggregate disagrees with final facts")
        else:
            if merged != fact.get("rows"):
                _fail(
                    "Coordinator packet aggregate disagrees with final objective facts"
                )
        explanation_id = (
            logical.removeprefix("ordinary-")
            if logical.startswith("ordinary-")
            else "A-05"
            if logical == "objective-assessment"
            else "C-01"
        )
        explanations = bundle.get("explanations")
        if not isinstance(explanations, Mapping) or aggregate[
            "explanation"
        ] != explanations.get(explanation_id):
            _fail("Coordinator packet aggregate explanation differs from bundle")
        if aggregate_status == "fallback":
            if aggregate["explanation"] != unavailable_explanation():
                _fail("Coordinator packet aggregate fallback is invalid")
        else:
            selected = selected_source_ids(fact, kind=kind)
            try:
                validate_explanation(aggregate["explanation"], catalog, selected)
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(
                    "Coordinator packet aggregate explanation is invalid"
                ) from exc
