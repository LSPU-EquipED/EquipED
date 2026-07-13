"""Tests for Coordinator's three entry points.

Coordinator's rubric is identical to SME's (see
server/data/rubrics/rubrics.json), and 9 of its 10 criteria would always
match SME's score/justification exactly (same SLM input, same math) -- so
paying for a second 6-call engine pass just to re-derive an answer SME
already computed was wasteful and was tipping full evaluations over the
shared LLM rate limit. Coordinator now has three entry points:

- ``run()`` -- what Supervisor actually calls (parallel with every other
  agent, unchanged call site). Cheap: ONE LLM call, ONE criterion (A-05).
- ``run_full_independent()`` -- today's original full engine pass (6 calls,
  all 10 criteria) -- used only as evaluations/orchestrator.py's fallback
  when SME failed. This is the OLD ``run()`` behavior, just renamed; these
  tests are the same regression coverage that existed before, retargeted.
- ``merge_with_sme()`` -- pure splice of SME's 9 non-A-05 scores with
  Coordinator's own A-05 score, tested in isolation with no LLM/DB at all.
"""

from __future__ import annotations

import uuid

import pytest
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.coordinator import Coordinator
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.scoring import registry

from .test_sme_run import _ALL_BASKETS_IN_ORDER, _BASKET_A1, SequencedFakeClient

_TITLES = {code: f"{code} Coordinator Title" for code in registry.REGISTERED_CODES}

_CHUNK_INFOS = [{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}]


def _make_agent(monkeypatch, client) -> Coordinator:
    agent = Coordinator(llm_client=client)
    monkeypatch.setattr(
        Coordinator, "_load_document_text", lambda self, document_id: None
    )
    monkeypatch.setattr(
        "server.modules.agents.engine_scoring.get_active_rubric_criteria",
        lambda agent_id, db=None: _TITLES,
    )
    return agent


# ---------------------------------------------------------------------------
# run() -- the cheap, Supervisor-facing path: 1 call, 1 criterion (A-05).
# ---------------------------------------------------------------------------
class TestRunCheapPath:
    def test_makes_exactly_one_call_and_scores_only_a05(self, monkeypatch) -> None:
        client = SequencedFakeClient([_BASKET_A1])
        agent = _make_agent(monkeypatch, client)

        result = agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
        )

        assert client.calls == 1
        assert result.success is True
        assert [s.criterion_id for s in result.criterion_scores] == ["A-05"]
        assert result.subtotal == result.criterion_scores[0].score

    def test_curriculum_attached_produces_curriculum_grounded_justification(
        self, monkeypatch
    ) -> None:
        basket = dict(_BASKET_A1)
        basket["curriculum_alignment"] = [
            {"objective_id": 1, "is_addressed": True, "evidence": "curriculum quote"}
        ]
        client = SequencedFakeClient([basket])
        agent = _make_agent(monkeypatch, client)
        monkeypatch.setattr(
            Coordinator,
            "_prepare_curriculum_text",
            lambda self, document_id, curriculum_id, db: "Course: Foo\n\nBar",
        )

        result = agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
            reference_document_ids={"curriculum": uuid.uuid4()},
        )

        assert client.calls == 1
        a05 = result.criterion_scores[0]
        assert "Curriculum-grounded" in a05.justification
        assert a05.evidence == ("curriculum quote",)

    def test_no_curriculum_id_keeps_slm_only_a05(self, monkeypatch) -> None:
        client = SequencedFakeClient([_BASKET_A1])
        agent = _make_agent(monkeypatch, client)

        result = agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
            reference_document_ids=None,
        )

        assert client.calls == 1
        assert "Curriculum-grounded" not in result.criterion_scores[0].justification

    def test_curriculum_retrieval_failure_falls_back_to_slm_only(
        self, monkeypatch
    ) -> None:
        client = SequencedFakeClient([_BASKET_A1])
        agent = _make_agent(monkeypatch, client)

        def _raise(self, document_id, curriculum_id, db):
            raise RuntimeError("chroma unavailable")

        monkeypatch.setattr(Coordinator, "_prepare_curriculum_text", _raise)

        result = agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
            reference_document_ids={"curriculum": uuid.uuid4()},
        )

        assert client.calls == 1
        assert "Curriculum-grounded" not in result.criterion_scores[0].justification

    def test_raises_when_no_chunk_infos(self, monkeypatch) -> None:
        agent = _make_agent(monkeypatch, SequencedFakeClient([]))

        with pytest.raises(AgentExecutionError):
            agent.run(
                evaluation_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_infos=[],
                context_text="full slm text",
            )

    def test_propagates_when_the_single_call_fails(self, monkeypatch) -> None:
        # No fallback inside the cheap path by design -- a failure here is
        # exactly what should make Supervisor mark Coordinator success=False,
        # which is what triggers the orchestrator's independent-scoring
        # fallback (see test_orchestrator_reconciliation.py).
        client = SequencedFakeClient([None])
        agent = _make_agent(monkeypatch, client)

        with pytest.raises(Exception):  # noqa: B017 - deliberately broad, see comment
            agent.run(
                evaluation_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_infos=_CHUNK_INFOS,
                context_text="full slm text",
            )


