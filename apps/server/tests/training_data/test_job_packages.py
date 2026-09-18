from __future__ import annotations

import io
import uuid as uuid_module
import zipfile

from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.modules.training_data.job_packages import (
    FrozenJobPackage,
    freeze_job_dataset,
    serialize_job_package_zip,
)
from server.tests.evaluations.conftest import _add_document


def _make_gad_generation(db_session, owner_id, agent_id="gad"):
    document_id = _add_document(db_session, owner_id=owner_id, source_type="slm")
    job = EvaluationJob(evaluation_id=uuid_module.uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name=agent_id,
        subtotal=2.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="GAD evaluation summary",
        success=True,
    )
    db_session.add(agent_result)
    db_session.flush()

    generation = AgentGeneration(
        generation_id=uuid_module.uuid4(),
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_id=agent_id,
        unit_key="gad-01",
        criterion_ids=["GAD-01"],
        prompt_text="prompt",
        response_text='{"gad-01": {"score": 2, "reasoning": "r"}}',
        response_json={"gad-01": {"score": 2, "reasoning": "r"}},
        response_contract_key="gad_scores.v1",
        response_contract_version=1,
        model_name="test-model",
        envelope_status="ok",
        prompt_sha256="p" * 64,
        response_sha256="r" * 64,
    )
    db_session.add(generation)
    db_session.commit()
    return job.evaluation_id


def test_freeze_job_dataset_returns_frozen_job_package(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)

    package = freeze_job_dataset(db_session, "gad")

    assert isinstance(package, FrozenJobPackage)
    assert isinstance(package.manifest_json, dict)
    assert isinstance(package.pairs_content, str)
    assert isinstance(package.provenance_content, str)


def test_serialize_job_package_zip_creates_expected_zip_entries():
    pairs = '{"prompt": "p"}\n'
    provenance = '{"eval_id": "1"}\n'
    manifest = {"agent_id": "gad", "count": 1}

    zip_bytes = serialize_job_package_zip(pairs, provenance, manifest)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        expected = {"pairs.jsonl", "provenance.jsonl", "manifest.json"}
        assert set(zf.namelist()) == expected
        assert zf.read("pairs.jsonl").decode("utf-8") == pairs
        assert zf.read("provenance.jsonl").decode("utf-8") == provenance
        assert "gad" in zf.read("manifest.json").decode("utf-8")
