"""Independent integrity checks for the current Coordinator unit contract."""

from __future__ import annotations

import re
from typing import Any

from equiped_harness.agents.coordinator.catalog import CatalogItem, read_catalog
from equiped_harness.agents.coordinator.context_packets import (
    build_packet_tasks,
    validate_retrieval,
)
from equiped_harness.agents.coordinator.reporting import unavailable_explanation
from equiped_harness.agents.coordinator.unit_measurements import (
    combine_unit_rows,
    score_unit_row,
    validate_unit_row,
)
from equiped_harness.agents.coordinator.unit_objectives import (
    combine_objective_rows,
    validate_objective_rows,
)
from equiped_harness.agents.coordinator.unit_prompts import task_prompt
from equiped_harness.agents.coordinator.unit_reporting import (
    build_objective_explanation,
    build_unit_explanation,
    build_unit_summary,
    render_unit_justification,
    validate_unit_explanation,
)
from equiped_harness.agents.coordinator.unit_verification import (
    UNIT_REVIEW_BATCH_SIZE,
    apply_objective_reviews,
)
from equiped_harness.contracts import CriterionDefinition, LlmRubricGuidanceConfig
from equiped_harness.contracts.results import AgentEvaluationResult, CriterionScore
from equiped_harness.runtime.bands import ratio_band

_BUNDLE_KEYS = {
    "contract",
    "catalog",
    "criteria",
    "objective",
    "curriculum",
    "criterion_definitions",
    "explanations",
    "reasoning_status",
    "source_retrieval",
    "packet_outcomes",
}


def _fail(message: str) -> None:
    raise ValueError(message)


