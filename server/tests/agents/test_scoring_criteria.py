"""Unit tests for the pure compute() halves of each SME criterion.

These test the facts -> band math directly, with no LLM involved -- the same
functions the agent will call once facts come from a shared/grouped call.
"""

from __future__ import annotations

from server.modules.agents.scoring import (
    clear_directions,
    enhancement_activities,
    interactivity,
    learner_transformation,
    objective_alignment,
    progress_monitoring,
    varied_assessment,
)


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


class TestClearDirectionsCompute:
    def test_all_tasks_clear(self) -> None:
        tasks = [
            {"text": "Activity 1", "directions": "Write a 200-word essay on...",
             "has_clear_directions": True},
            {"text": "Quiz", "directions": "Answer items 1-10 in your notebook.",
             "has_clear_directions": True},
        ]
        result = clear_directions.compute(tasks)
        assert result.clear == 2
        assert result.total == 2
        assert result.score == 4  # 100%

    def test_partial_clear_ratio(self) -> None:
        tasks = [
            {"text": "A", "directions": "Do X clearly.", "has_clear_directions": True},
            {"text": "B", "directions": "Do Y clearly.", "has_clear_directions": True},
            {"text": "C", "directions": "vague", "has_clear_directions": False},
            {"text": "D", "directions": "vague", "has_clear_directions": False},
        ]
        result = clear_directions.compute(tasks)
        assert result.clear == 2
        assert result.total == 4
        assert result.pct == 50.0
        assert result.score == 3  # 50% -> moderate band 3

    def test_clear_flag_without_directions_does_not_count(self) -> None:
        # A bare title marked clear but with no quotable instructions must not
        # count toward the numerator (real-content rule), but still counts as a
        # task in the denominator.
        tasks = [
            {"text": "Activity 1", "directions": "", "has_clear_directions": True},
            {"text": "Activity 2", "directions": "Solve all items.",
             "has_clear_directions": True},
        ]
        result = clear_directions.compute(tasks)
        assert result.clear == 1
        assert result.total == 2
        assert result.score == 3  # 1/2 = 50%

    def test_duplicate_tasks_deduped(self) -> None:
        tasks = [
            {"text": "Activity 1", "directions": "Do it.",
             "has_clear_directions": True},
            {"text": "activity 1", "directions": "Do it again.",
             "has_clear_directions": True},  # same label
        ]
        result = clear_directions.compute(tasks)
        assert result.total == 1
        assert result.clear == 1

    def test_no_tasks_scores_one(self) -> None:
        result = clear_directions.compute([])
        assert result.total == 0
        assert result.score == 1
        assert result.pct is None


class TestEnhancementActivitiesCompute:
    def test_counts_genuine_activities(self) -> None:
        elements = [
            {"text": "Enrichment", "evidence": "Research a local invention and..."},
            {"text": "Extension", "evidence": "Interview a scientist in your town."},
        ]
        result = enhancement_activities.compute(elements)
        assert result.count == 2
        assert result.score == 3  # 2 -> band 3

    def test_three_or_more_scores_four(self) -> None:
        elements = [
            {"text": f"Enhancement {i}", "evidence": f"do extra task {i}"}
            for i in range(3)
        ]
        result = enhancement_activities.compute(elements)
        assert result.count == 3
        assert result.score == 4  # 3+ -> band 4

    def test_bare_heading_without_content_dropped(self) -> None:
        elements = [
            {"text": "For further study", "evidence": ""},  # bare heading
            {"text": "Real-world task", "evidence": "Apply the concept at home."},
        ]
        result = enhancement_activities.compute(elements)
        assert result.count == 1  # only the one with real content
        assert result.score == 2  # 1 -> band 2

    def test_duplicates_deduped(self) -> None:
        elements = [
            {"text": "Enrichment", "evidence": "quote a"},
            {"text": "enrichment", "evidence": "quote a again"},  # same label
        ]
        result = enhancement_activities.compute(elements)
        assert result.count == 1

    def test_no_activities_scores_one(self) -> None:
        result = enhancement_activities.compute([])
        assert result.count == 0
        assert result.score == 1


