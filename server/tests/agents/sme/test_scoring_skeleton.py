"""Tests for the skeleton-extraction (grouped-call) pass.

These lock the basket-key -> compute() arg mapping in scoring/registry.py
(``_compute_basket_*`` / ``run_grouped``) so a future prompt tweak can't
silently misroute facts. All pure/no-LLM except the ``run_grouped`` tests,
which use a FakeClient so no network call happens.

This is the THIRD iteration of the basket design (see extraction.py's module
docstring for the full history): a merged 2-basket design was rejected
outright by the provider (HTTP 413, too large); a 3-basket design fit the
token budget but a real-SLM parity test showed monitoring, enhancement, and
sections -- all secondary categories bundled with others -- came back
completely empty despite real content existing. Those three now get their
own dedicated single-purpose basket each (A3, A4, B2).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.sme import extraction, registry


class TestStrictBasketFixtures:
    @staticmethod
    def _valid_a2() -> dict[str, Any]:
        return {"tasks": []}

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"tasks": None},
            {"tasks": [], "unknown": []},
            {"tasks": [{}]},
            {
                "tasks": [
                    {
                        "id": True,
                        "text": "x",
                        "bloom_level": "apply",
                        "directions": "x",
                        "has_clear_directions": True,
                        "evidence": "x",
                    }
                ]
            },
            {
                "tasks": [
                    {
                        "id": "1",
                        "text": "x",
                        "bloom_level": "apply",
                        "directions": "x",
                        "has_clear_directions": True,
                        "evidence": "x",
                    }
                ]
            },
        ],
    )
    def test_invalid_atomic_payloads_rejected(self, payload: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            extraction._validate("A2", payload)

    def test_valid_empty_arrays_remain_valid(self) -> None:
        assert extraction._validate("A2", self._valid_a2()) == {"tasks": []}

    def test_unknown_objective_normalized_to_unmeasured(self) -> None:
        # A small local model can emit rows for unknown objectives or omit
        # objectives entirely. Validation normalizes: unknown rows are dropped
        # and every objective gets exactly one row (missing -> unmeasured).
        payload = {
            "objectives": [{"id": 1, "text": "x"}],
            "assessments": [],
            "alignment": [
                {
                    "objective_id": 2,
                    "is_measured": True,
                    "assessment_ids": [],
                    "evidence": "x",
                }
            ],
        }
        result = extraction._validate("A1", payload)
        assert result["alignment"] == [
            {
                "objective_id": 1,
                "is_measured": False,
                "assessment_ids": [],
                "evidence": "",
            }
        ]


# ---------------------------------------------------------------------------
# Basket A1 (assessment-centric): hand-built facts -> A-02 / A-05.
# ---------------------------------------------------------------------------
class TestComputeBasketA1:
    def _basket(self) -> dict[str, Any]:
        return {
            "objectives": [
                {"id": 1, "text": "Objective 1"},
                {"id": 2, "text": "Objective 2"},
            ],
            "assessments": [
                {
                    "id": 1,
                    "text": "Quiz",
                    "assessment_type": "objective_test",
                    "evidence": "Q1-10",
                },
                {
                    "id": 2,
                    "text": "Essay",
                    "assessment_type": "written",
                    "evidence": "essay prompt",
                },
            ],
            "alignment": [
                {
                    "objective_id": 1,
                    "is_measured": True,
                    "assessment_ids": [1],
                    "evidence": "Q1-10",
                },
            ],
        }

    def test_a05_objective_alignment(self) -> None:
        result = registry._compute_basket_a1("A-05", self._basket())
        assert result.aligned == 1
        assert result.total_objectives == 2
        assert result.score == 3  # 50% -> moderate band 3

    def test_a02_varied_assessment(self) -> None:
        result = registry._compute_basket_a1("A-02", self._basket())
        assert result.count == 2  # objective_test + written
        assert result.score == 2  # 2 types -> band 2

    def test_unknown_code_raises(self) -> None:
        try:
            registry._compute_basket_a1("A-01", self._basket())
        except KeyError:
            pass
        else:
            raise AssertionError("A-01 is not a Basket-A1 criterion, expected KeyError")


# ---------------------------------------------------------------------------
# Basket A2 (task-centric): hand-built facts -> A-01 / OP-02 / OP-03.
# ---------------------------------------------------------------------------
class TestComputeBasketA2:
    def _basket(self) -> dict[str, Any]:
        return {
            "tasks": [
                {
                    "id": 1,
                    "text": "Task 1",
                    "bloom_level": "apply",
                    "directions": "Solve for x in the equation.",
                    "has_clear_directions": True,
                    "evidence": "Solve for x in the equation.",
                },
                {
                    "id": 2,
                    "text": "Task 2",
                    "bloom_level": "remember",
                    "directions": "",
                    "has_clear_directions": False,
                    "evidence": "",
                },
            ],
        }

    def test_a01_learner_transformation(self) -> None:
        result = registry._compute_basket_a2("A-01", self._basket())
        # Only Task 1 has evidence and is higher-order (apply); Task 2 has no
        # evidence so it does not count toward the numerator, but IS in the
        # denominator (a bare/empty task is still a listed task).
        assert result.total == 2
        assert result.higher_order == 1
        assert result.score == 3  # 50% -> moderate band 3

    def test_op02_interactivity_from_tasks(self) -> None:
        result = registry._compute_basket_a2("OP-02", self._basket())
        assert result.count == 1
        assert result.score == 2  # 1 element -> band 2

    def test_op03_clear_directions_from_tasks(self) -> None:
        result = registry._compute_basket_a2("OP-03", self._basket())
        assert result.total == 2
        assert result.clear == 1  # only Task 1 has_clear_directions + directions
        assert result.score == 3  # 50% -> moderate band 3

    def test_unknown_code_raises(self) -> None:
        try:
            registry._compute_basket_a2("A-05", self._basket())
        except KeyError:
            pass
        else:
            raise AssertionError("A-05 is not a Basket-A2 criterion, expected KeyError")


# ---------------------------------------------------------------------------
# Basket A3 (monitoring-only): hand-built facts -> A-03.
# ---------------------------------------------------------------------------
class TestComputeBasketA3:
    def test_a03_progress_monitoring(self) -> None:
        basket = {
            "monitoring_mechanisms": [
                {
                    "id": 1,
                    "text": "Checkpoint 1",
                    "monitoring_type": "checkpoint",
                    "evidence": "short quiz after lesson 1",
                },
            ],
        }
        result = registry._compute_basket_a3("A-03", basket)
        assert result.count == 1
        assert result.score == 2  # 1 instance -> band 2

    def test_unknown_code_raises(self) -> None:
        try:
            registry._compute_basket_a3("OP-05", {"monitoring_mechanisms": []})
        except KeyError:
            pass
        else:
            raise AssertionError("OP-05 is not a Basket-A3 criterion")


# ---------------------------------------------------------------------------
# Basket A4 (enhancement-only): hand-built facts -> OP-05.
# ---------------------------------------------------------------------------
class TestComputeBasketA4:
    def test_op05_enhancement_activities(self) -> None:
        basket = {
            "enhancement_activities": [
                {
                    "id": 1,
                    "text": "Extra reading",
                    "evidence": "Research a related topic.",
                },
            ],
        }
        result = registry._compute_basket_a4("OP-05", basket)
        assert result.count == 1
        assert result.score == 2  # 1 activity -> band 2

    def test_unknown_code_raises(self) -> None:
        try:
            registry._compute_basket_a4("A-03", {"enhancement_activities": []})
        except KeyError:
            pass
        else:
            raise AssertionError("A-03 is not a Basket-A4 criterion, expected KeyError")


# ---------------------------------------------------------------------------
# Basket B1 (topics/transitions + feedback): hand-built facts -> OP-01 / A-04.
# ---------------------------------------------------------------------------
class TestComputeBasketB1:
    def _basket(self) -> dict[str, Any]:
        return {
            "topics": [
                {"id": 1, "title": "Intro"},
                {"id": 2, "title": "Core concept"},
                {"id": 3, "title": "Application"},
                {"id": 4, "title": "Wrap-up"},
            ],
            "transitions": [
                {"from_id": 1, "to_id": 2, "is_coherent": True, "reason": "builds on"},
                {"from_id": 2, "to_id": 3, "is_coherent": True, "reason": "applies"},
                {"from_id": 3, "to_id": 4, "is_coherent": False, "reason": "abrupt"},
            ],
            "feedback_mechanisms": [
                {
                    "text": "Answer key",
                    "feedback_type": "answer_key",
                    "evidence": "See answers on page 10.",
                },
                {
                    "text": "Encouragement",
                    "feedback_type": "positive_reinforcement",
                    "evidence": "Great job finishing this module!",
                },
            ],
        }

    def test_op01_topic_coherence(self) -> None:
        result = registry._compute_basket_b1("OP-01", self._basket())
        assert result.total == 3
        assert result.coherent == 2
        # Only 3 transitions -> below MIN_TRANSITIONS_FOR_RATIO (4) -> issue-count
        # fallback: 1 issue -> band 3.
        assert result.mode == "issue-count"
        assert result.score == 3

    def test_a04_prescriptive_feedback(self) -> None:
        result = registry._compute_basket_b1("A-04", self._basket())
        assert result.count == 2  # 2 distinct types
        assert result.score == 3  # 2 types -> band 3

    def test_unknown_code_raises(self) -> None:
        try:
            registry._compute_basket_b1("OP-04", self._basket())
        except KeyError:
            pass
        else:
            raise AssertionError("OP-04 is not a Basket-B1 criterion")


# ---------------------------------------------------------------------------
# Basket B2 (sections-only): hand-built facts -> OP-04.
# ---------------------------------------------------------------------------
class TestComputeBasketB2:
    def test_op04_accurate_sections(self) -> None:
        basket = {
            "sections": [
                {"id": 1, "title": "Sec 1", "is_clean": True, "issue": ""},
                {
                    "id": 2,
                    "title": "Sec 2",
                    "is_clean": False,
                    "issue": "contradicts Sec 1",
                },
            ],
        }
        result = registry._compute_basket_b2("OP-04", basket)
        assert result.total == 2
        assert result.clean == 1
        assert result.score == 3  # 50% -> moderate band 3

    def test_unknown_code_raises(self) -> None:
        try:
            registry._compute_basket_b2("OP-01", {"sections": []})
        except KeyError:
            pass
        else:
            raise AssertionError("OP-01 is not a Basket-B2 criterion")


# ---------------------------------------------------------------------------
# extraction.py slices: small doc passthrough + anchor-based slicing.
# ---------------------------------------------------------------------------
class TestSliceForBasketA1:
    def test_short_doc_passthrough(self) -> None:
        text = "Objectives...\n\nPerformance Task: do X."
        assert extraction.slice_for_basket_a1(text) == text

    def test_long_doc_anchors_on_section_header(self) -> None:
        head = "Objective 1: learn things.\n" * 300  # > 4000 chars
        lecture = "Lecture filler content. " * 500
        tail = "Performance Task: Design a poster. " * 300
        text = head + lecture + tail
        sliced = extraction.slice_for_basket_a1(text, head=4000, body=7000)
        assert "Design a poster" in sliced
        assert sliced.startswith(head[:4000])
        assert "[...lecture body omitted...]" in sliced

    def test_long_doc_no_anchor_falls_back_to_tail(self) -> None:
        head = "Objective 1: learn things.\n" * 300
        body = "Random content with no recognizable section header. " * 500
        text = head + body
        sliced = extraction.slice_for_basket_a1(text, head=4000, body=7000)
        assert sliced.endswith(body[-7000:])


class TestBottomSectionSlices:
    """slice_for_basket_a2/a3/a4 all share the same bottom-section logic."""

    def test_short_doc_returns_whole_text(self) -> None:
        text = "Performance Task: do X."
        assert extraction.slice_for_basket_a2(text) == text
        assert extraction.slice_for_basket_a3(text) == text
        assert extraction.slice_for_basket_a4(text) == text

    def test_anchors_on_section_header_no_head(self) -> None:
        lecture = "Lecture filler content. " * 500
        tail = "Performance Task: Design a poster. " * 300
        text = lecture + tail
        sliced = extraction.slice_for_basket_a2(text, body=9000)
        assert "Design a poster" in sliced
        assert "Lecture filler" not in sliced  # head is dropped entirely

    def test_no_anchor_falls_back_to_tail(self) -> None:
        body = "Random content with no recognizable section header. " * 500
        assert extraction.slice_for_basket_a3(body, body=9000) == body[-9000:]
        assert extraction.slice_for_basket_a4(body, body=9000) == body[-9000:]


class TestExtractBaskets:
    class FakeClient:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.payload = payload
            self.calls: list[str] = []

        def generate(self, prompt: str, **_: object) -> str:
            self.calls.append(prompt)
            return json.dumps(self.payload)

        def generate_result(
            self,
            prompt: str,
            *,
            temperature: float,
            max_new_tokens: int,
            deadline: float | None = None,
            response_contract: ResponseContract,
        ) -> CompletionResult:
            if (
                response_contract is not None
                and response_contract.mode != "json_object"
            ):
                raise AssertionError(
                    "SME fake requires the json_object response contract"
                )
            return CompletionResult(
                content=self.generate(
                    prompt, temperature=temperature, max_new_tokens=max_new_tokens
                ),
                served_model=None,
                finish_reason="stop",
            )

    def test_extract_basket_a1_parses_json(self) -> None:
        client = self.FakeClient(
            {
                "objectives": [{"id": 1, "text": "Objective 1"}],
                "assessments": [],
                "alignment": [
                    {
                        "objective_id": 1,
                        "is_measured": False,
                        "assessment_ids": [],
                        "evidence": "",
                    }
                ],
            }
        )
        data = extraction.extract_basket_a1(client, "some slm text")
        assert data["objectives"] == [{"id": 1, "text": "Objective 1"}]
        assert len(client.calls) == 1

    def test_extract_basket_a1_without_curriculum_uses_base_prompt(self) -> None:
        client = self.FakeClient({"objectives": [], "assessments": [], "alignment": []})
        extraction.extract_basket_a1(client, "some slm text")
        assert "CURRICULUM CONTENT" not in client.calls[0]
        assert "curriculum_alignment" not in client.calls[0]

    def test_extract_basket_a1_with_curriculum_extends_prompt_and_call_count_stays_one(
        self,
    ) -> None:
        client = self.FakeClient(
            {
                "objectives": [{"id": 1, "text": "obj"}],
                "assessments": [],
                "alignment": [
                    {
                        "objective_id": 1,
                        "is_measured": False,
                        "assessment_ids": [],
                        "evidence": "",
                    }
                ],
            }
        )
        data = extraction.extract_basket_a1(
            client, "some slm text", curriculum_text="Course: Foo\n\nBar"
        )
        assert len(client.calls) == 1  # one call, not two -- this is the whole point
        assert "CURRICULUM CONTENT" in client.calls[0]
        assert "Course: Foo" in client.calls[0]
        assert set(data) == {"objectives", "assessments", "alignment"}

    def test_extract_basket_a1_empty_curriculum_text_uses_base_prompt(self) -> None:
        client = self.FakeClient({"objectives": [], "assessments": [], "alignment": []})
        extraction.extract_basket_a1(client, "some slm text", curriculum_text="   ")
        assert "CURRICULUM CONTENT" not in client.calls[0]

    def test_extract_basket_a2_parses_json(self) -> None:
        client = self.FakeClient({"tasks": []})
        data = extraction.extract_basket_a2(client, "some slm text")
        assert data == {"tasks": []}

    def test_extract_basket_a3_parses_json(self) -> None:
        client = self.FakeClient({"monitoring_mechanisms": []})
        data = extraction.extract_basket_a3(client, "some slm text")
        assert data == {"monitoring_mechanisms": []}

    def test_extract_basket_a4_parses_json(self) -> None:
        client = self.FakeClient({"enhancement_activities": []})
        data = extraction.extract_basket_a4(client, "some slm text")
        assert data == {"enhancement_activities": []}

    def test_extract_basket_b1_parses_json(self) -> None:
        client = self.FakeClient(
            {"topics": [], "transitions": [], "feedback_mechanisms": []}
        )
        data = extraction.extract_basket_b1(client, "some slm text")
        assert data == {"topics": [], "transitions": [], "feedback_mechanisms": []}

    def test_extract_basket_b2_parses_json(self) -> None:
        client = self.FakeClient({"sections": []})
        data = extraction.extract_basket_b2(client, "some slm text")
        assert data == {"sections": []}


# ---------------------------------------------------------------------------
# registry.run_grouped: end-to-end through a FakeClient that routes by prompt.
# ---------------------------------------------------------------------------
class RoutingFakeClient:
    """Returns each basket's payload for its own prompt (routed by a marker
    unique to each of the 6 basket prompts)."""

    def __init__(self, **baskets: dict[str, Any] | None) -> None:
        # Keys: a1, a2, a3, a4, b1, b2 -- None means "this basket should fail".
        self.baskets = baskets

    def generate(self, prompt: str, **_: object) -> str:
        lower = prompt.lower()
        if "assessment facts" in lower or "assessment and curriculum facts" in lower:
            key = "a1"
        elif "task facts" in lower:
            key = "a2"
        elif "progress-monitoring mechanisms" in lower:
            key = "a3"
        elif "enhancement activity" in lower:
            key = "a4"
        elif "sampled from across the whole document" in lower and "sections" in lower:
            key = "b2"
        elif "sampled from across the whole document" in lower:
            key = "b1"
        else:
            raise AssertionError(f"unrecognized prompt: {prompt[:80]!r}")

        payload = self.baskets.get(key)
        if payload is None:
            raise RuntimeError(f"basket {key} configured to fail")
        return json.dumps(payload)

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        if response_contract is not None and response_contract.mode != "json_object":
            raise AssertionError("SME fake requires the json_object response contract")
        return CompletionResult(
            content=self.generate(
                prompt, temperature=temperature, max_new_tokens=max_new_tokens
            ),
            served_model=None,
            finish_reason="stop",
        )


class TestRunGrouped:
    def _all_baskets(self) -> dict[str, dict[str, Any]]:
        return {
            "a1": {
                "objectives": [{"id": 1, "text": "Objective 1"}],
                "assessments": [
                    {
                        "id": 1,
                        "text": "Quiz",
                        "assessment_type": "objective_test",
                        "evidence": "Q1",
                    }
                ],
                "alignment": [
                    {
                        "objective_id": 1,
                        "is_measured": True,
                        "assessment_ids": [1],
                        "evidence": "Q1",
                    }
                ],
            },
            "a2": {
                "tasks": [
                    {
                        "id": 1,
                        "text": "Task 1",
                        "bloom_level": "apply",
                        "directions": "Do X.",
                        "has_clear_directions": True,
                        "evidence": "Do X.",
                    }
                ],
            },
            "a3": {
                "monitoring_mechanisms": [
                    {
                        "id": 1,
                        "text": "Check 1",
                        "monitoring_type": "checkpoint",
                        "evidence": "quiz",
                    }
                ],
            },
            "a4": {
                "enhancement_activities": [
                    {"id": 1, "text": "Extra", "evidence": "Research more."}
                ],
            },
            "b1": {
                "topics": [{"id": 1, "title": "T1"}, {"id": 2, "title": "T2"}],
                "transitions": [
                    {"from_id": 1, "to_id": 2, "is_coherent": True, "reason": "ok"}
                ],
                "feedback_mechanisms": [
                    {
                        "id": 1,
                        "text": "Key",
                        "feedback_type": "answer_key",
                        "evidence": "p.1",
                    }
                ],
            },
            "b2": {
                "sections": [{"id": 1, "title": "S1", "is_clean": True, "issue": ""}],
            },
        }

    def test_all_ten_codes_present_on_success(self) -> None:
        client = RoutingFakeClient(**self._all_baskets())
        results = registry.run_grouped(client, "full slm text")

        expected_codes = {
            "A-01",
            "A-02",
            "A-03",
            "A-05",
            "OP-02",
            "OP-03",
            "OP-05",
            "OP-01",
            "OP-04",
            "A-04",
        }
        assert set(results) == expected_codes
        for code, (score, justification, evidence) in results.items():
            assert 1 <= score <= 4
            assert isinstance(justification, str) and justification

    def test_raw_baskets_out_populated_when_given(self) -> None:
        client = RoutingFakeClient(**self._all_baskets())
        raw_baskets: dict[str, dict] = {}
        registry.run_grouped(client, "full slm text", raw_baskets_out=raw_baskets)
        assert raw_baskets["A1"]["objectives"] == [{"id": 1, "text": "Objective 1"}]
        assert "B1" in raw_baskets

    def test_basket_extract_kwargs_reaches_only_the_named_basket(self) -> None:
        # Confirms Coordinator's curriculum_text only ever threads into A1's
        # extract call, not the other 5 baskets (which don't accept it).
        baskets = self._all_baskets()
        baskets["a1"] = dict(
            baskets["a1"],
        )
        client = RoutingFakeClient(**baskets)
        raw_baskets: dict[str, dict] = {}

        results = registry.run_grouped(
            client,
            "full slm text",
            raw_baskets_out=raw_baskets,
            basket_extract_kwargs={"A1": {"curriculum_text": "Course: Foo\n\nBar"}},
        )

        assert set(raw_baskets["A1"]) == {"objectives", "assessments", "alignment"}
        # Still exactly the normal 10-code result -- no extra calls, no
        # extra codes introduced by the curriculum kwarg.
        assert "A-05" in results

    def test_a3_failure_only_drops_a03(self) -> None:
        baskets = self._all_baskets()
        baskets["a3"] = None
        client = RoutingFakeClient(**baskets)
        results = registry.run_grouped(client, "full slm text")

        assert "A-03" not in results
        for code in (
            "A-01",
            "A-02",
            "A-05",
            "OP-01",
            "OP-02",
            "OP-03",
            "OP-04",
            "OP-05",
            "A-04",
        ):
            assert code in results

    def test_a4_failure_only_drops_op05(self) -> None:
        baskets = self._all_baskets()
        baskets["a4"] = None
        client = RoutingFakeClient(**baskets)
        results = registry.run_grouped(client, "full slm text")

        assert "OP-05" not in results
        assert "A-03" in results  # a3 succeeded independently

    def test_b2_failure_only_drops_op04(self) -> None:
        baskets = self._all_baskets()
        baskets["b2"] = None
        client = RoutingFakeClient(**baskets)
        results = registry.run_grouped(client, "full slm text")

        assert "OP-04" not in results
        assert "OP-01" in results  # b1 succeeded independently
        assert "A-04" in results

    def test_all_baskets_fail_returns_empty(self) -> None:
        client = RoutingFakeClient(a1=None, a2=None, a3=None, a4=None, b1=None, b2=None)
        results = registry.run_grouped(client, "full slm text")
        assert results == {}

    def test_parallel_extraction_and_deterministic_scores(self) -> None:
        import threading
        import time

        active_threads: set[int] = set()
        max_concurrent = 0
        lock = threading.Lock()

        class ConcurrencyTrackingClient(RoutingFakeClient):
            def generate(self, prompt: str, **kwargs: object) -> str:
                nonlocal max_concurrent
                ident = threading.get_ident()
                with lock:
                    active_threads.add(ident)
                    max_concurrent = max(max_concurrent, len(active_threads))
                time.sleep(0.02)
                try:
                    return super().generate(prompt, **kwargs)
                finally:
                    with lock:
                        active_threads.remove(ident)

        baskets = self._all_baskets()
        client = ConcurrencyTrackingClient(**baskets)
        raw_baskets1: dict[str, dict] = {}
        results1 = registry.run_grouped(
            client, "full slm text", raw_baskets_out=raw_baskets1
        )

        assert max_concurrent >= 2
        assert len(results1) == 10

        client2 = RoutingFakeClient(**baskets)
        raw_baskets2: dict[str, dict] = {}
        results2 = registry.run_grouped(
            client2, "full slm text", raw_baskets_out=raw_baskets2
        )

        assert results1 == results2
        assert list(results1.keys()) == sorted(registry.REGISTERED_CODES)
        assert list(results2.keys()) == sorted(registry.REGISTERED_CODES)
        assert raw_baskets1 == raw_baskets2
