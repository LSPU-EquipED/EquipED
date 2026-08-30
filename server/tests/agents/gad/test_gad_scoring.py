"""Tests for single-pass GAD extraction and code-side scoring."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.exceptions import AgentExecutionError, AgentLLMError
from server.modules.agents.gad.agent import GAD
from server.modules.agents.gad.envelope import (
    EXTRACTION_SCHEMA_VERSION,
    extraction_schema,
    parse_combined_response,
)
from server.modules.agents.gad.grounding import (
    MAX_INSTANCES_PER_CRITERION,
    ground_instances,
)
from server.modules.agents.gad.prompt import (
    build_combined_prompt,
)
from server.modules.agents.gad.registry import (
    REGISTRY_VERSION,
    score_from_combined,
)
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    GroundedInstance,
    GroundedInstanceMeasurement,
    PairedCountsMeasurement,
    RatioBandConfig,
)
from server.modules.rubrics.strategies.calculators import score_count, score_ratio
from server.tests.agents.gad.conftest import (
    REVISION_1_GAD_CRITERIA,
    make_gad_snapshot,
)

# ---------------------------------------------------------------------------
# Test double: records prompts/temperatures, serves responses in order
# ---------------------------------------------------------------------------


class _SequenceLLM:
    model = "gad-test-model"

    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.prompts: list[dict[str, object]] = []
        self.temperatures: list[float] = []

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        del max_new_tokens
        self.prompts.append(json.loads(prompt))
        self.temperatures.append(temperature)
        if not self.responses:
            raise AssertionError("GAD made more LLM calls than expected")
        return json.dumps(self.responses.pop(0))

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        del deadline
        assert response_contract.mode == "json_object"
        return CompletionResult(
            content=self.generate(
                prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            ),
            served_model=self.model,
            finish_reason="stop",
        )


class _TypedResultMixin:
    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        del deadline
        assert response_contract.mode == "json_object"
        return CompletionResult(
            content=self.generate(
                prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            ),
            served_model=self.model,
            finish_reason="stop",
        )


# ---------------------------------------------------------------------------
# Helper: build a combined response for test inputs
# ---------------------------------------------------------------------------


def _combined_response(
    *,
    gad_01_instances: list[dict] | None = None,
    gad_01_count: int = 0,
    gad_01_summary: str = "GAD-01 summary.",
    gad_02_female: int = 0,
    gad_02_male: int = 0,
    gad_02_summary: str = "GAD-02 summary.",
    gad_03_instances: list[dict] | None = None,
    gad_03_count: int = 0,
    gad_03_summary: str = "GAD-03 summary.",
    gad_04_instances: list[dict] | None = None,
    gad_04_count: int = 0,
    gad_04_summary: str = "GAD-04 summary.",
    gad_05_instances: list[dict] | None = None,
    gad_05_count: int = 0,
    gad_05_summary: str = "GAD-05 summary.",
) -> dict[str, object]:
    return {
        "gad-01": {
            "instance_count": gad_01_count,
            "instances": gad_01_instances or [],
            "summary": gad_01_summary,
        },
        "gad-02": {
            "female_count": gad_02_female,
            "male_count": gad_02_male,
            "summary": gad_02_summary,
        },
        "gad-03": {
            "instance_count": gad_03_count,
            "instances": gad_03_instances or [],
            "summary": gad_03_summary,
        },
        "gad-04": {
            "instance_count": gad_04_count,
            "instances": gad_04_instances or [],
            "summary": gad_04_summary,
        },
        "gad-05": {
            "instance_count": gad_05_count,
            "instances": gad_05_instances or [],
            "summary": gad_05_summary,
        },
    }


# ---------------------------------------------------------------------------
# 1.1 — Versioned constants
# ---------------------------------------------------------------------------


def test_extraction_schema_version_is_semver() -> None:
    parts = EXTRACTION_SCHEMA_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_registry_version_is_positive_int() -> None:
    assert isinstance(REGISTRY_VERSION, int)
    assert REGISTRY_VERSION >= 1


# ---------------------------------------------------------------------------
# 1.2 — Combined response parsing and validation
# ---------------------------------------------------------------------------


def test_parse_valid_combined_response() -> None:
    resp = _combined_response()
    snap = make_gad_snapshot()
    parsed = parse_combined_response(json.dumps(resp), snap)
    assert "gad-01" in parsed
    assert "gad-02" in parsed
    assert parsed["gad-02"]["female_count"] == 0
    assert parsed["gad-02"]["male_count"] == 0


def test_parse_rejects_missing_section() -> None:
    resp = _combined_response()
    del resp["gad-03"]
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="missing required sections"):
        parse_combined_response(json.dumps(resp), snap)


def test_parse_rejects_duplicate_key() -> None:
    resp = _combined_response()
    resp["GAD-01"] = resp["gad-01"]
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="duplicate key"):
        parse_combined_response(json.dumps(resp), snap)


def test_parse_rejects_numeric_score_field() -> None:
    resp = _combined_response()
    resp["gad-01"]["score"] = 4
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="prohibited numeric-score"):
        parse_combined_response(json.dumps(resp), snap)


def test_parse_rejects_score_in_instances() -> None:
    resp = _combined_response()
    resp["gad-01"]["instances"] = [{"excerpt": "test", "chunk_id": "c1", "score": 4}]
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="prohibited numeric-score"):
        parse_combined_response(json.dumps(resp), snap)


def test_parse_rejects_balance_section_with_instances() -> None:
    resp = _combined_response()
    resp["gad-02"]["instance_count"] = 0
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="unapproved field"):
        parse_combined_response(json.dumps(resp), snap)


def test_parse_rejects_stale_criterion_field() -> None:
    resp = _combined_response()
    resp["gad-01"]["criterion"] = "stale"
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="unapproved field"):
        parse_combined_response(json.dumps(resp), snap)


def test_parse_rejects_stale_category_field() -> None:
    resp = _combined_response()
    resp["gad-01"]["instances"] = [
        {"excerpt": "test", "chunk_id": "c1", "category": "gender"}
    ]
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="unapproved field"):
        parse_combined_response(json.dumps(resp), snap)


def test_parse_accepts_fenced_json() -> None:
    resp = _combined_response()
    fenced = f"```json\n{json.dumps(resp)}\n```"
    snap = make_gad_snapshot()
    parsed = parse_combined_response(fenced, snap)
    assert "gad-01" in parsed


def test_parse_accepts_curly_braces_in_text() -> None:
    resp = _combined_response()
    raw = json.dumps(resp)
    snap = make_gad_snapshot()
    parsed = parse_combined_response(raw, snap)
    assert "gad-01" in parsed


def test_parse_rejects_malformed_json() -> None:
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="invalid JSON"):
        parse_combined_response("not json at all", snap)


def test_parse_rejects_non_object() -> None:
    snap = make_gad_snapshot()
    with pytest.raises(AgentExecutionError, match="must be a JSON object"):
        parse_combined_response('"just a string"', snap)


# ---------------------------------------------------------------------------
# 1.3 — Evidence grounding
# ---------------------------------------------------------------------------

_SAMPLE_CHUNKS = [
    {"chunk_id": "c1", "page_number": 1, "text": "Women cannot lead teams."},
    {"chunk_id": "c2", "page_number": 2, "text": "Only boys should repair computers."},
    {"chunk_id": "c3", "page_number": 3, "text": "Everyone can participate equally."},
]


def test_ground_valid_instances() -> None:
    instances = [
        {"excerpt": "Women cannot lead teams.", "chunk_id": "c1"},
        {"excerpt": "Only boys should repair computers.", "chunk_id": "c2"},
    ]
    excerpts, ids, rejected = ground_instances("gad-01", instances, _SAMPLE_CHUNKS)
    assert len(excerpts) == 2
    assert "c1" in ids
    assert "c2" in ids
    assert rejected == 0


def test_ground_rejects_unknown_chunk_id() -> None:
    instances = [{"excerpt": "Women cannot lead teams.", "chunk_id": "unknown-chunk"}]
    excerpts, ids, rejected = ground_instances("gad-01", instances, _SAMPLE_CHUNKS)
    assert len(excerpts) == 0
    assert rejected == 1


def test_ground_rejects_duplicate_excerpt() -> None:
    instances = [
        {"excerpt": "Women cannot lead teams.", "chunk_id": "c1"},
        {"excerpt": "Women cannot lead teams.", "chunk_id": "c1"},
    ]
    excerpts, ids, rejected = ground_instances("gad-01", instances, _SAMPLE_CHUNKS)
    assert len(excerpts) == 1
    assert rejected == 1


def test_ground_rejects_excerpt_not_in_chunk() -> None:
    instances = [{"excerpt": "This text does not appear.", "chunk_id": "c1"}]
    excerpts, ids, rejected = ground_instances("gad-01", instances, _SAMPLE_CHUNKS)
    assert len(excerpts) == 0
    assert rejected == 1


def test_ground_rejects_malformed_instance() -> None:
    instances = [{"excerpt": "", "chunk_id": ""}]
    excerpts, ids, rejected = ground_instances("gad-01", instances, _SAMPLE_CHUNKS)
    assert len(excerpts) == 0
    assert rejected == 1


# ---------------------------------------------------------------------------
# 2.1 — Combined prompt builder
# ---------------------------------------------------------------------------


def test_build_combined_prompt_has_all_criteria() -> None:
    snap = make_gad_snapshot()
    prompt = build_combined_prompt(
        packed_chunks=_SAMPLE_CHUNKS,
        form_snapshot=snap,
        prompt_version="test-v1",
    )
    payload = json.loads(prompt)
    assert payload["agent"] == "gad"
    assert payload["prompt_version"] == "test-v1"
    assert len(payload["document_chunks"]) == len(_SAMPLE_CHUNKS)
    instructions = "\n".join(payload["instructions"])
    assert "UNTRUSTED DATA" in instructions
    for cid in ("GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"):
        assert cid in instructions


def test_build_combined_prompt_includes_managed_text() -> None:
    managed = "Custom managed GAD instruction text."
    snap = make_gad_snapshot()
    prompt = build_combined_prompt(
        packed_chunks=_SAMPLE_CHUNKS,
        form_snapshot=snap,
        prompt_version="v1",
        gad_managed_prompt=managed,
    )
    payload = json.loads(prompt)
    instructions = "\n".join(payload["instructions"])
    assert managed in instructions


def test_build_combined_prompt_no_score_fields() -> None:
    snap = make_gad_snapshot()
    prompt = build_combined_prompt(
        packed_chunks=_SAMPLE_CHUNKS,
        form_snapshot=snap,
        prompt_version="v1",
    )
    payload = json.loads(prompt)
    instructions = "\n".join(payload["instructions"])
    assert "criterion_scores" not in instructions.lower()


# ---------------------------------------------------------------------------
# 2.2-2.4 — Single-pass integration test with snapshot adapter
# ---------------------------------------------------------------------------


def test_gad_one_combined_call_yields_all_five_scores() -> None:
    fake = _SequenceLLM(
        [
            _combined_response(
                gad_01_instances=[
                    {"excerpt": "Women cannot lead teams.", "chunk_id": "c1"},
                    {"excerpt": "Only boys should repair computers.", "chunk_id": "c2"},
                ],
                gad_01_count=2,
                gad_01_summary="Two stereotypical instances found.",
                gad_02_female=4,
                gad_02_male=1,
                gad_02_summary="Representation is imbalanced toward female.",
                gad_03_summary="No instances of unequal respect found.",
                gad_04_instances=[
                    {"excerpt": "Girls should only take notes.", "chunk_id": "c2"},
                ],
                gad_04_count=1,
                gad_04_summary="One instance favoring male experience.",
                gad_05_summary="No discriminatory content found.",
            )
        ]
    )
    chunks = [
        {
            "chunk_id": "c1",
            "page_number": 1,
            "text": "Women cannot lead teams. Only boys should repair computers.",
        },
        {
            "chunk_id": "c2",
            "page_number": 2,
            "text": "Girls should only take notes.",
        },
    ]

    eval_id = uuid4()
    snap = make_gad_snapshot(eval_id)
    result = GAD(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunks,
        form_snapshot=snap,
        llm_temperature=0.8,
    )

    assert [score.criterion_id for score in result.criterion_scores] == [
        "GAD-01",
        "GAD-02",
        "GAD-03",
        "GAD-04",
        "GAD-05",
    ]
    assert [score.score for score in result.criterion_scores] == [3, 3, 4, 3, 4]
    assert result.subtotal == pytest.approx(3.4)

    assert len(fake.prompts) == 1
    assert fake.temperatures == [0.0]

    assert result.metadata["scoring_mode"] == "single_pass_snapshot_strategies"
    assert result.metadata["llm_call_count"] == 1

    stereotype = result.criterion_scores[0]
    assert stereotype.evidence == ("Women cannot lead teams.",)
    assert stereotype.chunk_ids == ("c1",)
    assert "1 unsupported" in stereotype.justification

    assert result.provenance["extraction_schema_version"] == EXTRACTION_SCHEMA_VERSION
    assert result.provenance["registry_version"] == REGISTRY_VERSION


# ---------------------------------------------------------------------------
# 3.1 — Whole-envelope repair
# ---------------------------------------------------------------------------


def test_repair_recovers_malformed_response() -> None:
    malformed = '{"gad-01": {"instance_count": 0, "instances": [], "summary": "ok."}'
    repair_response = _combined_response(
        gad_01_summary="Repaired GAD-01.",
        gad_02_summary="Repaired GAD-02.",
        gad_03_summary="Repaired GAD-03.",
        gad_04_summary="Repaired GAD-04.",
        gad_05_summary="Repaired GAD-05.",
    )

    class _RepairLLM(_TypedResultMixin):
        model = "gad-test-model"

        def __init__(self) -> None:
            self.call_count = 0
            self.prompts: list[str] = []

        def generate(
            self, prompt: str, *, temperature: float, max_new_tokens: int
        ) -> str:
            del max_new_tokens
            self.prompts.append(prompt)
            self.call_count += 1
            if self.call_count == 1:
                return malformed
            return json.dumps(repair_response)

    fake = _RepairLLM()
    chunks = [
        {"chunk_id": "c1", "page_number": 1, "text": "Neutral content."},
    ]

    eval_id = uuid4()
    result = GAD(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunks,
        form_snapshot=make_gad_snapshot(eval_id),
    )

    assert result.success is True
    assert len(result.criterion_scores) == 5
    assert result.metadata["llm_call_count"] == 2
    assert result.provenance["repair_occurred"] is True


def test_unrecoverable_response_returns_failure() -> None:
    class _FailLLM(_TypedResultMixin):
        model = "gad-fail-model"

        def __init__(self) -> None:
            self.call_count = 0

        def generate(
            self, prompt: str, *, temperature: float, max_new_tokens: int
        ) -> str:
            del prompt, temperature, max_new_tokens
            self.call_count += 1
            return "not valid json at all"

    fake = _FailLLM()
    chunks = [
        {"chunk_id": "c1", "page_number": 1, "text": "Neutral content."},
    ]

    eval_id = uuid4()
    result = GAD(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunks,
        form_snapshot=make_gad_snapshot(eval_id),
    )

    assert result.success is False
    assert len(result.criterion_scores) == 0
    assert result.provenance["repair_occurred"] is True
    assert result.provenance["actual_model"] == "gad-fail-model"
    assert result.error_message is not None
    assert result.metadata["scoring_mode"] == "single_pass_failed"


# ---------------------------------------------------------------------------
# 3.3 — Provenance keys
# ---------------------------------------------------------------------------


def test_provenance_contains_gad_scalar_keys() -> None:
    fake = _SequenceLLM(
        [
            _combined_response(
                gad_01_summary="s1",
                gad_02_summary="s2",
                gad_03_summary="s3",
                gad_04_summary="s4",
                gad_05_summary="s5",
            )
        ]
    )
    chunks = [
        {"chunk_id": "c1", "page_number": 1, "text": "Neutral content."},
    ]

    eval_id = uuid4()
    result = GAD(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunks,
        form_snapshot=make_gad_snapshot(eval_id),
    )

    prov = result.provenance
    assert prov is not None
    assert prov.get("extraction_schema_version") == EXTRACTION_SCHEMA_VERSION
    assert prov.get("registry_version") == REGISTRY_VERSION
    assert isinstance(prov.get("evidence_candidates"), int)
    assert isinstance(prov.get("evidence_accepted"), int)
    assert isinstance(prov.get("evidence_rejected"), int)
    assert isinstance(prov.get("requested_temperature"), (int, float))
    assert prov.get("requested_temperature") == 0.0


# ---------------------------------------------------------------------------
# Deterministic registry scoring boundaries
# ---------------------------------------------------------------------------


def test_instance_scoring_boundaries() -> None:
    c1 = CountBandConfig(
        strategy="count_band",
        mode="maximum_count",
        threshold_4=0,
        threshold_3=1,
        threshold_2=3,
    )
    assert score_count(c1, GroundedInstanceMeasurement(instances=())).score == 4
    assert (
        score_count(
            c1,
            GroundedInstanceMeasurement(instances=(GroundedInstance(excerpt="e"),)),
        ).score
        == 3
    )
    assert (
        score_count(
            c1,
            GroundedInstanceMeasurement(
                instances=(
                    GroundedInstance(excerpt="e1"),
                    GroundedInstance(excerpt="e2"),
                )
            ),
        ).score
        == 2
    )
    assert (
        score_count(
            c1,
            GroundedInstanceMeasurement(
                instances=tuple(GroundedInstance(excerpt=f"e{i}") for i in range(4))
            ),
        ).score
        == 1
    )


def test_representation_balance_boundaries() -> None:
    r1 = RatioBandConfig(
        strategy="ratio_band",
        mode="absolute_difference",
        threshold_4=2.0,
        threshold_3=5.0,
        threshold_2=10.0,
    )
    assert score_ratio(r1, PairedCountsMeasurement(count_a=5, count_b=5)).score == 4
    assert score_ratio(r1, PairedCountsMeasurement(count_a=5, count_b=2)).score == 3
    assert score_ratio(r1, PairedCountsMeasurement(count_a=10, count_b=2)).score == 2
    assert score_ratio(r1, PairedCountsMeasurement(count_a=12, count_b=1)).score == 1


# ---------------------------------------------------------------------------
# Blocker regression tests
# ---------------------------------------------------------------------------


def test_repair_prompt_never_exceeds_budget() -> None:
    settings = pytest.importorskip("server.core.config").get_settings()
    budget = settings.agent_total_prompt_budget_chars

    class _BigRepairLLM(_TypedResultMixin):
        model = "test"

        def generate(self, prompt: str, **kw) -> str:
            self.second_prompt = prompt
            if getattr(self, "called", False):
                return json.dumps(
                    _combined_response(
                        gad_01_summary="s1",
                        gad_02_summary="s2",
                        gad_03_summary="s3",
                        gad_04_summary="s4",
                        gad_05_summary="s5",
                    )
                )
            self.called = True
            return '{"gad-01": {"instance_count": 0, "instances": [], "summary": "ok."}'

    llm = _BigRepairLLM()
    chunks = [{"chunk_id": "c1", "page_number": 1, "text": "x" * 3000}]

    eval_id = uuid4()
    GAD(llm_client=llm).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunks,
        form_snapshot=make_gad_snapshot(eval_id),
    )
    assert len(llm.second_prompt) <= budget, (
        f"Repair prompt {len(llm.second_prompt)} > {budget} budget"
    )


def test_instance_cap_enforced_in_persisted_response() -> None:
    max_inst = MAX_INSTANCES_PER_CRITERION
    many = [{"excerpt": f"Instance {i}.", "chunk_id": "c1"} for i in range(20)]

    class _ManyInstLLM(_TypedResultMixin):
        model = "test"

        def generate(self, prompt: str, **kw) -> str:
            resp = _combined_response(
                gad_01_count=20,
                gad_01_instances=many,
                gad_02_summary="s2",
                gad_03_summary="s3",
                gad_04_summary="s4",
                gad_05_summary="s5",
            )
            return json.dumps(resp)

    instance_text = ". ".join(f"Instance {i}" for i in range(20)) + "."
    chunks = [
        {"chunk_id": "c1", "page_number": 1, "text": instance_text},
    ]

    eval_id = uuid4()
    result = GAD(llm_client=_ManyInstLLM()).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunks,
        form_snapshot=make_gad_snapshot(eval_id),
    )

    assert result.success is True
    raw = result.raw_response
    assert raw is not None
    import json as _json

    parsed_raw = _json.loads(raw)
    persisted_instances = parsed_raw.get("gad-01", {}).get("instances", [])
    assert len(persisted_instances) <= max_inst, (
        f"Persisted {len(persisted_instances)} instances, expected <= {max_inst}"
    )
    assert result.provenance["evidence_candidates"] <= max_inst


def test_repair_attempt_recorded_before_transport_failure() -> None:
    class _FailOnRepairLLM(_TypedResultMixin):
        model = "test"
        call_count = 0

        def generate(self, prompt: str, **kw) -> str:
            self.call_count += 1
            if self.call_count == 1:
                return json.dumps(
                    {
                        "gad-01": {
                            "instance_count": 0,
                            "instances": [],
                            "summary": "ok.",
                        }
                    }
                )
            raise AgentLLMError("repair transport failure")

    llm = _FailOnRepairLLM()
    eval_id = uuid4()
    result = GAD(llm_client=llm).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "x"}],
        form_snapshot=make_gad_snapshot(eval_id),
    )
    assert result.success is False
    assert result.provenance["repair_occurred"] is True
    assert result.metadata["llm_call_count"] == 2


def test_scoring_failure_returns_failed_result_no_extra_call() -> None:
    import server.modules.agents.gad.registry as _sp

    class _ScoreFailLLM(_TypedResultMixin):
        model = "test-model"

        def generate(self, prompt: str, **kw) -> str:
            return json.dumps(
                _combined_response(
                    gad_01_summary="s1",
                    gad_02_summary="s2",
                    gad_03_summary="s3",
                    gad_04_summary="s4",
                    gad_05_summary="s5",
                )
            )

    original_score = _sp.score_from_combined

    def _failing_score(*args, **kwargs):
        raise AgentExecutionError("simulated scoring failure")

    try:
        _sp.score_from_combined = _failing_score  # type: ignore[assignment]
        eval_id = uuid4()
        result = GAD(llm_client=_ScoreFailLLM()).run(
            evaluation_id=eval_id,
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "x"}],
            form_snapshot=make_gad_snapshot(eval_id),
        )
    finally:
        _sp.score_from_combined = original_score

    assert result.success is False
    assert len(result.criterion_scores) == 0
    assert result.subtotal == 0.0
    assert result.error_message is not None
    assert result.error_message.startswith("GADExecutionFailure (reference: ")
    assert "simulated scoring failure" not in result.error_message
    assert result.metadata["llm_call_count"] == 1
    assert result.provenance["repair_occurred"] is False
    assert result.provenance["fallback_occurred"] is False
    assert result.metadata["scoring_mode"] == "single_pass_failed"


def test_repair_budget_overhead_reserved_fails_before_transport(monkeypatch) -> None:
    from server.core.config import Settings
    from server.modules.agents.gad.pipeline import (
        _REPAIR_OVERHEAD_RESERVE,
    )

    tiny_budget = _REPAIR_OVERHEAD_RESERVE - 1
    tiny_settings = Settings(agent_total_prompt_budget_chars=tiny_budget)
    monkeypatch.setattr(
        "server.modules.agents.gad.pipeline.get_settings",
        lambda: tiny_settings,
    )

    class _NoopLLM(_TypedResultMixin):
        model = "test"
        called = False

        def generate(self, *a, **kw):
            self.called = True
            return "{}"

    llm = _NoopLLM()
    eval_id = uuid4()
    with pytest.raises(AgentExecutionError, match="exceeds total prompt budget"):
        GAD(llm_client=llm).run(
            evaluation_id=eval_id,
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "x"}],
            form_snapshot=make_gad_snapshot(eval_id),
        )
    assert llm.called is False


def test_same_frozen_chunks_used_for_initial_and_repair() -> None:
    class _ChunkCheckLLM(_TypedResultMixin):
        model = "test"
        prompts: list[str] = []

        def generate(self, prompt: str, **kw) -> str:
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                return json.dumps(
                    {
                        "gad-01": {
                            "instance_count": 0,
                            "instances": [],
                            "summary": "ok.",
                        }
                    }
                )
            return json.dumps(
                _combined_response(
                    gad_01_summary="s1",
                    gad_02_summary="s2",
                    gad_03_summary="s3",
                    gad_04_summary="s4",
                    gad_05_summary="s5",
                )
            )

    llm = _ChunkCheckLLM()
    chunks = [
        {"chunk_id": "c1", "page_number": 1, "text": "A"},
        {"chunk_id": "c2", "page_number": 2, "text": "B"},
    ]

    eval_id = uuid4()
    result = GAD(llm_client=llm).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunks,
        form_snapshot=make_gad_snapshot(eval_id),
    )
    assert result.success is True

    import json as _json

    initial_chunks = _json.loads(llm.prompts[0]).get("document_chunks", [])
    repair_raw = llm.prompts[1]
    json_boundary = repair_raw.find("\n\nYour previous GAD")
    if json_boundary >= 0:
        repair_json = repair_raw[:json_boundary]
    else:
        repair_json = repair_raw
    repair_chunks = _json.loads(repair_json).get("document_chunks", [])

    assert len(initial_chunks) == len(repair_chunks)
    initial_ids = [c["chunk_id"] for c in initial_chunks]
    repair_ids = [c["chunk_id"] for c in repair_chunks]
    assert initial_ids == repair_ids


# ---------------------------------------------------------------------------
# Phase 3 Snapshot Adapter Suite: Parity, Dynamic Forms, Novel Codes, Validation
# ---------------------------------------------------------------------------


def test_golden_parity_revision_1_threshold_ladders() -> None:
    snap = make_gad_snapshot()
    chunks = [
        {
            "chunk_id": "c1",
            "text": " ".join(f"Instance {i} adverse occurrence." for i in range(15)),
        }
    ]

    # Test GAD-01 ladder: 0, 1, 2, 3, 4 instances
    for count, expected in [(0, 4), (1, 3), (2, 2), (3, 2), (4, 1)]:
        instances = [
            {"excerpt": f"Instance {i} adverse occurrence.", "chunk_id": "c1"}
            for i in range(count)
        ]
        payload = _combined_response(gad_01_count=count, gad_01_instances=instances)
        scores, *_ = score_from_combined(payload, chunks, form_snapshot=snap)
        assert next(s for s in scores if s.criterion_id == "GAD-01").score == expected

    # Test GAD-02 ladder: differences 0, 2, 3, 5, 6, 10, 11
    for f, m, expected in [
        (5, 5, 4),
        (5, 3, 4),
        (6, 3, 3),
        (8, 3, 3),
        (9, 3, 2),
        (13, 3, 2),
        (15, 3, 1),
    ]:
        payload = _combined_response(gad_02_female=f, gad_02_male=m)
        scores, *_ = score_from_combined(payload, chunks, form_snapshot=snap)
        assert next(s for s in scores if s.criterion_id == "GAD-02").score == expected

    # Test GAD-03/04/05 ladders: 0, 1, 2, 3, 5, 6 instances
    for count, expected in [(0, 4), (1, 3), (2, 3), (3, 2), (5, 2), (6, 1)]:
        instances = [
            {"excerpt": f"Instance {i} adverse occurrence.", "chunk_id": "c1"}
            for i in range(count)
        ]
        payload = _combined_response(gad_03_count=count, gad_03_instances=instances)
        scores, *_ = score_from_combined(payload, chunks, form_snapshot=snap)
        assert next(s for s in scores if s.criterion_id == "GAD-03").score == expected


def test_dynamic_subset_of_criteria() -> None:
    subset_criteria = (
        REVISION_1_GAD_CRITERIA[0],
        REVISION_1_GAD_CRITERIA[1],
    )
    eval_id = uuid4()
    snap = make_gad_snapshot(eval_id, criteria=subset_criteria)

    fake = _SequenceLLM(
        [
            {
                "gad-01": {
                    "instance_count": 0,
                    "instances": [],
                    "summary": "No stereotypes.",
                },
                "gad-02": {
                    "female_count": 5,
                    "male_count": 5,
                    "summary": "Balanced.",
                },
            }
        ]
    )
    result = GAD(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "text": "Neutral text."}],
        form_snapshot=snap,
    )
    assert result.success is True
    assert len(result.criterion_scores) == 2
    assert [s.criterion_id for s in result.criterion_scores] == ["GAD-01", "GAD-02"]
    assert result.subtotal == 4.0

    prompt_payload = fake.prompts[0]
    prompt_text = "\n".join(prompt_payload["instructions"])
    assert "GAD-01" in prompt_text
    assert "GAD-02" in prompt_text
    assert "GAD-03" not in prompt_text


def test_dynamic_reordering_of_criteria() -> None:
    reversed_criteria = tuple(
        c.model_copy(update={"display_order": i})
        for i, c in enumerate(reversed(REVISION_1_GAD_CRITERIA), start=1)
    )
    eval_id = uuid4()
    snap = make_gad_snapshot(eval_id, criteria=reversed_criteria)

    response_payload = {
        crit.criterion_code.lower(): (
            {"female_count": 3, "male_count": 3, "summary": "ok."}
            if isinstance(crit.strategy_config, RatioBandConfig)
            else {"instance_count": 0, "instances": [], "summary": "ok."}
        )
        for crit in reversed_criteria
    }
    fake = _SequenceLLM([response_payload])
    result = GAD(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "text": "Neutral text."}],
        form_snapshot=snap,
    )
    assert result.success is True
    expected_order = [c.criterion_code for c in reversed_criteria]
    assert [s.criterion_id for s in result.criterion_scores] == expected_order


def test_novel_criterion_codes_and_thresholds() -> None:
    novel_criteria = (
        CriterionDefinition(
            rubric_criterion_id=uuid4(),
            criterion_code="CUSTOM-COUNT",
            title="Custom Count Adverse Criterion",
            description="Detect custom adverse instances.",
            scoring_rule="Count custom instances.",
            display_order=1,
            strategy_config=CountBandConfig(
                strategy="count_band",
                mode="maximum_count",
                threshold_4=0,
                threshold_3=2,
                threshold_2=4,
            ),
        ),
        CriterionDefinition(
            rubric_criterion_id=uuid4(),
            criterion_code="CUSTOM-RATIO",
            title="Custom Ratio Balance Criterion",
            description="Measure custom ratio balance.",
            scoring_rule="Count custom male and female instances.",
            display_order=2,
            strategy_config=RatioBandConfig(
                strategy="ratio_band",
                mode="absolute_difference",
                threshold_4=1.0,
                threshold_3=3.0,
                threshold_2=6.0,
            ),
        ),
    )
    eval_id = uuid4()
    snap = make_gad_snapshot(eval_id, criteria=novel_criteria)

    chunks = [{"chunk_id": "c1", "text": "Custom item 1. Custom item 2."}]
    fake = _SequenceLLM(
        [
            {
                "custom-count": {
                    "instance_count": 2,
                    "instances": [
                        {"excerpt": "Custom item 1.", "chunk_id": "c1"},
                        {"excerpt": "Custom item 2.", "chunk_id": "c1"},
                    ],
                    "summary": "Found 2 custom items.",
                },
                "custom-ratio": {
                    "female_count": 4,
                    "male_count": 2,
                    "summary": "Difference of 2.",
                },
            }
        ]
    )
    result = GAD(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunks,
        form_snapshot=snap,
    )
    assert result.success is True
    scores_by_code = {s.criterion_id: s.score for s in result.criterion_scores}
    assert scores_by_code["CUSTOM-COUNT"] == 3
    assert scores_by_code["CUSTOM-RATIO"] == 3


def test_validation_fails_boundedly_before_llm_call() -> None:
    class _UncalledLLM:
        def generate(self, *a, **kw):
            raise AssertionError("LLM should not have been called")

    agent = GAD(llm_client=_UncalledLLM())
    eval_id = uuid4()
    chunks = [{"chunk_id": "c1", "text": "Sample text."}]

    # 1. Missing form_snapshot
    with pytest.raises(AgentExecutionError, match="valid EvaluationFormSnapshotDTO"):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid4(),
            chunk_infos=chunks,
            form_snapshot=None,  # type: ignore[arg-type]
        )

    # 2. Evaluation ID mismatch
    snap_other_eval = make_gad_snapshot(uuid4())
    with pytest.raises(AgentExecutionError, match="evaluation_id mismatch"):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid4(),
            chunk_infos=chunks,
            form_snapshot=snap_other_eval,
        )

    # 3. Unsupported strategy mode
    unsupported_criteria = (
        CriterionDefinition(
            rubric_criterion_id=uuid4(),
            criterion_code="GAD-01",
            title="Title",
            description="Desc",
            display_order=1,
            strategy_config=CountBandConfig(
                strategy="count_band",
                mode="minimum_count",
                threshold_4=5,
                threshold_3=3,
                threshold_2=1,
            ),
        ),
    )
    snap_unsupported = make_gad_snapshot(eval_id, criteria=unsupported_criteria)
    with pytest.raises(
        AgentExecutionError, match="Unsupported count mode 'minimum_count'"
    ):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid4(),
            chunk_infos=chunks,
            form_snapshot=snap_unsupported,
        )


# ---------------------------------------------------------------------------
# Additional Regressions (Item 12)
# ---------------------------------------------------------------------------


def test_strict_draft202012_schema_validation() -> None:
    """Schema generated by extraction_schema must strictly define sections."""
    snap = make_gad_snapshot()
    schema = extraction_schema(snap)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "gad-01",
        "gad-02",
        "gad-03",
        "gad-04",
        "gad-05",
    }
    assert schema["properties"]["gad-01"]["additionalProperties"] is False
    assert schema["properties"]["gad-02"]["additionalProperties"] is False


def test_primary_and_repair_use_identical_deadline() -> None:
    """Primary and repair LLM calls must receive the identical deadline timestamp."""
    deadlines: list[float | None] = []

    class _DeadlineLLM:
        model = "test-model"

        def generate_result(self, prompt, *, deadline, **kw):
            deadlines.append(deadline)
            if len(deadlines) == 1:
                return CompletionResult(
                    content="not valid json",
                    served_model=self.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content=json.dumps(_combined_response()),
                served_model=self.model,
                finish_reason="stop",
            )

    eval_id = uuid4()
    snap = make_gad_snapshot(eval_id)
    result = GAD(llm_client=_DeadlineLLM()).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "text": "Neutral"}],
        form_snapshot=snap,
    )
    assert result.success is True
    assert len(deadlines) == 2
    assert deadlines[0] is not None
    assert deadlines[0] == deadlines[1]


def test_primary_truncation_triggers_one_repair_call() -> None:
    """Primary truncation error triggers repair retry; success records call_count=2."""

    class _TruncatingLLM:
        model = "test-model"
        calls = 0

        def generate_result(self, prompt, **kw):
            self.calls += 1
            if self.calls == 1:
                raise AgentLLMError("LLM output was truncated")
            return CompletionResult(
                content=json.dumps(_combined_response()),
                served_model=self.model,
                finish_reason="stop",
            )

    eval_id = uuid4()
    snap = make_gad_snapshot(eval_id)
    result = GAD(llm_client=_TruncatingLLM()).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "text": "Neutral"}],
        form_snapshot=snap,
    )
    assert result.success is True
    assert result.metadata["llm_call_count"] == 2
    assert result.provenance["repair_occurred"] is True


def test_primary_non_truncation_transport_error_fails_immediately() -> None:
    """Non-truncation transport error aborts without making a repair call."""

    class _TransportFailLLM:
        model = "test-model"
        calls = 0

        def generate_result(self, prompt, **kw):
            self.calls += 1
            raise AgentLLMError("Connection reset by peer")

    eval_id = uuid4()
    snap = make_gad_snapshot(eval_id)
    result = GAD(llm_client=_TransportFailLLM()).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "text": "Neutral"}],
        form_snapshot=snap,
    )
    assert result.success is False
    assert result.metadata["llm_call_count"] == 1
    assert result.provenance["repair_occurred"] is False
    assert "Connection reset" not in (result.error_message or "")


def test_served_model_alias_does_not_set_fallback() -> None:
    """Different served model alias from provider does not falsely set fallback."""

    class _AliasLLM:
        model = "requested-model"

        def generate_result(self, prompt, **kw):
            return CompletionResult(
                content=json.dumps(_combined_response()),
                served_model="served-alias",
                finish_reason="stop",
            )

    eval_id = uuid4()
    snap = make_gad_snapshot(eval_id)
    result = GAD(llm_client=_AliasLLM()).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "text": "Neutral"}],
        form_snapshot=snap,
    )
    assert result.success is True
    assert result.provenance["fallback_occurred"] is False
    assert result.provenance["actual_model"] == "served-alias"


def test_no_db_or_deleted_modules_imported_by_gad() -> None:
    """Ensure GAD modules never import database or deleted fixed-code modules."""
    import inspect

    import server.modules.agents.gad.agent as gad_agent
    import server.modules.agents.gad.envelope as gad_envelope
    import server.modules.agents.gad.grounding as gad_grounding
    import server.modules.agents.gad.pipeline as gad_pipeline
    import server.modules.agents.gad.prompt as gad_prompt
    import server.modules.agents.gad.registry as gad_registry

    banned_terms = (
        "get_session_factory",
        "get_active_rubric_scoring_rules",
        "resolve_rubric_agent_id",
        "RubricSet",
        "RubricCriterion",
        "female_male_count",
        "stereotypes",
        "potential",
        "life_experiences",
        "peace_and_equality",
        "FALLBACK_GAD_INSTRUCTIONS",
    )

    for mod in (
        gad_agent,
        gad_envelope,
        gad_grounding,
        gad_pipeline,
        gad_prompt,
        gad_registry,
    ):
        source = inspect.getsource(mod)
        for term in banned_terms:
            assert term not in source, f"Found banned term '{term}' in {mod.__name__}"
