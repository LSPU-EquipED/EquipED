"""Small deterministic ITSO prompt benchmark characterization."""

from uuid import uuid4

from server.modules.agents.itso.prompt import build_prompt
from server.modules.agents.runtime.context import ITSOExecutionContext
from server.tests.agents.itso.conftest_helper import make_itso_test_snapshot


def test_prompt_build_is_deterministic_for_same_mapping_values():
    snapshot = make_itso_test_snapshot()
    criteria = [c for d in snapshot.form.domains for c in d.criteria]
    context = ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c", "text": "x"},),
        provenance={"reference_count": 1},
        form_snapshot=snapshot,
    )
    assert build_prompt(
        context, ordered_criteria=criteria, reference_context=["s"]
    ) == build_prompt(context, ordered_criteria=criteria, reference_context=["s"])
