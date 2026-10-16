"""Varied source layouts and complete, grounded semantic-inventory contracts."""

import json
import time

import pytest
from equiped_harness import CompletionResult, ExecutionConfig, evaluate, execution_scope
from equiped_harness.coordinator.catalog import _catalog
from equiped_harness.coordinator.objective_gauging import ObjectiveSource
from equiped_harness.coordinator.source_inventory import resolve_inventory
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.runtime.llm import RunLLMClient
from equiped_harness.scoring import validate_coordinator_coverage
from test_coordinator_current_engine import CurrentFake, request


class InventoryClient:
    model = "fake"

    def __init__(self, regions, *, mutations=()):
        self.regions = regions
        self.mutations = iter(mutations)
        self.calls = []
        self.scoring = CurrentFake()

    def generate_result(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if prompt.user_context.startswith("{"):
            context, _ = json.JSONDecoder().raw_decode(prompt.user_context)
            if context.get("task_id", "").startswith("inventory-"):
                rows = []
                for number, value in context["lines"]:
                    start, _, kind = next(
                        r for r in self.regions if r[0] <= number <= r[1]
                    )
                    if kind == "objective" and number != start:
                        kind = "continuation"
                    rows.append(kind)
                mutate = next(self.mutations, None)
                if mutate:
                    rows = mutate(rows)
                return CompletionResult(json.dumps({"results": rows}), "fake")
        if "objective-assessment" in prompt.user_context:
            from test_coordinator_current_engine import _prompt_context

            context = _prompt_context(prompt.user_context)
            sid = context["source_catalog"][0]["source_id"]
            return CompletionResult(
                json.dumps(
                    {
                        "results": [
                            {"objective_id": obj["objective_id"], "source_ids": [sid]}
                            for obj in context["objectives"]
                        ]
                    }
                ),
                "fake",
            )
        return self.scoring.generate_result(prompt, **kwargs)


def resolve(source, client):
    with execution_scope(ExecutionConfig()):
        return resolve_inventory(
            source, RunLLMClient(client, "coordinator"), deadline=time.monotonic() + 60
        )


@pytest.mark.parametrize(
    "body,expected",
    [
        (
            "a) Explain a concept.\nb) Apply a method.",
            ("Explain a concept.", "Apply a method."),
        ),
        (
            "(a) Explain a concept.\n(b) Apply a method.",
            ("Explain a concept.", "Apply a method."),
        ),
        (
            "I. Explain a concept.\nII. Apply a method.",
            ("Explain a concept.", "Apply a method."),
        ),
        (
            "LO1: Explain a concept.\nLO2: Apply a method.",
            ("Explain a concept.", "Apply a method."),
        ),
        (
            "\uf0b7 Explain a concept.\n▪ Apply a method.",
            ("Explain a concept.", "Apply a method."),
        ),
        (
            "Explain a concept.\nApply a method.",
            ("Explain a concept.", "Apply a method."),
        ),
        (
            "Explain a concept. Apply a method.",
            ("Explain a concept.", "Apply a method."),
        ),
        (
            "1. Explain a concept; 2. Apply a method.",
            ("Explain a concept;", "Apply a method."),
        ),
        (
            "1. Explain a concept.\t2. Apply a method.",
            ("Explain a concept.", "Apply a method."),
        ),
    ],
)
def test_varied_markers_prose_and_table_cells_keep_exact_source_spans(body, expected):
    lines = body.count("\n") + 1
    source = (
        "What you should achieve\n"
        + body
        + "\nNow demonstrate it\nSolve a sample problem.\n"
    )
    regions = [
        (1, 1, "other"),
        (2, lines + 1, "objective"),
        (lines + 2, lines + 2, "other"),
        (lines + 3, lines + 3, "assessment"),
    ]
    client = InventoryClient(regions)
    resolved = resolve(source, client)
    inventory = resolved.inventory
    assert tuple(o.text for o in inventory.objectives) == expected
    assert all(source[o.start : o.end] == o.text for o in inventory.objectives)
    assert inventory.assessment_sections == ("Solve a sample problem.",)
    assert len(resolved.generations) == len(client.calls) == 2
    assert len({call[1]["deadline"] for call in client.calls}) == 1


def test_full_current_pipeline_captures_inventory_calls_and_freezes_the_denominator():
    source = (
        "Expected capabilities\na) Explain a concept.\nb) Apply a method.\n"
        "Your turn\nSolve a sample problem.\n"
    )
    client = InventoryClient(
        [(1, 1, "other"), (2, 3, "objective"), (4, 4, "other"), (5, 5, "assessment")]
    )
    result = evaluate(request(source=source), client, ExecutionConfig())
    validate_coordinator_coverage(result)
    assert result.success and len(result.criterion_scores) == 10
    assert len(result.advisory_outputs.objective_matches) == 2
    assert len(result.generations) == 13
    assert result.provenance["grouped_calls"] == 13
    assert sum(g.unit_key.startswith("inventory-") for g in result.generations) == 2
    assert set(result.metadata["group_responses"]) == set(
        result.metadata["envelope_status"]
    )
    assert (
        result.metadata["current_bundle"]["objective"]["assessment_available"] is True
    )


def test_unfamiliar_assessment_heading_is_not_silently_scored_as_missing():
    source = (
        "Objectives:\n1. Explain a concept.\nReferences:\nBook.\n"
        "Your turn\nSolve a sample problem.\n"
    )
    client = InventoryClient(
        [(1, 1, "other"), (2, 2, "objective"), (3, 5, "other"), (6, 6, "assessment")]
    )
    assert resolve(source, client).inventory.assessment_sections == (
        "Solve a sample problem.",
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rows: rows[:-1],
        lambda rows: ["fabricated", *rows[1:]],
        lambda rows: [True, *rows[1:]],
        lambda rows: [{"start": 1, "end": 2, "kind": "objective"}],
        lambda rows: [*rows, "objective"],
    ],
)
def test_invalid_source_ranges_get_one_bounded_repair_then_fail(mutate):
    client = InventoryClient(
        [(1, 1, "other"), (2, 2, "objective")], mutations=(mutate, mutate)
    )
    with pytest.raises(AgentExecutionError):
        resolve("Expected capabilities\nExplain a concept.\n", client)
    assert len(client.calls) == 2


