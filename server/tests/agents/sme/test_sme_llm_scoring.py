"""Tests for ``EngineScoredAgent._run_full_llm_scoring`` via ``SME.run()``.

SME now scores every criterion with 3 grouped direct-LLM calls (see
``sme/groups.py`` and ``sme/grouped_execution.py``). The retained
per-criterion engine lane (``registry.run_criterion``) is only a fallback for
a group whose grouped call fails outright.
"""

from __future__ import annotations

import uuid

import pytest
from server.modules.agents.sme import pipeline
from server.modules.agents.sme.agent import SME
from server.tests.agents.helpers import (
    SME_CRITERION_FALLBACKS,
    SME_GROUP_TITLES,
    GroupScoringFakeClient,
    sme_group_payloads,
)

_CHUNK_INFOS = [{"chunk_id": "c1", "page_number": 1, "text": "x"}]
_CANONICAL = "clean SLM text " * 50


@pytest.fixture(autouse=True)
def _titles(monkeypatch):
    monkeypatch.setattr(
        pipeline.EngineScoredAgent,
        "_rubric_titles",
        lambda self, db: SME_GROUP_TITLES,
    )


def _run(client: GroupScoringFakeClient):
    return SME().run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        canonical_source_text=_CANONICAL,
        llm_client=client,
    )


def test_sme_run_scores_all_ten_criteria_via_llm():
    client = GroupScoringFakeClient(sme_group_payloads(3))
    result = _run(client)

    assert result.success is True
    assert len(result.criterion_scores) == 10
    assert all(score.score == 3 for score in result.criterion_scores)
    assert all(score.chunk_ids == () for score in result.criterion_scores)
    # Exactly one LLM call per group, no per-criterion fallback.
    assert client.group_calls == 3
    assert client.fallback_calls == 0
    assert set(result.metadata["group_prompts"]) == {
        "assessment_alignment",
        "task_execution",
        "document_wide",
    }
    assert result.provenance["criterion_fallback_calls"] == 0
    assert result.provenance["logical_calls"] == 3


def test_sme_run_falls_back_to_per_criterion_when_one_group_fails():
    payloads = sme_group_payloads(3)
    payloads["assessment_alignment"] = "{still not valid"
    client = GroupScoringFakeClient(
        payloads,
        [SME_CRITERION_FALLBACKS["A-02"], SME_CRITERION_FALLBACKS["A-05"]],
    )
    result = _run(client)

    assert result.success is True
    assert len(result.criterion_scores) == 10
    by_id = {score.criterion_id: score for score in result.criterion_scores}
    # A-02/A-05 came from the per-criterion engine lane, so their justification
    # is the code-computed text, not the grouped LLM's.
    assert "code-computed" in by_id["A-02"].justification
    assert "code-computed" in by_id["A-05"].justification
    assert by_id["OP-02"].justification == "justification"
    # The failed group has no single snapshot-able prompt.
    assert "assessment_alignment" not in result.metadata["group_prompts"]
    assert "task_execution" in result.metadata["group_prompts"]
    assert "document_wide" in result.metadata["group_prompts"]
    assert client.fallback_calls == 2
    assert result.provenance["criterion_fallback_calls"] == 2


def test_group_prompts_are_the_exact_prompts_sent():
    client = GroupScoringFakeClient(sme_group_payloads(2))
    result = _run(client)

    assert set(result.metadata["group_prompts"].values()) <= set(client.prompts)
    for group, prompt in result.metadata["group_prompts"].items():
        assert f'"group": "{group}"' in prompt
