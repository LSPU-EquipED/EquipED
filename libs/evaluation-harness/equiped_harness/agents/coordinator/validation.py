"""Coordinator bundle and advisory validation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from equiped_harness.agents.coordinator.catalog import CatalogItem
from equiped_harness.agents.coordinator.contracts import (
    CoordinatorAlignmentAdvisory,
    CurriculumObjectiveMatch,
)
from equiped_harness.agents.coordinator.packet_validation import validate_packet_history
from equiped_harness.agents.coordinator.reporting import (
    evidence_quotes,
    render_justification,
    selected_source_ids,
    unavailable_explanation,
    validate_explanation,
)
from equiped_harness.contracts import (
    GroundedUnit,
    QualifyingUnitsMeasurement,
    RatioBandConfig,
)
from equiped_harness.contracts.results import AgentEvaluationResult
from equiped_harness.runtime.bands import ratio_band
from equiped_harness.strategies.calculators import score_ratio


def _validate_current_coordinator_bundle_v1(result: AgentEvaluationResult) -> None:
    """Validate the current Coordinator bundle without trusting model prose."""
    if result.agent_name != "coordinator":
        raise ValueError("current Coordinator contract requires coordinator result")
    metadata = result.metadata if isinstance(result.metadata, dict) else {}
    if metadata.get("execution_contract") != "coordinator_current.v1":
        raise ValueError("current Coordinator execution contract is missing")
    bundle = metadata.get("current_bundle")
    if not isinstance(bundle, dict) or set(bundle) != {
        "criteria",
        "objective",
        "curriculum",
        "catalog",
    }:
        raise ValueError("current Coordinator bundle is invalid")
    catalog = bundle["catalog"]
    if not isinstance(catalog, list) or len(
        {x.get("source_id") for x in catalog if isinstance(x, dict)}
    ) != len(catalog):
        raise ValueError("current Coordinator catalog is invalid")
    items = {
        x["source_id"]: x
        for x in catalog
        if isinstance(x, dict) and isinstance(x.get("source_id"), str)
    }
    if len(items) != len(catalog):
        raise ValueError("current Coordinator catalog item is invalid")
    facts = bundle["criteria"]
    if not isinstance(facts, dict):
        raise ValueError("current Coordinator criterion facts are invalid")
    by_id = {s.criterion_id: s for s in result.criterion_scores}
    fact_ids = set(facts)
    if fact_ids != set(by_id) - {"A-05"}:
        raise ValueError("current Coordinator criterion facts mismatch")
    for cid, fact in facts.items():
        if not isinstance(fact, dict) or fact.get("kind") not in {
            "guidance",
            "count",
            "ratio",
        }:
            raise ValueError("current Coordinator criterion fact is invalid")
        score = by_id[cid]
        kind = fact["kind"]
        if kind == "guidance":
            expected = fact.get("score")
            eid = fact.get("evidence_id")
            if type(expected) is not int or not 1 <= expected <= 4:
                raise ValueError("current guidance fact score is invalid")
            evidence = (items[eid]["text"],) if eid in items else ()
            if score.score != expected or score.evidence != evidence:
                raise ValueError("current guidance score is not deterministic")
            if score.justification != (
                f"{score.criterion_title}: {fact.get('status')} evidence; "
                f"deterministic score {expected}/4."
            ):
                raise ValueError("current guidance justification was tampered")
        elif kind == "count":
            ids = fact.get("instance_ids")
            thresholds = fact.get("thresholds")
            if (
                not isinstance(ids, list)
                or not isinstance(thresholds, list)
                or len(thresholds) != 3
            ):
                raise ValueError("current count fact is invalid")
            count = len(ids)
            expected = (
                4
                if count >= thresholds[0]
                else 3
                if count >= thresholds[1]
                else 2
                if count >= thresholds[2]
                else 1
            )
            evidence = (
                tuple(items[i]["text"] for i in ids[:8])
                if all(i in items for i in ids)
                else ()
            )
            if (
                score.score != expected
                or score.evidence != evidence
                or score.justification
                != (
                    f"{score.criterion_title}: {count} distinct instance(s); "
                    f"deterministic score {expected}."
                )
            ):
                raise ValueError("current count score is not deterministic")
        else:
            units = fact.get("unit_ids")
            qualifying = fact.get("qualifying_unit_ids")
            thresholds = fact.get("thresholds")
            if (
                not isinstance(units, list)
                or not isinstance(qualifying, list)
                or not isinstance(thresholds, list)
                or (not units and fact.get("status") != "absent")
                or not set(qualifying).issubset(units)
            ):
                raise ValueError("current ratio fact is invalid")
            config = RatioBandConfig(
                threshold_4=thresholds[0],
                threshold_3=thresholds[1],
                threshold_2=thresholds[2],
                short_sample=fact.get("short_sample"),
            )
            expected = score_ratio(
                config,
                QualifyingUnitsMeasurement(
                    total_units=tuple(
                        GroundedUnit(unit_id=i, evidence=items[i]["text"])
                        for i in units
                    ),
                    qualifying_unit_ids=tuple(qualifying),
                    has_measurable_content=bool(units),
                ),
            ).score
            evidence = (
                tuple(items[i]["text"] for i in units[:8])
                if all(i in items for i in units)
                else ()
            )
            if (
                score.score != expected
                or score.evidence != evidence
                or score.justification
                != (
                    f"{score.criterion_title}: {len(qualifying)}/{len(units)} "
                    f"qualifying unit(s); deterministic score {expected}."
                )
            ):
                raise ValueError("current ratio score is not deterministic")
    objective = bundle.get("objective")
    curriculum = bundle.get("curriculum")
    if not isinstance(objective, dict) or not isinstance(curriculum, dict):
        raise ValueError("current Coordinator objective facts are invalid")
    objective_rows = objective.get("rows")
    curriculum_rows = curriculum.get("rows")
    if (
        not isinstance(objective_rows, list)
        or not isinstance(curriculum_rows, list)
        or len(objective_rows) != len(curriculum_rows)
        or not objective_rows
    ):
        raise ValueError("current Coordinator objective denominator is invalid")
    if objective.get("assessment_available") is False and any(
        r.get("source_ids") for r in objective_rows if isinstance(r, dict)
    ):
        raise ValueError(
            "no-assessment current bundle must not contain objective evidence"
        )
    for row in objective_rows + curriculum_rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"objective_id", "source_ids"}
            or not isinstance(row["objective_id"], str)
            or not isinstance(row["source_ids"], list)
            or len(row["source_ids"]) > 2
        ):
            raise ValueError("current objective row is invalid")
    advisory = CoordinatorAlignmentAdvisory.from_dict(result.advisory_outputs.to_dict())
    if len(advisory.objective_matches) != len(curriculum_rows):
        raise ValueError("current curriculum advisory denominator mismatch")
    c_by_id = {r["objective_id"]: r for r in curriculum_rows}
    for match in advisory.objective_matches:
        row = c_by_id.get(match.objective_id)
        if row is None:
            raise ValueError("current curriculum advisory objective mismatch")
        if bool(row["source_ids"]) != match.matched:
            raise ValueError("current curriculum advisory score was tampered")
        expected_excerpt = (
            items[row["source_ids"][0]]["text"] if row["source_ids"] else ""
        )
        if match.excerpt != expected_excerpt:
            raise ValueError("current curriculum advisory evidence was tampered")
    curriculum_matched = sum(bool(r["source_ids"]) for r in curriculum_rows)
    expected_cscore = (
        4
        if curriculum_matched / len(curriculum_rows) >= 0.8
        else 3
        if curriculum_matched / len(curriculum_rows) >= 0.5
        else 2
        if curriculum_matched / len(curriculum_rows) >= 0.2
        else 1
    )
    if advisory.score != expected_cscore or advisory.justification != (
        f"Curriculum alignment: {curriculum_matched}/{len(curriculum_rows)} "
        f"objectives supported; deterministic score {expected_cscore}."
    ):
        raise ValueError("current curriculum advisory justification was tampered")
    a05 = by_id.get("A-05")
    if a05 is None:
        raise ValueError("current Coordinator is missing A-05")
    matched = sum(bool(r["source_ids"]) for r in objective_rows)
    expected_a05 = (
        4
        if objective_rows and matched / len(objective_rows) >= 0.8
        else 3
        if objective_rows and matched / len(objective_rows) >= 0.5
        else 2
        if objective_rows and matched / len(objective_rows) >= 0.2
        else 1
    )
    if a05.score != expected_a05:
        raise ValueError("current A-05 score was tampered")
    expected_a05_justification = (
        "Objective gauging: no assessment sections found; deterministic score 1."
        if objective.get("assessment_available") is False
        else (
            f"Objective gauging: {matched}/{len(objective_rows)} objectives supported "
            f"({matched / len(objective_rows) * 100:.1f}%); "
            f"deterministic score {expected_a05}."
        )
    )
    if a05.justification != expected_a05_justification:
        raise ValueError("current A-05 justification was tampered")


def validate_current_coordinator_bundle(
    result: AgentEvaluationResult, snapshot: Any | None = None
) -> None:
    """Validate versioned Coordinator measurements and their saved explanations."""
    if not isinstance(result.metadata, dict):
        raise ValueError("current Coordinator execution contract is missing")
    contract = result.metadata.get("execution_contract")
    if contract == "coordinator_current.v6":
        from equiped_harness.agents.coordinator.pipeline import validate_result

        return validate_result(result, snapshot)
    if contract == "coordinator_current.v5":
        from equiped_harness.agents.coordinator.batch_engine import (
            validate_batch_bundle,
        )
        from equiped_harness.exceptions import AgentExecutionError

        try:
            return validate_batch_bundle(result, snapshot)
        except AgentExecutionError as exc:
            raise ValueError("Coordinator batched evidence is invalid") from exc
    if contract == "coordinator_current.v4":
        from equiped_harness.agents.coordinator.narrative_contract import (
            validate_narrative_bundle,
        )
        from equiped_harness.exceptions import AgentExecutionError

        try:
            return validate_narrative_bundle(result, snapshot)
        except AgentExecutionError as exc:
            raise ValueError("Coordinator model finding is invalid") from exc
    if contract == "coordinator_current.v3":
        from equiped_harness.agents.coordinator.unit_validation import (
            validate_unit_coordinator_bundle,
        )
        from equiped_harness.exceptions import AgentExecutionError

        try:
            return validate_unit_coordinator_bundle(result, snapshot)
        except AgentExecutionError as exc:
            raise ValueError("current Coordinator unit evidence is invalid") from exc
    if contract == "coordinator_current.v1":
        return _validate_current_coordinator_bundle_v1(result)
    if contract != "coordinator_current.v2":
        raise ValueError("current Coordinator execution contract is unsupported")
    if result.agent_name != "coordinator":
        raise ValueError("current Coordinator contract requires coordinator result")
    bundle = result.metadata.get("current_bundle")
    if (
        not isinstance(bundle, dict)
        or set(bundle) - {"reasoning_unavailable", "source_retrieval"}
        != {
            "contract",
            "criteria",
            "objective",
            "curriculum",
            "catalog",
            "explanations",
        }
        or bundle.get("contract") != "coordinator_current.v2"
    ):
        raise ValueError("current Coordinator v2 bundle is invalid")
    raw_catalog = bundle["catalog"]
    if not isinstance(raw_catalog, list):
        raise ValueError("current Coordinator catalog is invalid")
    catalog: dict[str, CatalogItem] = {}
    for item in raw_catalog:
        if not isinstance(item, dict) or not isinstance(item.get("source_id"), str):
            raise ValueError("current Coordinator catalog item is invalid")
        source_id = item["source_id"]
        if (
            source_id in catalog
            or not isinstance(item.get("source"), str)
            or not isinstance(item.get("text"), str)
        ):
            raise ValueError("current Coordinator catalog item is invalid")
        catalog[source_id] = CatalogItem(
            source_id=source_id,
            source=item["source"],
            start=item.get("start", 0),
            end=item.get("end", len(item["text"])),
            text=item["text"],
            fingerprint=item.get("fingerprint", ""),
        )
    facts = bundle["criteria"]
    objective = bundle["objective"]
    curriculum = bundle["curriculum"]
    explanations = bundle["explanations"]
    if not all(
        isinstance(x, dict) for x in (facts, objective, curriculum, explanations)
    ):
        raise ValueError("current Coordinator v2 facts are invalid")
    # Validate row structure and every later catalog lookup before deriving coverage.
    objective_rows = objective.get("rows")
    curriculum_rows = curriculum.get("rows")
    if (
        not isinstance(objective_rows, list)
        or not objective_rows
        or not isinstance(curriculum_rows, list)
        or not curriculum_rows
        or len(objective_rows) != len(curriculum_rows)
    ):
        raise ValueError("current Coordinator objective denominator is invalid")
    objective_ids: list[str] = []
    for rows, namespace in (
        (objective_rows, "assessment"),
        (curriculum_rows, "curriculum"),
    ):
        seen_objectives: set[str] = set()
        for row in rows:
            if (
                not isinstance(row, dict)
                or set(row) != {"objective_id", "source_ids"}
                or not isinstance(row["objective_id"], str)
                or not row["objective_id"]
                or row["objective_id"] in seen_objectives
                or not isinstance(row["source_ids"], list)
                or len(row["source_ids"]) > 2
                or any(
                    not isinstance(source_id, str) for source_id in row["source_ids"]
                )
                or len(row["source_ids"]) != len(set(row["source_ids"]))
            ):
                raise ValueError("current Coordinator objective row is invalid")
            seen_objectives.add(row["objective_id"])
            for source_id in row["source_ids"]:
                if source_id not in catalog or catalog[source_id].source != namespace:
                    raise ValueError("current Coordinator objective source is invalid")
        current_ids = [row["objective_id"] for row in rows]
        if not objective_ids:
            objective_ids = current_ids
        elif current_ids != objective_ids:
            raise ValueError("current Coordinator objective rows do not align")
    if type(objective.get("assessment_available")) is not bool:
        raise ValueError("current Coordinator assessment availability is invalid")
    if objective["assessment_available"] is False and any(
        row["source_ids"] for row in objective_rows
    ):
        raise ValueError("unavailable assessment cannot contain objective evidence")

    for cid, fact in facts.items():
        if not isinstance(cid, str) or not isinstance(fact, dict):
            raise ValueError("current Coordinator criterion fact is invalid")
        kind = fact.get("kind")
        if kind == "guidance":
            selected = [fact["evidence_id"]] if fact.get("evidence_id") else []
        elif kind == "count":
            selected = fact.get("instance_ids")
            if (
                not isinstance(selected, list)
                or type(fact.get("count")) is not int
                or fact["count"] != len(selected)
            ):
                raise ValueError("current Coordinator count fact is inconsistent")
        elif kind == "ratio":
            selected = fact.get("unit_ids")
            qualifying = fact.get("qualifying_unit_ids")
            if (
                not isinstance(qualifying, list)
                or any(not isinstance(source_id, str) for source_id in qualifying)
                or len(qualifying) != len(set(qualifying))
                or not isinstance(selected, list)
                or not set(qualifying).issubset(selected)
                or type(fact.get("total")) is not int
                or fact["total"] != len(selected)
                or type(fact.get("qualifying")) is not int
                or fact["qualifying"] != len(qualifying)
            ):
                raise ValueError("current Coordinator ratio fact is invalid")
        else:
            raise ValueError("current Coordinator criterion fact is invalid")
        if (
            not isinstance(selected, list)
            or any(not isinstance(source_id, str) for source_id in selected)
            or len(selected) != len(set(selected))
        ):
            raise ValueError("current Coordinator criterion source IDs are invalid")
        for source_id in selected:
            if source_id not in catalog or catalog[source_id].source != "slm":
                raise ValueError("current Coordinator criterion source is invalid")

    by_id = {score.criterion_id: score for score in result.criterion_scores}
    expected_explanation_ids = (set(facts) - {"A-05"}) | {"A-05", "C-01"}
    if set(explanations) != expected_explanation_ids:
        raise ValueError("current Coordinator v2 explanations mismatch")
    kinds = {cid: fact["kind"] for cid, fact in facts.items()}
    kinds.update({"A-05": "objective", "C-01": "curriculum"})
    unavailable = bundle.get("reasoning_unavailable", [])
    if (
        not isinstance(unavailable, list)
        or any(not isinstance(cid, str) for cid in unavailable)
        or len(unavailable) != len(set(unavailable))
        or not set(unavailable).issubset(expected_explanation_ids)
    ):
        raise ValueError("current Coordinator unavailable reasoning marker is invalid")
    unavailable_ids = set(unavailable)
    envelope_status = result.metadata.get("envelope_status", {})
    if not isinstance(envelope_status, dict):
        raise ValueError("current Coordinator envelope status is invalid")

    def task_key(cid: str) -> str:
        if cid == "A-05":
            return "objective-assessment"
        if cid == "C-01":
            return "curriculum"
        return f"ordinary-{cid}"

    for cid in unavailable_ids:
        if envelope_status.get(task_key(cid)) != "fallback":
            raise ValueError("unavailable reasoning requires fallback task status")
    if any(
        status == "fallback"
        and key in {task_key(cid) for cid in expected_explanation_ids}
        and key not in {task_key(cid) for cid in unavailable_ids}
        for key, status in envelope_status.items()
    ):
        raise ValueError("fallback task status requires unavailable reasoning marker")
    allowed_by_id = {
        cid: selected_source_ids(fact, kind=kind)
        for cid, (fact, kind) in {
            **{cid: (fact, fact.get("kind")) for cid, fact in facts.items()},
            "A-05": (objective, "objective"),
            "C-01": (curriculum, "curriculum"),
        }.items()
    }
    normalized: dict[str, dict[str, Any]] = {}
    for cid in expected_explanation_ids:
        if cid not in by_id and cid != "C-01":
            raise ValueError("current Coordinator explanation has no score")
        allowed = allowed_by_id[cid]
        if cid in unavailable_ids:
            explanation = explanations[cid]
            if explanation != unavailable_explanation():
                raise ValueError("unavailable reasoning explanation was tampered")
        else:
            explanation = validate_explanation(explanations[cid], catalog, allowed)
        if explanation != explanations[cid]:
            raise ValueError(
                "stored explanation must retain original source quotations"
            )
        source_namespace = {
            "guidance": "slm",
            "count": "slm",
            "ratio": "slm",
            "objective": "assessment",
            "curriculum": "curriculum",
        }[kinds[cid]]
        if cid not in unavailable_ids and any(
            catalog[e["source_id"]].source != source_namespace
            for e in explanation["evidence"]
        ):
            raise ValueError("current Coordinator explanation source is invalid")
        normalized[cid] = explanation
        score = by_id.get(cid)
        if cid == "C-01":
            score = result.advisory_outputs
            score_value = score.score
        else:
            score_value = score.score
        fact = (
            facts[cid] if cid in facts else objective if cid == "A-05" else curriculum
        )
        expected_justification = render_justification(
            explanation, fact, score_value, kind=kinds[cid]
        )
        if score.justification != expected_justification:
            raise ValueError("current Coordinator explanation rendering was tampered")
        if cid != "C-01" and score.evidence != evidence_quotes(explanation):
            raise ValueError("current Coordinator explanation evidence was tampered")

    validate_packet_history(result, catalog, bundle)

    # Rebuild the legacy v1 representation solely for its deterministic fact checks.
    legacy_scores = []
    for score in result.criterion_scores:
        cid = score.criterion_id
        if cid == "A-05":
            rows = objective["rows"]
            matched = sum(bool(row["source_ids"]) for row in rows)
            if objective.get("assessment_available") is False:
                justification = (
                    "Objective gauging: no assessment sections found; "
                    "deterministic score 1."
                )
                evidence = ()
            else:
                justification = (
                    f"Objective gauging: {matched}/{len(rows)} objectives supported "
                    f"({matched / len(rows) * 100:.1f}%); "
                    f"deterministic score {score.score}."
                )
                evidence = tuple(
                    catalog[row["source_ids"][0]].text
                    for row in rows
                    if row["source_ids"]
                )
        else:
            fact = facts[cid]
            kind = fact["kind"]
            if kind == "guidance":
                justification = (
                    f"{score.criterion_title}: {fact.get('status')} evidence; "
                    f"deterministic score {score.score}/4."
                )
                ids = [fact["evidence_id"]] if fact.get("evidence_id") else []
            elif kind == "count":
                count = len(fact["instance_ids"])
                justification = (
                    f"{score.criterion_title}: {count} distinct instance(s); "
                    f"deterministic score {score.score}."
                )
                ids = fact["instance_ids"][:8]
            else:
                qualifying, units = fact["qualifying_unit_ids"], fact["unit_ids"]
                justification = (
                    f"{score.criterion_title}: {len(qualifying)}/{len(units)} "
                    f"qualifying unit(s); deterministic score {score.score}."
                )
                ids = units[:8]
            evidence = tuple(catalog[i].text for i in ids)
        legacy_scores.append(
            replace(score, justification=justification, evidence=evidence)
        )
    advisory = CoordinatorAlignmentAdvisory.from_dict(result.advisory_outputs.to_dict())
    curriculum_rows = curriculum["rows"]
    cm = sum(bool(row["source_ids"]) for row in curriculum_rows)
    advisory = advisory.model_copy(
        update={
            "justification": (
                f"Curriculum alignment: {cm}/{len(curriculum_rows)} "
                f"objectives supported; deterministic score {advisory.score}."
            )
        }
    )
    legacy_bundle = {
        key: value
        for key, value in bundle.items()
        if key
        not in {"contract", "explanations", "reasoning_unavailable", "source_retrieval"}
    }
    projected = replace(
        result,
        criterion_scores=tuple(legacy_scores),
        advisory_outputs=advisory,
        metadata={
            **result.metadata,
            "execution_contract": "coordinator_current.v1",
            "current_bundle": legacy_bundle,
        },
    )
    return _validate_current_coordinator_bundle_v1(projected)


def validate_coordinator_coverage(result: AgentEvaluationResult) -> None:
    """Dispatch current bundles explicitly; validate legacy v3 separately."""
    if isinstance(result.metadata, dict) and result.metadata.get(
        "execution_contract"
    ) in {
        "coordinator_current.v1",
        "coordinator_current.v2",
        "coordinator_current.v3",
        "coordinator_current.v4",
        "coordinator_current.v5",
        "coordinator_current.v6",
    }:
        return validate_current_coordinator_bundle(result)
    # Legacy adapter-3 persisted bundles retain the envelope_2 validator.
    advisory = CoordinatorAlignmentAdvisory.from_dict(result.advisory_outputs.to_dict())
    rows = (
        (result.metadata.get("group_responses") or {})
        .get("envelope_2", {})
        .get("objective_matches")
    )
    if not isinstance(rows, list) or len(rows) != len(advisory.objective_matches):
        raise ValueError("objective inventory mismatch")
    assessment_matches = []
    for row, c_match in zip(rows, advisory.objective_matches, strict=True):
        if not isinstance(row, dict) or set(row) != {
            "objective_id",
            "objective_text",
            "assessment_matched",
            "assessment_excerpt",
            "assessment_rejected",
            "curriculum_matched",
            "curriculum_excerpt",
            "curriculum_rejected",
        }:
            raise ValueError("invalid objective measurement fields")

        def match_for(dimension: str) -> CurriculumObjectiveMatch:
            return CurriculumObjectiveMatch(
                objective_id=row["objective_id"],
                objective_text=row["objective_text"],
                matched=row[f"{dimension}_matched"],
                excerpt=row[f"{dimension}_excerpt"],
                rejected=row[f"{dimension}_rejected"],
            )

        if match_for("curriculum") != c_match:
            raise ValueError("curriculum advisory disagrees with frozen measurement")
        assessment_matches.append(match_for("assessment"))
    a05 = next(s for s in result.criterion_scores if s.criterion_id == "A-05")
    derived_score = ratio_band(
        sum(m.matched for m in assessment_matches), len(rows)
    ).band
    if a05.score != derived_score or a05.evidence != tuple(
        m.excerpt for m in assessment_matches if m.matched
    ):
        raise ValueError("objective gauging disagrees with frozen measurement")


__all__ = ["validate_coordinator_coverage", "validate_current_coordinator_bundle"]
