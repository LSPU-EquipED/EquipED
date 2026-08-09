"""Contract tests for ITSO policy evidence."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from server.modules.agents.itso.evidence import ITSOEvidenceBuilder
from server.modules.agents.itso.prompt import build_prompt
from server.modules.agents.runtime.context import ITSOExecutionContext
from server.modules.embeddings.policy_retrieval import (
    PolicyEvidenceChunk,
    PolicyRetrievalResult,
)

CRITERIA = {
    "ITSO-03": "intellectual_property",
    "ITSO-04": "data_privacy",
    "ITSO-05": "academic_rights",
}


def _settings(enabled=False):
    return SimpleNamespace(
        itso_policy_delivery_enabled=enabled,
        agent_max_chunks=10,
        agent_max_excerpt_chars=1000,
        agent_prompt_budget_chars=10000,
        agent_small_doc_threshold=20,
    )


def _context(policy):
    return ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "text": "SLM text"},),
        policy_evidence=policy,
    )


def _available_snapshot():
    criteria = {
        cid: {
            "policy_area": area,
            "status": "available",
            "chunks": [{"text": f"clause {cid}"}],
        }
        for cid, area in CRITERIA.items()
    }
    return {
        "evidence": {
            "delivery_state": "enabled",
            "retrieval_version": "1",
            "criteria": criteria,
        },
        "provenance": {
            cid: {
                "status": "available",
                "chunk_count": 1,
                "provenance_hash": "a" * 64,
            }
            for cid in CRITERIA
        },
        "delivery_state": "enabled",
        "retrieval_version": "1",
    }


@pytest.mark.parametrize("settings", [_settings(False), SimpleNamespace()])
def test_blocked_policy_does_no_embedding_or_retrieval(monkeypatch, settings):
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.get_settings", lambda: settings
    )

    def fail(*args, **kwargs):
        pytest.fail("blocked policy must not perform policy work")

    monkeypatch.setattr(ITSOEvidenceBuilder, "_compute_query_embedding", fail)
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.retrieve_policy_context", fail
    )
    snapshot = ITSOEvidenceBuilder(db=object()).build(
        [{"chunk_id": "x", "text": "text"}]
    )
    assert snapshot.policy_evidence is None
    assert snapshot.provenance["policy_delivery_state"] == "blocked"
    assert snapshot.provenance["policy_retrieval_version"] == "1"
    policy_provenance = snapshot.provenance["policy_evidence"]
    assert all(
        item["status"] == "unavailable"
        and item["chunk_count"] == 0
        and len(item["provenance_hash"]) == 64
        and item["provenance_hash"] == item["provenance_hash"].lower()
        for item in policy_provenance.values()
    )
    assert set(policy_provenance) == set(CRITERIA)
    safe_provenance = {key: dict(value) for key, value in policy_provenance.items()}
    assert all(
        secret not in str(safe_provenance)
        for secret in ("clause", "text", "x")
    )


def test_enabled_delivery_without_db_is_blocked_from_retrieval(monkeypatch):
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.get_settings", lambda: _settings(True)
    )
    snapshot = ITSOEvidenceBuilder(db=None).build([{"chunk_id": "x", "text": "text"}])
    assert snapshot.policy_evidence is None
    assert snapshot.provenance["policy_delivery_state"] == "enabled"
    assert set(snapshot.provenance["policy_evidence"]) == set(CRITERIA)
    assert all(
        item["status"] == "unavailable" and item["chunk_count"] == 0
        for item in snapshot.provenance["policy_evidence"].values()
    )


def test_enabled_delivery_groups_concrete_clauses(monkeypatch):
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.get_settings", lambda: _settings(True)
    )
    monkeypatch.setattr(
        ITSOEvidenceBuilder, "_compute_query_embedding", lambda self, text: [1.0]
    )

    def retrieve(criterion_id, embedding, db, *, max_chunks):
        area = CRITERIA[criterion_id]
        chunk = PolicyEvidenceChunk(
            criterion_id + "-chunk", "doc", "approved " + criterion_id,
            area, 1, 2, 0.1,
        )
        return PolicyRetrievalResult(area, "available", (chunk,), "b" * 64)

    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.retrieve_policy_context", retrieve
    )
    snapshot = ITSOEvidenceBuilder(db=object())._build_policy_evidence_snapshot()
    assert {
        key: value["policy_area"]
        for key, value in snapshot["evidence"]["criteria"].items()
    } == CRITERIA
    prompt = build_prompt(
        _context(snapshot["evidence"]), rubric_context=[], reference_context=[]
    )
    assert all("approved " + cid in prompt for cid in CRITERIA)


def test_one_embedding_object_is_reused_for_all_retrievals(monkeypatch):
    builder = ITSOEvidenceBuilder(db=object())
    embeddings = []
    retrievals = []
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.get_settings", lambda: _settings(True)
    )

    def embed(text):
        embedding = [1.0]
        embeddings.append(embedding)
        return embedding

    def retrieve(criterion_id, embedding, db, **kwargs):
        retrievals.append((criterion_id, embedding))
        raise RuntimeError("unavailable")

    monkeypatch.setattr(builder, "_compute_query_embedding", embed)
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.retrieve_policy_context", retrieve
    )
    builder.build([{"chunk_id": "x", "text": "text"}])
    assert len(embeddings) == 1
    assert len(retrievals) == 3
    assert all(embedding is embeddings[0] for _, embedding in retrievals)


def test_retrieval_failure_is_unavailable_and_other_criteria_continue(monkeypatch):
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.get_settings", lambda: _settings(True)
    )
    monkeypatch.setattr(
        ITSOEvidenceBuilder, "_compute_query_embedding", lambda self, text: [1.0]
    )
    seen = []

    def retrieve(criterion_id, *args, **kwargs):
        seen.append(criterion_id)
        if criterion_id == "ITSO-04":
            raise RuntimeError("failure")
        return PolicyRetrievalResult("area", "unavailable", (), "c" * 64)

    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.retrieve_policy_context", retrieve
    )
    result = ITSOEvidenceBuilder(db=object())._build_policy_evidence_snapshot()
    assert seen == list(CRITERIA)
    assert all(result["provenance"][cid]["status"] == "unavailable" for cid in seen)


def test_provenance_is_opaque_exact_schema():
    provenance = _available_snapshot()["provenance"]
    assert set(provenance) == set(CRITERIA)
    assert all(
        set(item) == {"status", "chunk_count", "provenance_hash"}
        for item in provenance.values()
    )
    assert "clause" not in str(provenance).lower()


def test_blocked_and_unavailable_prompt_has_no_clause_text():
    policy = _available_snapshot()["evidence"] | {"delivery_state": "blocked"}
    prompt = build_prompt(_context(policy), rubric_context=[], reference_context=[])
    assert "approved ITSO" not in prompt
    assert "delivery_blocked" in prompt
    unavailable = {
        "delivery_state": "enabled",
        "criteria": {
            cid: {"policy_area": "area", "status": "unavailable", "chunks": []}
            for cid in CRITERIA
        },
    }
    assert "UNAVAILABLE" in build_prompt(
        _context(unavailable), rubric_context=[], reference_context=[]
    )


def test_builder_snapshot_is_recursively_immutable(monkeypatch):
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.get_settings", lambda: _settings(True)
    )
    monkeypatch.setattr(
        ITSOEvidenceBuilder, "_compute_query_embedding", lambda self, text: [1.0]
    )
    monkeypatch.setattr(
        "server.modules.agents.itso.evidence.retrieve_policy_context",
        lambda *args, **kwargs: PolicyRetrievalResult(
            "area",
            "available",
            (PolicyEvidenceChunk("c", "d", "secret", "area", 1, 1, 0.1),),
            "d" * 64,
        ),
    )
    snapshot = ITSOEvidenceBuilder(db=object()).build(
        [{"chunk_id": "x", "text": "text"}]
    )
    with pytest.raises(TypeError):
        snapshot.policy_evidence["criteria"] = {}
    with pytest.raises(TypeError):
        snapshot.policy_evidence["criteria"]["ITSO-03"]["status"] = "x"
    with pytest.raises(AttributeError):
        snapshot.policy_evidence["criteria"]["ITSO-03"]["chunks"].append({})
