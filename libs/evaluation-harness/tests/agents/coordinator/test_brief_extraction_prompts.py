from __future__ import annotations

from types import SimpleNamespace

from equiped_harness.agents.coordinator.unit_prompts import (
    extraction_prompt,
    task_prompt,
)


def _criterion():
    return SimpleNamespace(
        strategy_config=None,
        criterion_code="A-01",
        model_dump=lambda **_: {"code": "A-01"},
    )


def test_brief_task_prompt_keeps_measurement_shape_and_changes_only_finding_guidance():
    criterion = _criterion()
    common = {
        "task_id": "task",
        "criteria": (criterion,),
        "catalog": {},
        "kind": "ordinary",
    }
    full = task_prompt(**common)
    brief = extraction_prompt(**common)

    assert brief == task_prompt(**common, brief=True)
    assert "2-4 useful sentences" in full.system_instruction
    assert "2-4 useful sentences" not in brief.system_instruction
    assert "exactly one short extraction note of at most 240 characters" in (
        brief.system_instruction
    )
    for instruction in (
        "results contains one row with status and items",
        '"category":"student_task"',
        '"finding":"<why the evidence meets or falls short>"',
        '"limitation":"<observed gap, or empty>"',
    ):
        assert instruction in brief.system_instruction
        assert instruction in full.system_instruction
    assert full.user_context == brief.user_context