# ---------------------------------------------------------------------------
# run_full_independent() -- the original full engine pass, renamed. Same
# regression coverage the old run() tests provided.
# ---------------------------------------------------------------------------
class TestRunFullIndependent:
    def test_computes_independently(self, monkeypatch) -> None:
        client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
        agent = _make_agent(monkeypatch, client)

        result = agent.run_full_independent(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
        )

        assert result.success is True
        scored_codes = {s.criterion_id for s in result.criterion_scores}
        assert scored_codes == registry.REGISTERED_CODES
        assert client.calls == 6

    def test_fallback_raises_when_code_fails_both_engine_paths(
        self, monkeypatch
    ) -> None:
        responses = list(_ALL_BASKETS_IN_ORDER)
        responses[2] = None  # A3 basket fails
        responses.append(None)  # per-criterion fallback for A-03 also fails
        client = SequencedFakeClient(responses)
        agent = _make_agent(monkeypatch, client)

        with pytest.raises(AgentExecutionError):
            agent.run_full_independent(
                evaluation_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_infos=_CHUNK_INFOS,
                context_text="full slm text",
            )

    def test_model_name_falls_back_to_default(self, monkeypatch) -> None:
        from server.core.llm import get_llm_model_name

        client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
        agent = _make_agent(monkeypatch, client)
        result = agent.run_full_independent(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
        )
        assert result.model_name == get_llm_model_name()

    def test_model_name_uses_client_model(self, monkeypatch) -> None:
        client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
        client.model = "coord-custom-test-model"
        agent = _make_agent(monkeypatch, client)
        result = agent.run_full_independent(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
        )
        assert result.model_name == "coord-custom-test-model"

    def test_raises_when_no_chunk_infos(self, monkeypatch) -> None:
        agent = _make_agent(monkeypatch, SequencedFakeClient([]))

        with pytest.raises(AgentExecutionError):
            agent.run_full_independent(
                evaluation_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_infos=[],
                context_text="full slm text",
            )

    def test_curriculum_alignment_rides_the_a1_call_not_a_second_one(
        self, monkeypatch
    ) -> None:
        baskets = [dict(b) for b in _ALL_BASKETS_IN_ORDER]
        baskets[0]["curriculum_alignment"] = [
            {"objective_id": 1, "is_addressed": True, "evidence": "curriculum quote"}
        ]
        client = SequencedFakeClient(baskets)
        agent = _make_agent(monkeypatch, client)
        monkeypatch.setattr(
            Coordinator,
            "_prepare_curriculum_text",
            lambda self, document_id, curriculum_id, db: "Course: Foo\n\nBar",
        )

        result = agent.run_full_independent(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
            reference_document_ids={"curriculum": uuid.uuid4()},
        )

        assert client.calls == 6  # not 7 -- no separate curriculum LLM call
        a05 = next(s for s in result.criterion_scores if s.criterion_id == "A-05")
        assert "Curriculum-grounded" in a05.justification
        assert a05.evidence == ("curriculum quote",)

    def test_no_curriculum_id_keeps_slm_only_a05_and_six_calls(
        self, monkeypatch
    ) -> None:
        client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
        agent = _make_agent(monkeypatch, client)

        result = agent.run_full_independent(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
            reference_document_ids=None,
        )

        assert client.calls == 6
        a05 = next(s for s in result.criterion_scores if s.criterion_id == "A-05")
        assert "Curriculum-grounded" not in a05.justification

    def test_curriculum_retrieval_failure_falls_back_to_slm_only(
        self, monkeypatch
    ) -> None:
        client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
        agent = _make_agent(monkeypatch, client)

        def _raise(self, document_id, curriculum_id, db):
            raise RuntimeError("chroma unavailable")

        monkeypatch.setattr(Coordinator, "_prepare_curriculum_text", _raise)

        result = agent.run_full_independent(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
            reference_document_ids={"curriculum": uuid.uuid4()},
        )

        assert client.calls == 6
        a05 = next(s for s in result.criterion_scores if s.criterion_id == "A-05")
        assert "Curriculum-grounded" not in a05.justification


