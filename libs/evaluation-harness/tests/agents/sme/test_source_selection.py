"""SME must prioritize real evidence without depending on a fixed SLM template."""

from __future__ import annotations

import uuid

import pytest
from equiped_harness.agents.sme.prompt import build_envelope_prompt_and_source
from equiped_harness.agents.sme.source_selection import select_source_text
from equiped_harness.contracts import CriterionDefinition, LlmRubricGuidanceConfig
from equiped_harness.runtime.slicing import GAP_MARKER


def criterion(description: str, code: str = "CUSTOM-7") -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title="Review requirement",
        description=description,
        display_order=0,
        strategy_config=LlmRubricGuidanceConfig(guidance=description),
    )


def module(activity_heading="Activities", rubric_heading="Rubrics for Laboratory #1"):
    return (
        "SELF-PACED LEARNING MODULE\nINTELLECTUAL PROPERTY\n"
        + "Administrative copyright notice.\n" * 60
        + "\nLearning Outcomes\nExplain PHP and create a working script.\n"
        + "\nLesson Content\n"
        + "PHP scripts run on a web server and produce HTML.\n" * 200
        + f"\n{activity_heading}\nLaboratory #1 | PHP Set Up\n"
        + "Objective:\nBuild and test a PHP page.\nInstructions:\n"
        + "1. Install XAMPP.\n2. Write index.php.\n3. Test the page.\n"
        + 'Expected Output:\nA page displaying "Hello, World!".\n'
        + f"\n{rubric_heading}\n"
        + "Installation: 4 complete, 3 minor issues, 2 major issues, 1 missing.\n"
        + "\nReferences\n"
        + "PHP reference documentation.\n" * 40
    )


def test_assessment_selection_retains_objectives_lab_instructions_and_rubric():
    source = module()
    selected = select_source_text(
        source,
        (
            criterion(
                "Assess varied assessment tools and whether tasks measure objectives."
            ),
        ),
        budget=1800,
    )
    assert "Explain PHP and create a working script." in selected
    assert "1. Install XAMPP.\n2. Write index.php.\n3. Test the page." in selected
    assert 'A page displaying "Hello, World!".' in selected
    assert "Installation: 4 complete" in selected
    assert "Administrative copyright notice" not in selected
    assert len(selected) <= 1800
    assert all(part.strip() in source for part in selected.split(GAP_MARKER))


@pytest.mark.parametrize(
    "heading", ["Learning Tasks", "Learning Experience 1", "Gawain"]
)
def test_renamed_and_reordered_activity_sections_remain_selectable(heading):
    original = module(activity_heading=heading)
    # A changed layout can put references first without defining the page roles.
    source = "References\nA source entry.\n\n" + original
    selected = select_source_text(
        source,
        (criterion("Judge task directions and interactive activities."),),
        budget=1200,
    )
    assert "1. Install XAMPP." in selected
    assert len(selected) <= 1200


def test_changed_rubric_wording_changes_selection_without_relying_on_codes():
    source = module()
    activity = select_source_text(
        source, (criterion("Judge task instructions."),), budget=700
    )
    metadata = select_source_text(
        source, (criterion("Check cover metadata and copyright notices."),), budget=700
    )
    assert "Install XAMPP" in activity
    assert "Administrative copyright notice" not in activity
    assert "Administrative copyright notice" in metadata
    assert activity != metadata


def test_unknown_heading_can_be_found_from_task_structure():
    source = (
        "Introduction\n"
        + "General lesson explanation.\n" * 120
        + "\nTry This Yourself\nInstructions:\n"
        + "1. Create a PHP script.\n2. Submit your browser output.\n"
        + "Expected Output:\nA working web page.\n"
        + "\nReferences\n"
        + "Source entry.\n" * 30
    )
    selected = select_source_text(
        source, (criterion("Judge tasks and directions."),), budget=800
    )
    assert "1. Create a PHP script." in selected
    assert "2. Submit your browser output." in selected


def test_short_document_is_preserved_in_full():
    source = "Title\nA brief module with a task: write a script."
    assert (
        select_source_text(source, (criterion("Judge tasks."),), budget=1000) == source
    )


def test_explicit_learning_outcomes_after_activity_remain_a_separate_section():
    source = (
        "Activities\nInstructions:\n1. Build a web page.\n"
        + "Explain objectives before tasks.\n" * 100
        + "\nLearning Outcomes\nDistinguish server and client responsibilities.\n"
        + "\nReferences\n"
        + "Reference entry.\n" * 100
    )
    selected = select_source_text(
        source,
        (criterion("Check objectives."),),
        budget=700,
    )
    assert "Distinguish server and client responsibilities." in selected


def test_unrecognized_format_preserves_original_passages_and_budget():
    source = "\n\n".join(f"Passage {i}: unusual content for review." for i in range(80))
    criteria = (criterion("Review this unfamiliar requirement."),)
    selected = select_source_text(source, criteria, budget=400)
    assert selected
    assert len(selected) <= 400
    assert all(part.strip() in source for part in selected.split(GAP_MARKER))
    assert selected == select_source_text(source, criteria, budget=400)


def test_unknown_rubric_can_select_matching_unclassified_text():
    source = (
        "Introduction\n"
        + "Common explanatory lesson text.\n" * 100
        + "\nAccessibility note\nCaptions accompany every video demonstration.\n"
        + "\nReferences\n"
        + "Source entry.\n" * 100
    )
    selected = select_source_text(
        source, (criterion("Check video captions."),), budget=700
    )
    assert "Captions accompany every video demonstration." in selected


def test_front_matter_hint_does_not_hide_unrecognized_relevant_body():
    source = (
        "INTELLECTUAL PROPERTY\n"
        + "Administrative copyright notice.\n" * 100
        + "\nAn unfamiliar section\nCaptions accompany video demonstrations.\n"
        + "\nReferences\n"
        + "Book entry.\n" * 60
    )
    selected = select_source_text(
        source, (criterion("Check video captions."),), budget=600
    )
    assert "Captions accompany video demonstrations." in selected


def test_prompt_integration_uses_selected_source_and_reserves_repair_budget():
    prompt, source = build_envelope_prompt_and_source(
        (criterion("Judge assessment tasks and objective measurement."),),
        canonical_source_text=module(),
        prompt_budget=6500,
    )
    assert "Laboratory #1 | PHP Set Up" in source
    assert "Rubrics for Laboratory #1" in source
    assert source in prompt.user_context
    assert len(prompt) + 600 <= 6500
    assert "omitted" in prompt.system_instruction.lower()
