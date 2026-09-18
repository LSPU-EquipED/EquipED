"""Shared fixtures and database seeding helpers for training_data module tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.tests.admin.conftest import (  # noqa: F401 — re-exported fixtures
    admin_user,
    auth_cookies_admin,
    auth_cookies_faculty,
    faculty_user,
)
from server.tests.feedback.conftest import (  # noqa: F401 — re-exported fixtures
    evaluation_job,
)
from server.tests.rubrics.helpers import seed_all_rubrics


def seed_eligible_dpo_pair(
    db_session,
    owner_id,
    agent_id: str = "gad",
) -> EvaluationJob:
    """Seed a complete, eligible evaluation with rubrics, snapshot, AgentGeneration,
    and a PreferenceLog so export_dpo_package yields at least 1 pair."""
    doc_id = uuid4()
    doc = Document(
        document_id=doc_id,
        title="Test Doc",
        source_type="slm",
        file_path=f"uploads/{doc_id}.pdf",
        uploaded_by=owner_id,
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
        agent_domain=agent_id,
        chunk_index=0,
        page_number=1,
        text="Sample syllabus text.",
    )
    db_session.add(chunk)

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_id,
        submitted_by=owner_id,
        status="COMPLETED",
    )
    db_session.add(job)
    db_session.flush()

    seed_all_rubrics(db_session)
    resolve_or_reuse_evaluation_snapshots(
        db_session, job.evaluation_id, ("sme", "coordinator", "gad", "itso")
    )

    res_id = uuid4()
    gen_id = uuid4()

    if agent_id == "gad":
        orig_response = {
            "gad-01": {
                "score": 2,
                "evidence": "Stereotype statement.",
                "chunk_id": "c1",
                "reasoning": "Direct stereotype statement.",
                "summary": "One instance found.",
            }
        }
        contract_key = "gad_scores.v1"
        criterion_ids = ["GAD-01"]
        crit_id = "GAD-01"
        action = "EDIT"
        edited_json = {
            "score": 3,
            "justification": "Isolated instance.",
        }
    elif agent_id == "itso":
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
        contract_key = "itso_scores.v1"
        criterion_ids = ["ITSO-01"]
        crit_id = "ITSO-01"
        action = "EDIT"
        edited_json = {
            "score": 3,
            "justification": "Better.",
        }
    else:
        orig_response = {
            "summary": f"{agent_id} summary",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "A-01",
                    "score": 2,
                    "reasoning": "orig",
                }
            ],
        }
        contract_key = "criterion_measurements.v1"
        criterion_ids = ["A-01"]
        crit_id = "A-01"
        action = "EDIT"
        edited_json = {"score": 4, "justification": "better"}

    db_session.add(
        AgentResult(
            agent_result_id=res_id,
            evaluation_id=job.evaluation_id,
            document_id=doc_id,
            agent_name=agent_id,
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
            document_id=doc_id,
            agent_id=agent_id,
            unit_key="envelope_0",
            criterion_ids=criterion_ids,
            prompt_text=f"{agent_id} prompt",
            response_text=json.dumps(orig_response),
            response_json=orig_response,
            response_contract_key=contract_key,
            response_contract_version=1,
            model_name="gemma-3-4b",
            envelope_status="ok",
            prompt_sha256="abc" * 21 + "a",
            response_sha256="def" * 21 + "d",
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=owner_id,
            agent_name=agent_id,
            criterion_id=crit_id,
            action=action,
            edited_json=edited_json,
        )
    )
    db_session.commit()
    return job
