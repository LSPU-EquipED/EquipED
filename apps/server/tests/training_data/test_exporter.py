"""Integration tests for unified DPO package exporter."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.modules.training_data.capabilities import get_contract_capability
from server.modules.training_data.exporter import export_dpo_package
from server.tests.rubrics.helpers import seed_all_rubrics


def _setup_job_and_snapshots(db_session, user_id):
    doc_id = uuid4()
    doc = Document(
        document_id=doc_id,
        title="Test Doc",
        source_type="slm",
        file_path=f"uploads/{doc_id}.pdf",
        uploaded_by=user_id,
        uploaded_at=datetime.now(UTC),
        page_count=1,
        has_ocr_pages=False,
        processing_status="PROCESSED",
    )
    db_session.add(doc)
    chunk = DocumentChunk(
        chunk_id=uuid4(),
        document_id=doc_id,
        source_type="slm",
        agent_domain="sme",
        chunk_index=0,
        page_number=1,
        text="Sample syllabus text.",
    )
    db_session.add(chunk)
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_id,
        submitted_by=user_id,
        status="COMPLETED",
    )
    db_session.add(job)
    db_session.flush()

    seed_all_rubrics(db_session)
    agent_ids = ("sme", "coordinator", "gad", "itso")
    resolve_or_reuse_evaluation_snapshots(db_session, job.evaluation_id, agent_ids)
    db_session.commit()
    return job, doc


def test_capabilities_registry():
    cap_sme = get_contract_capability("criterion_measurements.v1", 1)
    assert cap_sme.supports_score_edit is True
    assert cap_sme.supports_item_rejection is True
    assert cap_sme.skip_reason is None

    cap_gad = get_contract_capability("gad_extraction.v1", 1)
    assert cap_gad.supports_score_edit is False
    assert cap_gad.skip_reason == "gad_score_edit_ineligible_for_extraction_contract"

    cap_itso = get_contract_capability("itso_scores.v1", 1)
    assert cap_itso.supports_score_edit is True
    assert cap_itso.supports_item_rejection is False

    cap_gad_scores = get_contract_capability("gad_scores.v1", 1)
    assert cap_gad_scores.supports_score_edit is True
    assert cap_gad_scores.supports_item_rejection is False
    assert cap_gad_scores.skip_reason is None

    cap_unknown = get_contract_capability("unknown.v99", 1)
    assert cap_unknown.supports_score_edit is False
    assert "unsupported_contract" in (cap_unknown.skip_reason or "")


def test_export_sme_score_edit(db_session, seeded_user, tmp_path: Path):
    job, doc = _setup_job_and_snapshots(db_session, seeded_user.user_id)
    res_id = uuid4()
    gen_id = uuid4()

    orig_response = {
        "summary": "sme summary",
        "criterion_measurements": [
            {
                "criterion_id": "A-01",
                "criterion_title": "A-01 title",
                "score": 2,
                "reasoning": "Baseline reasoning",
            }
        ],
    }

    db_session.add(
        AgentResult(
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_name="sme",
            model_name="gemma-3-4b",
            success=True,
            envelope_status={"envelope_0": "ok"},
        )
    )
    db_session.add(
        AgentGeneration(
            generation_id=gen_id,
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_id="sme",
            unit_key="envelope_0",
            criterion_ids=["A-01"],
            prompt_text="SME Prompt",
            response_text=json.dumps(orig_response),
            response_json=orig_response,
            response_contract_key="criterion_measurements.v1",
            response_contract_version=1,
            model_name="gemma-3-4b",
            envelope_status="ok",
            prompt_sha256="abc",
            response_sha256="def",
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 4, "justification": "Exemplary syllabus alignment"},
        )
    )
    db_session.commit()

    output_dir = tmp_path / "sme_package"
    manifest = export_dpo_package(
        session=db_session,
        agent_id="sme",
        output_dir=output_dir,
    )

    assert manifest.pair_count == 1
    assert manifest.evaluation_count == 1
    assert manifest.reviewer_count == 1
    assert manifest.agent_id == "sme"
    assert "criterion_measurements.v1" in manifest.response_contract_keys
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "pairs.jsonl").exists()
    assert (output_dir / "provenance.jsonl").exists()

    # Check sha256 of pairs.jsonl matches manifest
    pairs_bytes = (output_dir / "pairs.jsonl").read_bytes()
    assert hashlib.sha256(pairs_bytes).hexdigest() == manifest.pairs_sha256

    # Verify pairs content
    pairs_lines = pairs_bytes.decode("utf-8").splitlines()
    pairs_data = [json.loads(line) for line in pairs_lines if line]
    assert len(pairs_data) == 1
    assert pairs_data[0]["prompt"] == "SME Prompt"
    chosen_obj = json.loads(pairs_data[0]["chosen"])
    assert chosen_obj["criterion_measurements"][0]["score"] == 4


def test_export_coordinator_item_rejection(db_session, seeded_user, tmp_path: Path):
    job, doc = _setup_job_and_snapshots(db_session, seeded_user.user_id)
    res_id = uuid4()
    gen_id = uuid4()

    orig_response = {
        "summary": "coordinator summary",
        "criterion_measurements": [
            {
                "criterion_id": "OP-01",
                "criterion_title": "OP-01 title",
                "instances": [{"excerpt": "good"}, {"excerpt": "bad"}],
            }
        ],
    }

    db_session.add(
        AgentResult(
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_name="coordinator",
            model_name="gemma-3-4b",
            success=True,
            envelope_status={"envelope_0": "ok"},
        )
    )
    db_session.add(
        AgentGeneration(
            generation_id=gen_id,
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_id="coordinator",
            unit_key="envelope_0",
            criterion_ids=["OP-01"],
            prompt_text="Coord Prompt",
            response_text=json.dumps(orig_response),
            response_json=orig_response,
            response_contract_key="criterion_measurements.v1",
            response_contract_version=1,
            model_name="gemma-3-4b",
            envelope_status="ok",
            prompt_sha256="abc",
            response_sha256="def",
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="coordinator",
            criterion_id="OP-01",
            item_id="instance_1",
            action="ITEM_REJECT",
        )
    )
    db_session.commit()

    output_dir = tmp_path / "coord_package"
    manifest = export_dpo_package(
        session=db_session,
        agent_id="coordinator",
        output_dir=output_dir,
    )

    assert manifest.pair_count == 1
    assert (output_dir / "pairs.jsonl").exists()

    coord_lines = (output_dir / "pairs.jsonl").read_text().splitlines()
    pairs_data = [json.loads(line) for line in coord_lines if line]
    chosen_obj = json.loads(pairs_data[0]["chosen"])
    assert len(chosen_obj["criterion_measurements"][0]["instances"]) == 1
    assert chosen_obj["criterion_measurements"][0]["instances"][0]["excerpt"] == "good"


def test_export_itso_score_and_justification(db_session, seeded_user, tmp_path: Path):
    job, doc = _setup_job_and_snapshots(db_session, seeded_user.user_id)
    res_id = uuid4()
    gen_id = uuid4()

    orig_response = {
        "summary": "itso summary",
        "criterion_scores": [
            {
                "criterion_id": "ITSO-01",
                "criterion_title": "No IP Issue",
                "score": 1,
                "justification": "Poor",
                "chunk_ids": ["c1"],
                "evidence": ["evidence text"],
            }
        ],
    }

    db_session.add(
        AgentResult(
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_name="itso",
            model_name="gemma-3-4b",
            success=True,
            envelope_status={"envelope_0": "ok"},
        )
    )
    db_session.add(
        AgentGeneration(
            generation_id=gen_id,
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_id="itso",
            unit_key="envelope_0",
            criterion_ids=["ITSO-01"],
            prompt_text="ITSO Prompt",
            response_text=json.dumps(orig_response),
            response_json=orig_response,
            response_contract_key="itso_scores.v1",
            response_contract_version=1,
            model_name="gemma-3-4b",
            envelope_status="ok",
            prompt_sha256="abc",
            response_sha256="def",
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="ITSO-01",
            action="EDIT",
            edited_json={
                "score": 3,
                "justification": "Corrected citation standards met",
            },
        )
    )
    db_session.commit()

    output_dir = tmp_path / "itso_package"
    manifest = export_dpo_package(
        session=db_session,
        agent_id="itso",
        output_dir=output_dir,
    )

    assert manifest.pair_count == 1
    itso_lines = (output_dir / "pairs.jsonl").read_text().splitlines()
    pairs_data = [json.loads(line) for line in itso_lines if line]
    chosen_obj = json.loads(pairs_data[0]["chosen"])
    assert chosen_obj["criterion_scores"][0]["score"] == 3
    assert (
        chosen_obj["criterion_scores"][0]["justification"]
        == "Corrected citation standards met"
    )


def test_export_gad_scores_edit(db_session, seeded_user, tmp_path: Path):
    job, doc = _setup_job_and_snapshots(db_session, seeded_user.user_id)
    res_id = uuid4()
    gen_id = uuid4()

    orig_response = {
        "gad-01": {
            "score": 2,
            "evidence": "Women are inherently too emotional for leadership.",
            "chunk_id": "c1",
            "reasoning": "Direct stereotype statement.",
            "summary": "One instance found.",
        }
    }

    db_session.add(
        AgentResult(
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_name="gad",
            model_name="gemma-3-4b",
            success=True,
            envelope_status={"envelope_0": "ok"},
        )
    )
    db_session.add(
        AgentGeneration(
            generation_id=gen_id,
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_id="gad",
            unit_key="envelope_0",
            criterion_ids=["GAD-01"],
            prompt_text="GAD Prompt",
            response_text=json.dumps(orig_response),
            response_json=orig_response,
            response_contract_key="gad_scores.v1",
            response_contract_version=1,
            model_name="gemma-3-4b",
            envelope_status="ok",
            prompt_sha256="abc",
            response_sha256="def",
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="gad",
            criterion_id="GAD-01",
            action="EDIT",
            edited_json={
                "score": 3,
                "justification": "Only one isolated instance, not pervasive.",
            },
        )
    )
    db_session.commit()

    output_dir = tmp_path / "gad_scores_package"
    manifest = export_dpo_package(
        session=db_session,
        agent_id="gad",
        output_dir=output_dir,
    )

    assert manifest.pair_count == 1
    gad_lines = (output_dir / "pairs.jsonl").read_text().splitlines()
    pairs_data = [json.loads(line) for line in gad_lines if line]
    chosen_obj = json.loads(pairs_data[0]["chosen"])
    assert chosen_obj["gad-01"]["score"] == 3
    assert (
        chosen_obj["gad-01"]["reasoning"]
        == "Only one isolated instance, not pervasive."
    )


def test_export_gad_skip_behavior(db_session, seeded_user, tmp_path: Path):
    job, doc = _setup_job_and_snapshots(db_session, seeded_user.user_id)
    res_id = uuid4()
    gen_id = uuid4()

    orig_response = {
        "gad-01": {"instance_count": 0, "instances": [], "summary": "none"}
    }

    db_session.add(
        AgentResult(
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_name="gad",
            model_name="gemma-3-4b",
            success=True,
            envelope_status={"envelope_0": "ok"},
        )
    )
    db_session.add(
        AgentGeneration(
            generation_id=gen_id,
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_id="gad",
            unit_key="envelope_0",
            criterion_ids=["gad-01"],
            prompt_text="GAD Prompt",
            response_text=json.dumps(orig_response),
            response_json=orig_response,
            response_contract_key="gad_extraction.v1",
            response_contract_version=1,
            model_name="gemma-3-4b",
            envelope_status="ok",
            prompt_sha256="abc",
            response_sha256="def",
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="gad",
            criterion_id="gad-01",
            action="EDIT",
            edited_json={"score": 3},
        )
    )
    db_session.commit()

    output_dir = tmp_path / "gad_package"
    manifest = export_dpo_package(
        session=db_session,
        agent_id="gad",
        output_dir=output_dir,
    )

    assert manifest.pair_count == 0
    assert (
        manifest.skipped_counts.get("gad_score_edit_ineligible_for_extraction_contract")
        == 1
    )


def test_non_ok_envelope_status_exclusion(db_session, seeded_user, tmp_path: Path):
    job, doc = _setup_job_and_snapshots(db_session, seeded_user.user_id)
    res_id = uuid4()

    orig_response = {
        "summary": "sme",
        "criterion_measurements": [{"criterion_id": "A-01", "score": 1}],
    }

    for status in ["fallback", "repaired"]:
        db_session.add(
            AgentGeneration(
                generation_id=uuid4(),
                agent_result_id=res_id,
                evaluation_id=job.evaluation_id,
                document_id=doc.document_id,
                agent_id="sme",
                unit_key=f"env_{status}",
                criterion_ids=["A-01"],
                prompt_text="Prompt",
                response_text=json.dumps(orig_response),
                response_json=orig_response,
                response_contract_key="criterion_measurements.v1",
                response_contract_version=1,
                model_name="gemma-3-4b",
                envelope_status=status,
                prompt_sha256="abc",
                response_sha256="def",
            )
        )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 4},
        )
    )
    db_session.commit()

    output_dir = tmp_path / "status_package"
    manifest = export_dpo_package(
        session=db_session,
        agent_id="sme",
        output_dir=output_dir,
    )

    # All non-ok generations were excluded by query
    assert manifest.pair_count == 0


def test_atomic_directory_write_and_dry_run(db_session, seeded_user, tmp_path: Path):
    job, doc = _setup_job_and_snapshots(db_session, seeded_user.user_id)
    res_id = uuid4()
    gen_id = uuid4()

    orig_response = {
        "summary": "sme summary",
        "criterion_measurements": [
            {
                "criterion_id": "A-01",
                "criterion_title": "A-01",
                "score": 2,
                "reasoning": "orig",
            }
        ],
    }

    db_session.add(
        AgentResult(
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_name="sme",
            model_name="gemma-3-4b",
            success=True,
            envelope_status={"envelope_0": "ok"},
        )
    )
    db_session.add(
        AgentGeneration(
            generation_id=gen_id,
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_id="sme",
            unit_key="envelope_0",
            criterion_ids=["A-01"],
            prompt_text="SME Prompt",
            response_text=json.dumps(orig_response),
            response_json=orig_response,
            response_contract_key="criterion_measurements.v1",
            response_contract_version=1,
            model_name="gemma-3-4b",
            envelope_status="ok",
            prompt_sha256="abc",
            response_sha256="def",
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 4, "justification": "better"},
        )
    )
    db_session.commit()

    dry_dir = tmp_path / "dry_run_dir"
    manifest_dry = export_dpo_package(
        session=db_session,
        agent_id="sme",
        output_dir=dry_dir,
        dry_run=True,
    )
    assert manifest_dry.pair_count == 1
    assert not dry_dir.exists()

    real_dir = tmp_path / "real_dir"
    manifest_real = export_dpo_package(
        session=db_session,
        agent_id="sme",
        output_dir=real_dir,
        dry_run=False,
    )
    assert manifest_real.pair_count == 1
    assert real_dir.exists()
    assert (real_dir / "manifest.json").exists()


def test_trainer_package_validation(tmp_path: Path):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "training"))
    try:
        from train_dpo_lora import _resolve_package
    finally:
        sys.path.pop(0)

    pkg_dir = tmp_path / "test_trainer_pkg"
    pkg_dir.mkdir()

    # Missing manifest
    with pytest.raises(FileNotFoundError, match="manifest.json not found"):
        _resolve_package(pkg_dir)

    # Empty pair count
    manifest_file = pkg_dir / "manifest.json"
    manifest_file.write_text(json.dumps({"pair_count": 0, "pairs_sha256": "fake"}))
    with pytest.raises(ValueError, match="reports 0 pairs"):
        _resolve_package(pkg_dir)

    # Missing pairs.jsonl
    manifest_file.write_text(json.dumps({"pair_count": 1, "pairs_sha256": "fake"}))
    with pytest.raises(FileNotFoundError, match="pairs.jsonl not found"):
        _resolve_package(pkg_dir)

    # SHA256 mismatch
    pairs_file = pkg_dir / "pairs.jsonl"
    pairs_content = b'{"prompt": "p", "chosen": "c", "rejected": "r"}\n'
    pairs_file.write_bytes(pairs_content)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        _resolve_package(pkg_dir)

    # Valid package
    correct_sha = hashlib.sha256(pairs_content).hexdigest()
    manifest_file.write_text(json.dumps({"pair_count": 1, "pairs_sha256": correct_sha}))
    resolved = _resolve_package(pkg_dir)
    assert resolved == pairs_file