# ---------------------------------------------------------------------------
# merge_with_sme() -- pure, no I/O.
# ---------------------------------------------------------------------------
class TestMergeWithSme:
    def _sme_result(self) -> AgentEvaluationResult:
        scores = tuple(
            CriterionScore(
                criterion_id=code,
                criterion_title=f"{code} SME Title",
                score=3,
                justification=f"{code} sme justification",
                evidence=(f"{code} sme evidence",),
            )
            for code in sorted(registry.REGISTERED_CODES)
        )
        return AgentEvaluationResult(
            agent_name="sme",
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            subtotal=3.0,
            criterion_scores=scores,
            summary="",
            model_name="sme-model",
            processing_seconds=1.0,
            token_count=100,
            success=True,
        )

    def _coordinator_result(self, *, score=4) -> AgentEvaluationResult:
        a05 = CriterionScore(
            criterion_id="A-05",
            criterion_title="A-05 Coordinator Title",
            score=score,
            justification="Curriculum-grounded: 1/1 objective(s) addressed.",
            evidence=("curriculum quote",),
        )
        return AgentEvaluationResult(
            agent_name="coordinator",
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            subtotal=float(score),
            criterion_scores=(a05,),
            summary="",
            model_name="coord-model",
            processing_seconds=0.2,
            token_count=20,
            success=True,
        )

    def test_merges_nine_sme_scores_with_coordinators_own_a05(self) -> None:
        sme_result = self._sme_result()
        coordinator_result = self._coordinator_result(score=4)

        merged = Coordinator.merge_with_sme(coordinator_result, sme_result)

        assert len(merged.criterion_scores) == 10
        merged_a05 = next(
            s for s in merged.criterion_scores if s.criterion_id == "A-05"
        )
        assert merged_a05.score == 4
        expected_justification = coordinator_result.criterion_scores[0].justification
        assert merged_a05.justification == expected_justification
        others = [s for s in merged.criterion_scores if s.criterion_id != "A-05"]
        assert all(s.score == 3 for s in others)
        assert all("sme justification" in s.justification for s in others)

    def test_subtotal_recomputed_over_all_ten(self) -> None:
        sme_result = self._sme_result()  # 9 criteria at score=3
        coordinator_result = self._coordinator_result(score=4)  # A-05 at 4

        merged = Coordinator.merge_with_sme(coordinator_result, sme_result)

        expected = (3 * 9 + 4) / 10
        assert merged.subtotal == pytest.approx(expected)

    def test_agent_metadata_comes_from_coordinator_not_sme(self) -> None:
        sme_result = self._sme_result()
        coordinator_result = self._coordinator_result()

        merged = Coordinator.merge_with_sme(coordinator_result, sme_result)

        assert merged.agent_name == "coordinator"
        assert merged.model_name == coordinator_result.model_name
        assert merged.processing_seconds == coordinator_result.processing_seconds
        assert merged.token_count == coordinator_result.token_count

    def test_raises_when_coordinator_result_has_no_a05(self) -> None:
        sme_result = self._sme_result()
        coordinator_result = AgentEvaluationResult(
            agent_name="coordinator",
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            subtotal=0.0,
            criterion_scores=(),
            summary="",
            model_name="coord-model",
            processing_seconds=0.1,
            token_count=0,
            success=True,
        )

        with pytest.raises(AgentExecutionError):
            Coordinator.merge_with_sme(coordinator_result, sme_result)
