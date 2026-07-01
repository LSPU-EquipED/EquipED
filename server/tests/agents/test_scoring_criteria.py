"""Unit tests for the pure compute() halves of each SME criterion.

These test the facts -> band math directly, with no LLM involved -- the same
functions the agent will call once facts come from a shared/grouped call.
"""

from __future__ import annotations

from server.modules.agents.scoring import interactivity, objective_alignment


class TestObjectiveAlignmentCompute:
    def test_all_objectives_measured(self) -> None:
        objectives = [{"id": 1}, {"id": 2}, {"id": 3}]
        alignment = [
            {"objective_id": 1, "is_measured": True},
            {"objective_id": 2, "is_measured": True},
            {"objective_id": 3, "is_measured": True},
        ]
        result = objective_alignment.compute(objectives, [], alignment)
        assert result.aligned == 3
        assert result.total_objectives == 3
        assert result.score == 4  # 100%

    def test_duplicate_rows_do_not_inflate(self) -> None:
        # Regression for the 10/3 = 333% bug: the LLM emitted many alignment
        # rows for only 3 objectives. Distinct measured objectives must cap at 3.
        objectives = [{"id": 1}, {"id": 2}, {"id": 3}]
        alignment = [
            {"objective_id": 1, "is_measured": True},
            {"objective_id": 1, "is_measured": True},
            {"objective_id": 2, "is_measured": True},
            {"objective_id": 2, "is_measured": True},
            {"objective_id": 3, "is_measured": True},
            {"objective_id": 3, "is_measured": True},
        ]
        result = objective_alignment.compute(objectives, [], alignment)
        assert result.aligned == 3
        assert result.pct == 100.0

    def test_unknown_objective_id_ignored(self) -> None:
        objectives = [{"id": 1}, {"id": 2}]
        alignment = [
            {"objective_id": 1, "is_measured": True},
            {"objective_id": 99, "is_measured": True},  # hallucinated id
        ]
        result = objective_alignment.compute(objectives, [], alignment)
        assert result.aligned == 1  # 99 does not count
        assert result.score == 3  # 1/2 = 50%

    def test_no_objectives_scores_one(self) -> None:
        result = objective_alignment.compute([], [], [])
        assert result.score == 1
        assert result.pct is None


class TestInteractivityCompute:
    def test_counts_genuine_elements(self) -> None:
        elements = [
            {"text": "Answer Me", "evidence": "List 5 inventions and explain each."},
            {"text": "Reflection", "evidence": "How did S&T shape history?"},
            {"text": "Performance Task", "evidence": "Design a poster showing..."},
        ]
        result = interactivity.compute(elements)
        assert result.count == 3
        assert result.score == 3  # 2-3 elements -> band 3

    def test_bare_title_without_content_dropped(self) -> None:
        elements = [
            {"text": "Activity 1", "evidence": ""},  # bare title -> does not count
            {"text": "Try This", "evidence": "Solve for x in the equation..."},
        ]
        result = interactivity.compute(elements)
        assert result.count == 1  # only the one with real content
        assert result.score == 2  # 1 element -> band 2

    def test_duplicates_deduped(self) -> None:
        elements = [
            {"text": "Answer Me", "evidence": "quote a"},
            {"text": "answer me", "evidence": "quote a again"},  # same label
        ]
        result = interactivity.compute(elements)
        assert result.count == 1

    def test_four_or_more_scores_four(self) -> None:
        elements = [
            {"text": f"Task {i}", "evidence": f"do task {i}"} for i in range(4)
        ]
        result = interactivity.compute(elements)
        assert result.count == 4
        assert result.score == 4

    def test_no_elements_scores_one(self) -> None:
        result = interactivity.compute([])
        assert result.count == 0
        assert result.score == 1
