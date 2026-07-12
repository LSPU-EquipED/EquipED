"""Tests for council-identified blockers (fixes 1–6)."""

from __future__ import annotations

import json
from uuid import uuid4

from server.core.config import get_settings
from server.core.exceptions import ConfigurationError
from server.modules.agents.itso import ITSOAgent
from server.modules.agents.provenance import sanitize_provenance

from .conftest import _FakeLLM, _mock_settings

# ---------------------------------------------------------------------------
# Fix 1: Benchmark harness must make zero DB/network calls
# ---------------------------------------------------------------------------


def _make_benchmark_chunks():
    return [
        {
            "chunk_id": "c1",
            "page_number": 1,
            "text": "Body text.\n\nReferences\nAuthor, A. (2020). Title.",
        },
    ]


class _BreakOnCallLLM:
    """Fake LLM that raises if any method is called beyond generate."""

    model = "fix-benchmark-model"

    def generate(self, prompt, *, temperature, max_new_tokens):
        return json.dumps(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "ITSO-01", "score": 3, "justification": "ok"},
                ],
            }
        )


def test_benchmark_no_db_calls(monkeypatch) -> None:
    """Benchmark-style agent run with precomputed_context should NOT
    reach the database for rubric or reference context.

    We monkeypatch the rubric/service and retrieval modules to raise.
    """
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("DB CALLED")),
    )
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("DB CALLED")),
    )

    agent = ITSOAgent(llm_client=_BreakOnCallLLM())
    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_make_benchmark_chunks(),
        provenance={
            "precheck_version": "1",
            "bibliography_found": True,
            "reference_count": 1,
        },
        precomputed_context={"rubric_itso": []},
    )
    assert result.success
    assert result.subtotal == 3.0


# ---------------------------------------------------------------------------
# Fix 2: Repair call captures actual model from repair LLM
# ---------------------------------------------------------------------------


class _FirstCallFailsLLM:
    """First call returns malformed JSON (triggers repair); second succeeds."""

    model = "initial-model"

    def __init__(self):
        self._call_count = 0

    def generate(self, prompt, *, temperature, max_new_tokens):
        self._call_count += 1
        if self._call_count == 1:
            return "truncated { bad json"
        return json.dumps(
            {
                "summary": "repaired",
                "criterion_scores": [
                    {
                        "criterion_id": "ITSO-01",
                        "score": 3,
                        "justification": "repaired",
                    },
                ],
            }
        )


def _make_bad_json_chunks():
    return [{"chunk_id": "c1", "page_number": 1, "text": "test content"}]


def test_repair_updates_actual_model(monkeypatch) -> None:
    """When repair succeeds, actual_model_used should reflect the model
    that produced the final answer. If the repair call returns a different
    model, provenance must reflect it.

    We monkey-patch the rubric/reference retrieval so the agent never
    touches the database, and also intercept _call_llm to simulate a
    first JSON-parse failure followed by a repair call on a fallback model.
    """
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )
    # Prevent any DB access by patching retrieve_context and rubric service.
    monkeypatch.setattr(
        "server.modules.rubrics.service.get_active_rubric_context",
        lambda *a, **kw: [],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *a, **kw: [],
    )

    agent = ITSOAgent(llm_client=_FakeLLM({"summary": "dummy", "criterion_scores": []}))
    call_log: list[tuple[str, str]] = []

    def _patched_call(prompt, temperature=None):
        if not call_log:
            # First call: return malformed JSON
            call_log.append(("first", "initial-model"))
            return "truncated { bad json", "initial-model"
        # Second (repair) call: return valid JSON from fallback model
        call_log.append(("repair", "repair-model"))
        return (
            json.dumps(
                {
                    "summary": "repaired",
                    "criterion_scores": [
                        {
                            "criterion_id": "ITSO-01",
                            "score": 2,
                            "justification": "fallback repair",
                        },
                    ],
                }
            ),
            "repair-model",
        )

    agent._call_llm = _patched_call

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_make_bad_json_chunks(),
        precomputed_context={"rubric_itso": []},
    )
    assert result.success
    assert result.provenance is not None
    # The final model_name should be "repair-model" (repair model)
    assert result.model_name == "repair-model"
    assert result.provenance["actual_model"] == "repair-model"
    assert result.provenance["fallback_occurred"] is True
    assert result.provenance["repair_occurred"] is True
    assert len(call_log) == 2


