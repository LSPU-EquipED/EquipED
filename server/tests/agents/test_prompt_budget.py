"""Tests for the end-to-end total-prompt budget cap.

The total-prompt budget is the final safety net that prevents the
assembled prompt (document_chunks + rubric_context + reference_context +
reference_text + instructions) from exceeding remote LLM provider request
limits (e.g. Groq HTTP 413 "Request too large" / TPM rate limit).

These tests exercise the `_enforce_total_prompt_budget` method on
`BaseAgent` directly, with no real LLM calls. The method takes a JSON
prompt string and progressively trims it:

  1. reference_context entries (most expendable)
  2. rubric_context entries
  3. individual entries truncated to ~400 chars + ellipsis

The method returns a ``_BudgetEnforcementResult`` named tuple with
fields:

  - ``prompt``: the (possibly trimmed) prompt string
  - ``reference_context_dropped``: how many reference entries were removed
  - ``trimmed``: ``True`` if the budget enforcement modified the prompt

Integration tests in this file also verify the ``prompt_trimmed`` and
``reference_context_dropped`` fields exposed on the
``AgentEvaluationResult.metadata`` dict.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from .conftest import (
    _DummyAgent,
    _FakeLLM,
    _RetrievedChunk,
    _mock_settings,
    patch_settings,
)


# ------------------------------------------------------------------
# Direct method tests (deterministic, no LLM)
# ------------------------------------------------------------------


def _build_payload(
    *,
    rubric_context: list[str] | None = None,
    reference_context: list[str] | None = None,
    document_chunks: list[dict] | None = None,
    reference_text: str | None = None,
    instructions: list[str] | None = None,
) -> str:
    """Build a JSON prompt string shaped like _build_prompt() output."""
    payload = {
        "agent": "dummy",
        "prompt_version": "v1",
        "document_chunks": document_chunks
        if document_chunks is not None
        else [{"chunk_id": "c1", "page_number": 1, "text": "doc text"}],
        "rubric_context": rubric_context if rubric_context is not None else [],
        "reference_context": (
            reference_context if reference_context is not None else []
        ),
        "reference_text": reference_text,
        "instructions": instructions
        if instructions is not None
        else [
            "Return JSON with summary and criterion_scores.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def test_prompt_under_budget_passes_through_unchanged() -> None:
    """A prompt that already fits the budget is returned untouched."""
    agent = _DummyAgent()
    prompt = _build_payload(
        rubric_context=["rubric-1"],
        reference_context=["ref-1"],
    )
    budget = len(prompt) + 1000  # generous

    result = agent._enforce_total_prompt_budget(prompt, budget_chars=budget)

    assert result.prompt == prompt
    assert result.trimmed is False
    assert result.reference_context_dropped == 0
    assert len(result.prompt) <= budget


def test_prompt_exactly_at_budget_passes_through_unchanged() -> None:
    """A prompt exactly at the budget boundary is not modified."""
    agent = _DummyAgent()
    prompt = _build_payload(
        rubric_context=["rubric-1"],
        reference_context=["ref-1"],
    )
    budget = len(prompt)  # exactly equal

    result = agent._enforce_total_prompt_budget(prompt, budget_chars=budget)

    assert result.prompt == prompt
    assert result.trimmed is False
    assert result.reference_context_dropped == 0
    assert len(result.prompt) == budget


def test_oversized_prompt_trims_reference_context_first() -> None:
    """When over budget, reference_context entries are dropped first."""
    agent = _DummyAgent()
    # Build 3 large reference entries and small rubric; over a tight budget.
    long_refs = [f"reference entry {i} " + ("X" * 500) for i in range(3)]
    prompt = _build_payload(
        rubric_context=["rubric-1", "rubric-2"],
        reference_context=long_refs,
    )
    # Set a budget that forces at least one reference to be dropped.
    budget = len(prompt) - 600

    result = agent._enforce_total_prompt_budget(prompt, budget_chars=budget)
    parsed = json.loads(result.prompt)

    # Trim was performed and 3 reference entries were dropped.
    assert result.trimmed is True
    assert result.reference_context_dropped == 3
    # Reference entries should be fully cleared.
    assert parsed["reference_context"] == []
    # Rubric context is preserved (we never needed to touch it).
    assert len(parsed["rubric_context"]) == 2
    assert parsed["rubric_context"] == ["rubric-1", "rubric-2"]
    # Result fits in budget (modulo pathological overhead we still cap at 400).
    assert len(result.prompt) <= budget + 100


def test_oversized_prompt_trims_rubric_context_after_references() -> None:
    """When reference drop is not enough, rubric_context is trimmed next."""
    agent = _DummyAgent()
    # Small reference (expendable) and several long rubric entries.
    long_rubrics = [f"rubric criterion {i} " + ("Y" * 500) for i in range(3)]
    prompt = _build_payload(
        rubric_context=long_rubrics,
        reference_context=["small ref"],
    )
    # Force a budget that requires dropping the reference AND at least one
    # rubric entry, but leaves the first rubric intact.
    # Rough size: 3 rubrics * 518 + small ref + JSON overhead ≈ 1700.
    budget = len(prompt) - 700

    result = agent._enforce_total_prompt_budget(prompt, budget_chars=budget)
    parsed = json.loads(result.prompt)

    # Trim fired and the single small reference was dropped.
    assert result.trimmed is True
    assert result.reference_context_dropped == 1
    # Then rubric entries are dropped from the end (some kept).
    assert 0 < len(parsed["rubric_context"]) < 3
    # The remaining rubric entries are the leading ones (front-preserving).
    assert parsed["rubric_context"][0].startswith("rubric criterion 0")


def test_individual_entry_truncation_when_dropping_not_enough() -> None:
    """When dropping all entries still leaves us over budget, surviving
    individual entries are truncated to ~400 chars + ellipsis."""
    agent = _DummyAgent()
    # Single huge entry that we cannot drop without losing everything.
    huge = "Z" * 5000
    prompt = _build_payload(
        rubric_context=[huge],
        reference_context=[],
    )
    # Budget that forces truncation: dropping the only rubric entry would
    # leave us with an empty prompt, so the safety net truncates it instead.
    budget = 800

    result = agent._enforce_total_prompt_budget(prompt, budget_chars=budget)
    parsed = json.loads(result.prompt)

    # The rubric entry was truncated, not dropped (we keep at least one).
    assert len(parsed["rubric_context"]) == 1
    truncated = parsed["rubric_context"][0]
    assert truncated.endswith("...")
    # Truncation respects the ~400-char cap.
    assert len(truncated) <= agent._ENTRY_TRUNCATE_CHARS
    # And the result fits within budget (plus minimal JSON overhead).
    assert len(result.prompt) <= budget + 50
    # No reference entries existed, so none were dropped.
    assert result.reference_context_dropped == 0
    # Trim still fired (truncation is a modification).
    assert result.trimmed is True


def test_entry_truncation_respects_cap_on_remaining_entries() -> None:
    """If we cannot drop everything, each remaining entry is capped at
    _ENTRY_TRUNCATE_CHARS, not the original entry size."""
    agent = _DummyAgent()
    large_entry = "A" * 2000
    prompt = _build_payload(
        rubric_context=[large_entry, large_entry, large_entry],
        reference_context=[large_entry],
    )
    # Very tight budget: must drop references, then truncate rubric entries.
    budget = 1500

    result = agent._enforce_total_prompt_budget(prompt, budget_chars=budget)
    parsed = json.loads(result.prompt)

    # References dropped first.
    assert parsed["reference_context"] == []
    assert result.reference_context_dropped == 1
    # Each remaining rubric entry must be at most the truncation cap.
    for entry in parsed["rubric_context"]:
        assert len(entry) <= agent._ENTRY_TRUNCATE_CHARS
        assert entry.endswith("...")


def test_invalid_json_returns_prompt_unchanged(caplog) -> None:
    """A non-JSON prompt cannot be trimmed; return as-is and log a warning."""
    agent = _DummyAgent()
    bad_prompt = "not valid json {{{" + "X" * 500
    caplog.set_level(logging.WARNING, logger="server.modules.agents.base")

    result = agent._enforce_total_prompt_budget(bad_prompt, budget_chars=100)

    assert result.prompt == bad_prompt
    assert result.trimmed is False
    assert result.reference_context_dropped == 0
    # A warning should be emitted with status=invalid_json.
    assert any(
        "EVAL_PROMPT_BUDGET" in r.message and "invalid_json" in r.message
        for r in caplog.records
    )


def test_non_object_payload_returns_prompt_unchanged(caplog) -> None:
    """A top-level JSON array (not a dict) cannot be safely trimmed."""
    agent = _DummyAgent()
    bad_prompt = json.dumps(["not", "a", "dict"] * 200)  # large array
    caplog.set_level(logging.WARNING, logger="server.modules.agents.base")

    result = agent._enforce_total_prompt_budget(bad_prompt, budget_chars=100)

    assert result.prompt == bad_prompt
    assert result.trimmed is False
    assert result.reference_context_dropped == 0
    assert any(
        "EVAL_PROMPT_BUDGET" in r.message
        and "non_object_payload" in r.message
        for r in caplog.records
    )


def test_trim_emits_warning_with_expected_fields(caplog) -> None:
    """The trim path should log a warning with original/trimmed/budget fields."""
    agent = _DummyAgent()
    long_refs = [f"ref {i} " + ("X" * 500) for i in range(3)]
    prompt = _build_payload(reference_context=long_refs)
    caplog.set_level(logging.WARNING, logger="server.modules.agents.base")

    agent._enforce_total_prompt_budget(prompt, budget_chars=600)

    warnings = [r for r in caplog.records if "EVAL_PROMPT_BUDGET" in r.message]
    assert len(warnings) == 1
    msg = warnings[0].message
    assert "agent=dummy" in msg
    assert "original=" in msg
    assert "trimmed=" in msg
    assert "budget=600" in msg


def test_no_trim_emits_no_budget_warning(caplog) -> None:
    """A prompt that already fits should NOT emit EVAL_PROMPT_BUDGET warning."""
    agent = _DummyAgent()
    prompt = _build_payload(reference_context=["small"])
    caplog.set_level(logging.WARNING, logger="server.modules.agents.base")

    agent._enforce_total_prompt_budget(prompt, budget_chars=100_000)

    assert not any("EVAL_PROMPT_BUDGET" in r.message for r in caplog.records)


# ------------------------------------------------------------------
# Integration: end-to-end run() wires the budget cap
# ------------------------------------------------------------------


def _patch_retrieval(monkeypatch) -> None:
    """Patch retrieval so we don't hit ChromaDB during the integration test."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )


