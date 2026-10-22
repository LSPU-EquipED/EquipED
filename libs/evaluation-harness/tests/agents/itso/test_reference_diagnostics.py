"""Missing public evidence is explained without exposing document or query data."""

import json
from types import SimpleNamespace

import pytest
from equiped_harness.agents.itso.execution import _references
from equiped_harness.exceptions import AgentExecutionError


def _context(*, attempts, search_attempts, source_attempts, errors=None):
    report = {
        "status": "completed",
        "scope": ["ITSO-01", "ITSO-02"],
        "attempts": attempts,
        "references": [
            {
                "query": "PRIVATE QUERY SENTINEL",
                "status": "unverified",
                "source_url": "https://private-sentinel.example/source",
                "title": "PRIVATE TITLE SENTINEL",
                "excerpt": "PRIVATE PASSAGE SENTINEL",
                "matched_fields": [],
                "mismatches": [],
                "search_attempts": search_attempts,
                "source_attempts": source_attempts,
                "errors": errors or [],
            }
        ],
    }
    return SimpleNamespace(
        precomputed_context={"public_reference_verification": (json.dumps(report),)}
    )


def test_no_candidate_failure_explains_counts_without_logging_source_data(caplog):
    context = _context(
        attempts={"search": 2, "source": 0},
        search_attempts=[{"candidate_count": 0}, {"candidate_count": 0}],
        source_attempts=[],
    )
    with pytest.raises(AgentExecutionError, match="usable public reference passage"):
        _references(context)
    assert "search_attempts=2 | candidates=0 | source_attempts=0" in caplog.text
    assert "PRIVATE" not in caplog.text
    assert "private-sentinel" not in caplog.text


def test_failed_source_retrieval_has_distinct_diagnostics(caplog):
    context = _context(
        attempts={"search": 1, "source": 3},
        search_attempts=[{"candidate_count": 3}],
        source_attempts=[
            {"reason": "http_error"},
            {"reason": "title_mismatch"},
            {"reason": "no_substantive_passage"},
        ],
    )
    with pytest.raises(AgentExecutionError, match="usable public reference passage"):
        _references(context)
    assert "candidates=3 | source_attempts=3" in caplog.text
    assert "source_http_errors=1 | title_mismatches=1 | no_passage=1" in caplog.text


def test_untrusted_optional_attempt_metadata_cannot_enter_logs(caplog):
    context = _context(
        attempts={"search": "PRIVATE COUNT SENTINEL", "source": -1},
        search_attempts=[None, {"candidate_count": True}],
        source_attempts=[None, {"reason": "PRIVATE REASON SENTINEL"}],
    )
    with pytest.raises(AgentExecutionError, match="usable public reference passage"):
        _references(context)
    assert "search_attempts=0 | candidates=0 | source_attempts=0" in caplog.text
    assert "PRIVATE" not in caplog.text


def test_provider_failure_counts_distinguish_search_outage_from_no_matches(caplog):
    context = _context(
        attempts={"search": 4, "source": 0},
        search_attempts=[{"candidate_count": 0}, {"candidate_count": 0}],
        source_attempts=[],
        errors=[
            "provider_http_error",
            "public_page_access_unavailable",
            "tool_deadline_exceeded",
            "PRIVATE ERROR SENTINEL",
        ],
    )
    with pytest.raises(AgentExecutionError, match="usable public reference passage"):
        _references(context)
    assert "provider_http_errors=1 | provider_access_errors=1" in caplog.text
    assert "provider_timeouts=1" in caplog.text
    assert "PRIVATE" not in caplog.text
