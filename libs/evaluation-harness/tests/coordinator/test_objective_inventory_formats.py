"""Synthetic PDF-shaped Coordinator v3 objective inventory regressions."""

import pytest
from equiped_harness.coordinator.objective_gauging import inventory_source
from equiped_harness.exceptions import AgentExecutionError


def test_institutional_heading_aliases_leadin_and_five_bullets_keep_exact_spans():
    source = (
        "Lesson Learning Outcomes\nIntended Learning Outcomes\n"
        "Targets/ Objectives\nAt the end of this module,\n"
        "the students should be able to:\n"
        "• Identify a concept.\n• Explain a concept.\n"
        "• Compare examples.\n• Apply a method.\n• Evaluate a result.\n"
        "Student Learning Strategies\nGroup discussion.\n"
        "Online Activities (Synchronous/ Asynchronous)\nQuiz\nQuiz: answer questions.\n"
    )
    inventory = inventory_source(source)
    expected = [
        "Identify a concept.",
        "Explain a concept.",
        "Compare examples.",
        "Apply a method.",
        "Evaluate a result.",
    ]
    assert [o.objective_id for o in inventory.objectives] == [
        f"OBJ-{i:04}" for i in range(1, 6)
    ]
    assert [o.text for o in inventory.objectives] == expected
    assert all(source[o.start : o.end] == o.text for o in inventory.objectives)
    assert inventory.assessment_sections == ("Quiz: answer questions.",)


def test_unicode_whitespace_headings_preface_and_pdf_bullets_preserve_raw_spans():
    source = (
        "Lesson\u00a0Learning Outcomes\nIntended Learning Outcomes\n"
        "Targets/ Objectives\nAt the end of this module,\u00a0\n"
        "the students should be able to:\n"
        "·\u00a0Identify a concept.\n· Explain a concept with 3·14 data.\n"
        "·\nCompare examples.\n·\nApply a method.\n"
        "· Evaluate\u00a0a result.\n"
        "Student Learning Strategies\nGroup discussion.\n"
        "Quiz\nQuiz: answer questions.\n"
    )
    inventory = inventory_source(source)
    expected = [
        "Identify a concept.",
        "Explain a concept with 3·14 data.",
        "Compare examples.",
        "Apply a method.",
        "Evaluate\u00a0a result.",
    ]
    assert len(inventory.objectives) == len(expected) == 5
    assert [o.objective_id for o in inventory.objectives] == [
        f"OBJ-{i:04}" for i in range(1, 6)
    ]
    assert [o.text for o in inventory.objectives] == expected
    assert all(source[o.start : o.end] == o.text for o in inventory.objectives)
    assert inventory.objectives[-1].start == source.index("Evaluate\u00a0a result.")
    assert inventory.assessment_sections == ("Quiz: answer questions.",)


def test_line_wrapped_leadin_and_split_markers():
    source = (
        "Learning Outcomes:\nAfter completing the course,\n"
        "learners will be able to:\n1.\nExplain a process.\n"
        "2)\nDescribe a result.\nAssessment:\nQuiz.\n"
    )
    inventory = inventory_source(source)
    assert [o.text for o in inventory.objectives] == [
        "Explain a process.",
        "Describe a result.",
    ]
    assert all(source[o.start : o.end] == o.text for o in inventory.objectives)


@pytest.mark.parametrize(
    "source",
    [
        "Objectives:\nA learner should be able to do something.\n",
        "Objectives:\n1. Explain a complete idea.\nAdjacent unheaded prose.\n",
        "Objectives:\n1. Explain.\n3. Skip.\n",
        "Objectives:\n1. Explain.\n2. Explain.\n",
        "Targets for Discussion:\n1. Explain.\n",
        "Objectives:\n"
        "At the beginning of this module, students should be able to:\n"
        "1. Explain.\n",
    ],
)
def test_unsupported_or_ambiguous_format_remains_fail_closed(source):
    with pytest.raises(AgentExecutionError):
        inventory_source(source)


def test_unindented_pdf_wrap_only_after_clear_incomplete_line():
    source = (
        "Objectives:\n1. Explain the relationship between\nvariables and results.\n"
        "Assessment:\nQuiz.\n"
    )
    inventory = inventory_source(source)
    assert (
        inventory.objectives[0].text
        == "Explain the relationship between\nvariables and results."
    )
    assert (
        source[inventory.objectives[0].start : inventory.objectives[0].end]
        == inventory.objectives[0].text
    )


@pytest.mark.parametrize(
    "body",
    [
        "An unnumbered target about the module\n1. Marked objective.\nAssessment:\n"
        "Quiz.",
        "An unnumbered objective about the module\n1. Marked objective.\n"
        "Assessment:\nQuiz.",
        "At the end of this module,\n1. Marked objective.\nAssessment:\nQuiz.",
        "At the end of this module,\nAssessment:\nQuiz.",
        "At the end of this module,",
        "At the end of this module,\nLearning Outcomes:\n1. Marked objective.",
        "At the end of this module,\nunknown narrative about the course\n"
        "1. Marked objective.",
        "At the end of this module, students should be able to:\n"
        "At the end of this module, students should be able to:\n"
        "1. Marked objective.",
        "1. First objective.\n"
        "At the end of this module, students should be able to:\n"
        "2. Second objective.",
        "students should be able to:\n1. Marked objective.",
        "1.\n2. Second objective.\nAssessment:\nQuiz.",
        "1.\n1. First objective.\nAssessment:\nQuiz.",
        "•\n  • Nested objective.\nAssessment:\nQuiz.",
        "1.\n  First objective.\nAssessment:\nQuiz.",
        "1. Explain the relationship between\nvariables and results.",
        "1. Explain the relationship between\nvariables and\nAssessment:\nQuiz.",
        "1. Explain the relationship between\nvariables and results.\n"
        "more unrelated body prose\nAssessment:\nQuiz.",
        "Learning Outcomes:\nIntroduction:\nBody.\nObjectives:\n1. Marked objective.",
        "1. First objective.\nLearning Outcomes:\nObjectives:\nAssessment:\nQuiz.",
    ],
)
def test_denominator_safety_rejects_discarded_or_merged_source(body):
    with pytest.raises(AgentExecutionError):
        inventory_source("Objectives:\n" + body + "\n")


def test_each_nonempty_objective_section_can_have_one_complete_preface():
    source = (
        "Objectives:\nAt the end of this module, students should be able to:\n"
        "1. First objective.\nIntroduction:\nBody.\nLearning Outcomes:\n"
        "After completing the\ncourse,\nlearners will be able to:\n"
        "1. Second objective.\nAssessment:\nQuiz.\n"
    )
    inventory = inventory_source(source)
    assert [o.text for o in inventory.objectives] == [
        "First objective.",
        "Second objective.",
    ]
    assert all(source[o.start : o.end] == o.text for o in inventory.objectives)


def test_unindented_wrap_bounded_by_next_marker():
    source = (
        "Objectives:\n1. Explain relationships between\nvariables.\n"
        "2. Compare results.\nAssessment:\nQuiz.\n"
    )
    assert len(inventory_source(source).objectives) == 2


@pytest.mark.parametrize(
    "terminator",
    [
        "Student Learning Strategies",
        "Online Activities",
        "Online Activities (Synchronous/ Asynchronous)",
    ],
)
def test_teaching_and_online_headings_are_not_assessment_evidence(terminator):
    source = f"Objectives:\n1. Explain a concept.\n{terminator}\nTask A.\n"
    inventory = inventory_source(source)
    assert len(inventory.objectives) == 1
    assert inventory.assessment_sections == ()