def test_a_corrected_inventory_is_checked_again_before_scoring():
    # Extraction misses an objective, but still accounts for its line as other.
    def wrong(rows):
        return ["other"] * len(rows)

    client = InventoryClient([(1, 1, "other"), (2, 2, "objective")], mutations=(wrong,))
    result = resolve("Expected capabilities\nExplain a concept.\n", client)
    assert len(result.inventory.objectives) == 1
    assert len(client.calls) == len(result.generations) == 3


def test_unresolved_semantic_disagreement_does_not_produce_a_score():
    def wrong(rows):
        return ["other"] * len(rows)

    client = InventoryClient(
        [(1, 1, "other"), (2, 2, "objective")], mutations=(None, wrong)
    )
    with pytest.raises(AgentExecutionError, match="could not verify"):
        resolve("Expected capabilities\nExplain a concept.\n", client)
    assert len(client.calls) == 3


def test_windows_cover_late_objectives_and_join_adjacent_continuations():
    source = (
        "Expected capabilities\n"
        + "Discussion text.\n" * 22
        + "Explain a concept\nwith examples.\n"
        + "More discussion.\n" * 30
        + "Apply a method.\n"
    )
    client = InventoryClient(
        [
            (1, 23, "other"),
            (24, 25, "objective"),
            (26, 55, "other"),
            (56, 56, "objective"),
        ]
    )
    result = resolve(source, client)
    assert tuple(o.text for o in result.inventory.objectives) == (
        "Explain a concept\nwith examples.",
        "Apply a method.",
    )
    assert len(client.calls) == 10
    shown = []
    for prompt, _ in client.calls[::2]:
        shown.extend(number for number, _ in json.loads(prompt.user_context)["lines"])
    assert shown == list(range(1, 57))


def test_no_explicit_objectives_reports_an_actionable_failure_after_full_scan():
    client = InventoryClient([(1, 2, "other")])
    with pytest.raises(
        AgentExecutionError, match="provide readable learning objectives"
    ):
        resolve("A lesson\nDiscussion only.\n", client)
    assert len(client.calls) == 2


def test_truncated_input_is_not_sent_to_a_model():
    from equiped_harness.runtime.slicing import GAP_MARKER

    client = InventoryClient([])
    with pytest.raises(AgentExecutionError, match="truncated"):
        resolve("Expected capabilities\n" + GAP_MARKER + "\nA target.", client)
    assert not client.calls


def test_catalog_keeps_every_character_of_long_assessment_and_curriculum():
    source = "Question: " + "a" * 9000
    curriculum = "b" * 9100
    catalog = _catalog(source, ObjectiveSource((), (source,)), curriculum)
    for kind, original in [("assessment", source), ("curriculum", curriculum)]:
        entries = [item for item in catalog.values() if item.source == kind]
        assert "".join(item.as_dict()["text"] for item in entries) == original
        assert all(original[item.start : item.end] == item.text for item in entries)
        assert all(len(item.text) <= 4000 for item in entries)
