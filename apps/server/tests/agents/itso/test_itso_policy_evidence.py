"""Server adapter tests for library-owned policy plans and evidence projection."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from equiped_harness.agents.itso.contracts import ITSOExecutionContext
from equiped_harness.agents.itso.prompt import build_prompt
from equiped_harness.contracts.references import (
    PolicyEvidenceChunk,
    PolicyRetrievalResult,
)
from equiped_harness.policy import get_policy_plan

from server.modules.embeddings import policy_context
from server.modules.embeddings.policy_context import PolicyContextLoader
from server.tests.agents.itso.conftest_helper import make_itso_test_snapshot

CRITERIA = {
    "ITSO-03": "intellectual_property",
    "ITSO-04": "data_privacy",
    "ITSO-05": "academic_rights",
}


def _settings(enabled: bool = False):
    return SimpleNamespace(
        itso_policy_delivery_enabled=enabled,
        llm_api_base="http://127.0.0.1:8000/v1",
    )


def _itso_context(policy):
    return ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "text": "SLM text"},),
        policy_evidence=policy,
        form_snapshot=make_itso_test_snapshot(),
    )


def test_blocked_policy_skips_embedding_and_local_retrieval(monkeypatch):
    monkeypatch.setattr(policy_context, "get_settings", lambda: _settings())

    def fail(*args, **kwargs):
        raise AssertionError("blocked policy must not perform policy work")

    monkeypatch.setattr(PolicyContextLoader, "_compute_query_embedding", fail)
    monkeypatch.setattr(policy_context, "retrieve_policy_context", fail)
    result = PolicyContextLoader(db=object()).build_policy_context(
        get_policy_plan("itso", 3)
    )
    assert result.policy_evidence is None
    assert result.provenance["policy_delivery_state"] == "blocked"
    assert result.provenance["policy_retrieval_version"] == "1"
    per_criterion = result.provenance["policy_evidence"]
    assert set(per_criterion) == {"ITSO-03", "ITSO-04", "ITSO-05"}
    assert all(item["status"] == "unavailable" for item in per_criterion.values())
    assert all(item["chunk_count"] == 0 for item in per_criterion.values())
    assert all(len(item["provenance_hash"]) == 64 for item in per_criterion.values())
    assert "clause" not in str(per_criterion)
    assert "secret policy text" not in str(per_criterion)


def test_enabled_delivery_without_db_keeps_enabled_unavailable_provenance(monkeypatch):
    monkeypatch.setattr(policy_context, "get_settings", lambda: _settings(True))
    result = PolicyContextLoader(db=None).build_policy_context(
        get_policy_plan("itso", 3)
    )
    assert result.policy_evidence is None
    assert result.provenance["policy_delivery_state"] == "enabled"
    assert set(result.provenance["policy_evidence"]) == set(CRITERIA)
    assert all(
        item["status"] == "unavailable" and item["chunk_count"] == 0
        for item in result.provenance["policy_evidence"].values()
    )


def test_enabled_policy_reuses_embedding_and_supplies_explicit_areas(monkeypatch):
    monkeypatch.setattr(policy_context, "get_settings", lambda: _settings(True))
    loader = PolicyContextLoader(db=object())
    embeddings = []
    calls = []

    def embed(text):
        embeddings.append(text)
        return [1.0]

    def retrieve(areas, embedding, db, *, max_chunks):
        calls.append((areas, embedding, max_chunks))
        area = areas[0]
        chunk = PolicyEvidenceChunk("c1", "d1", "approved clause", area, 1, 2, 0.1)
        return PolicyRetrievalResult(area, "available", (chunk,), "a" * 64)

    monkeypatch.setattr(loader, "_compute_query_embedding", embed)
    monkeypatch.setattr(policy_context, "retrieve_policy_context", retrieve)
    result = loader.build_policy_context(get_policy_plan("itso", 3))

    assert embeddings == [
        "information security data privacy intellectual property academic rights"
    ]
    assert len(calls) == 3
    assert all(call[1] is calls[0][1] for call in calls)
    assert calls[0][0] == ("intellectual_property", "general_itso")
    assert calls[1][0] == ("data_privacy", "general_itso")
    assert result.policy_evidence["criteria"]["ITSO-03"]["chunks"][0]["text"] == (
        "approved clause"
    )
    assert result.provenance["policy_evidence"]["ITSO-03"]["provenance_hash"] == (
        "a" * 64
    )


def test_retrieval_failure_is_unavailable_and_other_criteria_continue(monkeypatch):
    monkeypatch.setattr(policy_context, "get_settings", lambda: _settings(True))
    loader = PolicyContextLoader(db=object())
    monkeypatch.setattr(loader, "_compute_query_embedding", lambda text: [1.0])
    seen = []

    def retrieve(areas, *_args, **_kwargs):
        seen.append(areas)
        if areas[0] == "data_privacy":
            raise RuntimeError("private failure detail")
        return PolicyRetrievalResult(areas[0], "unavailable", (), "c" * 64)

    monkeypatch.setattr(policy_context, "retrieve_policy_context", retrieve)
    result = loader.build_policy_context(get_policy_plan("itso", 3))
    assert seen == list(get_policy_plan("itso", 3).criteria_areas.values())
    assert all(
        item["status"] == "unavailable"
        for item in result.provenance["policy_evidence"].values()
    )
    assert "private failure detail" not in str(result.provenance)


def test_snapshot_is_recursively_immutable_and_provenance_is_opaque(monkeypatch):
    monkeypatch.setattr(policy_context, "get_settings", lambda: _settings(True))
    loader = PolicyContextLoader(db=object())
    monkeypatch.setattr(loader, "_compute_query_embedding", lambda text: [1.0])
    monkeypatch.setattr(
        policy_context,
        "retrieve_policy_context",
        lambda *args, **kwargs: PolicyRetrievalResult(
            "intellectual_property",
            "available",
            (
                PolicyEvidenceChunk(
                    "c", "d", "secret", "intellectual_property", 1, 1, 0.1
                ),
            ),
            "d" * 64,
        ),
    )
    result = loader.build_policy_context(get_policy_plan("itso", 3))
    assert set(result.provenance["policy_evidence"]) == set(CRITERIA)
    assert all(
        set(value) == {"status", "chunk_count", "provenance_hash"}
        for value in result.provenance["policy_evidence"].values()
    )
    with pytest.raises(TypeError):
        result.policy_evidence["criteria"] = {}
    with pytest.raises(TypeError):
        result.policy_evidence["criteria"]["ITSO-03"]["status"] = "x"
    with pytest.raises(AttributeError):
        result.policy_evidence["criteria"]["ITSO-03"]["chunks"].append({})


def test_itso_prompt_uses_available_clauses_and_suppresses_unavailable_text():
    plan = get_policy_plan("itso", 3)
    assert plan is not None
    results = {
        criterion_id: PolicyRetrievalResult(
            area,
            "available",
            (
                PolicyEvidenceChunk(
                    "c", "d", f"approved {criterion_id}", area, 1, 1, 0.1
                ),
            ),
            "a" * 64,
        )
        for criterion_id, area in CRITERIA.items()
    }
    from equiped_harness.policy import format_policy_snapshot

    evidence = format_policy_snapshot(plan, results, delivery_state="enabled")[
        "evidence"
    ]
    snapshot = make_itso_test_snapshot()
    criteria = [
        criterion for domain in snapshot.form.domains for criterion in domain.criteria
    ][2:]
    prompt = build_prompt(
        _itso_context(evidence), ordered_criteria=criteria, reference_context=[]
    )
    assert all(f"approved {criterion_id}" in str(prompt) for criterion_id in CRITERIA)

    blocked = format_policy_snapshot(plan, results, delivery_state="blocked")[
        "evidence"
    ]
    blocked_prompt = build_prompt(
        _itso_context(blocked), ordered_criteria=criteria, reference_context=[]
    )
    assert 'local_policy_status": "unavailable"' in blocked_prompt.user_context
    assert "approved ITSO-03" not in str(blocked_prompt)