def test_run_enforces_budget_when_prompt_oversized(monkeypatch, caplog) -> None:
    """When the assembled prompt exceeds the total budget, run() should
    call _enforce_total_prompt_budget and emit both EVAL_PROMPT_SIZE and
    EVAL_PROMPT_BUDGET logs."""
    caplog.set_level(logging.INFO, logger="server.modules.agents.base")
    _patch_retrieval(monkeypatch)

    # Force retrieval to return a large rubric context so the prompt
    # exceeds the configured total budget.
    huge_rubric = "R" * 5000

    def _huge_rubric(*args, **kwargs):
        return [huge_rubric, huge_rubric, huge_rubric]

    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context", _huge_rubric,
    )
    patch_settings(
        monkeypatch,
        agent_prompt_budget_chars=2000,
        agent_total_prompt_budget_chars=1500,  # very tight
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
    )

    # EVAL_PROMPT_SIZE log was emitted.
    size_logs = [r for r in caplog.records if "EVAL_PROMPT_SIZE" in r.message]
    assert any(
        "agent=dummy" in r.message and "prompt_chars=" in r.message
        for r in size_logs
    )
    # And the budget-trim warning fired.
    assert any(
        "EVAL_PROMPT_BUDGET" in r.message and "agent=dummy" in r.message
        for r in caplog.records
    )


