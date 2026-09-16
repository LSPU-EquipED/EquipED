"""Tests for feedback request schema validation, including item-level actions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from server.modules.feedback.schemas import CriterionFeedbackCreate


def test_item_reject_requires_item_id():
    with pytest.raises(ValidationError, match="require 'item_id'"):
        CriterionFeedbackCreate(agent_name="sme", action="ITEM_REJECT")


def test_item_reject_valid_for_sme():
    body = CriterionFeedbackCreate(agent_name="sme", action="ITEM_REJECT", item_id="u1")
    assert body.item_id == "u1"
    assert body.score is None
    assert body.justification is None


def test_item_accept_valid_for_coordinator():
    body = CriterionFeedbackCreate(
        agent_name="coordinator", action="ITEM_ACCEPT", item_id="instance_0"
    )
    assert body.item_id == "instance_0"


def test_item_reject_rejected_for_itso():
    with pytest.raises(ValidationError, match="only supported for agents"):
        CriterionFeedbackCreate(agent_name="itso", action="ITEM_REJECT", item_id="u1")


def test_item_reject_rejected_for_gad():
    with pytest.raises(ValidationError, match="only supported for agents"):
        CriterionFeedbackCreate(agent_name="gad", action="ITEM_REJECT", item_id="u1")


def test_item_reject_forbids_score():
    with pytest.raises(ValidationError, match="forbid 'score' and 'justification'"):
        CriterionFeedbackCreate(
            agent_name="sme", action="ITEM_REJECT", item_id="u1", score=2
        )


def test_non_item_action_forbids_item_id():
    with pytest.raises(ValidationError, match="forbid 'item_id'"):
        CriterionFeedbackCreate(agent_name="sme", action="ACCEPT", item_id="u1")


def test_edit_still_requires_score_and_justification():
    with pytest.raises(ValidationError, match="EDIT actions require"):
        CriterionFeedbackCreate(agent_name="sme", action="EDIT")


def test_accept_still_works_unchanged():
    body = CriterionFeedbackCreate(agent_name="itso", action="ACCEPT")
    assert body.item_id is None
    assert body.score is None
