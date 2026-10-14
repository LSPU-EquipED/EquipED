"""Anonymized layout from the actual canonical PDF, never its private SLM body."""

from dataclasses import replace

import pytest
from equiped_harness import ExecutionConfig, evaluate
from equiped_harness.coordinator.objective_gauging import inventory_source
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.scoring import validate_coordinator_coverage
from test_evaluate import CURRICULUM, FakeClient, prepared_request

# Same heading breaks, explicit U+2022 split markers, syntax, wraps and terminator.
# SymbolMT renders U+2022 (not U+F0B7) in the privately inspected actual PDF.
OBJECTIVES = (
    "Describe a sample concept",
    "Recognize a sample relationship;",
    "Discuss a sample technique;",
    "Identify and explain the application of sample techniques to\n"
    "construct examples using sample methods; and",
    "Recognize the role of examples and practice in the\n"
    "Illustration Learning Framework",
)
PREFIX = (
    "Lesson\nLearning Outcomes\nIntended\nLearning\nOutcomes\nTargets/\n"
    "Objectives\nAt the end of this module, the students should be able to:\n"
)
ENTRIES = "".join(f"•\n{text}\n" for text in OBJECTIVES)
TERMINATOR = (
    "Student Learning Strategies\nOnline Activities\n(synchronous/\n"
    "Asynchronous)\nA synthetic teaching prompt.\nOverview\nSynthetic content.\n"
    "The main objective in SAMPLE has been to illustrate and discuss\n"
    "synthetic examples.\n"
)
SOURCE = PREFIX + ENTRIES + TERMINATOR


def test_actual_layout_inventory_has_five_exact_complete_source_spans():
    inventory = inventory_source(SOURCE)
    assert tuple(o.text for o in inventory.objectives) == OBJECTIVES
    assert tuple(o.objective_id for o in inventory.objectives) == tuple(
        f"OBJ-{i:04d}" for i in range(1, 6)
    )
    for objective in inventory.objectives:
        assert objective.start == SOURCE.index(objective.text)
        assert objective.end == objective.start + len(objective.text)
        assert SOURCE[objective.start : objective.end] == objective.text
    assert inventory.assessment_sections == ()


@pytest.mark.parametrize(
    "source",
    [
        PREFIX + "•\n• Marked adjacent row.\n" + TERMINATOR,
        PREFIX + "•\n•\nMarked adjacent row.\n" + TERMINATOR,
        "Learning Outcomes\nIntended\nLearning\n•\nA target.\n" + TERMINATOR,
        "Learning Outcomes\nIntended\n\nLearning\nOutcomes\n" + ENTRIES,
        PREFIX.replace("the students should be able to:", "unknown private preamble"),
        PREFIX + "An unmarked objective.\n" + ENTRIES + TERMINATOR,
        PREFIX + "•\nA target.\nUnknown Heading:\n" + ENTRIES,
        PREFIX + "•\nA target.\n  • Nested objective.\n" + TERMINATOR,
        PREFIX + "1. A target.\n3. Another target.\n" + TERMINATOR,
        PREFIX + "•\nA target.\n•\nA target.\n" + TERMINATOR,
        PREFIX + "•\nA finished target.\nunheaded prose\n" + TERMINATOR,
        PREFIX + "•\nA finished target.\nUnheaded Prose\n" + TERMINATOR,
        PREFIX + "•\nA target in the\nAn Unrelated Sentence.\n" + TERMINATOR,
        PREFIX + "•\nA target in the\nIdentify Another Concept\n" + TERMINATOR,
        PREFIX + "•\nA target in the\nUnrelated Capitalized Prose\n" + TERMINATOR,
        PREFIX + "•\nA target to\n\ncomplete a task\n" + TERMINATOR,
        PREFIX + "•\nA target in the\nIllustration Learning Framework",
        PREFIX + "•\nA target; and\n" + TERMINATOR,
        PREFIX + "•\nA target in the\n" + TERMINATOR,
        PREFIX + "•\nA target in the\nIllustration Learning Framework\n"
        "unheaded prose\n" + TERMINATOR,
        PREFIX
        + "•\nA target.\nThe main objective in SAMPLE has been to explain\n"
        + TERMINATOR,
        "The main objective\n•\nA target.\n" + SOURCE,
        "Intended\nLearning\n•\nA skipped target.\n" + SOURCE,
        PREFIX + "Intended\nunknown prose\n•\nA skipped target.\n" + TERMINATOR,
        "The main objective has been to explain:\n•\nA target.\n" + SOURCE,
        "Learning Outcomes\nIntended\nLearning\nOutcomes\n"
        "At the end of this module,\n\nthe students should be able to:\n" + ENTRIES,
        PREFIX + "•\nA target.\nOnline Activities\n(synchronous/\nUnknown)\n",
        PREFIX + "\uf0b7\nA target.\n" + TERMINATOR,
    ],
)
def test_actual_format_does_not_swallow_ambiguous_source(source):
    with pytest.raises(AgentExecutionError):
        inventory_source(source)


