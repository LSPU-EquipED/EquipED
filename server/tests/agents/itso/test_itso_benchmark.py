"""Small deterministic ITSO prompt benchmark characterization."""

from uuid import uuid4

from server.modules.agents.itso.prompt import build_prompt
from server.modules.agents.runtime.context import ITSOExecutionContext


def test_prompt_build_is_deterministic_for_same_mapping_values():
    context = ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c", "text": "x"},),
        provenance={"reference_count": 1},
    )
    assert build_prompt(
        context, rubric_context=["r"], reference_context=["s"]
    ) == build_prompt(context, rubric_context=["r"], reference_context=["s"])
