"""Tests for the SME Phase-3 strategy-shaped snapshot adapter."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentExecutionError, AgentLLMError
from server.modules.agents.sme.agent import SME
from server.modules.agents.sme.packing import pack_domains
from server.modules.agents.sme.prompt import (
    REPAIR_SUFFIX,
    build_envelope_prompt_and_source,
)
from server.modules.agents.sme.response import (
    build_envelope_schema,
    parse_and_validate_envelope_response,
)
from server.modules.agents.sme.scoring import (
    score_criterion_measurement,
)
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    LlmScoreDescriptor,
    RatioBandConfig,
    ShortSampleConfig,
)
from server.modules.rubrics.snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    build_evaluation_form_snapshot,
)


def _make_criterion(
    code: str,
    title: str,
    strategy_config: Any,
    scoring_rule: str | None = None,
    display_order: int = 0,
) -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=title,
        description=f"Description for {title}",
        scoring_rule=scoring_rule,
        display_order=display_order,
        strategy_config=strategy_config,
    )


def _full_rev1_form() -> FormDefinition:
    d1_criteria = (
        _make_criterion(
            "OP-01",
            "Topic Coherence",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
                short_sample=ShortSampleConfig(
                    min_units=4,
                    max_issues_4=0,
                    max_issues_3=1,
                    max_issues_2=2,
                ),
            ),
            display_order=0,
        ),
        _make_criterion(
            "OP-02",
            "Interactive Elements",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=4,
                threshold_3=2,
                threshold_2=1,
            ),
            display_order=1,
        ),
        _make_criterion(
            "OP-03",
            "Clear Directions",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            display_order=2,
        ),
        _make_criterion(
            "OP-04",
            "Accurate Sections",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            display_order=3,
        ),
        _make_criterion(
            "OP-05",
            "Enhancement Activities",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=3,
                threshold_3=2,
                threshold_2=1,
            ),
            display_order=4,
        ),
    )

    d2_criteria = (
        _make_criterion(
            "A-01",
            "Higher-Order Thinking Tasks",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            display_order=0,
        ),
        _make_criterion(
            "A-02",
            "Varied Assessment Types",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=5,
                threshold_3=3,
                threshold_2=2,
            ),
            display_order=1,
        ),
        _make_criterion(
            "A-03",
            "Progress Monitoring",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=4,
                threshold_3=2,
                threshold_2=1,
            ),
            display_order=2,
        ),
        _make_criterion(
            "A-04",
            "Prescriptive Feedback",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=3,
                threshold_3=2,
                threshold_2=1,
            ),
            display_order=3,
        ),
        _make_criterion(
            "A-05",
            "Objective Gauging",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            display_order=4,
        ),
    )

    return FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Revision 1 SME Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="ID_ORG",
                title="Instructional Design and Organization",
                display_order=0,
                criteria=d1_criteria,
            ),
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="ASSESSMENT",
                title="Assessment",
                display_order=1,
                criteria=d2_criteria,
            ),
        ),
    )


def _make_snapshot(
    eval_id: uuid.UUID | None = None, form: FormDefinition | None = None
) -> EvaluationFormSnapshotDTO:
    evaluation_id = eval_id or uuid.uuid4()
    form_def = form or _full_rev1_form()
    return build_evaluation_form_snapshot(evaluation_id, form_def)


class EnvelopeFakeClient:
    """Mock LLM client that returns canned JSON payloads for envelope calls."""

    def __init__(
        self, payloads: list[Any] | tuple[Any, ...], model: str = "mock-sme-model"
    ) -> None:
        self.payloads = list(payloads)
        self.model = model
        self.call_count = 0
        self.prompts: list[str] = []

    def generate_result(self, prompt: str, **kwargs: Any) -> CompletionResult:
        self.prompts.append(prompt)
        self.call_count += 1
        if not self.payloads:
            raise RuntimeError("No more payloads configured in mock client")
        item = self.payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        return CompletionResult(
            content=item,
            served_model=self.model,
            prompt_tokens=25,
            completion_tokens=50,
            total_tokens=75,
            finish_reason="stop",
            attempts=1,
        )


def test_rev1_threshold_goldens_and_op01_short_sample() -> None:
    # Test OP-01 with short sample (< 4 units)
    crit_op01 = _make_criterion(
        "OP-01",
        "Topic Coherence",
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
            short_sample=ShortSampleConfig(
                min_units=4,
                max_issues_4=0,
                max_issues_3=1,
                max_issues_2=2,
            ),
        ),
    )

    # 2 units, 0 issues (qualifying = 2) -> issues = 0 <= max_issues_4 (0) -> Score 4
    m_op01_4 = {
        "criterion_id": "OP-01",
        "criterion_title": "Topic Coherence",
        "total_units": [
            {"unit_id": "u1", "evidence": "Unit 1 Topic A."},
            {"unit_id": "u2", "evidence": "Unit 2 Topic B."},
        ],
        "qualifying_unit_ids": ["u1", "u2"],
        "has_measurable_content": True,
    }
    score_res = score_criterion_measurement(crit_op01, m_op01_4)
    assert score_res.score == 4
    assert "short sample applied" in score_res.justification
    assert "0 issue(s)" in score_res.justification

    # 3 units, 1 issue (qualifying = 2) -> issues = 1 <= max_issues_3 (1) -> Score 3
    m_op01_3 = {
        "criterion_id": "OP-01",
        "criterion_title": "Topic Coherence",
        "total_units": [
            {"unit_id": "u1", "evidence": "Unit 1 Topic A."},
            {"unit_id": "u2", "evidence": "Unit 2 Topic B."},
            {"unit_id": "u3", "evidence": "Practice task."},
        ],
        "qualifying_unit_ids": ["u1", "u2"],
        "has_measurable_content": True,
    }
    assert score_criterion_measurement(crit_op01, m_op01_3).score == 3

    # Test count criterion (OP-02: 4+ -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1)
    crit_op02 = _make_criterion(
        "OP-02",
        "Interactive Elements",
        CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=2,
            threshold_2=1,
        ),
    )
    m_op02_3 = {
        "criterion_id": "OP-02",
        "criterion_title": "Interactive Elements",
        "instances": [
            {"excerpt": "Practice task."},
            {"excerpt": "Activity 1."},
        ],
    }
    assert score_criterion_measurement(crit_op02, m_op02_3).score == 3

    # Test empty ratio with has_measurable_content=False -> Score 1
    crit_a01 = _make_criterion(
        "A-01",
        "Higher-Order Thinking Tasks",
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        ),
    )
    m_a01_empty = {
        "criterion_id": "A-01",
        "criterion_title": "Higher-Order Thinking Tasks",
        "total_units": [],
        "qualifying_unit_ids": [],
        "has_measurable_content": False,
    }
    res_a01 = score_criterion_measurement(crit_a01, m_a01_empty)
    assert res_a01.score == 1
    assert "no measurable content" in res_a01.justification


def test_all_three_measurement_shapes() -> None:
    source = (
        "Sample source text containing definition fact and interactive activity "
        "and question."
    )

    c_guidance = _make_criterion(
        "G-01",
        "Guidance Criterion",
        LlmRubricGuidanceConfig(
            guidance="Assess factual clarity.",
            level_descriptors=(
                LlmScoreDescriptor(score=4, descriptor="Excellent"),
                LlmScoreDescriptor(score=3, descriptor="Good"),
                LlmScoreDescriptor(score=2, descriptor="Fair"),
                LlmScoreDescriptor(score=1, descriptor="Poor"),
            ),
        ),
        display_order=0,
    )
    c_count = _make_criterion(
        "C-01",
        "Count Criterion",
        CountBandConfig(
            mode="minimum_count",
            threshold_4=3,
            threshold_3=2,
            threshold_2=1,
        ),
        display_order=1,
    )
    c_ratio = _make_criterion(
        "R-01",
        "Ratio Criterion",
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        ),
        display_order=2,
    )

    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Custom 3 Shapes Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="ALL_SHAPES",
                title="All Shapes Domain",
                display_order=0,
                criteria=(c_guidance, c_count, c_ratio),
            ),
        ),
    )

    payload = json.dumps(
        {
            "summary": "Evaluation of 3 shapes.",
            "criterion_measurements": [
                {
                    "criterion_id": "G-01",
                    "criterion_title": "Guidance Criterion",
                    "score": 4,
                    "evidence": "Sample source text",
                    "reasoning": "Clear factual content.",
                },
                {
                    "criterion_id": "C-01",
                    "criterion_title": "Count Criterion",
                    "instances": [
                        {"excerpt": "definition fact"},
                        {"excerpt": "interactive activity"},
                    ],
                    "summary": "Found 2 instances.",
                },
                {
                    "criterion_id": "R-01",
                    "criterion_title": "Ratio Criterion",
                    "total_units": [
                        {"unit_id": "u1", "evidence": "definition fact"},
                        {"unit_id": "u2", "evidence": "question"},
                    ],
                    "qualifying_unit_ids": ["u1", "u2"],
                    "has_measurable_content": True,
                },
            ],
        }
    )

    client = EnvelopeFakeClient([payload])
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id, form)

    agent = SME(llm_client=client)
    result = agent.run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=[{"text": "chunk"}],
        canonical_source_text=source,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 3
    # G-01 -> Score 4, evidence exact quote
    assert result.criterion_scores[0].criterion_id == "G-01"
    assert result.criterion_scores[0].score == 4
    assert result.criterion_scores[0].evidence == ("Sample source text",)
    # C-01 -> 2 instances (thresholds 3->4, 2->3, 1->2) -> Score 3
    assert result.criterion_scores[1].criterion_id == "C-01"
    assert result.criterion_scores[1].score == 3
    assert result.criterion_scores[1].evidence == (
        "definition fact",
        "interactive activity",
    )
    # R-01 -> 2/2 = 100% (threshold 4 >= 80%) -> Score 4
    assert result.criterion_scores[2].criterion_id == "R-01"
    assert result.criterion_scores[2].score == 4
    assert result.criterion_scores[2].evidence == ("definition fact", "question")


def test_domain_packing_and_arbitrary_novel_codes() -> None:
    # 5 domains packed into 3 contiguous envelopes
    domains = tuple(
        DomainDefinition(
            rubric_domain_id=uuid.uuid4(),
            code=f"D_{i}",
            title=f"Domain {i}",
            display_order=i,
            criteria=(
                _make_criterion(
                    f"NOVEL-{i}-1",
                    f"Novel Criterion {i}-1",
                    CountBandConfig(
                        mode="minimum_count",
                        threshold_4=3,
                        threshold_3=2,
                        threshold_2=1,
                    ),
                ),
            ),
        )
        for i in range(5)
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="5 Domains Form",
        domains=domains,
    )

    envelopes = pack_domains(domains)
    assert len(envelopes) == 3
    assert sum(len(env) for env in envelopes) == 5

    # Test full execution with 3 primary calls
    source = "Novel content excerpt for domain tests."
    payloads = [
        json.dumps(
            {
                "summary": f"Env {idx} summary",
                "criterion_measurements": [
                    {
                        "criterion_id": c.criterion_code,
                        "criterion_title": c.title,
                        "instances": [{"excerpt": "Novel content excerpt"}],
                    }
                    for c in env
                ],
            }
        )
        for idx, env in enumerate(envelopes)
    ]

    client = EnvelopeFakeClient(payloads)
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id, form)

    agent = SME(llm_client=client)
    result = agent.run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=[{"text": "chunk"}],
        canonical_source_text=source,
    )

    assert result.success is True
    assert client.call_count == 3
    assert len(result.criterion_scores) == 5
    # Check that summary uses generic fallback for novel codes
    assert "consider revisiting this criterion" in result.summary


def test_repair_mechanism_success_and_failure() -> None:
    source = "Clean document content for repair test."
    c1 = _make_criterion(
        "A-01",
        "Tasks",
        CountBandConfig(
            mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Single Domain Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="D_1",
                title="Domain 1",
                display_order=0,
                criteria=(c1,),
            ),
        ),
    )

    # 1. Primary fails JSON decode, repair succeeds
    bad_payload = "Not valid JSON {"
    good_payload = json.dumps(
        {
            "summary": "Repaired summary",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "Tasks",
                    "instances": [{"excerpt": "Clean document content"}],
                }
            ],
        }
    )

    client = EnvelopeFakeClient([bad_payload, good_payload])
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id, form)

    agent = SME(llm_client=client)
    result = agent.run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=[{"text": "chunk"}],
        canonical_source_text=source,
    )

    assert result.success is True
    assert client.call_count == 2
    assert result.provenance["repair_occurred"] is True

    # 2. Both primary and repair fail -> raises AgentExecutionError, no partial result
    client_fail = EnvelopeFakeClient(
        [bad_payload, "Still bad JSON {"],
    )
    with pytest.raises(AgentExecutionError, match="invalid JSON"):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=[{"text": "chunk"}],
            canonical_source_text=source,
            llm_client=client_fail,
        )


def test_truncated_primary_response_uses_one_complete_envelope_repair() -> None:
    source = "Clean document content for truncation repair."
    criterion = _make_criterion(
        "NEW-COUNT",
        "Novel Count",
        CountBandConfig(
            mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Truncation Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="D_1",
                title="Domain 1",
                display_order=0,
                criteria=(criterion,),
            ),
        ),
    )
    repaired_payload = json.dumps(
        {
            "summary": "Repaired summary",
            "criterion_measurements": [
                {
                    "criterion_id": "NEW-COUNT",
                    "criterion_title": "Novel Count",
                    "instances": [{"excerpt": "Clean document content"}],
                }
            ],
        }
    )
    client = EnvelopeFakeClient(
        [AgentLLMError("LLM output was truncated"), repaired_payload]
    )
    evaluation_id = uuid.uuid4()

    result = SME(llm_client=client).run(
        evaluation_id=evaluation_id,
        document_id=uuid.uuid4(),
        form_snapshot=_make_snapshot(evaluation_id, form),
        chunk_infos=[{"text": source}],
        canonical_source_text=source,
    )

    assert result.success is True
    assert client.call_count == 2
    assert result.provenance["repair_occurred"] is True


def test_strict_mutation_rejections() -> None:
    source = "Valid document source text."
    c1 = _make_criterion(
        "A-01",
        "Criterion A",
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        ),
    )
    criteria = (c1,)

    # 1. Ungrounded excerpt
    p_ungrounded = json.dumps(
        {
            "summary": "ok",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "Criterion A",
                    "total_units": [
                        {
                            "unit_id": "u1",
                            "evidence": "hallucinated quote not in source",
                        }
                    ],
                    "qualifying_unit_ids": ["u1"],
                    "has_measurable_content": True,
                }
            ],
        }
    )
    with pytest.raises(AgentExecutionError, match="not an exact substring"):
        parse_and_validate_envelope_response(p_ungrounded, criteria, source)

    # 2. Duplicate keys
    p_dup_key = (
        '{"summary": "ok", "summary": "duplicate", "criterion_measurements": []}'
    )
    with pytest.raises(AgentExecutionError, match="duplicate key"):
        parse_and_validate_envelope_response(p_dup_key, criteria, source)

    # 3. Prohibited score field in ratio measurement
    p_score_field = json.dumps(
        {
            "summary": "ok",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "Criterion A",
                    "score": 4,
                    "total_units": [
                        {"unit_id": "u1", "evidence": "Valid document source text."}
                    ],
                    "qualifying_unit_ids": ["u1"],
                    "has_measurable_content": True,
                }
            ],
        }
    )
    with pytest.raises(AgentExecutionError, match="Prohibited numeric-score field"):
        parse_and_validate_envelope_response(p_score_field, criteria, source)

    # 4. Unknown qualifying unit ID
    p_unknown_qual = json.dumps(
        {
            "summary": "ok",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "Criterion A",
                    "total_units": [
                        {"unit_id": "u1", "evidence": "Valid document source text."}
                    ],
                    "qualifying_unit_ids": ["u999"],
                    "has_measurable_content": True,
                }
            ],
        }
    )
    with pytest.raises(AgentExecutionError, match="does not exist in total_units"):
        parse_and_validate_envelope_response(p_unknown_qual, criteria, source)

    # 5. has_measurable_content=False with non-empty units
    p_false_nonempty = json.dumps(
        {
            "summary": "ok",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "Criterion A",
                    "total_units": [
                        {"unit_id": "u1", "evidence": "Valid document source text."}
                    ],
                    "qualifying_unit_ids": ["u1"],
                    "has_measurable_content": False,
                }
            ],
        }
    )
    with pytest.raises(AgentExecutionError, match="requires empty total_units"):
        parse_and_validate_envelope_response(p_false_nonempty, criteria, source)

    # 6. Omission markers are never valid source evidence.
    marker_source = "Valid text\n\n[...]\n\nOther text"
    p_marker_evidence = json.dumps(
        {
            "summary": "ok",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "Criterion A",
                    "total_units": [{"unit_id": "u1", "evidence": "[...]"}],
                    "qualifying_unit_ids": ["u1"],
                    "has_measurable_content": True,
                }
            ],
        }
    )
    with pytest.raises(AgentExecutionError, match="not an exact substring"):
        parse_and_validate_envelope_response(p_marker_evidence, criteria, marker_source)

    # 7. Optional measurement text cannot be blank or silently trimmed later.
    count_criterion = _make_criterion(
        "COUNT-01",
        "Count Criterion",
        CountBandConfig(
            mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
        ),
    )
    p_blank_summary = json.dumps(
        {
            "summary": "ok",
            "criterion_measurements": [
                {
                    "criterion_id": "COUNT-01",
                    "criterion_title": "Count Criterion",
                    "instances": [],
                    "summary": " ",
                }
            ],
        }
    )
    with pytest.raises(AgentExecutionError, match="nonblank, trimmed string"):
        parse_and_validate_envelope_response(
            p_blank_summary, (count_criterion,), source
        )


def test_dynamic_schema_allows_null_optional_fields_and_no_extra_items() -> None:
    criterion = _make_criterion(
        "COUNT-01",
        "Count Criterion",
        CountBandConfig(
            mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
        ),
    )
    schema = build_envelope_schema((criterion,))
    scores_schema = schema["properties"]["criterion_measurements"]
    assert scores_schema["items"] is False
    explanation_schema = scores_schema["prefixItems"][0]["properties"]["instances"][
        "items"
    ]["properties"]["explanation"]
    assert {branch["type"] for branch in explanation_schema["anyOf"]} == {
        "string",
        "null",
    }


def test_prompt_budgeting_and_source_downsampling_true_tail() -> None:
    long_text = "HEAD START " + ("filler words " * 2000) + " TRUE TAIL END."
    c1 = _make_criterion(
        "A-01",
        "Criterion A",
        CountBandConfig(
            mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
        ),
    )
    prompt, source_packet = build_envelope_prompt_and_source(
        (c1,),
        canonical_source_text=long_text,
        prompt_budget=15000,
    )
    assert len(prompt) + len(REPAIR_SUFFIX) <= 15000
    assert "TRUE TAIL END." in source_packet
    assert "HEAD START" in source_packet
    assert "\n\n[...]\n\n" in source_packet


def test_snapshot_precheck_validations() -> None:
    agent = SME()
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)

    # 1. Missing form_snapshot
    with pytest.raises(AgentExecutionError, match="valid EvaluationFormSnapshotDTO"):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            form_snapshot=None,  # type: ignore[arg-type]
            chunk_infos=[{"text": "chunk"}],
            canonical_source_text="source",
        )

    # 2. Evaluation ID mismatch
    with pytest.raises(AgentExecutionError, match="evaluation_id"):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=[{"text": "chunk"}],
            canonical_source_text="source",
        )

    # 3. Missing canonical_source_text
    with pytest.raises(AgentExecutionError, match="canonical source text"):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=[{"text": "chunk"}],
            canonical_source_text="",
        )