def _validate_packet_outcomes(
    bundle: dict[str, Any], catalog: dict[str, CatalogItem]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    outcomes = bundle["packet_outcomes"]
    retrieval = bundle["source_retrieval"]
    packets = retrieval.get("packets") if isinstance(retrieval, dict) else None
    if (
        not isinstance(outcomes, list)
        or not isinstance(packets, dict)
        or len(outcomes) != len(packets)
    ):
        _fail("Coordinator packet outcomes are incomplete")
    seen: set[str] = set()
    ordinary: dict[str, list[dict[str, Any]]] = {}
    objective_parts: dict[str, list[dict[str, Any]]] = {
        "assessment": [],
        "curriculum": [],
    }
    for outcome in outcomes:
        expected = {
            "task_id",
            "logical_id",
            "kind",
            "source_ids",
            "objective_ids",
            "parsed",
            "reasoning_unavailable",
            "review_decisions",
            "accepted_items",
        }
        if not isinstance(outcome, dict) or set(outcome) != expected:
            _fail("Coordinator packet outcome fields are invalid")
        task_id = outcome["task_id"]
        packet = packets.get(task_id)
        if (
            not isinstance(task_id, str)
            or task_id in seen
            or not isinstance(packet, dict)
        ):
            _fail("Coordinator packet outcome identity is invalid")
        seen.add(task_id)
        if any(
            outcome[k] != packet.get(k)
            for k in ("logical_id", "source_ids", "objective_ids")
        ):
            _fail("Coordinator packet outcome scope differs from its plan")
        kind = outcome["kind"]
        logical_id = outcome["logical_id"]
        parsed = outcome["parsed"]
        if (
            kind not in {"ordinary", "objective", "curriculum"}
            or not isinstance(parsed, dict)
            or set(parsed) != {"results", "explanation"}
        ):
            _fail("Coordinator packet parsed response is invalid")
        source_ids = outcome["source_ids"]
        if (
            not isinstance(source_ids, list)
            or len(set(source_ids)) != len(source_ids)
            or any(sid not in catalog for sid in source_ids)
        ):
            _fail("Coordinator packet source scope is invalid")
        if not isinstance(parsed["results"], list):
            _fail("Coordinator packet results are invalid")
        source_scope = set(source_ids)
        for row in parsed["results"]:
            if not isinstance(row, dict):
                _fail("Coordinator packet result row is invalid")
            if kind == "ordinary":
                if isinstance(row.get("items"), list):
                    selected = [
                        item.get("source_id")
                        for item in row["items"]
                        if isinstance(item, dict)
                    ]
                else:
                    selected = [row["evidence_id"]] if row.get("evidence_id") else []
            else:
                selected = list(row.get("source_ids", []))
                if isinstance(row.get("matches"), list):
                    selected.extend(
                        match.get("source_id")
                        for match in row["matches"]
                        if isinstance(match, dict)
                    )
            if any(
                not isinstance(sid, str) or sid not in source_scope for sid in selected
            ):
                _fail("Coordinator packet result selects a source outside its packet")
        if type(outcome["reasoning_unavailable"]) is not bool:
            _fail("Coordinator packet reasoning status is invalid")
        explanation = parsed["explanation"]
        if not outcome["reasoning_unavailable"]:
            if not isinstance(parsed["results"], list):
                _fail("Coordinator packet results are invalid")
            if (
                kind == "ordinary"
                and isinstance(parsed["results"], list)
                and len(parsed["results"]) == 1
            ):
                row = parsed["results"][0]
                if isinstance(row, dict) and isinstance(row.get("items"), list):
                    allowed = {
                        i.get("source_id") for i in row["items"] if isinstance(i, dict)
                    }
                else:
                    evidence_id = (
                        row.get("evidence_id") if isinstance(row, dict) else None
                    )
                    allowed = {evidence_id} if isinstance(evidence_id, str) else set()
            else:
                allowed = {
                    source_id
                    for row in parsed["results"]
                    if isinstance(row, dict)
                    for source_id in row.get("source_ids", [])
                    if isinstance(source_id, str)
                }
            validate_unit_explanation(explanation, catalog, allowed)
        elif explanation != unavailable_explanation():
            _fail("Unavailable packet explanation was tampered")
        decisions = outcome["review_decisions"]
        accepted = outcome["accepted_items"]
        if not isinstance(decisions, list) or not isinstance(accepted, list):
            _fail("Coordinator review history is invalid")
        for decision in decisions:
            expected_keys = (
                {"item_id", "source_id", "decision", "reason"}
                if kind == "ordinary"
                else {"objective_id", "decision", "reason"}
            )
            if not isinstance(decision, dict) or set(decision) != expected_keys:
                _fail("Coordinator review decision fields are invalid")
            if (
                decision["decision"]
                not in {"qualifies", "does_not_qualify", "not_a_unit"}
                or not isinstance(decision["reason"], str)
                or decision["reason"] != decision["reason"].strip()
                or not decision["reason"]
                or len(decision["reason"]) > 500
            ):
                _fail("Coordinator review decision is invalid")
        if kind == "ordinary":
            if len(parsed["results"]) != 1:
                _fail("Coordinator ordinary packet must contain one result")
            ordinary.setdefault(logical_id, []).append(parsed["results"][0])
        else:
            namespace = "assessment" if kind == "objective" else "curriculum"
            packet_objectives = tuple(
                {
                    "objective_id": key,
                    "text": catalog[key.replace("OBJ-", "objective-")].text,
                }
                for key in outcome["objective_ids"]
            )
            canonical_rows = validate_objective_rows(
                parsed["results"],
                packet_objectives,
                {key: catalog[key] for key in source_ids},
                namespace,
            )
            if canonical_rows != parsed["results"]:
                _fail("Stored objective quotes must retain original source text")
            objective_parts[namespace].append(
                apply_objective_reviews(parsed["results"], decisions)
            )
    if seen != set(packets):
        _fail("Coordinator packet outcomes do not cover the packet plan")
    return ordinary, objective_parts


def validate_unit_coordinator_bundle(
    result: AgentEvaluationResult,
    snapshot: Any | None = None,
    *,
    prompt_factory: Any = task_prompt,
) -> None:
    """Rebuild unit measurements, scores, and explanations from source facts."""
    if result.agent_name != "coordinator" or not isinstance(result.metadata, dict):
        _fail("current Coordinator contract requires coordinator result")
    if result.metadata.get("execution_contract") != "coordinator_current.v3":
        _fail("current Coordinator v3 execution marker is missing")
    bundle = result.metadata.get("current_bundle")
    if (
        not isinstance(bundle, dict)
        or set(bundle) != _BUNDLE_KEYS
        or bundle.get("contract") != "coordinator_current.v3"
    ):
        _fail("current Coordinator v3 bundle is invalid")
    persisted_bundle = bundle
    responses = result.metadata.get("group_responses")
    if (
        not isinstance(responses, dict)
        or responses.get("__current_bundle__") != persisted_bundle
    ):
        _fail("Coordinator persisted bundle response is invalid")
    hydrated_outcomes = []
    for stored in bundle["packet_outcomes"]:
        if (
            not isinstance(stored, dict)
            or "parsed" in stored
            or "accepted_items" in stored
            or set(stored)
            != {
                "task_id",
                "logical_id",
                "kind",
                "source_ids",
                "objective_ids",
                "reasoning_unavailable",
                "review_decisions",
            }
        ):
            _fail("Coordinator persisted packet outcome fields are invalid")
        parsed = responses.get(stored.get("task_id"))
        if not isinstance(parsed, dict):
            _fail("Coordinator persisted packet response is missing")
        hydrated_outcomes.append({**stored, "parsed": parsed})
    catalog = read_catalog(bundle["catalog"])

    try:
        definitions = tuple(
            CriterionDefinition.model_validate(x)
            for x in bundle["criterion_definitions"]
        )
    except Exception as exc:
        raise ValueError(
            "current Coordinator criterion definitions are invalid"
        ) from exc
    if len({c.criterion_code for c in definitions}) != len(definitions):
        _fail("current Coordinator criterion definitions are duplicated")
    if snapshot is not None:
        frozen = tuple(c for d in snapshot.form.domains for c in d.criteria)
        if tuple(c.model_dump(mode="json") for c in definitions) != tuple(
            c.model_dump(mode="json") for c in frozen
        ):
            _fail("current Coordinator criterion definitions differ from snapshot")
    by_code = {c.criterion_code: c for c in definitions}
    for outcome in hydrated_outcomes:
        accepted = []
        if outcome["kind"] == "ordinary":
            code = outcome["logical_id"].removeprefix("ordinary-")
            criterion = by_code.get(code)
            if criterion is not None and not isinstance(
                criterion.strategy_config, LlmRubricGuidanceConfig
            ):
                packet_catalog = {sid: catalog[sid] for sid in outcome["source_ids"]}
                if len(outcome["parsed"]["results"]) != 1:
                    _fail("Coordinator ordinary packet must contain one result")
                canonical_row = validate_unit_row(
                    criterion, outcome["parsed"]["results"][0], packet_catalog
                )
                if canonical_row != outcome["parsed"]["results"][0]:
                    _fail("Stored unit proposals must retain original source text")
                proposals = canonical_row["items"]
                decisions = outcome["review_decisions"]
                if not isinstance(decisions, list) or len(decisions) != len(proposals):
                    _fail("Coordinator review decisions do not cover packet proposals")
                for item, decision in zip(proposals, decisions, strict=True):
                    if (
                        not isinstance(decision, dict)
                        or decision.get("item_id") != item["item_id"]
                        or decision.get("source_id") != item["source_id"]
                        or decision.get("decision")
                        not in {"qualifies", "does_not_qualify", "not_a_unit"}
                        or not isinstance(decision.get("reason"), str)
                    ):
                        _fail(
                            "Coordinator review decision does not bind to its proposal"
                        )
                    if decision["decision"] != "not_a_unit":
                        accepted.append(
                            {
                                **item,
                                "qualifies": decision["decision"] == "qualifies",
                                "reason": decision["reason"],
                            }
                        )
            elif outcome["review_decisions"]:
                _fail("Coordinator packet cannot contain unit review history")
        outcome["accepted_items"] = accepted
    bundle = {**bundle, "packet_outcomes": hydrated_outcomes}
    facts = bundle["criteria"]
    if not isinstance(facts, dict) or set(facts) != set(by_code) - {"A-05"}:
        _fail("current Coordinator criterion facts mismatch")

    objectives = tuple(
        {
            "objective_id": item.source_id.replace("objective-", "OBJ-"),
            "text": item.text,
        }
        for item in catalog.values()
        if item.source == "objective"
    )
    objective = bundle["objective"]
    curriculum = bundle["curriculum"]
    retrieval = bundle["source_retrieval"]
    if (
        not isinstance(objective, dict)
        or not isinstance(curriculum, dict)
        or not isinstance(retrieval, dict)
    ):
        _fail("current Coordinator objective or retrieval facts are invalid")
    if type(objective.get("assessment_available")) is not bool:
        _fail("current Coordinator assessment availability is invalid")
    if set(retrieval) != {
        "contract",
        "document_id",
        "source_hash",
        "embedding_model",
        "rankings",
        "coverage",
        "packets",
        "prompt_budget",
    }:
        _fail("current Coordinator packet retrieval fields are invalid")
    try:
        from equiped_harness.agents.coordinator.packet_validation import _source_catalog

        canonical = _source_catalog(catalog)
        validate_retrieval(
            {
                k: retrieval[k]
                for k in (
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
        specs = [
            (f"ordinary-{c.criterion_code}", "ordinary", (c,))
            for c in definitions
            if c.criterion_code != "A-05"
        ]
        if objective["assessment_available"]:
            specs.append(("objective-assessment", "objective", ()))
        specs.append(("curriculum", "curriculum", ()))
        prompt_budget = retrieval.get("prompt_budget")
        if type(prompt_budget) is not int or not 1 <= prompt_budget <= 16_000:
            _fail("current Coordinator packet prompt budget is invalid")
        planned, expected_coverage = build_packet_tasks(
            specs,
            catalog,
            objectives,
            retrieval,
            prompt_budget=prompt_budget,
            prompt_factory=prompt_factory,
            max_objectives=2,
            max_source_chars=4_000,
        )
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(
            "current Coordinator packet plan cannot be reconstructed"
        ) from exc
    expected_packets = {
        p.task.task_id: {
            "logical_id": p.logical_id,
            "source_ids": list(p.source_ids),
            "objective_ids": list(p.objective_ids),
        }
        for p in planned
    }
    if (
        retrieval.get("coverage") != expected_coverage
        or retrieval.get("packets") != expected_packets
    ):
        _fail("current Coordinator packet plan differs from reconstructed plan")

    ordinary_parts, objective_parts = _validate_packet_outcomes(bundle, catalog)
    expected_generation_ids = set(expected_packets)
    for outcome in bundle["packet_outcomes"]:
        if outcome["kind"] != "ordinary" and outcome["review_decisions"]:
            expected_generation_ids.add(f"verify-{outcome['task_id']}-001")
        if (
            outcome["kind"] == "ordinary"
            and outcome["logical_id"].removeprefix("ordinary-") in by_code
            and not isinstance(
                by_code[
                    outcome["logical_id"].removeprefix("ordinary-")
                ].strategy_config,
                LlmRubricGuidanceConfig,
            )
        ):
            count = len(outcome["review_decisions"])
            expected_generation_ids.update(
                f"verify-{outcome['task_id']}-{index:03d}"
                for index in range(
                    1,
                    (count + UNIT_REVIEW_BATCH_SIZE - 1) // UNIT_REVIEW_BATCH_SIZE + 1,
                )
            )
    generations = getattr(result, "generations", ())
    captured_by_id = {g.unit_key: g for g in generations}
    envelope_status = result.metadata.get("envelope_status")
    if not isinstance(responses, dict) or not isinstance(envelope_status, dict):
        _fail("Coordinator packet response history is invalid")
    inventory_ids = {
        key
        for key in responses
        if isinstance(key, str) and re.fullmatch(r"inventory-\d{3}-[1-9]", key)
    }
    if generations and (
        len(captured_by_id) != len(generations)
        or set(captured_by_id) != expected_generation_ids | inventory_ids
    ):
        _fail("Coordinator captured generation task set is invalid")
    if not (expected_generation_ids | inventory_ids).issubset(responses) or not (
        expected_generation_ids | inventory_ids
    ).issubset(envelope_status):
        _fail("Coordinator packet response task set is incomplete")
    if envelope_status.get("__current_bundle__") != "ok":
        _fail("Coordinator persisted bundle response is invalid")
    for outcome in bundle["packet_outcomes"]:
        generation = captured_by_id.get(outcome["task_id"])
        response = responses.get(outcome["task_id"])
        status = envelope_status.get(outcome["task_id"])
        if (
            response != outcome["parsed"]
            or status not in {"ok", "repaired", "fallback"}
            or outcome["reasoning_unavailable"] != (status == "fallback")
            or (
                generation is not None
                and (
                    generation.response_json != response
                    or generation.envelope_status != status
                )
            )
        ):
            _fail("Coordinator packet response differs from its captured generation")
        if (
            outcome["kind"] == "ordinary"
            and outcome["logical_id"].removeprefix("ordinary-") in by_code
            and not isinstance(
                by_code[
                    outcome["logical_id"].removeprefix("ordinary-")
                ].strategy_config,
                LlmRubricGuidanceConfig,
            )
        ):
            proposals = outcome["parsed"]["results"][0]["items"]
            decisions = outcome["review_decisions"]
            if not isinstance(proposals, list) or len(proposals) != len(decisions):
                _fail("Coordinator review decisions do not cover packet proposals")
            for offset in range(0, len(decisions), UNIT_REVIEW_BATCH_SIZE):
                batch_index = offset // UNIT_REVIEW_BATCH_SIZE + 1
                generation_id = f"verify-{outcome['task_id']}-{batch_index:03d}"
                generation = captured_by_id.get(generation_id)
                verifier_response = responses.get(generation_id)
                verifier_status = envelope_status.get(generation_id)
                rows = (
                    verifier_response.get("results")
                    if isinstance(verifier_response, dict)
                    else None
                )
                expected_decisions = decisions[offset : offset + UNIT_REVIEW_BATCH_SIZE]
                if (
                    not isinstance(rows, list)
                    or len(rows) != len(expected_decisions)
                    or any(
                        not isinstance(row, dict)
                        or set(row) != {"decision", "reason"}
                        or row.get("decision") != decision["decision"]
                        or row.get("reason", "").strip() != decision["reason"]
                        or decision["item_id"] != proposals[offset + index]["item_id"]
                        or decision["source_id"]
                        != proposals[offset + index]["source_id"]
                        for index, (row, decision) in enumerate(
                            zip(rows, expected_decisions, strict=True)
                        )
                    )
                ):
                    _fail(
                        "Coordinator verification response differs from review "
                        "decisions"
                    )
                if verifier_status not in {"ok", "repaired"} or (
                    generation is not None
                    and (
                        generation.response_json != verifier_response
                        or generation.envelope_status != verifier_status
                    )
                ):
                    _fail(
                        "Coordinator verification response differs from its "
                        "captured generation"
                    )
    for outcome in bundle["packet_outcomes"]:
        if outcome["kind"] == "ordinary" or not outcome["review_decisions"]:
            continue
        generation_id = f"verify-{outcome['task_id']}-001"
        response = responses.get(generation_id)
        expected_rows = [
            {"decision": d["decision"], "reason": d["reason"]}
            for d in outcome["review_decisions"]
        ]
        if not isinstance(response, dict) or response != {"results": expected_rows}:
            _fail("Coordinator objective review differs from captured decisions")
    for generation_id in expected_generation_ids - set(expected_packets):
        generation = captured_by_id.get(generation_id)
        if (
            not re.fullmatch(r"verify-.+\.part-\d{3}-\d{3}", generation_id)
            or envelope_status.get(generation_id) not in {"ok", "repaired"}
            or (
                generation is not None
                and (
                    responses.get(generation_id) != generation.response_json
                    or envelope_status.get(generation_id) != generation.envelope_status
                )
            )
        ):
            _fail(
                "Coordinator verification response differs from its captured generation"
            )
    for generation_id in inventory_ids:
        generation = captured_by_id.get(generation_id)
        if envelope_status.get(generation_id) not in {"ok", "repaired", "fallback"} or (
            generation is not None
            and (
                responses.get(generation_id) != generation.response_json
                or envelope_status.get(generation_id) != generation.envelope_status
            )
        ):
            _fail("Coordinator inventory response differs from its captured generation")
    by_score = {s.criterion_id: s for s in result.criterion_scores}
    if set(by_score) != set(by_code):
        _fail("current Coordinator score inventory mismatch")
    explanations = bundle["explanations"]
    statuses = bundle["reasoning_status"]
    if (
        not isinstance(explanations, dict)
        or set(explanations) != set(by_code) | {"C-01"}
        or not isinstance(statuses, dict)
        or set(statuses) != set(explanations)
    ):
        _fail("current Coordinator explanations or reasoning status are invalid")
    logical_refs = {f"ordinary-{c}": c for c in by_code if c != "A-05"}
    logical_refs["curriculum"] = "C-01"
    if objective["assessment_available"]:
        logical_refs["objective-assessment"] = "A-05"
    for key, code in logical_refs.items():
        expected_status = "ok" if statuses[code] == "complete" else "fallback"
        if (
            responses.get(key) != {"bundle_criterion": code}
            or envelope_status.get(key) != expected_status
        ):
            _fail("Coordinator logical response reference was tampered")

    rebuilt_facts: dict[str, dict[str, Any]] = {}
    rebuilt_scores = {}
    rebuilt_rows: dict[str, dict[str, Any]] = {}
    for code, criterion in by_code.items():
        if code == "A-05":
            continue
        logical = f"ordinary-{code}"
        parts = ordinary_parts.get(logical)
        if not parts:
            _fail("current Coordinator criterion packet results are missing")
        if isinstance(criterion.strategy_config, LlmRubricGuidanceConfig):
            row = parts[0]
            score, fact = score_unit_row(criterion, parts[0], catalog)
        else:
            packet_rows = []
            for outcome in bundle["packet_outcomes"]:
                if outcome["kind"] == "ordinary" and outcome["logical_id"] == logical:
                    packet_rows.append(
                        {
                            "status": "supported"
                            if outcome["accepted_items"]
                            else "absent",
                            "items": outcome["accepted_items"],
                        }
                    )
            row = combine_unit_rows(criterion, packet_rows, catalog)
            score, fact = score_unit_row(criterion, row, catalog)
        rebuilt_scores[code] = score
        rebuilt_facts[code] = fact
        rebuilt_rows[code] = row
    for code, fact in rebuilt_facts.items():
        stored = facts.get(code)
        if stored != fact:
            _fail("current Coordinator unit measurement facts were tampered")

    # Verify review decisions and accepted canonical items against each packet proposal.
    # Packet-local proposals are retained in `parsed.results`; review decisions bind by
    # the deterministic canonical item identity generated from the source span.
    for outcome in bundle["packet_outcomes"]:
        if (
            outcome["kind"] != "ordinary"
            or outcome["logical_id"].split("ordinary-")[-1] not in by_code
        ):
            continue
        code = outcome["logical_id"].removeprefix("ordinary-")
        criterion = by_code[code]
        if isinstance(criterion.strategy_config, LlmRubricGuidanceConfig):
            if outcome["review_decisions"] or outcome["accepted_items"]:
                _fail("Guidance packet cannot contain unit review history")
            continue
        packet_catalog = {sid: catalog[sid] for sid in outcome["source_ids"]}
        row = validate_unit_row(
            criterion, outcome["parsed"]["results"][0], packet_catalog
        )
        proposals = row["items"]
        decisions = outcome["review_decisions"]
        if len(decisions) != len(proposals):
            _fail("Coordinator review decisions do not cover packet proposals")
        accepted = []
        for item, decision in zip(proposals, decisions, strict=True):
            if (
                decision["item_id"] != item["item_id"]
                or decision["source_id"] != item["source_id"]
            ):
                _fail("Coordinator review decision does not bind to its proposal")
            reviewed = {
                **item,
                "qualifies": decision["decision"] == "qualifies",
                "reason": decision["reason"],
            }
            if decision["decision"] != "not_a_unit":
                accepted.append(reviewed)
        if outcome["accepted_items"] != accepted:
            _fail("Coordinator accepted items differ from review decisions")

    # Objective rows and scores are rebuilt from complete objective inventories.
    objectives = tuple(
        {
            "objective_id": item.source_id.replace("objective-", "OBJ-"),
            "text": item.text,
        }
        for item in catalog.values()
        if item.source == "objective"
    )
    objective = bundle["objective"]
    curriculum = bundle["curriculum"]
    if not isinstance(objective, dict) or not isinstance(curriculum, dict):
        _fail("current Coordinator objective facts are invalid")
    for namespace, destination in (
        ("assessment", objective),
        ("curriculum", curriculum),
    ):
        parts = objective_parts[namespace]
        if not parts:
            if namespace == "assessment" and objective["assessment_available"] is False:
                continue
            _fail("current Coordinator objective packet results are missing")
        merged = combine_objective_rows(parts, objectives, catalog, namespace)
        if destination.get("rows") != merged:
            _fail("current Coordinator objective facts were tampered")

    # Rebuild explanations, official scores, rendered evidence and summary from
    # the packet facts so persisted prose cannot override deterministic results.
    if any(
        value not in {"complete", "partial", "unavailable"}
        for value in statuses.values()
    ):
        _fail("current Coordinator reasoning status is invalid")
    for logical_id, criterion in (
        (f"ordinary-{c.criterion_code}", c)
        for c in definitions
        if c.criterion_code != "A-05"
    ):
        parts = [o for o in bundle["packet_outcomes"] if o["logical_id"] == logical_id]
        code = criterion.criterion_code
        if isinstance(criterion.strategy_config, LlmRubricGuidanceConfig):
            expected_explanation = next(
                (
                    p["parsed"]["explanation"]
                    for p in parts
                    if not p["reasoning_unavailable"]
                ),
                unavailable_explanation(),
            )
            expected_status = (
                "complete"
                if any(not p["reasoning_unavailable"] for p in parts)
                else "unavailable"
            )
        else:
            decisions = [d for p in parts for d in p["review_decisions"]]
            by_item = {d["item_id"]: d for d in decisions}
            proposed = [
                {
                    **item,
                    "qualifies": by_item[item["item_id"]]["decision"] == "qualifies",
                    "reason": by_item[item["item_id"]]["reason"],
                }
                for p in parts
                for item in p["parsed"]["results"][0]["items"]
            ]
            expected_explanation, expected_status = build_unit_explanation(
                criterion_title=criterion.title,
                fact=rebuilt_facts[code],
                packet_explanations=[
                    p["parsed"]["explanation"]
                    for p in parts
                    if not p["reasoning_unavailable"]
                ],
                unavailable_packets=sum(p["reasoning_unavailable"] for p in parts),
                review_decisions=decisions,
                proposed_items=proposed,
            )
        if (
            explanations[code] != expected_explanation
            or statuses[code] != expected_status
        ):
            _fail("current Coordinator unit explanation was tampered")

    for key, namespace, kind in (
        ("A-05", "assessment", "objective"),
        ("C-01", "curriculum", "curriculum"),
    ):
        destination = objective if key == "A-05" else curriculum
        if namespace == "assessment" and not objective["assessment_available"]:
            expected_rows = [
                {
                    "objective_id": o["objective_id"],
                    "matches": [],
                    "source_ids": [],
                    "reason": (
                        "No assessment section was identified in the extracted module."
                    ),
                }
                for o in objectives
            ]
            if destination.get("rows") != expected_rows:
                _fail("unavailable assessment objective rows were tampered")
            parts = []
        else:
            parts = [p for p in bundle["packet_outcomes"] if p["kind"] == kind]
        expected_explanation, expected_status = build_objective_explanation(
            objectives=objectives,
            rows=destination["rows"],
            packet_explanations=[
                p["parsed"]["explanation"]
                for p in parts
                if not p["reasoning_unavailable"]
            ],
            unavailable_packets=sum(p["reasoning_unavailable"] for p in parts),
            catalog=catalog,
            kind=kind,
        )
        if (
            explanations[key] != expected_explanation
            or statuses[key] != expected_status
        ):
            _fail("current Coordinator objective explanation was tampered")

    expected_scores: dict[str, CriterionScore] = dict(rebuilt_scores)
    assessment_matched = sum(bool(row.get("matches")) for row in objective["rows"])
    a05_score = ratio_band(
        assessment_matched, len(objective["rows"]), scale="moderate"
    ).band
    expected_scores["A-05"] = CriterionScore(
        "A-05", by_code["A-05"].title, a05_score, "", evidence=()
    )
    curriculum_matched = sum(bool(row.get("matches")) for row in curriculum["rows"])
    cscore = ratio_band(
        curriculum_matched, len(curriculum["rows"]), scale="moderate"
    ).band
    if curriculum.get("score") != cscore:
        _fail("current Coordinator curriculum advisory score was tampered")
    expected_order = [c.criterion_code for c in definitions]
    if [s.criterion_id for s in result.criterion_scores] != expected_order:
        _fail("current Coordinator scores are out of rubric order")
    for criterion in definitions:
        code = criterion.criterion_code
        if code == "A-05":
            score = a05_score
            fact, kind = objective, "objective"
        else:
            score = expected_scores[code].score
            fact, kind = rebuilt_facts[code], None
        justification = render_unit_justification(
            explanations[code], fact, score, kind=kind
        )
        evidence = tuple(row["quote"] for row in explanations[code]["evidence"])
        stored = by_score[code]
        if (
            stored.score != score
            or stored.criterion_title != criterion.title
            or stored.justification != justification
            or stored.evidence != evidence
        ):
            _fail("current Coordinator score rendering was tampered")
    expected_subtotal = sum(s.score for s in result.criterion_scores) / len(
        result.criterion_scores
    )
    if result.subtotal != expected_subtotal:
        _fail("current Coordinator subtotal was tampered")
    expected_summary = build_unit_summary(
        list(result.criterion_scores), explanations, statuses
    )
    if result.summary != expected_summary:
        _fail("current Coordinator summary was tampered")
    advisory = result.advisory_outputs
    expected_matches = [
        {
            "objective_id": row["objective_id"],
            "objective_text": objectives[index]["text"],
            "matched": bool(row["matches"]),
            "excerpt": row["matches"][0]["quote"] if row["matches"] else "",
            "rejected": False,
        }
        for index, row in enumerate(curriculum["rows"])
    ]
    if (
        advisory is None
        or advisory.criterion_id != "C-01"
        or advisory.criterion_title != "Curriculum Alignment"
        or advisory.advisory_only is not True
        or advisory.score != cscore
        or advisory.justification
        != render_unit_justification(
            explanations["C-01"], curriculum, cscore, kind="curriculum"
        )
        or [row.model_dump(mode="json") for row in advisory.objective_matches]
        != expected_matches
    ):
        _fail("current Coordinator curriculum advisory was tampered")


__all__ = ["validate_unit_coordinator_bundle"]
