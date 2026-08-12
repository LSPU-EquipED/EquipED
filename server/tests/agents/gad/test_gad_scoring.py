"""Tests for single-pass GAD extraction and code-side scoring (tasks 1.1-3.4)."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.gad.agent import GAD
from server.modules.agents.gad.envelope import (
    EXTRACTION_SCHEMA_VERSION,
    parse_combined_response,
)
from server.modules.agents.gad.female_male_count import (
    score_representation_balance,
)
from server.modules.agents.gad.grounding import (
    MAX_INSTANCES_PER_CRITERION,
    ground_instances,
)
from server.modules.agents.gad.life_experiences import (
    score_life_experience_instances,
)
from server.modules.agents.gad.peace_and_equality import (
    score_peace_equality_instances,
)
from server.modules.agents.gad.potential import (
    score_respect_potential_instances,
)
from server.modules.agents.gad.prompt import (
    build_combined_prompt,
)
from server.modules.agents.gad.registry import (
    REGISTRY_VERSION,
)
from server.modules.agents.gad.stereotypes import (
    score_stereotype_instances,
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
            "criterion": "The material is free from gender stereotypes",
            "instance_count": gad_01_count,
            "instances": gad_01_instances or [],
            "summary": gad_01_summary,
        },
        "gad-02": {
            "criterion": (
                "The material shows females and males an equal number of times"
            ),
            "female_count": gad_02_female,
            "male_count": gad_02_male,
            "summary": gad_02_summary,
        },
        "gad-03": {
            "criterion": (
                "The material shows females and males with equal respect and potential"
            ),
            "instance_count": gad_03_count,
            "instances": gad_03_instances or [],
            "summary": gad_03_summary,
        },
        "gad-04": {
            "criterion": (
                "The material reflects the needs and life experiences of both male "
                "and female students"
            ),
            "instance_count": gad_04_count,
            "instances": gad_04_instances or [],
            "summary": gad_04_summary,
        },
        "gad-05": {
            "criterion": (
                "The material promotes peace and equality regardless of gender, race, "
                "class, disability, religion, sexual orientation, or ethnic background"
            ),
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
    parsed = parse_combined_response(json.dumps(resp))
    assert "gad-01" in parsed
    assert "gad-02" in parsed
    assert parsed["gad-02"]["female_count"] == 0
    assert parsed["gad-02"]["male_count"] == 0


def test_parse_rejects_missing_section() -> None:
    resp = _combined_response()
    del resp["gad-03"]
    with pytest.raises(AgentExecutionError, match="missing required sections"):
        parse_combined_response(json.dumps(resp))


def test_parse_rejects_duplicate_key() -> None:
    resp = _combined_response()
    # Add a second key that is a case-insensitive duplicate of gad-01
    resp["GAD-01"] = resp["gad-01"]
    with pytest.raises(AgentExecutionError, match="duplicate key"):
        parse_combined_response(json.dumps(resp))


def test_parse_rejects_numeric_score_field() -> None:
    resp = _combined_response()
    resp["gad-01"]["score"] = 4
    with pytest.raises(AgentExecutionError, match="prohibited numeric-score"):
        parse_combined_response(json.dumps(resp))


def test_parse_rejects_score_in_instances() -> None:
    resp = _combined_response()
    resp["gad-01"]["instances"] = [{"excerpt": "test", "chunk_id": "c1", "score": 4}]
    with pytest.raises(AgentExecutionError, match="prohibited numeric-score"):
        parse_combined_response(json.dumps(resp))


def test_parse_rejects_balance_section_with_instances() -> None:
    resp = _combined_response()
    resp["gad-02"]["instance_count"] = 0
    with pytest.raises(AgentExecutionError, match="unapproved field"):
        parse_combined_response(json.dumps(resp))


def test_parse_accepts_fenced_json() -> None:
    resp = _combined_response()
    fenced = f"```json\n{json.dumps(resp)}\n```"
    parsed = parse_combined_response(fenced)
    assert "gad-01" in parsed


def test_parse_accepts_curly_braces_in_text() -> None:
    """Combined envelope must survive plain-text extraction."""
    resp = _combined_response()
    raw = json.dumps(resp)
    # No fencing, no prefix — should parse directly
    parsed = parse_combined_response(raw)
    assert "gad-01" in parsed


def test_parse_rejects_malformed_json() -> None:
    with pytest.raises(AgentExecutionError, match="invalid JSON"):
        parse_combined_response("not json at all")


def test_parse_rejects_non_object() -> None:
    with pytest.raises(AgentExecutionError, match="must be a JSON object"):
        parse_combined_response('"just a string"')


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
    prompt = build_combined_prompt(
        packed_chunks=_SAMPLE_CHUNKS,
        prompt_version="test-v1",
    )
    payload = json.loads(prompt)
    assert payload["agent"] == "gad"
    assert payload["prompt_version"] == "test-v1"
    assert len(payload["document_chunks"]) == len(_SAMPLE_CHUNKS)
    instructions = "\n".join(payload["instructions"])
    for cid in ("GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"):
        assert cid in instructions


def test_build_combined_prompt_includes_managed_text() -> None:
    managed = "Custom managed GAD instruction text."
    prompt = build_combined_prompt(
        packed_chunks=_SAMPLE_CHUNKS,
        prompt_version="v1",
        gad_managed_prompt=managed,
    )
    payload = json.loads(prompt)
    instructions = "\n".join(payload["instructions"])
    assert managed in instructions


def test_build_combined_prompt_no_score_fields() -> None:
    prompt = build_combined_prompt(
        packed_chunks=_SAMPLE_CHUNKS,
        prompt_version="v1",
    )
    payload = json.loads(prompt)
    instructions = "\n".join(payload["instructions"])
    # Score-related terms should not be in the instructions
    assert "criterion_scores" not in instructions.lower()


# ---------------------------------------------------------------------------
# 2.2-2.4 — Single-pass integration test (replaces the five-call test)
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

    result = GAD(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        llm_temperature=0.8,
    )

    # All five criteria present
    assert [score.criterion_id for score in result.criterion_scores] == [
        "GAD-01",
        "GAD-02",
        "GAD-03",
        "GAD-04",
        "GAD-05",
    ]
    # Expected scores from grounded evidence
    assert [score.score for score in result.criterion_scores] == [3, 3, 4, 3, 4]
    assert result.subtotal == pytest.approx(3.4)

    # Exactly one LLM call (no criterion-level fallback)
    assert len(fake.prompts) == 1
    assert fake.temperatures == [0.0]

    # Metadata reflects single-pass mode
    assert result.metadata["scoring_mode"] == "single_pass_code_bands"
    assert result.metadata["llm_call_count"] == 1

    # Grounded evidence
    stereotype = result.criterion_scores[0]
    assert stereotype.evidence == ("Women cannot lead teams.",)
    assert stereotype.chunk_ids == ("c1",)
    assert "1 unsupported" in stereotype.justification  # reported 2, grounded 1

    # Provenance
    assert result.provenance["extraction_schema_version"] == EXTRACTION_SCHEMA_VERSION
    assert result.provenance["registry_version"] == REGISTRY_VERSION


# ---------------------------------------------------------------------------
# 3.1 — Whole-envelope repair
# ---------------------------------------------------------------------------


def test_repair_recovers_malformed_response() -> None:
    """Malformed combined response triggers one repair call then succeeds."""
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

    result = GAD(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 5
    assert result.metadata["llm_call_count"] == 2  # original + repair
    assert result.provenance["repair_occurred"] is True


def test_unrecoverable_response_returns_failure() -> None:
    """When repair also fails, GAD returns failed result with metadata."""

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

    result = GAD(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
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

    result = GAD(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
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
# Deterministic registry scoring boundaries (unchanged from original)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scorer", "values", "expected"),
    [
        (score_stereotype_instances, (0, 1, 2, 4), (4, 3, 2, 1)),
        (score_respect_potential_instances, (0, 1, 3, 6), (4, 3, 2, 1)),
        (score_life_experience_instances, (0, 2, 5, 6), (4, 3, 2, 1)),
        (score_peace_equality_instances, (0, 2, 5, 6), (4, 3, 2, 1)),
    ],
)
def test_instance_scoring_boundaries(scorer, values, expected) -> None:
    assert tuple(scorer(value) for value in values) == expected


def test_representation_balance_boundaries() -> None:
    assert score_representation_balance(5, 5) == 4
    assert score_representation_balance(5, 2) == 3
    assert score_representation_balance(10, 2) == 2
    assert score_representation_balance(12, 1) == 1


# ---------------------------------------------------------------------------
# Blocker regression tests
# ---------------------------------------------------------------------------


def test_repair_prompt_never_exceeds_budget() -> None:
    """Blocker 1: repair prompt must fit within total prompt budget."""
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

    GAD(llm_client=llm).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
    )
    # Repair prompt should be within budget (whether repair succeeded or not)
    assert len(llm.second_prompt) <= budget, (
        f"Repair prompt {len(llm.second_prompt)} > {budget} budget"
    )


def test_instance_cap_enforced_in_persisted_response() -> None:
    """Blocker 2: instances exceeding MAX_INSTANCES_PER_CRITERION must be
    truncated in the persisted raw_response, not just in scoring."""
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

    result = GAD(llm_client=_ManyInstLLM()).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
    )

    assert result.success is True
    # The raw_response should contain at most max_inst instances
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
    """Blocker 3: repair_occurred set True and llm_call_count=2 even
    when repair transport fails (not just after successful response)."""

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
            raise RuntimeError("repair transport failure")

    llm = _FailOnRepairLLM()
    result = GAD(llm_client=llm).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "x"}],
    )
    assert result.success is False
    assert result.provenance["repair_occurred"] is True
    assert result.metadata["llm_call_count"] == 2


def test_scoring_failure_returns_failed_result_no_extra_call() -> None:
    """Blocker 2: when ``score_from_combined`` raises, the engine-path
    returns a standard failed ``AgentEvaluationResult`` with correct
    provenance — no extra LLM call for recovery."""
    import server.modules.agents.gad.registry as _sp

    class _ScoreFailLLM(_TypedResultMixin):
        model = "test-model"

        def generate(self, prompt: str, **kw) -> str:
            # Return valid combined response that passes parsing.
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
        result = GAD(llm_client=_ScoreFailLLM()).run(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "x"}],
        )
    finally:
        _sp.score_from_combined = original_score

    assert result.success is False
    assert len(result.criterion_scores) == 0
    assert result.subtotal == 0.0
    assert result.error_message is not None
    assert result.error_message.startswith("GADExecutionFailure (reference: ")
    assert "simulated scoring failure" not in result.error_message
    # No extra LLM call was made for scoring recovery
    assert result.metadata["llm_call_count"] == 1
    assert result.provenance["repair_occurred"] is False
    assert result.provenance["fallback_occurred"] is False
    assert result.metadata["scoring_mode"] == "single_pass_failed"


def test_repair_budget_overhead_reserved_fails_before_transport(monkeypatch) -> None:
    """When _REPAIR_OVERHEAD_RESERVE >= total budget, GAD fails before
    any LLM transport, raising AgentExecutionError."""
    from server.core.config import Settings
    from server.modules.agents.gad.pipeline import (
        _REPAIR_OVERHEAD_RESERVE,
    )

    # Create settings with a total budget smaller than the reserve.
    tiny_budget = _REPAIR_OVERHEAD_RESERVE - 1  # just under reserve
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
    with pytest.raises(AgentExecutionError, match="exceeds total prompt budget"):
        GAD(llm_client=llm).run(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "x"}],
        )
    # No LLM call was ever made
    assert llm.called is False


def test_same_frozen_chunks_used_for_initial_and_repair() -> None:
    """The same frozen packed chunks from the budget-enforced initial
    prompt are reused for repair and grounding — never repacked."""

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

    result = GAD(llm_client=llm).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
    )
    assert result.success is True

    # Extract frozen chunks from both prompts.
    # The initial prompt is pure JSON. The repair prompt is initial_prompt +
    # plain-text suffix (repair instructions + error + partial). We parse the
    # JSON prefix by finding the boundary where the JSON ends.
    import json as _json

    initial_chunks = _json.loads(llm.prompts[0]).get("document_chunks", [])

    repair_raw = llm.prompts[1]
    # The JSON prefix ends at the closing brace of the initial prompt, which
    # is followed by "\n\nYour previous GAD extraction..."
    json_boundary = repair_raw.find("\n\nYour previous GAD")
    if json_boundary >= 0:
        repair_json = repair_raw[:json_boundary]
    else:
        repair_json = repair_raw
    repair_chunks = _json.loads(repair_json).get("document_chunks", [])

    # Same identity — same chunk count, same chunk_ids
    assert len(initial_chunks) == len(repair_chunks)
    initial_ids = [c["chunk_id"] for c in initial_chunks]
    repair_ids = [c["chunk_id"] for c in repair_chunks]
    assert initial_ids == repair_ids, (
        f"Frozen chunk IDs differ: initial={initial_ids} repair={repair_ids}"
    )
