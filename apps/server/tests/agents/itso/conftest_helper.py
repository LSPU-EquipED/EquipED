"""Shared test helpers for ITSO unit and contract suites."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from equiped_harness.agents.itso.response import ITSO_CRITERIA_TITLES
from equiped_harness.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    LlmScoreDescriptor,
)
from equiped_harness.contracts.snapshots import (
    EvaluationFormSnapshotDTO,
    build_evaluation_form_snapshot,
)


def public_reference_context() -> dict[str, tuple[str, ...]]:
    """Return a minimal bounded adapter-3 public verification report."""
    report = {
        "status": "completed",
        "scope": ["ITSO-01", "ITSO-02"],
        "bibliography_status": "not_detected",
        "coverage": {"found": 0, "checked": 0, "skipped": 0, "total": 0},
        "references": [
            {
                "query": "no citation detected",
                "status": "matched",
                "source_url": "https://example.org/paper",
                "title": "Public reference",
                "excerpt": "Public source passage for verifying citation claims.",
                "matched_fields": [],
                "mismatches": [],
            }
        ],
    }
    return {"public_reference_verification": (json.dumps(report),)}


def v3_response_for_prompt(
    prompt: Any, response: str, *, generate_valid_evidence: bool = False
) -> str:
    """Narrow legacy fixtures and fill absent grounding from prompt examples.

    Supplied chunk IDs and evidence are left untouched by default so malformed
    model outputs still exercise the real pipeline validators. Legacy fixtures
    may opt into prompt-derived evidence when they intentionally omit evidence.
    """
    try:
        payload = json.loads(response)
        scores = payload["criterion_scores"]
        rows = list(scores.values()) if isinstance(scores, dict) else scores
        if not isinstance(rows, list) or len(rows) != 5:
            return response
        expected = json.loads(prompt.user_context)["response_example"][
            "criterion_scores"
        ]
        expected_ids = {item["criterion_id"] for item in expected}
        if not expected_ids:
            return response
        if isinstance(scores, dict):
            payload["criterion_scores"] = {
                key: value for key, value in scores.items() if key in expected_ids
            }
            output_rows = list(payload["criterion_scores"].values())
        else:
            payload["criterion_scores"] = [
                row for row in rows if row.get("criterion_id") in expected_ids
            ]
            output_rows = payload["criterion_scores"]
        if expected_ids <= {"ITSO-01", "ITSO-02"}:
            from equiped_harness.agents.itso.prompt import MISSING_BIBLIOGRAPHY_NOTICE

            for row in output_rows:
                justification = str(row.get("justification") or "")
                if not any(
                    marker in justification.casefold() for marker in ("[source 1]",)
                ):
                    justification = f"{justification} [source 1]".strip()
                if row.get("criterion_id") == "ITSO-02":
                    if (
                        MISSING_BIBLIOGRAPHY_NOTICE.casefold()
                        not in justification.casefold()
                    ):
                        justification = f"{justification} {MISSING_BIBLIOGRAPHY_NOTICE}"
                row["justification"] = justification
        user_context = json.loads(prompt.user_context)
        excerpts = user_context["document_chunks"]
        evidence_options = user_context.get("module_evidence_options", {})
        if generate_valid_evidence and excerpts:
            for row in output_rows:
                options = evidence_options.get(row["criterion_id"], [])
                if options:
                    row["chunk_ids"] = [options[0]["chunk_id"]]
                    row["evidence"] = [options[0]["quote"]]
                elif row["criterion_id"] in {"ITSO-01", "ITSO-02"}:
                    row["chunk_ids"] = [excerpts[0]["chunk_id"]]
                    row["evidence"] = [excerpts[0]["text"]]
                elif row["criterion_id"] not in {"ITSO-01", "ITSO-02"}:
                    row["chunk_ids"] = []
                    row["evidence"] = []
                    if row["criterion_id"] == "ITSO-04":
                        row["score"] = 4
        return json.dumps(payload)
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return response


def make_itso_test_snapshot(
    evaluation_id: UUID | None = None,
    criteria_specs: tuple[tuple[str, str], ...] | None = None,
    adapter_key: str = "itso",
    adapter_version: int = 3,
    agent_id: str = "itso",
) -> EvaluationFormSnapshotDTO:
    """Build a valid EvaluationFormSnapshotDTO for ITSO test suites."""
    eval_id = evaluation_id or uuid4()
    set_id = uuid4()
    specs = (
        criteria_specs
        if criteria_specs is not None
        else tuple(ITSO_CRITERIA_TITLES.items())
    )

    crit_defs = tuple(
        CriterionDefinition(
            rubric_criterion_id=uuid4(),
            criterion_code=cid,
            title=title,
            description=f"Description for {cid}",
            scoring_rule=f"Scoring rule for {cid}",
            display_order=idx,
            strategy_config=LlmRubricGuidanceConfig(
                guidance=f"Guidance for {cid}",
                level_descriptors=(
                    LlmScoreDescriptor(score=1, descriptor=f"Level 1 for {cid}"),
                    LlmScoreDescriptor(score=2, descriptor=f"Level 2 for {cid}"),
                    LlmScoreDescriptor(score=3, descriptor=f"Level 3 for {cid}"),
                    LlmScoreDescriptor(score=4, descriptor=f"Level 4 for {cid}"),
                ),
            ),
        )
        for idx, (cid, title) in enumerate(specs)
    )
    dom = DomainDefinition(
        rubric_domain_id=uuid4(),
        code="DOM-ITSO",
        title="ITSO Domain",
        display_order=0,
        criteria=crit_defs,
    )
    form = FormDefinition(
        rubric_set_id=set_id,
        agent_id=agent_id,
        name="ITSO Form",
        version_number=1,
        adapter_key=adapter_key,
        adapter_version=adapter_version,
        domains=(dom,),
    )
    return build_evaluation_form_snapshot(eval_id, form)
