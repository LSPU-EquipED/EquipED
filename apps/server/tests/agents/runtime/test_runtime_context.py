"""Immutability contracts for ITSO runtime contexts."""

from uuid import uuid4

import pytest
from server.modules.agents.runtime.context import ITSOExecutionContext, thaw


def test_nested_context_is_immutable_and_thaw_is_isolated():
    source = {"nested": {"items": [{"value": 1}]}}
    context = ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        provenance=source,
    )

    with pytest.raises(TypeError):
        context.provenance["nested"]["items"] = ()
    with pytest.raises(AttributeError):
        context.provenance["nested"]["items"].append(2)

    mutable_copy = thaw(context.provenance)
    mutable_copy["nested"]["items"][0]["value"] = 9
    mutable_copy["nested"]["items"].append({"value": 3})
    assert source["nested"]["items"] == [{"value": 1}]
    assert context.provenance["nested"]["items"][0]["value"] == 1
