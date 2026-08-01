import uuid

from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import AgentResult
from server.modules.synthesis.service import start_sme_syllabus_alignment
from sqlalchemy.orm import sessionmaker


class CapturedBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, function, *args):
        self.tasks.append((function, args))


def test_explicit_start_queues_alignment_without_changing_scores_or_job(
    db_session, seeded_user, monkeypatch
):
    slm_id = uuid.uuid4()
    syllabus_id = uuid.uuid4()
    evaluation_id = uuid.uuid4()
    result_id = uuid.uuid4()
    db_session.add_all(
        [
            Document(
                document_id=slm_id,
                title="SLM",
                source_type="slm",
                file_path="uploads/slm.pdf",
                uploaded_by=seeded_user.user_id,
                processing_status="PROCESSED",
            ),
            Document(
                document_id=syllabus_id,
                title="Syllabus",
                source_type="syllabus",
                file_path="uploads/syllabus.pdf",
                uploaded_by=seeded_user.user_id,
                processing_status="PROCESSED",
            ),
            EvaluationJob(
                evaluation_id=evaluation_id,
                document_id=slm_id,
                syllabus_id=syllabus_id,
                submitted_by=seeded_user.user_id,
                status=EvaluationStatus.COMPLETED.value,
            ),
            AgentResult(
                agent_result_id=result_id,
                evaluation_id=evaluation_id,
                document_id=slm_id,
                agent_name="sme",
                subtotal=3.25,
                processing_seconds=1.0,
                token_count=100,
                model_name="test-model",
                summary="SME scoring complete.",
                success=True,
            ),
        ]
    )
    db_session.commit()
    background = CapturedBackgroundTasks()

    response = start_sme_syllabus_alignment(
        db_session, evaluation_id, seeded_user.user_id, background
    )

    db_session.expire_all()
    job = db_session.get(EvaluationJob, evaluation_id)
    result = db_session.get(AgentResult, result_id)
    assert response.processing_state == "RUNNING"
    assert len(background.tasks) == 1
    assert job.status == EvaluationStatus.COMPLETED.value
    assert result.subtotal == 3.25
    assert (
        result.advisory_outputs["syllabus_alignment"]["processing_state"] == "RUNNING"
    )

    from server.core import database, llm
    from server.modules.agents import syllabus_alignment

    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False)
    monkeypatch.setattr(database, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(llm, "get_llm_client_for_agent", lambda _name: object())
    monkeypatch.setattr(
        syllabus_alignment,
        "evaluate",
        lambda _client, _chunks, selected_syllabus_id: {
            "status": "MEETS",
            "statement": "Every substantial topic is aligned.",
            "syllabus_document_id": str(selected_syllabus_id),
            "total_topics": 1,
            "aligned_topics": 1,
            "outcome_matches": [],
            "unmatched_topics": [],
            "advisory_only": True,
        },
    )
    task, task_args = background.tasks[0]
    task(*task_args)
    db_session.expire_all()
    result = db_session.get(AgentResult, result_id)
    job = db_session.get(EvaluationJob, evaluation_id)
    assert result.advisory_outputs["syllabus_alignment"]["status"] == "MEETS"
    assert (
        result.advisory_outputs["syllabus_alignment"]["processing_state"]
        == "COMPLETED"
    )
    assert job.status == EvaluationStatus.COMPLETED.value

    start_sme_syllabus_alignment(
        db_session, evaluation_id, seeded_user.user_id, background
    )
    assert len(background.tasks) == 2