class TestLearnerTransformationCompute:
    def test_all_higher_order_scores_four(self) -> None:
        tasks = [
            {"text": "A", "bloom_level": "apply", "evidence": "Solve the problem."},
            {"text": "B", "bloom_level": "create", "evidence": "Design a model."},
        ]
        result = learner_transformation.compute(tasks)
        assert result.higher_order == 2
        assert result.total == 2
        assert result.score == 4  # 100%

    def test_half_higher_order_scores_three(self) -> None:
        tasks = [
            {"text": "A", "bloom_level": "apply", "evidence": "Solve the problem."},
            {"text": "B", "bloom_level": "analyze", "evidence": "Compare the two."},
            {"text": "C", "bloom_level": "remember", "evidence": "List the terms."},
            {"text": "D", "bloom_level": "understand", "evidence": "Explain it."},
        ]
        result = learner_transformation.compute(tasks)
        assert result.higher_order == 2
        assert result.total == 4
        assert result.pct == 50.0
        assert result.score == 3  # 50% -> moderate band 3

    def test_higher_order_without_evidence_does_not_count(self) -> None:
        # A higher-order verb with no quotable content must not count toward
        # the numerator (real-content rule), but still counts as a task.
        tasks = [
            {"text": "Activity 1", "bloom_level": "apply", "evidence": ""},
            {"text": "Activity 2", "bloom_level": "create",
             "evidence": "Build a working prototype."},
        ]
        result = learner_transformation.compute(tasks)
        assert result.higher_order == 1
        assert result.total == 2
        assert result.score == 3  # 1/2 = 50%

    def test_duplicate_tasks_deduped(self) -> None:
        tasks = [
            {"text": "Activity 1", "bloom_level": "apply", "evidence": "Do it."},
            {"text": "activity 1", "bloom_level": "apply",
             "evidence": "Do it again."},  # same label
        ]
        result = learner_transformation.compute(tasks)
        assert result.total == 1
        assert result.higher_order == 1

    def test_unknown_level_treated_as_lower_order(self) -> None:
        tasks = [
            {"text": "A", "bloom_level": "recall", "evidence": "List the parts."},
        ]
        result = learner_transformation.compute(tasks)
        assert result.higher_order == 0
        assert result.score == 1  # 0% -> below lowest band

    def test_no_tasks_scores_one(self) -> None:
        result = learner_transformation.compute([])
        assert result.total == 0
        assert result.score == 1
        assert result.pct is None


class TestVariedAssessmentCompute:
    def test_full_variety_scores_four(self) -> None:
        assessments = [
            {"text": "Quiz 1", "assessment_type": "objective_test",
             "evidence": "Choose the correct answer for items 1-10."},
            {"text": "Essay", "assessment_type": "written",
             "evidence": "Write a 200-word essay on..."},
            {"text": "Journal", "assessment_type": "reflection",
             "evidence": "Write about what you learned this week."},
            {"text": "Demo", "assessment_type": "performance_task",
             "evidence": "Demonstrate the procedure to the class."},
            {"text": "Portfolio", "assessment_type": "project",
             "evidence": "Compile your outputs into a portfolio."},
        ]
        result = varied_assessment.compute(assessments)
        assert result.count == 5
        assert result.score == 4  # 5+ types -> band 4

    def test_two_types_scores_two(self) -> None:
        assessments = [
            {"text": "Quiz", "assessment_type": "objective_test",
             "evidence": "Answer items 1-10."},
            {"text": "Essay", "assessment_type": "written",
             "evidence": "Write about the topic."},
        ]
        result = varied_assessment.compute(assessments)
        assert result.count == 2
        assert result.score == 2  # 2 types -> band 2

    def test_repeated_instances_of_one_type_collapse(self) -> None:
        # Five multiple-choice quizzes are one type, not five -- the whole
        # point of A-02 is counting distinct types, not instances.
        assessments = [
            {"text": f"Quiz {i}", "assessment_type": "objective_test",
             "evidence": f"Answer items for quiz {i}."}
            for i in range(5)
        ]
        result = varied_assessment.compute(assessments)
        assert result.count == 1
        assert result.score == 1  # 1 type -> band 1

    def test_type_without_evidence_does_not_count(self) -> None:
        assessments = [
            {"text": "Final Exam", "assessment_type": "objective_test",
             "evidence": ""},  # bare title -> does not count
            {"text": "Essay", "assessment_type": "written",
             "evidence": "Write a reflection on..."},
        ]
        result = varied_assessment.compute(assessments)
        assert result.count == 1

    def test_unknown_type_dropped(self) -> None:
        assessments = [
            {"text": "Mystery Task", "assessment_type": "gamified_challenge",
             "evidence": "Complete the escape room."},
            {"text": "Essay", "assessment_type": "written",
             "evidence": "Write about the topic."},
        ]
        result = varied_assessment.compute(assessments)
        assert result.count == 1  # unknown type dropped, not guessed

    def test_no_assessments_scores_one(self) -> None:
        result = varied_assessment.compute([])
        assert result.count == 0
        assert result.score == 1


