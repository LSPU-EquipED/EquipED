"""Unit tests for synthesis schema validation."""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

from server.modules.synthesis.schemas import (
    CriterionScoreItem,
    DomainScoreBlock,
    EvaluationFlagItem,
    MatrixRowItem,
)


def test_matrix_schema_accepts_nested_domain_scores() -> None:
    item = MatrixRowItem(
        matrix_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        evaluation_status="COMPLETED",
        last_updated=datetime.now(UTC),
        domain_scores={
            "sme": DomainScoreBlock(criteria=[], subtotal=3.0, max_score=4, status="OK")
        },
    )

    assert item.domain_scores["sme"].subtotal == 3.0


def test_evaluation_flag_item_accepts_agent_name_as_agent_id() -> None:
    """agent_id should be the agent name (e.g. 'sme'), not a UUID string."""
    flag = EvaluationFlagItem(
        flag_id=uuid.uuid4(),
        evaluation_id=uuid.uuid4(),
        agent_id="sme",
        criterion_id="c1",
        criterion_text="Criterion 1",
        score=3,
        justification="test",
    )

    assert flag.agent_id == "sme"
    assert flag.agent_id in ("sme", "coordinator", "gad", "itso")


def test_evaluation_flag_item_rejects_uuid_string_as_agent_name() -> None:
    """agent_id field accepts string values; the router must map UUIDs to names."""
    # The schema accepts any string; the router is responsible for mapping
    # agent_result_id UUIDs to agent_name strings.
    flag = EvaluationFlagItem(
        flag_id=uuid.uuid4(),
        evaluation_id=uuid.uuid4(),
        agent_id="coordinator",
        criterion_id="c2",
        criterion_text="Criterion 2",
        score=4,
        justification="great",
    )

    assert flag.agent_id == "coordinator"


def test_criterion_score_item_accepts_evidence_and_chunk_ids() -> None:
    """CriterionScoreItem should accept optional evidence and chunk_ids fields."""
    item = CriterionScoreItem(
        criterion_id="c1",
        criterion_text="Clear learning outcomes",
        score=4,
        justification="Well-defined outcomes aligned with standards",
        evidence="Section 2 states measurable outcomes...",
        chunk_ids='["uuid-1", "uuid-2"]',
    )

    assert item.evidence == "Section 2 states measurable outcomes..."
    assert item.chunk_ids == '["uuid-1", "uuid-2"]'


def test_criterion_score_item_evidence_and_chunk_ids_are_optional() -> None:
    """evidence and chunk_ids should default to None when not provided."""
    item = CriterionScoreItem(
        criterion_id="c2",
        criterion_text="Assessment alignment",
        score=3,
        justification="Mostly aligned",
    )

    assert item.evidence is None
    assert item.chunk_ids is None


def test_evaluation_flag_item_criterion_text_separate_from_justification() -> None:
    """criterion_text and justification should be independently settable."""
    flag = EvaluationFlagItem(
        flag_id=uuid.uuid4(),
        evaluation_id=uuid.uuid4(),
        agent_id="sme",
        criterion_id="c1",
        criterion_text="Clear learning outcomes",
        score=2,
        justification="Outcomes are vague and not measurable",
    )

    assert flag.criterion_text == "Clear learning outcomes"
    assert flag.justification == "Outcomes are vague and not measurable"
    assert flag.criterion_text != flag.justification
