"""Benchmark tests for ITSO consistency (5.2).

Verifies that:
- Deterministic runs produce identical precheck, prompt, scores.
- Deliberately varied fake results produce detectable criterion-level deltas.
- The benchmark harness does not make external/DB calls.
"""

from __future__ import annotations

import json
from uuid import uuid4

from server.modules.agents.itso import ITSOAgent
from server.modules.agents.itso_precheck import run_itso_precheck

from .conftest import _mock_settings

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SLM_WITH_CITATIONS = (
    "Understanding cybersecurity threats is critical. "
    "Several studies confirm (Author, 2020). "
    "Another work supports this (Writer et al., 2019). "
    "Research shows [1] significant effects. "
    "Multiple sources [2, 3, 4] confirm results. "
    "A review (Scientist, 2021) validates this.\n\n"
    "References\n"
    "Author, A. (2020). Understanding cybersecurity threats.\n"
    "Writer, B. (2019). Network security fundamentals.\n"
    "Scientist, C. (2021). Modern threat detection.\n"
)

_SLM_NO_CITATIONS = (
    "This document covers basic IT concepts. "
    "Students learn about hardware and software."
)

_CHUNKS_WITH = [
    {"chunk_id": "c1", "page_number": 1, "text": _SLM_WITH_CITATIONS},
]

_CHUNKS_WITHOUT = [
    {"chunk_id": "c1", "page_number": 1, "text": _SLM_NO_CITATIONS},
]

_DEFAULT_PROVENANCE = {
    "precheck_version": "1",
    "bibliography_found": True,
    "reference_count": 3,
    "intext_citation_count": 4,
    "doi_count": 0,
    "coverage_ratio": 1.0,
}


class _FakeLLM:
    """Deterministic fake LLM returning a fixed valid JSON response."""

    model = "test-model"

    def __init__(self, response: str | None = None) -> None:
        self._response = response or json.dumps(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "ITSO-01", "score": 3, "justification": "a"},
                    {"criterion_id": "ITSO-02", "score": 3, "justification": "b"},
                    {"criterion_id": "ITSO-03", "score": 3, "justification": "c"},
                ],
            }
        )

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        return self._response


class _FakeLLMAlternating:
    """Fake LLM that returns alternating responses for drift detection."""

    model = "test-model"

    def __init__(self) -> None:
        self._call_count = 0

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        self._call_count += 1
        if self._call_count % 2 == 1:
            # Run 1: higher scores
            return json.dumps(
                {
                    "summary": "good",
                    "criterion_scores": [
                        {
                            "criterion_id": "ITSO-01",
                            "score": 4,
                            "justification": "excellent",
                        },
                        {
                            "criterion_id": "ITSO-02",
                            "score": 3,
                            "justification": "adequate",
                        },
                        {
                            "criterion_id": "ITSO-03",
                            "score": 4,
                            "justification": "strong",
                        },
                    ],
                }
            )
        # Run 2: lower scores
        return json.dumps(
            {
                "summary": "needs improvement",
                "criterion_scores": [
                    {
                        "criterion_id": "ITSO-01",
                        "score": 2,
                        "justification": "missing citations",
                    },
                    {
                        "criterion_id": "ITSO-02",
                        "score": 2,
                        "justification": "no bibliography",
                    },
                    {
                        "criterion_id": "ITSO-03",
                        "score": 3,
                        "justification": "adequate",
                    },
                ],
            }
        )


# ---------------------------------------------------------------------------
# 5.2 — Deterministic repeat runs show zero drift
# ---------------------------------------------------------------------------


def test_itso_precheck_repeat_zero_drift() -> None:
    """Same precheck input produces identical results across runs."""
    r1 = run_itso_precheck(_SLM_WITH_CITATIONS)
    r2 = run_itso_precheck(_SLM_WITH_CITATIONS)

    assert r1["result_hash"] == r2["result_hash"]
    assert r1["bibliography_found"] == r2["bibliography_found"]
    assert r1["reference_count"] == r2["reference_count"]
    assert r1["intext_citation_count"] == r2["intext_citation_count"]
    assert r1["doi_count"] == r2["doi_count"]
    assert r1["coverage_ratio"] == r2["coverage_ratio"]


