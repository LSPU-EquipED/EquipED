"""Direct, stateless ITSO prompt tests."""

import json
from uuid import uuid4

from server.modules.agents.itso.prompt import build_prompt
from server.modules.agents.runtime.context import ITSOExecutionContext


def _context(**values):
    return ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "text": "security"},),
        **values,
    )


def test_prompt_uses_mapping_context_and_is_deterministic():
    context = _context(provenance={"bibliography_found": True}, prompt_version="v1")
    first = build_prompt(
        context, rubric_context=["rubric"], reference_context=["reference"]
    )
    second = build_prompt(
        context, rubric_context=["rubric"], reference_context=["reference"]
    )
    assert first == second
    assert json.loads(first)["document_chunks"][0]["chunk_id"] == "c1"
    assert "IMPORTANT" in first