class TestProgressMonitoringCompute:
    def test_four_instances_scores_four(self) -> None:
        # A-03 counts INSTANCES (frequency), not distinct types -- the
        # opposite of A-02 -- because "on-going record" implies repetition
        # over time is the signal.
        mechanisms = [
            {"text": "Mid-unit check", "monitoring_type": "checkpoint",
             "evidence": "Answer this short check before moving on."},
            {"text": "Self-check", "monitoring_type": "self_assessment",
             "evidence": "Rate your confidence on each skill."},
            {"text": "Reflection", "monitoring_type": "reflection",
             "evidence": "What did you learn this week?"},
            {"text": "Final project", "monitoring_type": "cumulative",
             "evidence": "Combine skills from all lessons into one output."},
        ]
        result = progress_monitoring.compute(mechanisms)
        assert result.count == 4
        assert len(result.types) == 4
        assert result.score == 4  # 4+ -> band 4

    def test_two_instances_scores_three(self) -> None:
        mechanisms = [
            {"text": "Reflection", "monitoring_type": "reflection",
             "evidence": "What did you learn?"},
            {"text": "Self-check", "monitoring_type": "self_assessment",
             "evidence": "Rate your understanding."},
        ]
        result = progress_monitoring.compute(mechanisms)
        assert result.count == 2
        assert result.score == 3  # 2-3 -> band 3

    def test_repeated_instances_of_one_type_count_separately(self) -> None:
        # The key A-03 behavior (reversed from A-02): three DISTINCTLY
        # labelled checkpoints are three genuine instances of on-going
        # monitoring, not one -- frequency is exactly what this criterion
        # rewards.
        mechanisms = [
            {"text": f"Checkpoint {i}", "monitoring_type": "checkpoint",
             "evidence": f"Check your understanding after topic {i}."}
            for i in range(3)
        ]
        result = progress_monitoring.compute(mechanisms)
        assert result.count == 3
        assert result.types == ["checkpoint"]  # still only 1 distinct type
        assert result.score == 3  # 2-3 -> band 3

    def test_exact_duplicate_mechanism_deduped(self) -> None:
        # Unlike distinctly-labelled repeats above, the SAME mechanism quoted
        # twice (same label) must still collapse to one -- guards against the
        # LLM emitting the same finding twice inflating the count.
        mechanisms = [
            {"text": "Mid-unit check", "monitoring_type": "checkpoint",
             "evidence": "Answer this short check."},
            {"text": "mid-unit check", "monitoring_type": "checkpoint",
             "evidence": "Answer this short check again."},  # same label
        ]
        result = progress_monitoring.compute(mechanisms)
        assert result.count == 1

    def test_type_without_evidence_does_not_count(self) -> None:
        mechanisms = [
            {"text": "Reflection", "monitoring_type": "reflection",
             "evidence": ""},  # bare heading -> does not count
            {"text": "Self-check", "monitoring_type": "self_assessment",
             "evidence": "Rate your confidence."},
        ]
        result = progress_monitoring.compute(mechanisms)
        assert result.count == 1

    def test_unknown_type_dropped(self) -> None:
        mechanisms = [
            {"text": "Mystery", "monitoring_type": "gamification_badge",
             "evidence": "Earn a badge for completing the unit."},
            {"text": "Reflection", "monitoring_type": "reflection",
             "evidence": "What did you learn?"},
        ]
        result = progress_monitoring.compute(mechanisms)
        assert result.count == 1  # unknown type dropped, not guessed

    def test_no_mechanisms_scores_one(self) -> None:
        result = progress_monitoring.compute([])
        assert result.count == 0
        assert result.score == 1