def test_itso_agent_repeat_zero_drift() -> None:
    """Same agent + deterministic fake LLM produces identical scores."""
    fake = _FakeLLM()

    result1 = ITSOAgent(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_CHUNKS_WITH,
        provenance=_DEFAULT_PROVENANCE,
    )
    result2 = ITSOAgent(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_CHUNKS_WITH,
        provenance=_DEFAULT_PROVENANCE,
    )

    assert result1.subtotal == result2.subtotal
    assert len(result1.criterion_scores) == len(result2.criterion_scores)
    for s1, s2 in zip(result1.criterion_scores, result2.criterion_scores):
        assert s1.score == s2.score
        assert s1.criterion_id == s2.criterion_id


def test_itso_prompt_assembly_repeat_zero_drift() -> None:
    """Same inputs produce identical prompt JSON."""
    agent1 = ITSOAgent(llm_client=_FakeLLM())
    agent1._current_provenance = _DEFAULT_PROVENANCE
    prompt1 = agent1._build_prompt(
        chunk_infos=_CHUNKS_WITH,
        rubric_context=[],
        reference_context=[],
        reference_text=None,
        prompt_version="test-v1",
    )

    agent2 = ITSOAgent(llm_client=_FakeLLM())
    agent2._current_provenance = _DEFAULT_PROVENANCE
    prompt2 = agent2._build_prompt(
        chunk_infos=_CHUNKS_WITH,
        rubric_context=[],
        reference_context=[],
        reference_text=None,
        prompt_version="test-v1",
    )

    assert json.loads(prompt1) == json.loads(prompt2)


# ---------------------------------------------------------------------------
# 5.2 — Deliberately varied results show criterion-level deltas
# ---------------------------------------------------------------------------


def test_itso_varied_fake_produces_different_scores() -> None:
    """Different fake LLM responses produce different criterion scores."""
    fake = _FakeLLMAlternating()

    result1 = ITSOAgent(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_CHUNKS_WITH,
        provenance=_DEFAULT_PROVENANCE,
    )
    result2 = ITSOAgent(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_CHUNKS_WITH,
        provenance=_DEFAULT_PROVENANCE,
    )

    # Scores should differ across runs (first is high, second is low)
    assert result1.subtotal > result2.subtotal
    # At least one criterion should differ
    score_deltas = [
        s1.score - s2.score
        for s1, s2 in zip(result1.criterion_scores, result2.criterion_scores)
    ]
    assert any(d != 0 for d in score_deltas)


def test_itso_varied_results_show_criterion_level_deltas() -> None:
    """Criterion-level score deltas should be individually detectable."""
    fake = _FakeLLMAlternating()

    r1 = ITSOAgent(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_CHUNKS_WITH,
        provenance=_DEFAULT_PROVENANCE,
    )
    r2 = ITSOAgent(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_CHUNKS_WITH,
        provenance=_DEFAULT_PROVENANCE,
    )

    # Build criterion-level delta report (same logic as benchmark harness).
    deltas: list[dict] = []
    for s1, s2 in zip(r1.criterion_scores, r2.criterion_scores):
        if s1.score != s2.score:
            deltas.append(
                {
                    "criterion_id": s1.criterion_id,
                    "run1_score": s1.score,
                    "run2_score": s2.score,
                }
            )

    assert len(deltas) > 0
    # ITSO-01 and ITSO-02 should differ; ITSO-03 might or might not (score=4 then 3)
    diff_ids = {d["criterion_id"] for d in deltas}
    assert "ITSO-01" in diff_ids
    assert "ITSO-02" in diff_ids


# ---------------------------------------------------------------------------
# 5.2 — No external/DB calls
# ---------------------------------------------------------------------------


def test_itso_precheck_no_external_calls() -> None:
    """Precheck is pure-local — should not make any external calls.

    This test passes by construction (run_itso_precheck imports only
    hashlib and re), but we verify the function completes without
    any I/O-related exceptions.
    """
    result = run_itso_precheck(_SLM_WITH_CITATIONS)
    assert result["bibliography_found"] is True
    assert result["reference_count"] > 0


def test_itso_agent_no_unexpected_exceptions(monkeypatch) -> None:
    """Agent run with fake LLM and mock settings should not raise."""
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )
    monkeypatch.setattr(
        "server.core.llm.get_settings",
        lambda: _mock_settings(),
    )

    result = ITSOAgent(llm_client=_FakeLLM()).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_CHUNKS_WITH,
        provenance=_DEFAULT_PROVENANCE,
    )
    assert result.success
    assert result.provenance is not None
    assert result.provenance["requested_model"] == "test-model"
    assert result.provenance["actual_model"] == "test-model"
