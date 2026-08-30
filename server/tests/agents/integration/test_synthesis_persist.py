"""Tests for synthesis persistence of agent outputs and flag creation."""

from __future__ import annotations

from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import AgentResult, EvaluationFlag
from server.modules.synthesis.service import persist_agent_outputs
from server.tests.agents.helpers import _seed_active_prompts
from server.tests.evaluations.snapshot_test_helpers import (
    make_agent_result,
    prepare_test_snapshots,
)


def test_persist_agent_outputs_creates_flags_for_low_scores(db_session) -> None:
    owner_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    evaluation_id = uuid4()

    db_session.add(
        Document(
            document_id=document_id,
            title="SLM",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
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
            agent_domain="all",
            page_number=1,
            text="chunk text",
            token_count=2,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    _seed_active_prompts(db_session)
    prompt_version_id = (
        db_session.query(PromptVersion).filter_by(agent_id="sme").one().version_id
    )
    db_session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            syllabus_id=uuid4(),
            curriculum_id=uuid4(),
            status=EvaluationStatus.EVALUATING.value,
            submitted_by=owner_id,
            partial_without_curriculum=True,
        )
    )
    db_session.flush()
    prepare_test_snapshots(db_session, evaluation_id, partial_without_curriculum=True)
    db_session.commit()

    results = [
        make_agent_result(
            "sme",
            evaluation_id,
            document_id,
            prompt_version_id=prompt_version_id,
            scores_by_criterion={"A-01": 1, "A-02": 3},
            chunk_ids_by_criterion={"A-01": (str(chunk_id),)},
            evidence_by_criterion={"A-01": ("evidence",)},
        ),
        make_agent_result("gad", evaluation_id, document_id),
        make_agent_result("itso", evaluation_id, document_id),
    ]

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        results,
        verify_ownership=lambda db: None,
    )

    result_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=evaluation_id, agent_name="sme")
        .one()
    )
    assert result_row.prompt_version_id == prompt_version_id
    assert result_row.form_snapshot_id is not None
    flags = (
        db_session.query(EvaluationFlag)
        .filter(
            EvaluationFlag.evaluation_id == evaluation_id,
            EvaluationFlag.chunk_id.isnot(None),
        )
        .all()
    )
    assert len(flags) == 1
    flag = flags[0]
    assert flag.chunk_id == chunk_id
    assert flag.score == 1
    assert flag.criterion_id == "A-01"


def test_persist_agent_outputs_ignores_invalid_and_missing_chunk_ids(
    db_session,
) -> None:
    owner_id = uuid4()
    document_id = uuid4()
    valid_chunk_id = uuid4()
    evaluation_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="SLM",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.add(
        DocumentChunk(
            chunk_id=valid_chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="chunk text",
            token_count=2,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    _seed_active_prompts(db_session)
    prompt_version_id = (
        db_session.query(PromptVersion).filter_by(agent_id="sme").one().version_id
    )
    db_session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            syllabus_id=uuid4(),
            curriculum_id=uuid4(),
            status=EvaluationStatus.EVALUATING.value,
            submitted_by=owner_id,
            partial_without_curriculum=True,
        )
    )
    db_session.flush()
    prepare_test_snapshots(db_session, evaluation_id, partial_without_curriculum=True)
    db_session.commit()

    results = [
        make_agent_result(
            "sme",
            evaluation_id,
            document_id,
            prompt_version_id=prompt_version_id,
            scores_by_criterion={"A-01": 1},
            chunk_ids_by_criterion={
                "A-01": ("not-a-uuid", str(uuid4()), str(valid_chunk_id))
            },
            evidence_by_criterion={"A-01": ("evidence",)},
        ),
        make_agent_result("gad", evaluation_id, document_id),
        make_agent_result("itso", evaluation_id, document_id),
    ]

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        results,
        verify_ownership=lambda db: None,
    )

    result_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=evaluation_id, agent_name="sme")
        .one()
    )
    assert result_row.prompt_version_id == prompt_version_id
    flags = (
        db_session.query(EvaluationFlag)
        .filter(
            EvaluationFlag.evaluation_id == evaluation_id,
            EvaluationFlag.chunk_id.isnot(None),
        )
        .all()
    )
    assert len(flags) == 1
    flag = flags[0]
    assert flag.chunk_id == valid_chunk_id


def test_persist_agent_outputs_stores_group_prompts(db_session) -> None:
    owner_id = uuid4()
    document_id = uuid4()
    evaluation_id = uuid4()

    db_session.add(
        Document(
            document_id=document_id,
            title="SLM",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            syllabus_id=uuid4(),
            curriculum_id=uuid4(),
            status=EvaluationStatus.EVALUATING.value,
            submitted_by=owner_id,
            partial_without_curriculum=True,
        )
    )
    db_session.flush()
    prepare_test_snapshots(db_session, evaluation_id, partial_without_curriculum=True)
    db_session.commit()

    results = [
        make_agent_result(
            "sme",
            evaluation_id,
            document_id,
            metadata={"group_prompts": {"task_execution": "prompt text"}},
        ),
        make_agent_result("gad", evaluation_id, document_id),
        make_agent_result("itso", evaluation_id, document_id),
    ]

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        results,
        verify_ownership=lambda db: None,
    )

    result_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=evaluation_id, agent_name="sme")
        .one()
    )
    assert result_row.group_prompts == {"task_execution": "prompt text"}
