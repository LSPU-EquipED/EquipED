"""Tests for GAD envelope schema/parsing of llm_rubric_guidance criteria."""

from __future__ import annotations

import json
import uuid

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.gad.envelope import (
    extraction_schema,
    parse_combined_response,
)
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    LlmScoreDescriptor,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot


def _llm_guidance_snapshot():
    crit = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="GAD-01",
        title="Free from Stereotypes",
        description="Judge freedom from gender stereotypes.",
        scoring_rule="4 = none. 3 = one isolated instance. 2 = a few. 1 = frequent.",
        display_order=1,
        strategy_config=LlmRubricGuidanceConfig(
            guidance="Judge how free the material is from gender stereotypes.",
            level_descriptors=(
                LlmScoreDescriptor(score=4, descriptor="No stereotypes found."),
                LlmScoreDescriptor(score=3, descriptor="One isolated instance."),
                LlmScoreDescriptor(score=2, descriptor="A few instances."),
                LlmScoreDescriptor(score=1, descriptor="Frequent or pervasive."),
            ),
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Rubric v2",
        version_number=2,
        adapter_key="gad",
        adapter_version=2,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="GAD",
                title="Inclusivity & Gender Sensitivity",
                display_order=1,
                criteria=(crit,),
            ),
        ),
    )
    return build_evaluation_form_snapshot(uuid.uuid4(), form)


def test_extraction_schema_includes_llm_rubric_guidance_section() -> None:
    snapshot = _llm_guidance_snapshot()
    schema = extraction_schema(snapshot)
    section = schema["properties"]["gad-01"]
    assert section["required"] == ["score", "evidence", "chunk_id", "summary"]
    assert section["properties"]["score"]["minimum"] == 1
    assert section["properties"]["score"]["maximum"] == 4


def test_parse_combined_response_accepts_valid_llm_rubric_guidance_section() -> None:
    snapshot = _llm_guidance_snapshot()
    raw = json.dumps(
        {
            "gad-01": {
                "score": 3,
                "evidence": "Women are inherently too emotional for leadership.",
                "chunk_id": "chunk_1",
                "reasoning": "One isolated stereotype found.",
                "summary": "One isolated stereotype found.",
            }
        }
    )
    parsed = parse_combined_response(raw, form_snapshot=snapshot)
    assert parsed["gad-01"]["score"] == 3
    assert parsed["gad-01"]["chunk_id"] == "chunk_1"


def test_parse_combined_response_rejects_out_of_range_score() -> None:
    snapshot = _llm_guidance_snapshot()
    raw = json.dumps(
        {
            "gad-01": {
                "score": 5,
                "evidence": "Some excerpt.",
                "chunk_id": "chunk_1",
                "summary": "s",
            }
        }
    )
    with pytest.raises(AgentExecutionError, match="score"):
        parse_combined_response(raw, form_snapshot=snapshot)


def test_parse_combined_response_rejects_missing_chunk_id() -> None:
    snapshot = _llm_guidance_snapshot()
    raw = json.dumps(
        {"gad-01": {"score": 3, "evidence": "Some excerpt.", "summary": "s"}}
    )
    with pytest.raises(AgentExecutionError, match="chunk_id"):
        parse_combined_response(raw, form_snapshot=snapshot)
