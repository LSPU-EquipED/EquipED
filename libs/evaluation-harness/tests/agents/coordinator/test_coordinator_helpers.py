"""Shared current Coordinator request and fake client for harness tests."""

from __future__ import annotations

from uuid import uuid4

from equiped_harness import EvaluationRequest
from equiped_harness.agents.coordinator.rubric import guidance_for
from equiped_harness.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
)
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot
from equiped_harness.runtime.source_retrieval import source_hash

SOURCE = (
    "Learning Objectives:\n1. Explain arrays.\n2. Apply arrays.\n3. Compare arrays.\n"
    "4. Design arrays.\n5. Evaluate arrays.\nAssessment Tasks:\n"
    "Task one applies arrays. Task two compares arrays.\n"
)


def request(*, source: str = SOURCE) -> EvaluationRequest:
    criteria = tuple(
        CriterionDefinition(
            rubric_criterion_id=uuid4(),
            criterion_code=code,
            title=code,
            description=code,
            display_order=index,
            strategy_config=guidance_for(code),
        )
        for index, code in enumerate(
            tuple(f"OP-{i:02d}" for i in range(1, 6))
            + tuple(f"A-{i:02d}" for i in range(1, 6))
        )
    )
    form = FormDefinition(
        rubric_set_id=uuid4(),
        name="Coordinator",
        agent_id="coordinator",
        adapter_key="coordinator",
        adapter_version=4,
        version_number=5,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid4(),
                code="coord",
                title="Coordinator",
                display_order=1,
                criteria=criteria,
            ),
        ),
    )
    evaluation_id = uuid4()
    retrieval = {
        "contract": "slm_retrieval.v2",
        "document_id": str(document_id := uuid4()),
        "source_hash": source_hash(source),
        "embedding_model": "offline-test-encoder",
        "rankings": {
            group: ["S1"] for group in ("organization", "assessment", "alignment")
        },
        "passages": {"S1": {"start": 0, "end": min(120, len(source))}},
    }
    return EvaluationRequest(
        evaluation_id=evaluation_id,
        document_id=document_id,
        form_snapshot=build_evaluation_form_snapshot(evaluation_id, form),
        chunk_infos=({"chunk_id": "chunk-1", "text": source},),
        canonical_source_text=source,
        curriculum_id=uuid4(),
        curriculum_context="Arrays are applied in programming tasks.",
        source_retrieval=retrieval,
    )