def test_singular_objective_discussion_sentence_does_not_terminate_assessment():
    sentence = "The main objective in SAMPLE has been to explain a technique"
    inventory = inventory_source(SOURCE + f"Quiz\n{sentence}\nsynthetic examples.\n")
    assert inventory.assessment_sections == (sentence + "\nsynthetic examples.",)
    assert len(inventory.objectives) == 5


def test_exact_split_known_terminator_and_assessment_headings():
    inventory = inventory_source(
        PREFIX + "•\nA target.\nStudent Learning\nStrategies\nTeaching only.\n"
        "Assessment\nTasks\nA synthetic task.\nReferences\nSynthetic book.\n"
    )
    assert len(inventory.objectives) == 1
    assert inventory.assessment_sections == ("A synthetic task.",)


@pytest.mark.parametrize("prefix", ["Intended", "Targets/", "Learning"])
def test_incomplete_heading_before_marker_fails_before_llm(prefix):
    request, payloads = prepared_request("coordinator")
    source = prefix + "\n•\nA skipped target.\n" + SOURCE
    client = FakeClient(payloads)
    with pytest.raises(AgentExecutionError):
        evaluate(
            replace(request, canonical_source_text=source), client, ExecutionConfig()
        )
    assert client.calls == []


@pytest.mark.parametrize(
    "prefix",
    [
        "Intended",
        "Targets/",
        "Learning",
        "## Intended",
        "A. Learning",
        "B. Targets/",
        "lEaRnInG\u00a0",
        "## Intended\nLearning",
    ],
)
@pytest.mark.parametrize("ending", ["\n•\nA skipped target.\n", "\n", ""])
def test_incomplete_heading_variants_fail_before_llm(prefix, ending):
    request, payloads = prepared_request("coordinator")
    source = SOURCE + prefix + ending
    client = FakeClient(payloads)
    with pytest.raises(AgentExecutionError):
        evaluate(
            replace(request, canonical_source_text=source), client, ExecutionConfig()
        )
    assert client.calls == []


@pytest.mark.parametrize("prefix", ["Intended", "Targets/", "Learning"])
def test_marked_nonobjective_body_payload_is_not_an_orphan_heading(prefix):
    source = SOURCE + "•\n" + prefix + "\n•\nOrdinary body item.\n"
    assert tuple(o.text for o in inventory_source(source).objectives) == OBJECTIVES


def test_known_prefix_before_unrelated_body_prose_preserves_objectives():
    source = "Course\nOrdinary introductory prose.\n" + SOURCE
    assert tuple(o.text for o in inventory_source(source).objectives) == OBJECTIVES


def test_complete_lesson_heading_and_unrelated_prose_preserve_objectives():
    source = "Lesson\nOrdinary introductory prose.\n" + SOURCE
    assert tuple(o.text for o in inventory_source(source).objectives) == OBJECTIVES


def test_actual_style_public_evaluate_keeps_missing_assessments_and_full_count():
    request, payloads = prepared_request("coordinator")
    request = replace(
        request,
        canonical_source_text=SOURCE,
        chunk_infos=({"chunk_id": "c1", "text": SOURCE},),
    )
    for payload in payloads:
        if "objective_matches" in payload:
            payload["objective_matches"] = [
                {
                    "objective_id": f"OBJ-{i:04d}",
                    "assessment_matched": False,
                    "assessment_excerpt": "",
                    "curriculum_matched": i <= 4,
                    "curriculum_excerpt": CURRICULUM if i <= 4 else "",
                }
                for i in range(1, 6)
            ]
        else:
            for row in payload["criterion_measurements"]:
                row["evidence"] = "A synthetic teaching prompt."
    result = evaluate(request, FakeClient(payloads), ExecutionConfig())
    validate_coordinator_coverage(result)
    assert len(result.criterion_scores) == 10
    assert "C-01" not in {r.criterion_id for r in result.criterion_scores}
    a05 = next(r for r in result.criterion_scores if r.criterion_id == "A-05")
    assert a05.score == 1
    assert "0/5 objectives supported" in a05.justification
    assert result.subtotal == 3.7
    assert result.advisory_outputs.score == 4
    assert tuple(
        r.objective_text for r in result.advisory_outputs.objective_matches
    ) == (OBJECTIVES)
