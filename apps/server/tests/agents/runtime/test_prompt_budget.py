"""Tests for the end-to-end total-prompt budget cap.

The total-prompt budget is the final safety net that prevents the
assembled prompt (document_chunks + rubric_context + reference_context +
reference_text + instructions) from exceeding remote LLM provider request
limits (e.g. Groq HTTP 413 "Request too large" / TPM rate limit).

These tests exercise the `_enforce_total_prompt_budget` method on
the runtime prompt-budget helper directly, with no real LLM calls. It takes a JSON
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

from equiped_harness.runtime.model import CompletionResult, ResponseContract
from equiped_harness.runtime.prompt_budget import enforce_total_prompt_budget

from server.tests.agents.helpers import (
    _DummyAgent,
    _FakeLLM,
    patch_settings,
)
from server.tests.agents.runtime.response_helpers import itso_response

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
    prompt = _build_payload(
        rubric_context=["rubric-1"],
        reference_context=["ref-1"],
    )
    budget = len(prompt) + 1000  # generous

    result = enforce_total_prompt_budget(
        prompt, budget_chars=budget, agent_name="dummy"
    )

    assert result.prompt == prompt
    assert result.trimmed is False
    assert result.reference_context_dropped == 0
    assert len(result.prompt) <= budget


def test_prompt_exactly_at_budget_passes_through_unchanged() -> None:
    """A prompt exactly at the budget boundary is not modified."""
    prompt = _build_payload(
        rubric_context=["rubric-1"],
        reference_context=["ref-1"],
    )
    budget = len(prompt)  # exactly equal

    result = enforce_total_prompt_budget(
        prompt, budget_chars=budget, agent_name="dummy"
    )

    assert result.prompt == prompt
    assert result.trimmed is False
    assert result.reference_context_dropped == 0
    assert len(result.prompt) == budget


def test_oversized_prompt_trims_reference_context_first() -> None:
    """When over budget, reference_context entries are dropped first."""
    # Build 3 large reference entries and small rubric; over a tight budget.
    long_refs = [f"reference entry {i} " + ("X" * 500) for i in range(3)]
    prompt = _build_payload(
        rubric_context=["rubric-1", "rubric-2"],
        reference_context=long_refs,
    )
    # Set a budget that forces at least one reference to be dropped.
    budget = len(prompt) - 600

    result = enforce_total_prompt_budget(
        prompt, budget_chars=budget, agent_name="dummy"
    )
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

    result = enforce_total_prompt_budget(
        prompt, budget_chars=budget, agent_name="dummy"
    )
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
    # Single huge entry that we cannot drop without losing everything.
    huge = "Z" * 5000
    prompt = _build_payload(
        rubric_context=[huge],
        reference_context=[],
    )
    # Budget that forces truncation: dropping the only rubric entry would
    # leave us with an empty prompt, so the safety net truncates it instead.
    budget = 800

    result = enforce_total_prompt_budget(
        prompt, budget_chars=budget, agent_name="dummy"
    )
    parsed = json.loads(result.prompt)

    # The rubric entry was truncated, not dropped (we keep at least one).
    assert len(parsed["rubric_context"]) == 1
    truncated = parsed["rubric_context"][0]
    assert truncated.endswith("...")
    # Truncation respects the ~400-char cap.
    assert len(truncated) <= 400
    # And the result fits within budget (plus minimal JSON overhead).
    assert len(result.prompt) <= budget + 50
    # No reference entries existed, so none were dropped.
    assert result.reference_context_dropped == 0
    # Trim still fired (truncation is a modification).
    assert result.trimmed is True


def test_entry_truncation_respects_cap_on_remaining_entries() -> None:
    """If we cannot drop everything, each remaining entry is capped at
    _ENTRY_TRUNCATE_CHARS, not the original entry size."""
    large_entry = "A" * 2000
    prompt = _build_payload(
        rubric_context=[large_entry, large_entry, large_entry],
        reference_context=[large_entry],
    )
    # Very tight budget: must drop references, then truncate rubric entries.
    budget = 1500

    result = enforce_total_prompt_budget(
        prompt, budget_chars=budget, agent_name="dummy"
    )
    parsed = json.loads(result.prompt)

    # References dropped first.
    assert parsed["reference_context"] == []
    assert result.reference_context_dropped == 1
    # Each remaining rubric entry must be at most the truncation cap.
    for entry in parsed["rubric_context"]:
        assert len(entry) <= 400
        assert entry.endswith("...")


def test_invalid_json_returns_prompt_unchanged(caplog) -> None:
    """A non-JSON prompt cannot be trimmed; return as-is and log a warning."""
    bad_prompt = "not valid json {{{" + "X" * 500
    caplog.set_level(logging.WARNING)

    result = enforce_total_prompt_budget(bad_prompt, budget_chars=100)

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
    bad_prompt = json.dumps(["not", "a", "dict"] * 200)  # large array
    caplog.set_level(logging.WARNING, logger="equiped_harness.runtime.prompt_budget")

    result = enforce_total_prompt_budget(bad_prompt, budget_chars=100)

    assert result.prompt == bad_prompt
    assert result.trimmed is False
    assert result.reference_context_dropped == 0
    assert any(
        "EVAL_PROMPT_BUDGET" in r.message and "non_object_payload" in r.message
        for r in caplog.records
    )


def test_trim_emits_warning_with_expected_fields(caplog) -> None:
    """The trim path should log a warning with original/trimmed/budget fields."""
    long_refs = [f"ref {i} " + ("X" * 500) for i in range(3)]
    prompt = _build_payload(reference_context=long_refs)
    caplog.set_level(logging.WARNING, logger="equiped_harness.runtime.prompt_budget")

    enforce_total_prompt_budget(prompt, budget_chars=600, agent_name="dummy")

    warnings = [r for r in caplog.records if "EVAL_PROMPT_BUDGET" in r.message]
    assert len(warnings) == 1
    msg = warnings[0].message
    assert "agent=dummy" in msg
    assert "original=" in msg
    assert "trimmed=" in msg
    assert "budget=600" in msg


def test_no_trim_emits_no_budget_warning(caplog) -> None:
    """A prompt that already fits should NOT emit EVAL_PROMPT_BUDGET warning."""
    prompt = _build_payload(reference_context=["small"])
    caplog.set_level(logging.WARNING, logger="equiped_harness.runtime.prompt_budget")

    enforce_total_prompt_budget(prompt, budget_chars=100_000)

    assert not any("EVAL_PROMPT_BUDGET" in r.message for r in caplog.records)


# ------------------------------------------------------------------
# Integration: end-to-end run() wires the budget cap
# ------------------------------------------------------------------


def _patch_retrieval(monkeypatch) -> None:
    """No-op helper retained for compatibility."""
    pass


def test_run_reports_budget_for_each_adapter3_envelope(
    monkeypatch, caplog, harness_config
) -> None:
    """The prepared report and context fit each adapter-3 envelope cap."""
    caplog.set_level(logging.INFO)
    _patch_retrieval(monkeypatch)

    huge_ref = "R" * 5000
    patch_settings(
        monkeypatch,
        harness_config,
        agent_prompt_budget_chars=5000,
        agent_total_prompt_budget_chars=12000,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(itso_response()),
    )

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
        precomputed_context={"syllabus": [huge_ref, huge_ref, huge_ref]},
    )

    # EVAL_PROMPT_SIZE log was emitted.
    size_logs = [r for r in caplog.records if "EVAL_PROMPT_SIZE" in r.message]
    assert any(
        "agent=itso" in r.message and "prompt_chars=" in r.message for r in size_logs
    )
    # Adapter 3 budgets both envelopes independently; the prepared report and
    # bounded reference inputs leave each prompt below this test's limit.
    assert len(size_logs) == 2
    assert all("trimmed=no" in r.message for r in size_logs)
    assert all("budget=12000" in r.message for r in size_logs)


def test_run_under_budget_logs_size_without_trim_warning(
    monkeypatch, caplog, harness_config
) -> None:
    """When the prompt is within budget, EVAL_PROMPT_SIZE logs but no
    EVAL_PROMPT_BUDGET warning should fire."""
    caplog.set_level(logging.INFO)
    _patch_retrieval(monkeypatch)
    patch_settings(
        monkeypatch,
        harness_config,
        agent_total_prompt_budget_chars=12000,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(itso_response()),
    )

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
        precomputed_context={"syllabus": ["tiny ref"]},
    )

    # EVAL_PROMPT_SIZE log was emitted.
    size_logs = [r for r in caplog.records if "EVAL_PROMPT_SIZE" in r.message]
    assert any("prompt_chars=" in r.message for r in size_logs)
    # No EVAL_PROMPT_BUDGET warning (the prompt fit).
    assert not any("EVAL_PROMPT_BUDGET" in r.message for r in caplog.records)


def test_run_bounds_both_adapter3_envelopes(monkeypatch, harness_config) -> None:
    """Both prepared adapter-3 envelopes stay within the configured cap."""
    _patch_retrieval(monkeypatch)

    long_refs = [f"reference entry {i} " + ("X" * 500) for i in range(3)]
    patch_settings(
        monkeypatch,
        harness_config,
        agent_prompt_budget_chars=5000,
        agent_total_prompt_budget_chars=12000,
    )

    captured_prompts: list[str] = []

    class _CapturingLLM:
        def generate(self, prompt, *, temperature, max_new_tokens):
            captured_prompts.append(prompt)
            return json.dumps(itso_response())

        def generate_result(
            self,
            prompt,
            *,
            temperature,
            max_new_tokens,
            deadline=None,
            response_contract,
        ):
            assert response_contract == ResponseContract.json_object()
            from server.tests.agents.itso.conftest_helper import v3_response_for_prompt

            captured_prompts.append(prompt)
            content = v3_response_for_prompt(
                prompt,
                json.dumps(itso_response()),
                generate_valid_evidence=True,
            )
            return CompletionResult(
                content,
                "fake-model",
                finish_reason="stop",
            )

    agent = _DummyAgent(llm_client=_CapturingLLM())
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
        precomputed_context={"syllabus": long_refs},
    )

    assert len(captured_prompts) == 2
    for prompt in captured_prompts:
        assert len(prompt.render_flat()) <= 12000
        payload = json.loads(prompt.user_context)
        ids = {
            row["criterion_id"]
            for row in payload["response_example"]["criterion_scores"]
        }
        if ids <= {"ITSO-01", "ITSO-02"}:
            assert payload["public_reference_verification"]["status"] == "completed"


# ------------------------------------------------------------------
# Metadata observability (Council R1)
# ------------------------------------------------------------------


def test_run_metadata_records_prompt_trimmed_and_dropped_count(
    monkeypatch,
    harness_config,
) -> None:
    """Adapter-3 prompt metadata records the stable prepared reference inputs."""
    _patch_retrieval(monkeypatch)

    # These references fit with the mandatory report and repair reserve.
    long_refs = [f"reference entry {i} " + ("X" * 500) for i in range(3)]
    patch_settings(
        monkeypatch,
        harness_config,
        agent_prompt_budget_chars=5000,
        agent_total_prompt_budget_chars=12000,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(itso_response()),
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
        reference_document_ids={"syllabus": uuid4()},
        precomputed_context={"syllabus": long_refs},
    )

    # Metadata must include the new observability fields.
    assert result.metadata["prompt_trimmed"] is False
    assert result.metadata["reference_context_dropped"] == 0
    # The pre-trim context sizes are still recorded (as the original sizes).
    assert result.metadata["reference_context_size"] == 4


def test_run_metadata_records_no_trim_when_under_budget(
    monkeypatch,
    harness_config,
) -> None:
    """When the prompt fits the budget, run() must record
    ``prompt_trimmed=False`` and ``reference_context_dropped=0``."""
    _patch_retrieval(monkeypatch)
    patch_settings(
        monkeypatch,
        harness_config,
        agent_total_prompt_budget_chars=12000,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(itso_response()),
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "small doc text"},
        ],
        context_text="query",
        reference_document_ids={"syllabus": uuid4()},
        precomputed_context={"syllabus": ["small reference"]},
    )

    assert result.metadata["prompt_trimmed"] is False
    assert result.metadata["reference_context_dropped"] == 0


def test_run_metadata_counts_prepared_reference_report(
    monkeypatch,
    harness_config,
) -> None:
    """Metadata counts only references actually removed by adapter-3 packing."""
    _patch_retrieval(monkeypatch)

    long_refs = [f"reference entry {i} " + ("X" * 500) for i in range(3)]
    patch_settings(
        monkeypatch,
        harness_config,
        agent_prompt_budget_chars=5000,
        agent_total_prompt_budget_chars=12000,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(itso_response()),
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "c1", "page_number": 1, "text": "doc text"},
        ],
        context_text="query",
        reference_document_ids={"syllabus": uuid4()},
        precomputed_context={"syllabus": long_refs},
    )

    assert result.metadata["prompt_trimmed"] is False
    assert result.metadata["reference_context_dropped"] == 0
    # The original count is still tracked separately.
    assert result.metadata["reference_context_size"] == 4
