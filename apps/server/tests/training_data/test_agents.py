from __future__ import annotations

import pytest
from server.modules.training_data.agents import VALID_AGENT_IDS, validate_agent_id
from server.modules.training_data.exceptions import InvalidAgentIdError


def test_valid_agent_ids():
    assert VALID_AGENT_IDS == frozenset({"sme", "coordinator", "gad", "itso"})


def test_validate_agent_id_accepts_valid():
    for agent_id in ("sme", "coordinator", "gad", "itso"):
        assert validate_agent_id(agent_id) == agent_id


def test_validate_agent_id_rejects_invalid():
    with pytest.raises(InvalidAgentIdError) as exc_info:
        validate_agent_id("not-an-agent")
    assert "unknown agent_id" in str(exc_info.value)