def test_repair_same_model_no_fallback_flag(monkeypatch) -> None:
    """When repair runs on the same model, fallback_occurred stays False."""
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )
    monkeypatch.setattr(
        "server.modules.rubrics.service.get_active_rubric_context",
        lambda *a, **kw: [],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *a, **kw: [],
    )

    class _SameModelLLM:
        model = "same-model"

        def generate(self, prompt, *, temperature, max_new_tokens):
            return '{"summary":"ok","criterion_scores":[]}'

    agent = ITSOAgent(llm_client=_SameModelLLM())
    call_count = [0]

    def _patched_call(prompt, temperature=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return "truncated { bad json", "same-model"
        return (
            json.dumps(
                {
                    "summary": "repaired",
                    "criterion_scores": [
                        {
                            "criterion_id": "ITSO-01",
                            "score": 3,
                            "justification": "same-model repair",
                        },
                    ],
                }
            ),
            "same-model",
        )

    agent._call_llm = _patched_call

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=_make_bad_json_chunks(),
        precomputed_context={"rubric_itso": []},
    )
    assert result.success
    assert result.provenance is not None
    assert result.model_name == "same-model"
    assert result.provenance["repair_occurred"] is True
    # When repair uses the same model as initial, fallback_occurred is False.
    assert result.provenance["fallback_occurred"] is False


# ---------------------------------------------------------------------------
# Fix 3: Bounded provenance chunk IDs
# ---------------------------------------------------------------------------


def test_chunk_ids_bounded_in_provenance(monkeypatch) -> None:
    """Provenance chunk_ids_ordered should be capped and include count/hash."""
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )

    # Make more chunks than the cap (64).
    many_chunks = [
        {"chunk_id": f"chunk-{i:04d}", "page_number": i, "text": f"text {i}"}
        for i in range(80)
    ]

    from server.modules.agents.supervisor import Supervisor

    sup = Supervisor(agents=[], db=None)
    result = sup._precompute_itso_context(many_chunks)
    prov = result["provenance"]
    assert prov is not None
    assert len(prov["chunk_ids_ordered"]) == 64  # capped
    assert prov["chunk_id_count"] == 80  # original count
    assert isinstance(prov["chunk_ids_hash"], str)
    assert len(prov["chunk_ids_hash"]) == 64  # SHA-256 hex


def test_chunk_ids_fewer_than_cap_not_truncated(monkeypatch) -> None:
    """Fewer than 64 chunks should not be truncated."""
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )

    few_chunks = [
        {"chunk_id": f"c{i}", "page_number": i, "text": f"text {i}"} for i in range(5)
    ]

    from server.modules.agents.supervisor import Supervisor

    sup = Supervisor(agents=[], db=None)
    result = sup._precompute_itso_context(few_chunks)
    prov = result["provenance"]
    assert prov is not None
    assert len(prov["chunk_ids_ordered"]) == 5
    assert prov["chunk_id_count"] == 5


def test_chunk_ids_hash_stable(monkeypatch) -> None:
    """Same chunk IDs should produce the same hash."""
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )

    chunks = [
        {"chunk_id": "a", "page_number": 1, "text": "x"},
        {"chunk_id": "b", "page_number": 2, "text": "y"},
    ]

    from server.modules.agents.supervisor import Supervisor

    sup = Supervisor(agents=[], db=None)
    r1 = sup._precompute_itso_context(chunks)
    r2 = sup._precompute_itso_context(chunks)
    assert r1["provenance"]["chunk_ids_hash"] == r2["provenance"]["chunk_ids_hash"]


# ---------------------------------------------------------------------------
# Fix 4: Provenance allowlist/schema enforcement
# ---------------------------------------------------------------------------