def test_run_under_budget_logs_size_without_trim_warning(
    monkeypatch, caplog
) -> None:
    """When the prompt is within budget, EVAL_PROMPT_SIZE logs but no
    EVAL_PROMPT_BUDGET warning should fire."""
    caplog.set_level(logging.INFO, logger="server.modules.agents.base")
    _patch_retrieval(monkeypatch)
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda *args, **kwargs: ["tiny rubric"],
    )
    patch_settings(
        monkeypatch,
        agent_total_prompt_budget_chars=8000,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
    )

    # EVAL_PROMPT_SIZE log was emitted.
    size_logs = [r for r in caplog.records if "EVAL_PROMPT_SIZE" in r.message]
    assert any("prompt_chars=" in r.message for r in size_logs)
    # No EVAL_PROMPT_BUDGET warning (the prompt fit).
    assert not any(
        "EVAL_PROMPT_BUDGET" in r.message for r in caplog.records
    )


def test_run_drops_overgrown_reference_context(monkeypatch) -> None:
    """Integration: run() should drop overgrown reference_context entries
    when the prompt exceeds the total budget."""
    _patch_retrieval(monkeypatch)

    long_refs = [f"reference entry {i} " + ("X" * 500) for i in range(3)]

    def _long_refs(*args, **kwargs):
        return list(long_refs)

    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context", _long_refs,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda *args, **kwargs: [],
    )
    patch_settings(
        monkeypatch,
        agent_prompt_budget_chars=2000,
        agent_total_prompt_budget_chars=1500,
    )

    captured_prompts: list[str] = []

    class _CapturingLLM:
        def generate(self, prompt, *, temperature, max_new_tokens):
            captured_prompts.append(prompt)
            return json.dumps(
                {
                    "summary": "ok",
                    "criterion_scores": [
                        {"criterion_id": "c1", "score": 3, "justification": "ok"},
                    ],
                }
            )

    agent = _DummyAgent(llm_client=_CapturingLLM())
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
    )

    assert len(captured_prompts) == 1
    final_prompt = captured_prompts[0]
    # The prompt that reached the LLM fits within the total budget.
    assert len(final_prompt) <= 1500
    parsed = json.loads(final_prompt)
    # At least one reference was dropped.
    assert len(parsed["reference_context"]) < 3


