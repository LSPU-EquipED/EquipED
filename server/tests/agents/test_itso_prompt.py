"""Tests for ITSO prompt injection and evidence status (3.4)."""

from __future__ import annotations

import json
from uuid import uuid4

from server.modules.agents.itso import ITSOAgent


class _FakeLLM:
    model = "test-model"

    def __init__(self, response_str: str | None = None):
        self.response_str = response_str or (
            '{"summary": "ok", "criterion_scores": [{"criterion_id": "c1", "score": 3, "justification": "ok"}]}'
        )

    def generate(self, prompt, *, temperature, max_new_tokens):
        return self.response_str


def _run_agent_with_provenance(
    chunk_text: str,
    provenance: dict | None = None,
    **kwargs,
):
    """Helper: run ITSO agent with fake LLM and optional provenance."""
    agent = ITSOAgent(llm_client=_FakeLLM())
    return agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": chunk_text}],
        provenance=provenance,
        **kwargs,
    )


def test_prompt_includes_evidence_summary_when_provenance_present() -> None:
    """When provenance with precheck data is provided, the prompt should
    include the local evidence summary and evidence-status guidance."""
    agent = ITSOAgent(llm_client=_FakeLLM())
    agent._current_provenance = {
        "bibliography_found": True,
        "reference_count": 5,
        "intext_citation_count": 12,
        "doi_count": 3,
    }
    prompt = agent._build_prompt(
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "content"}],
        rubric_context=[],
        reference_context=[],
        reference_text=None,
        prompt_version="test prompt v1",
    )
    payload = json.loads(prompt)
    instructions = payload["instructions"]

    joined = "\n".join(instructions)
    assert "Local evidence precheck summary" in joined
    assert "VERIFIED" in joined
    assert "NOT_VERIFIED" in joined
    assert "INSUFFICIENT_EVIDENCE" in joined
    assert "TOOL_UNAVAILABLE" in joined
    assert "bibliography_section: FOUND" in joined
    assert "reference_entries: 5" in joined
    assert "intext_citations: 12" in joined
    assert "doi_candidates: 3" in joined


def test_prompt_forbids_plagiarism_conclusion() -> None:
    """The prompt must explicitly forbid plagiarism/legal conclusions
    from absent local signals."""
    agent = ITSOAgent(llm_client=_FakeLLM())
    agent._current_provenance = {
        "bibliography_found": False,
        "reference_count": 0,
        "intext_citation_count": 0,
        "doi_count": 0,
    }
    prompt = agent._build_prompt(
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "content"}],
        rubric_context=[],
        reference_context=[],
        reference_text=None,
        prompt_version="test prompt v1",
    )
    payload = json.loads(prompt)
    instructions = "\n".join(payload["instructions"])

    assert "Do NOT assert plagiarism" in instructions
    assert "invalid citation" in instructions
    assert "misconduct" in instructions
    assert "legal noncompliance" in instructions
    assert "Absent local evidence" in instructions


def test_prompt_produces_valid_json_score_format() -> None:
    """The ITSO prompt should still produce valid JSON matching the
    expected score format."""
    result = _run_agent_with_provenance(
        "Document with citations (Author, 2020).",
        provenance={
            "bibliography_found": True,
            "reference_count": 1,
            "intext_citation_count": 1,
        },
    )
    assert result.success
    assert len(result.criterion_scores) == 1
    assert 1 <= result.criterion_scores[0].score <= 4


def test_prompt_backward_compatible_without_provenance() -> None:
    """Without provenance, the agent should produce a valid result
    without evidence-status instructions in the prompt."""
    result = _run_agent_with_provenance(
        "Some text.",
        provenance=None,
    )
    assert result.success
    assert len(result.criterion_scores) == 1
    assert result.criterion_scores[0].score == 3


def test_evidence_status_not_in_score_field() -> None:
    """Evidence status should appear in justification, not in score."""
    agent = ITSOAgent(llm_client=_FakeLLM())
    agent._current_provenance = {
        "bibliography_found": False,
        "reference_count": 0,
        "intext_citation_count": 0,
    }
    prompt = agent._build_prompt(
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "content"}],
        rubric_context=[],
        reference_context=[],
        reference_text=None,
        prompt_version="test prompt v1",
    )
    payload = json.loads(prompt)
    instructions = "\n".join(payload["instructions"])

    # The instructions should mention evidence status in the guidance,
    # but the guidance says "use in your criterion justification, NOT in
    # the score field"
    assert "NOT in the score field" in instructions


def test_precheck_absent_signals_labeled_not_verified() -> None:
    """When precheck shows no bibliography found, the prompt should
    indicate NOT_FOUND."""
    agent = ITSOAgent(llm_client=_FakeLLM())
    agent._current_provenance = {
        "bibliography_found": False,
        "reference_count": 0,
        "intext_citation_count": 0,
        "doi_count": 0,
    }
    prompt = agent._build_prompt(
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "content"}],
        rubric_context=[],
        reference_context=[],
        reference_text=None,
        prompt_version="test prompt v1",
    )
    payload = json.loads(prompt)
    instructions = "\n".join(payload["instructions"])

    assert "bibliography_section: NOT_FOUND" in instructions


def test_prompt_budget_respected_with_extra_instructions() -> None:
    """The extra evidence-status instructions should not blow the
    prompt budget beyond reasonable limits."""
    agent = ITSOAgent(llm_client=_FakeLLM())
    agent._current_provenance = {
        "bibliography_found": True,
        "reference_count": 10,
        "intext_citation_count": 25,
        "doi_count": 5,
    }
    prompt = agent._build_prompt(
        chunk_infos=[
            {"chunk_id": f"c{i}", "page_number": i, "text": "x" * 200}
            for i in range(5)
        ],
        rubric_context=["rubric item"] * 3,
        reference_context=["ref"] * 3,
        reference_text=None,
        prompt_version="test prompt v1",
    )
    # The prompt should still be reasonable (< 20K chars).
    assert len(prompt) < 20000
    payload = json.loads(prompt)
    assert "Local evidence precheck summary" in "\n".join(payload["instructions"])
