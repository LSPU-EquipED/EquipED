"""New Coordinator jobs must never bind a retired execution adapter."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from server.modules.evaluations.admission import create_evaluation
from server.modules.evaluations.exceptions import EvaluationPipelineUnavailableError
from server.modules.evaluations.models import EvaluationJob
from server.modules.evaluations.schemas import EvaluationSubmitRequest


def test_retired_coordinator_is_rejected_before_preparation_or_job_creation(
    db_session, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.evaluations.admission._validate_evaluation_target",
        lambda *args, **kwargs: SimpleNamespace(program="BSCS"),
    )
    monkeypatch.setattr(
        "server.modules.rubrics.get_active_rubric_adapter_version",
        lambda db, agent, *, lock: 3,
    )
    monkeypatch.setattr(
        "server.modules.evaluations.admission.check_curriculum_readiness",
        lambda **kwargs: pytest.fail("Retired adapters must stop before preparation"),
    )
    request = EvaluationSubmitRequest(
        document_id=uuid4(),
        curriculum_id=uuid4(),
        target_agent="coordinator",
        confirmed_program="BSCS",
    )
    with pytest.raises(EvaluationPipelineUnavailableError, match="upgrade"):
        create_evaluation(request, uuid4(), db_session)
    assert db_session.query(EvaluationJob).count() == 0