# ------------------------------------------------------------------
# Metadata observability (Council R1)
# ------------------------------------------------------------------


def test_run_metadata_records_prompt_trimmed_and_dropped_count(
    monkeypatch,
) -> None:
    """When the prompt is trimmed, run() must record ``prompt_trimmed=True``
    and the count of dropped reference entries in metadata."""
    _patch_retrieval(monkeypatch)

    # Long reference entries to force budget enforcement to drop them.
    long_refs = [
        _RetrievedChunk(f"reference entry {i} " + ("X" * 500))
        for i in range(3)
    ]

    def _long_refs(*args, **kwargs):
        return list(long_refs)

    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context", _long_refs,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda *args, **kwargs: [],
    )
    patch_settings(
        monkeypatch,
        agent_prompt_budget_chars=2000,
        agent_total_prompt_budget_chars=1500,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
        reference_document_ids={"syllabus": uuid4()},
    )

    # Metadata must include the new observability fields.
    assert result.metadata["prompt_trimmed"] is True
    # All 3 reference entries were dropped.
    assert result.metadata["reference_context_dropped"] == 3
    # The pre-trim context sizes are still recorded (as the original sizes).
    assert result.metadata["reference_context_size"] == 3


def test_run_metadata_records_no_trim_when_under_budget(
    monkeypatch,
) -> None:
    """When the prompt fits the budget, run() must record
    ``prompt_trimmed=False`` and ``reference_context_dropped=0``."""
    _patch_retrieval(monkeypatch)
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda *args, **kwargs: ["small rubric"],
    )
    patch_settings(
        monkeypatch,
        agent_total_prompt_budget_chars=8000,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "small doc text"},
        ],
        context_text="query",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.metadata["prompt_trimmed"] is False
    assert result.metadata["reference_context_dropped"] == 0


def test_run_metadata_partial_drop_counts_only_actually_dropped(
    monkeypatch,
) -> None:
    """When only some reference entries are dropped, the count must reflect
    only the actual removals (not the surviving entries)."""
    _patch_retrieval(monkeypatch)

    # One huge reference (always dropped) and several moderate ones
    # (may or may not be dropped depending on budget pressure).
    long_refs = [
        _RetrievedChunk(f"reference entry {i} " + ("X" * 500))
        for i in range(3)
    ]

    def _long_refs(*args, **kwargs):
        return list(long_refs)

    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context", _long_refs,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda *args, **kwargs: [],
    )
    # Loose enough budget that references are dropped but we still record
    # exactly the count that disappeared.
    patch_settings(
        monkeypatch,
        agent_prompt_budget_chars=2000,
        agent_total_prompt_budget_chars=1500,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
        reference_document_ids={"syllabus": uuid4()},
    )

    # Trim fired (prompt was over budget).
    assert result.metadata["prompt_trimmed"] is True
    # Exactly 3 reference entries were dropped (the step clears all refs).
    assert result.metadata["reference_context_dropped"] == 3
    # The original count is still tracked separately.
    assert result.metadata["reference_context_size"] == 3