def test_sanitize_provenance_drops_unknown_keys() -> None:
    """sanitize_provenance should drop keys not in PROVENANCE_ALLOWLIST."""
    raw = {
        "bibliography_found": True,
        "reference_count": 5,
        "should_not_be_here": "secret",
        "api_key_provided": "abc123",
        "prompt_text": "some raw prompt",
    }
    sanitized = sanitize_provenance(raw)
    assert sanitized is not None
    assert "bibliography_found" in sanitized
    assert "reference_count" in sanitized
    assert "should_not_be_here" not in sanitized
    assert "api_key_provided" not in sanitized
    assert "prompt_text" not in sanitized


def test_sanitize_provenance_caps_string_length() -> None:
    """Long string values should be truncated to their max length."""
    raw = {
        "requested_model": "x" * 500,
        "actual_model": "y" * 500,
    }
    sanitized = sanitize_provenance(raw)
    assert sanitized is not None
    assert len(sanitized["requested_model"]) == 200
    assert len(sanitized["actual_model"]) == 200


def test_sanitize_provenance_caps_list_length() -> None:
    """List values should be capped to their max length."""
    raw = {
        "chunk_ids_ordered": [f"c{i}" for i in range(200)],
    }
    sanitized = sanitize_provenance(raw)
    assert sanitized is not None
    assert len(sanitized["chunk_ids_ordered"]) == 64


def test_sanitize_provenance_redacts_sensitive_strings() -> None:
    """Provenance containing sensitive substrings should return None."""
    raw = {
        "bibliography_found": True,
        "requested_model": "contains-api_key-in-path",
    }
    sanitized = sanitize_provenance(raw)
    assert sanitized is None


def test_sanitize_provenance_none_and_empty() -> None:
    """None and empty dict should return None."""
    assert sanitize_provenance(None) is None
    assert sanitize_provenance({}) is None


def test_sanitize_provenance_type_mismatch_dropped() -> None:
    """Values with wrong types should be dropped."""
    raw = {
        "bibliography_found": "yes",  # should be bool
        "reference_count": "five",  # should be int
        "coverage_ratio": "high",  # should be float
    }
    sanitized = sanitize_provenance(raw)
    assert sanitized == {} or sanitized is None


# ---------------------------------------------------------------------------
# Fix 5: Preserve frozen phase-1 provenance for ITSO failures
# ---------------------------------------------------------------------------


def test_failed_itso_preserves_phase1_provenance(monkeypatch) -> None:
    """When ITSO agent fails, the error result should carry phase-1 provenance."""
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_settings",
        lambda: _mock_settings(),
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )

    from server.modules.agents.supervisor import Supervisor

    class _FailingAgent:
        agent_name = "itso"

        def run(self, **kwargs):
            raise RuntimeError("deliberate failure")

    sup = Supervisor(
        agents=[_FailingAgent()],
        db=None,
    )

    # Replace prompt loading so tests don't need DB
    monkeypatch.setattr(
        sup,
        "_load_active_prompt_versions",
        lambda: {
            "itso": type("Row", (), {"version_id": uuid4(), "prompt_text": "test"})()
        },
    )
    # Replace precomputed_context
    monkeypatch.setattr(
        sup,
        "_build_precomputed_context",
        lambda *a, **kw: {},
    )

    result = sup.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=[
            type("Chunk", (), {"chunk_id": uuid4(), "page_number": 1, "text": "x"})(),
        ],
    )

    itso_result = next(r for r in result.agent_results if r.agent_name == "itso")
    assert not itso_result.success
    assert itso_result.provenance is not None
    assert "precheck_version" in itso_result.provenance
    assert "chunk_ids_ordered" in itso_result.provenance


# ---------------------------------------------------------------------------
# Fix 6: Reject negative LLM_TEMPERATURE_ITSO
# ---------------------------------------------------------------------------


def test_config_rejects_negative_itso_temperature(monkeypatch) -> None:
    """LLM_TEMPERATURE_ITSO < 0 should raise ConfigurationError."""
    from server.core import config as _config_mod

    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_TEMPERATURE_ITSO", "-0.1")
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "must be between 0.0" in str(exc)
    finally:
        get_settings.cache_clear()
