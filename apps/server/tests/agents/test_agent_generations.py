"""Tests for agent generations capture and persistence across all 4 agents."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from server.core.llm import get_llm_model_name
from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.gad.agent import GAD
from server.modules.agents.itso import execution as itso_execution
from server.modules.agents.runtime.context import ITSOExecutionContext
from server.modules.agents.runtime.llm import RunLLMClient
from server.modules.agents.sme.agent import SME
from server.modules.agents.sme.packing import pack_domains
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.models import AgentGeneration
from server.modules.synthesis.service import persist_agent_outputs
from server.tests.agents.coordinator.test_coordinator_agent import (
    CURRICULUM,
    SOURCE,
    TEN,
    _envelope_response,
)
from server.tests.agents.helpers import SequencedFakeClient, make_coordinator_snapshot
from server.tests.agents.itso.conftest_helper import make_itso_test_snapshot
from server.tests.agents.itso.test_itso_execution import (
    _LLM,
    _context,
    _response,
    _settings,
)
from server.tests.agents.sme.test_sme_run import (
    MockLLM,
    _make_snapshot,
    _valid_payload_for_d1,
    _valid_payload_for_d2,
)
from server.tests.rubrics.helpers import seed_all_rubrics

_SME_SAMPLE_TEXT = (
    "Unit 1 Topic A. Unit 2 Topic B. "
    "Interactive practice task. Accurate section details."
)


def test_sme_emits_generations():
    eval_id = uuid4()
    doc_id = uuid4()
    snapshot = _make_snapshot(eval_id)
    client = MockLLM([_valid_payload_for_d1(), _valid_payload_for_d2()])

    sme = SME(llm_client=client)
    result = sme.run(
        evaluation_id=eval_id,
        document_id=doc_id,
        chunk_infos=[{"chunk_id": "c1", "text": _SME_SAMPLE_TEXT}],
        canonical_source_text=_SME_SAMPLE_TEXT,
        form_snapshot=snapshot,
    )

    assert result.success is True
    assert len(result.generations) == 2
    g1, g2 = result.generations

    assert g1.unit_key == "envelope_0"
    assert g1.criterion_ids == ("OP-01", "OP-02")
    assert g1.response_contract_key == "criterion_measurements.v1"
    assert g1.response_contract_version == 1
    assert g1.envelope_status == "ok"
    assert g1.model_name == client.model
    assert "Topic A" in g1.prompt_text
    assert g1.response_json is not None
    assert g1.response_text == json.dumps(g1.response_json, ensure_ascii=False)
    assert g1.prompt_messages is not None
    assert len(g1.prompt_messages) == 2

    assert g2.unit_key == "envelope_1"
    assert g2.criterion_ids == ("A-01", "A-02")
    assert g2.response_contract_key == "criterion_measurements.v1"
    assert g2.envelope_status == "ok"


def test_coordinator_emits_generations():
    snap, titles = make_coordinator_snapshot()
    raw_responses = [
        _envelope_response(TEN[:5], titles),
        _envelope_response(TEN[5:9], titles),
        _envelope_response(TEN[9:], titles),
    ]
    fake = SequencedFakeClient(raw_responses)
    fake.model = get_llm_model_name()
    client = RunLLMClient(fake, "coordinator", requested_model="test-model")

    coord = Coordinator()
    result = coord.run(
        evaluation_id=snap.evaluation_id,
        document_id=uuid4(),
        form_snapshot=snap,
        chunk_infos=[{"chunk_id": str(uuid4()), "text": SOURCE}],
        canonical_source_text=SOURCE,
        curriculum_id=uuid4(),
        curriculum_context=CURRICULUM,
        llm_client=client,
    )

    assert result.success is True
    assert len(result.generations) == 3
    for idx, (gen, expected_codes) in enumerate(
        zip(result.generations, (TEN[:5], TEN[5:9], TEN[9:]), strict=False)
    ):
        assert gen.unit_key == f"envelope_{idx}"
        assert gen.criterion_ids == expected_codes
        assert gen.response_contract_key == "criterion_measurements.v1"
        assert gen.response_contract_version == 1
        assert gen.envelope_status == "ok"
        assert gen.model_name == client.model
        assert "photosynthesis" in gen.prompt_text
        assert gen.response_json is not None
        assert gen.response_text == json.dumps(gen.response_json, ensure_ascii=False)
        assert gen.prompt_messages is not None
        assert len(gen.prompt_messages) == 2


def test_gad_emits_generations():
    from server.tests.agents.gad.test_snapshot_adapter import (
        _CHUNKS,
        _MockLLM,
        make_gad_snapshot,
    )

    eval_id = uuid4()
    doc_id = uuid4()
    snapshot = make_gad_snapshot(evaluation_id=eval_id)

    response_payload = {
        "gad-01": {
            "instance_count": 0,
            "instances": [],
            "summary": "No stereotypes.",
        },
        "gad-02": {
            "female_count": 1,
            "male_count": 1,
            "summary": "Balanced representation.",
        },
        "gad-03": {
            "instance_count": 0,
            "instances": [],
            "summary": "Equal respect maintained.",
        },
        "gad-04": {
            "instance_count": 0,
            "instances": [],
            "summary": "Needs reflected equally.",
        },
        "gad-05": {
            "instance_count": 0,
            "instances": [],
            "summary": "Promotes peace and equality.",
        },
    }

    mock_llm = _MockLLM([json.dumps(response_payload)])
    gad = GAD(llm_client=mock_llm)

    result = gad.run(
        evaluation_id=eval_id,
        document_id=doc_id,
        chunk_infos=_CHUNKS,
        form_snapshot=snapshot,
    )

    assert result.success is True
    assert len(result.generations) == 1
    g = result.generations[0]
    assert g.unit_key == "envelope_0"
    expected_cids = tuple(
        c.criterion_code for d in snapshot.form.domains for c in d.criteria
    )
    assert g.criterion_ids == expected_cids
    assert g.response_contract_key == "gad_extraction.v1"
    assert g.response_contract_version == 1
    assert g.envelope_status == "ok"
    assert g.model_name == mock_llm.model
    assert len(g.prompt_text) > 0
    assert g.response_json == response_payload
    assert g.response_text == json.dumps(response_payload, ensure_ascii=False)


def test_itso_emits_generations(monkeypatch):
    monkeypatch.setattr(itso_execution, "get_settings", lambda: _settings())
    client = _LLM([_response("ok")])
    eval_id = uuid4()
    snapshot = make_itso_test_snapshot(evaluation_id=eval_id)
    context = _context(client, form_snapshot=snapshot, evaluation_id=eval_id)

    result = itso_execution.execute(context)

    assert result.success is True
    assert len(result.generations) == 1
    g = result.generations[0]
    assert g.unit_key == "envelope_0"
    assert g.criterion_ids == tuple(s.criterion_id for s in result.criterion_scores)
    assert g.response_contract_key == "itso_scores.v1"
    assert g.response_contract_version == 1
    assert g.envelope_status == "ok"
    assert g.model_name == client.model
    assert len(g.prompt_text) > 0
    assert g.response_json is not None
    assert g.response_text == json.dumps(g.response_json, ensure_ascii=False)


def test_persist_agent_outputs_persists_generations_for_all_four_agents(
    db_session, seeded_user
):
    document_id = uuid4()
    chunk_id = uuid4()
    chunk_id_str = str(chunk_id)
    db_session.add(
        Document(
            document_id=document_id,
            title="all_agents_doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=seeded_user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.add(
        DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="itso",
            chunk_index=0,
            text="Topic A. Interactive practice task. security. " * 3,
            page_number=1,
        )
    )
    db_session.flush()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=document_id,
        submitted_by=seeded_user.user_id,
        status="COMPLETED",
    )
    db_session.add(job)
    db_session.flush()

    seed_all_rubrics(db_session)
    agent_ids = ("sme", "coordinator", "gad", "itso")
    snap_tuple = resolve_or_reuse_evaluation_snapshots(
        db_session, job.evaluation_id, agent_ids
    )
    snapshots = dict(zip(agent_ids, snap_tuple, strict=True))
    db_session.commit()

    # 1. SME
    sme_snap = snapshots["sme"]
    sme_source = "Excerpt from educational material. " * 5
    envelopes = pack_domains(sme_snap.form.domains)

    count_codes = {"OP-02", "OP-05", "A-02", "A-03", "A-04"}

    def _sme_criterion_payload(c):
        if c.criterion_code in count_codes:
            return {
                "criterion_id": c.criterion_code,
                "criterion_title": c.title,
                "instances": [{"excerpt": "Excerpt from educational material."}],
            }
        return {
            "criterion_id": c.criterion_code,
            "criterion_title": c.title,
            "total_units": [
                {
                    "unit_id": "u1",
                    "evidence": "Excerpt from educational material.",
                }
            ],
            "qualifying_unit_ids": ["u1"],
            "has_measurable_content": True,
        }

    sme_responses = [
        json.dumps(
            {
                "summary": f"Env {idx} summary",
                "criterion_measurements": [
                    _sme_criterion_payload(c) for c in env
                ],
            }
        )
        for idx, env in enumerate(envelopes)
    ]
    sme_client = MockLLM(sme_responses)
    sme = SME(llm_client=sme_client)
    sme_res = sme.run(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        chunk_infos=[{"chunk_id": chunk_id_str, "text": sme_source}],
        canonical_source_text=sme_source,
        form_snapshot=sme_snap,
    )

    # 2. Coordinator
    coord_snap = snapshots["coordinator"]
    titles = {
        c.criterion_code: c.title
        for d in coord_snap.form.domains
        for c in d.criteria
    }
    raw_responses = [
        _envelope_response(TEN[:5], titles),
        _envelope_response(TEN[5:9], titles),
        _envelope_response(TEN[9:], titles),
    ]
    fake = SequencedFakeClient(raw_responses)
    fake.model = get_llm_model_name()
    coord_client = RunLLMClient(fake, "coordinator", requested_model="test-model")
    coord = Coordinator()
    coord_res = coord.run(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        form_snapshot=coord_snap,
        chunk_infos=[{"chunk_id": chunk_id_str, "text": SOURCE}],
        canonical_source_text=SOURCE,
        curriculum_id=uuid4(),
        curriculum_context=CURRICULUM,
        llm_client=coord_client,
    )

    # 3. GAD
    from server.tests.agents.gad.test_snapshot_adapter import _MockLLM

    gad_payload = {
        "gad-01": {"instance_count": 0, "instances": [], "summary": "none"},
        "gad-02": {"female_count": 1, "male_count": 1, "summary": "balanced"},
        "gad-03": {"instance_count": 0, "instances": [], "summary": "none"},
        "gad-04": {"instance_count": 0, "instances": [], "summary": "none"},
        "gad-05": {"instance_count": 0, "instances": [], "summary": "none"},
    }
    gad_client = _MockLLM([json.dumps(gad_payload)])
    gad = GAD(llm_client=gad_client)
    gad_res = gad.run(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        chunk_infos=[{"chunk_id": chunk_id_str, "text": "chunk text"}],
        form_snapshot=snapshots["gad"],
    )

    # 4. ITSO
    itso_payload = {
        "summary": "ok",
        "criterion_scores": [
            {
                "criterion_id": c.criterion_code,
                "criterion_title": c.title,
                "score": 3,
                "justification": "justification",
                "chunk_ids": [chunk_id_str],
                "evidence": ["security"],
            }
            for d in snapshots["itso"].form.domains
            for c in d.criteria
        ],
    }
    itso_client = _LLM([json.dumps(itso_payload)])
    itso_ctx = ITSOExecutionContext(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        chunk_infos=(
            {"chunk_id": chunk_id_str, "page_number": 1, "text": "security"},
        ),
        form_snapshot=snapshots["itso"],
        llm_client=itso_client,
    )
    itso_res = itso_execution.execute(itso_ctx)

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document_id,
        [sme_res, coord_res, gad_res, itso_res],
        verify_ownership=lambda db: None,
    )

    gens = (
        db_session.query(AgentGeneration)
        .filter(AgentGeneration.evaluation_id == job.evaluation_id)
        .all()
    )

    # SME: 2, Coordinator: 3, GAD: 1, ITSO: 1 => total 7
    assert len(gens) == 7

    by_agent: dict[str, list[AgentGeneration]] = {}
    for g in gens:
        by_agent.setdefault(g.agent_id, []).append(g)

    assert len(by_agent["sme"]) == 2
    for g in by_agent["sme"]:
        assert g.response_contract_key == "criterion_measurements.v1"
        assert g.response_contract_version == 1
        assert g.envelope_status == "ok"
        assert g.capture_origin == "native"
        assert g.prompt_text
        assert g.response_text

    assert len(by_agent["coordinator"]) == 3
    for g in by_agent["coordinator"]:
        assert g.response_contract_key == "criterion_measurements.v1"
        assert g.response_contract_version == 1
        assert g.envelope_status == "ok"
        assert g.capture_origin == "native"

    assert len(by_agent["gad"]) == 1
    gad_gen = by_agent["gad"][0]
    assert gad_gen.response_contract_key == "gad_extraction.v1"
    assert gad_gen.response_contract_version == 1
    assert gad_gen.unit_key == "envelope_0"
    assert gad_gen.envelope_status == "ok"

    assert len(by_agent["itso"]) == 1
    itso_gen = by_agent["itso"][0]
    assert itso_gen.response_contract_key == "itso_scores.v1"
    assert itso_gen.response_contract_version == 1
    assert itso_gen.unit_key == "envelope_0"
    assert itso_gen.envelope_status == "ok"
