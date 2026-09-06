"""Shared fakes, helpers, and fixtures for agent tests."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, replace
from typing import Any

from server.core.llm import CompletionResult, ResponseContract, get_llm_model_name
from server.modules.admin.models import PromptVersion
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.itso.agent import ITSO
from server.modules.agents.runtime.prompt_budget import pack_chunks
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
    ShortSampleConfig,
)
from server.modules.rubrics.snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    build_evaluation_form_snapshot,
)


def _make_dummy_snapshot(
    agent_id: str,
    evaluation_id: Any | None = None,
) -> EvaluationFormSnapshotDTO:
    """Create a minimal valid EvaluationFormSnapshotDTO matching agent manifest."""
    eval_id = evaluation_id or uuid.uuid4()
    set_id = uuid.uuid4()

    if agent_id == "coordinator":
        snapshot, _titles = make_coordinator_snapshot(eval_id)
        return snapshot

    if agent_id == "gad":
        crit_code = "GAD-01"
        strategy_config = CountBandConfig(
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=2,
        )
    elif agent_id == "itso":
        crit_code = "ITSO-01"
        strategy_config = LlmRubricGuidanceConfig(guidance="Evaluate ITSO guidance.")
    else:  # sme or default
        crit_code = "OP-01"
        strategy_config = LlmRubricGuidanceConfig(guidance="Evaluate content quality.")

    crit = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=crit_code,
        title=f"{agent_id} Criterion",
        description=f"{agent_id} description",
        scoring_rule="Scoring rule",
        display_order=0,
        strategy_config=strategy_config,
    )
    dom = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM-01",
        title="Domain 1",
        display_order=0,
        criteria=(crit,),
    )
    form = FormDefinition(
        rubric_set_id=set_id,
        agent_id=agent_id,
        name=f"{agent_id} Form",
        version_number=1,
        adapter_key=agent_id,
        adapter_version=1,
        domains=(dom,),
    )
    return build_evaluation_form_snapshot(eval_id, form)


_COORDINATOR_RATIO = RatioBandConfig(
    mode="coverage_percentage",
    threshold_4=80.0,
    threshold_3=50.0,
    threshold_2=20.0,
)
_COORDINATOR_CONFIGS: dict[str, Any] = {
    "OP-01": RatioBandConfig(
        mode="coverage_percentage",
        threshold_4=80.0,
        threshold_3=50.0,
        threshold_2=20.0,
        short_sample=ShortSampleConfig(
            min_units=4, max_issues_4=0, max_issues_3=1, max_issues_2=2
        ),
    ),
    "OP-02": CountBandConfig(
        mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1
    ),
    "OP-03": _COORDINATOR_RATIO,
    "OP-04": _COORDINATOR_RATIO,
    "OP-05": CountBandConfig(
        mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
    ),
    "A-01": _COORDINATOR_RATIO,
    "A-02": CountBandConfig(
        mode="minimum_count", threshold_4=5, threshold_3=3, threshold_2=2
    ),
    "A-03": CountBandConfig(
        mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1
    ),
    "A-04": CountBandConfig(
        mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
    ),
    "A-05": CurriculumAlignmentConfig(),
}


def make_coordinator_snapshot(
    evaluation_id: Any | None = None,
) -> tuple[EvaluationFormSnapshotDTO, dict[str, str]]:
    """Build a 10-criterion adapter_version-2 Coordinator snapshot.

    Two domains (OP: OP-01..05, A: A-01..05) with strategy configs matching
    ``server/scripts/seed_rubrics.py::_COORDINATOR_STRATEGY_CONFIGS``. Returns
    ``(snapshot_dto, {criterion_code: criterion_title})``.
    """
    eval_id = evaluation_id or uuid.uuid4()
    titles = {code: f"{code} Criterion" for code in _COORDINATOR_CONFIGS}

    def _criteria(codes: list[str]) -> tuple[CriterionDefinition, ...]:
        return tuple(
            CriterionDefinition(
                rubric_criterion_id=uuid.uuid4(),
                criterion_code=code,
                title=titles[code],
                description=f"Description for {code}",
                display_order=idx,
                strategy_config=_COORDINATOR_CONFIGS[code],
            )
            for idx, code in enumerate(codes)
        )

    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="coordinator",
        adapter_key="coordinator",
        adapter_version=2,
        version_number=1,
        name="Coordinator Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="OP",
                title="Organization & Presentation",
                display_order=0,
                criteria=_criteria(["OP-01", "OP-02", "OP-03", "OP-04", "OP-05"]),
            ),
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="A",
                title="Assessment",
                display_order=1,
                criteria=_criteria(["A-01", "A-02", "A-03", "A-04", "A-05"]),
            ),
        ),
    )
    return build_evaluation_form_snapshot(eval_id, form), titles


class SequencedFakeClient:
    """Return canned JSON payloads in call order for basket tests."""

    model: str

    def __init__(self, responses: list[dict[str, Any] | None]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, **_: object) -> str:
        if self.calls >= len(self.responses):
            raise AssertionError(
                f"LLM called more times than expected (call #{self.calls + 1})"
            )
        payload = self.responses[self.calls]
        self.calls += 1
        if payload is None:
            raise RuntimeError("configured to fail")
        return json.dumps(payload)

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        if response_contract is not None and response_contract.mode != "json_object":
            raise AssertionError("SME fake requires the json_object response contract")
        return CompletionResult(
            content=self.generate(
                prompt, temperature=temperature, max_new_tokens=max_new_tokens
            ),
            served_model=getattr(self, "model", get_llm_model_name()),
            finish_reason="stop",
        )


_BASKET_A1 = {
    "objectives": [{"id": 1, "text": "Objective"}],
    "assessments": [
        {"id": 1, "text": "Quiz", "assessment_type": "objective_test", "evidence": "Q1"}
    ],
    "alignment": [
        {
            "objective_id": 1,
            "is_measured": True,
            "assessment_ids": [1],
            "evidence": "Q1",
        }
    ],
}
_BASKET_A2 = {
    "tasks": [
        {
            "id": 1,
            "text": "Task 1",
            "bloom_level": "apply",
            "directions": "Do X.",
            "has_clear_directions": True,
            "evidence": "Do X.",
        }
    ]
}
_BASKET_A3 = {
    "monitoring_mechanisms": [
        {
            "id": 1,
            "text": "Check 1",
            "monitoring_type": "checkpoint",
            "evidence": "quiz",
        }
    ]
}
_BASKET_A4 = {
    "enhancement_activities": [{"id": 1, "text": "Extra", "evidence": "Research more."}]
}
_BASKET_B1 = {
    "topics": [{"id": 1, "title": "T1"}, {"id": 2, "title": "T2"}],
    "transitions": [{"from_id": 1, "to_id": 2, "is_coherent": True, "reason": "ok"}],
    "feedback_mechanisms": [
        {
            "id": 1,
            "text": "Key",
            "feedback_type": "answer_key",
            "evidence": "p.1",
        }
    ],
}
_BASKET_B2 = {"sections": [{"id": 1, "title": "S1", "is_clean": True, "issue": ""}]}
_ALL_BASKETS_IN_ORDER = [
    _BASKET_A1,
    _BASKET_A2,
    _BASKET_A3,
    _BASKET_A4,
    _BASKET_B1,
    _BASKET_B2,
]


# --- SME grouped LLM-scoring fakes -------------------------------------------
# ``SME.run()`` scores via 3 grouped direct-LLM calls (see
# ``sme/grouped_execution.execute_group``) and only falls back to the
# per-criterion engine lane (``registry.run_criterion``) for a group whose call
# fails. A fake therefore has to answer BOTH prompt shapes: the grouped JSON
# prompt, and the plain-text per-criterion extraction prompt.

SME_GROUP_TITLES: dict[str, str] = {
    "A-01": "Learner Transformation",
    "A-02": "Varied Assessment Tools",
    "A-03": "Progress Monitoring",
    "A-04": "Prescriptive Feedback",
    "A-05": "Objective Gauging",
    "OP-01": "Topic Coherence",
    "OP-02": "Interactivity",
    "OP-03": "Clear Directions",
    "OP-04": "Accurate Sections",
    "OP-05": "Enhancement Activities",
}

# The grouped prompt is a JSON object, but the repair retry appends a plain
# suffix to it, so it is no longer parseable as JSON -- match the group name
# textually instead of json.loads()-ing the whole prompt.
_SME_GROUP_RE = re.compile(r'"group":\s*"([a-z_]+)"')

# Per-criterion fallback payloads, keyed by criterion code. Each one satisfies
# that code's closed contract in ``sme/criterion_contracts.py``.
SME_CRITERION_FALLBACKS: dict[str, dict[str, Any]] = {
    "A-01": {
        "tasks": [
            {"id": 1, "text": "Task 1", "bloom_level": "apply", "evidence": "Do X."}
        ]
    },
    "A-02": {
        "assessments": [
            {
                "id": 1,
                "text": "Quiz",
                "assessment_type": "objective_test",
                "evidence": "Q1",
            }
        ]
    },
    "A-03": {
        "mechanisms": [
            {
                "id": 1,
                "text": "Check 1",
                "monitoring_type": "checkpoint",
                "evidence": "quiz",
            }
        ]
    },
    "A-04": {
        "mechanisms": [
            {
                "id": 1,
                "text": "Key",
                "feedback_type": "answer_key",
                "evidence": "p.1",
            }
        ]
    },
    "A-05": _BASKET_A1,
    "OP-01": {
        "topics": [{"id": 1, "title": "T1"}, {"id": 2, "title": "T2"}],
        "transitions": [
            {"from_id": 1, "to_id": 2, "is_coherent": True, "reason": "ok"}
        ],
    },
    "OP-02": {
        "interactive_elements": [{"id": 1, "text": "Try it", "evidence": "Try it now"}]
    },
    "OP-03": {
        "tasks": [
            {
                "id": 1,
                "text": "Task 1",
                "directions": "Do X.",
                "has_clear_directions": True,
                "evidence": "Do X.",
            }
        ]
    },
    "OP-04": {"sections": [{"id": 1, "title": "S1", "is_clean": True, "issue": ""}]},
    "OP-05": {
        "enhancement_activities": [
            {"id": 1, "text": "Extra", "evidence": "Research more."}
        ]
    },
}


def sme_group_payloads(
    score: int = 3, *, titles: dict[str, str] | None = None
) -> dict[str, str]:
    """One valid grouped-scoring JSON response per group, all criteria scored
    ``score``."""
    from server.modules.agents.sme import groups

    titles = titles or SME_GROUP_TITLES
    return {
        group_name: json.dumps(
            {
                "summary": "ok",
                "criterion_scores": [
                    {
                        "criterion_id": code,
                        "criterion_title": titles[code],
                        "score": score,
                        "justification": "justification",
                        "evidence": ["evidence"],
                    }
                    for code in codes
                ],
            }
        )
        for group_name, codes in groups.GROUP_CODES.items()
    }


class GroupScoringFakeClient:
    """Answers SME's grouped-scoring calls and its per-criterion fallbacks.

    ``group_payloads`` maps a group name to the raw response body to return
    (``None`` raises a transport error instead). ``fallback_payloads`` is an
    ordered list consumed one entry per per-criterion fallback call (a ``None``
    entry raises); a ``dict`` keyed by criterion code is also accepted when the
    order is not what the test is asserting.
    """

    def __init__(
        self,
        group_payloads: dict[str, str | None],
        fallback_payloads: list[dict[str, Any] | None] | None = None,
        *,
        model: str | None = None,
    ) -> None:
        self.group_payloads = dict(group_payloads)
        self.fallback_payloads = list(fallback_payloads or [])
        if model is not None:
            self.model = model
        self.prompts: list[str] = []
        self.group_calls = 0
        self.fallback_calls = 0

    @property
    def calls(self) -> int:
        return self.group_calls + self.fallback_calls

    def _result(self, content: str) -> CompletionResult:
        return CompletionResult(
            content,
            getattr(self, "model", None) or get_llm_model_name(),
            10,
            20,
            30,
            "stop",
            attempts=1,
        )

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract | None = None,
    ) -> CompletionResult:
        self.prompts.append(prompt)
        match = _SME_GROUP_RE.search(prompt)
        if match is not None:
            self.group_calls += 1
            content = self.group_payloads[match.group(1)]
            if content is None:
                raise RuntimeError("configured group transport failure")
            return self._result(content)

        self.fallback_calls += 1
        if not self.fallback_payloads:
            raise AssertionError(
                f"unexpected per-criterion fallback call #{self.fallback_calls}"
            )
        payload = self.fallback_payloads.pop(0)
        if payload is None:
            raise RuntimeError("configured per-criterion fallback failure")
        return self._result(json.dumps(payload))


@dataclass
class _RetrievedChunk:
    text: str


class _FakeLLM:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        self.prompts.append(prompt)
        return json.dumps(self.response)

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        if not isinstance(response_contract, ResponseContract):
            raise AssertionError("response contract is required")
        content = self.generate(
            prompt, temperature=temperature, max_new_tokens=max_new_tokens
        )
        return CompletionResult(
            content=content,
            served_model="fake-model",
            finish_reason="stop",
        )


class _RawLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        return self.response


class _DummyAgent:
    """Minimal generic double for tests that only need agent metadata/run."""

    agent_name = "dummy"

    def __init__(self, *, llm_client=None, **kwargs):
        self.llm_client = llm_client

    def run(self, **kwargs):
        if "form_snapshot" not in kwargs:
            from server.tests.agents.itso.conftest_helper import make_itso_test_snapshot

            kwargs["form_snapshot"] = make_itso_test_snapshot(
                kwargs.get("evaluation_id")
            )
        result = ITSO(llm_client=self.llm_client).run(**kwargs)
        return replace(result, agent_name=self.agent_name)


class _BatchAgent:
    agent_name = "sme"

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def run(
        self,
        *,
        evaluation_id,
        document_id,
        chunk_infos,
        context_text=None,
        reference_text=None,
        prompt_version=None,
        prompt_version_id=None,
        reference_document_ids=None,
        **kwargs,
    ):
        self.batches.append([chunk["text"] for chunk in chunk_infos])
        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=float(len(chunk_infos)),
            criterion_scores=(),
            summary="batch",
            model_name="local-model",
            processing_seconds=0.0,
            token_count=len(chunk_infos),
            prompt_version_id=prompt_version_id,
        )


class _FailingAgent:
    agent_name = "coordinator"

    def __init__(self) -> None:
        self.calls = 0

    def run(
        self,
        *,
        evaluation_id,
        document_id,
        chunk_infos,
        context_text=None,
        reference_text=None,
        prompt_version=None,
        prompt_version_id=None,
        reference_document_ids=None,
        **kwargs,
    ):
        self.calls += 1
        raise RuntimeError("agent failed")


class _PromptRow:
    def __init__(self, version_id, prompt_text: str) -> None:
        self.version_id = version_id
        self.prompt_text = prompt_text


def _seed_active_prompts(db_session) -> None:
    for agent_id in ["sme", "coordinator", "gad", "itso"]:
        db_session.add(
            PromptVersion(
                agent_id=agent_id,
                version_number=1,
                prompt_text=f"{agent_id} prompt",
                is_active=True,
            )
        )
    db_session.commit()


def _make_chunk_infos(n: int, *, keyword: str = "") -> list[dict[str, object]]:
    """Generate n chunk infos, optionally embedding a keyword in every chunk."""
    return [
        {
            "chunk_id": f"chunk-{i}",
            "page_number": i + 1,
            "text": f"Page {i + 1} content about {keyword}"
            if keyword
            else f"Page {i + 1} generic content",  # noqa: E501
        }
        for i in range(n)
    ]


def _make_mixed_chunks() -> list[dict[str, object]]:
    """Generate chunks with mixed domain keywords for selection testing."""
    return [
        {
            "chunk_id": "c1",
            "page_number": 1,
            "text": "Gender equity and inclusion are important",
        },  # noqa: E501
        {
            "chunk_id": "c2",
            "page_number": 2,
            "text": "Data encryption and authentication protocols",
        },  # noqa: E501
        {
            "chunk_id": "c3",
            "page_number": 3,
            "text": "Course learning outcomes and program alignment",
        },  # noqa: E501
        {
            "chunk_id": "c4",
            "page_number": 4,
            "text": "Security threats and vulnerability assessment",
        },  # noqa: E501
        {
            "chunk_id": "c5",
            "page_number": 5,
            "text": "Content accuracy and factual knowledge",
        },  # noqa: E501
        {
            "chunk_id": "c6",
            "page_number": 6,
            "text": "Diversity representation and accessibility",
        },  # noqa: E501
        {
            "chunk_id": "c7",
            "page_number": 7,
            "text": "Curriculum standards and competencies",
        },  # noqa: E501
        {
            "chunk_id": "c8",
            "page_number": 8,
            "text": "Privacy protection and data integrity",
        },  # noqa: E501
        {
            "chunk_id": "c9",
            "page_number": 9,
            "text": "Theory principles and correct definitions",
        },  # noqa: E501
        {
            "chunk_id": "c10",
            "page_number": 10,
            "text": "Assessment goals and course objectives",
        },  # noqa: E501
    ]


class _PackingCaptureAgent:
    """Concrete adapter that captures the runtime chunk-packing result."""

    agent_name = "capture"
    rubric_source_type = "rubric_sme"
    domain_keywords = (
        "security",
        "data",
        "encryption",
    )

    def __init__(self, *args, **kwargs):
        self.captured_chunks: list[dict[str, object]] = []
        self.captured_chunks_dropped = False
        self.captured_text_excerpted = False

    def run(self, *, chunk_infos, **kwargs):
        del kwargs
        from server.core.config import get_settings

        settings = get_settings()
        packed, chunks_dropped, text_excerpted = pack_chunks(
            [dict(chunk) for chunk in chunk_infos],
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
            domain_keywords=self.domain_keywords,
            agent_name="capture",
        )
        self.captured_chunks = packed
        self.captured_chunks_dropped = chunks_dropped
        self.captured_text_excerpted = text_excerpted
        return None


def _mock_settings(**overrides):
    """Build a minimal Settings-like object for tests."""
    defaults = {
        "llm_model_name": "test-model",
        "llm_temperature": 0.2,
        "llm_temperature_itso": 0.0,
        "llm_max_new_tokens": 2048,
        "agent_max_chunks": 12,
        "agent_max_excerpt_chars": 800,
        "agent_prompt_budget_chars": 5000,
        "agent_small_doc_threshold": 6,
        "agent_total_prompt_budget_chars": 8000,
        "itso_policy_delivery_enabled": False,
    }
    defaults.update(overrides)

    def get_agent_temperature(_self, agent_name):
        if agent_name == "itso":
            return defaults["llm_temperature_itso"]
        return defaults["llm_temperature"]

    defaults["get_agent_temperature"] = get_agent_temperature
    return type("Settings", (), defaults)()


def patch_settings(monkeypatch, **overrides) -> None:
    """Monkeypatch every ``get_settings`` import the agents touch.

    ``ITSO.run()`` calls both ``get_settings`` (in
    ``server.modules.agents.itso.execution``) and ``get_llm_model_name()`` (which
    transitively calls ``get_settings`` in ``server.core.llm``). The
    supervisor also imports ``get_settings`` directly. If the real one
    raises (because the new 8,000-char total budget default conflicts
    with the 5,000-char chunk budget default), the cached
    ``get_engine()`` / ``get_session_factory()`` would refuse to
    build, breaking ``get_active_rubric_context`` for any test that
    hits the real database.

    Patching all three ``get_settings`` references with a mock silences
    the cross-field validation everywhere it would fire inside the
    agent layer. The database module keeps its real ``get_settings``
    reference so the engine chain can still build against the
    ``DATABASE_URL`` from the project's ``.env``.
    """
    mock = _mock_settings(**overrides)
    monkeypatch.setattr(
        "server.modules.agents.itso.execution.get_settings", lambda: mock
    )
    monkeypatch.setattr("server.modules.agents.itso.prompt.get_settings", lambda: mock)
    monkeypatch.setattr(
        "server.core.llm.get_settings",
        lambda: mock,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.dispatch.get_settings",
        lambda: mock,
    )
    monkeypatch.setattr(
        "server.core.database.get_settings",
        lambda: mock,
    )
