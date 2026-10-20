from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from server.modules.training_data.itso_guard import reject_itso_v2_export

from .conftest import seed_historical_assessment


def test_training_export_blocks_only_matching_saved_itso_assessments(
    db_session, actors, owned
):
    reject_itso_v2_export(db_session, agent_id="sme")
    reject_itso_v2_export(db_session, agent_id="itso", evaluation_id=uuid4())

    doc, source = owned
    job, _ = seed_historical_assessment(db_session, doc, actors[0], source)
    db_session.flush()
    reject_itso_v2_export(
        db_session,
        agent_id="itso",
        since=datetime.now(UTC) + timedelta(days=1),
    )
    with pytest.raises(ValueError, match="unsupported_version"):
        reject_itso_v2_export(
            db_session, agent_id="itso", evaluation_id=job.evaluation_id
        )
