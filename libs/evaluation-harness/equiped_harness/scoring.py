"""Supported semantic scoring helpers shared with backend result consumers."""

from .contracts import (
    GroundedUnit,
    QualifyingUnitsMeasurement,
    RatioBandConfig,
)
from .result_contracts import (
    AgentEvaluationResult,
    CoordinatorAlignmentAdvisory,
    CurriculumObjectiveMatch,
)
from .runtime.bands import RatioBand, count_band, mean_band, ratio_band
from .sme.scoring import score_criterion_measurement
from .strategies.calculators import score_ratio


def validate_score_band(score: int) -> int:
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 4:
        raise ValueError("criterion score out of bounds")
    return score


__all__ = [
    "score_criterion_measurement",
    "RatioBand",
    "ratio_band",
    "count_band",
    "mean_band",
    "validate_score_band",
    "validate_coordinator_coverage",
    "validate_current_coordinator_bundle",
]


def validate_current_coordinator_bundle(result: AgentEvaluationResult) -> None:
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


def validate_coordinator_coverage(result: AgentEvaluationResult) -> None:
    """Dispatch current bundles explicitly; validate legacy v3 separately."""
    if (
        isinstance(result.metadata, dict)
        and result.metadata.get("execution_contract") == "coordinator_current.v1"
    ):
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
