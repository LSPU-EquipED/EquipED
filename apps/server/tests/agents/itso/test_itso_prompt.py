"""Direct, stateless ITSO prompt tests."""

import json
from uuid import uuid4

from server.modules.agents.itso.prompt import build_prompt, pack_itso_chunks
from server.modules.agents.runtime.context import ITSOExecutionContext
from server.tests.agents.itso.conftest_helper import make_itso_test_snapshot


def _context(**values):
    return ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "text": "security"},),
        **values,
    )


def test_prompt_uses_mapping_context_and_is_deterministic():
    snapshot = make_itso_test_snapshot()
    criteria = [c for d in snapshot.form.domains for c in d.criteria]
    context = _context(
        provenance={"bibliography_found": True},
        prompt_version="v1",
        form_snapshot=snapshot,
    )
    first = build_prompt(
        context,
        ordered_criteria=criteria,
        reference_context=["reference"],
    )
    second = build_prompt(
        context,
        ordered_criteria=criteria,
        reference_context=["reference"],
    )
    assert first == second
    payload = json.loads(first)
    assert payload["document_chunks"][0]["chunk_id"] == "c1"
    assert "IMPORTANT" in first
    assert "rubric_context" not in payload
    assert "=== EVALUATION CRITERIA GUIDANCE ===" in first


def test_prompt_contains_level_descriptors_and_untrusted_boundary():
    snapshot = make_itso_test_snapshot()
    criteria = [c for d in snapshot.form.domains for c in d.criteria]
    context = _context(form_snapshot=snapshot)
    prompt = build_prompt(
        context,
        ordered_criteria=criteria,
        reference_context=["ref doc content"],
    )
    assert "Level 1 for ITSO-01" in prompt
    assert "Level 4 for ITSO-01" in prompt
    assert "Untrusted content boundary" in prompt


def test_itso_prompt_with_novel_codes_contains_only_snapshot_criteria():
    """Novel criterion codes are used dynamically without hardcoded legacy codes."""
    import importlib

    mig = importlib.import_module(
        "server.alembic.versions.20260829_0005_criterion_agnostic_agent_prompts"
    )

    specs = (
        ("NOVEL-ITSO-A", "Novel Title A"),
        ("NOVEL-ITSO-B", "Novel Title B"),
    )
    snapshot = make_itso_test_snapshot(criteria_specs=specs)
    criteria = [c for d in snapshot.form.domains for c in d.criteria]
    context = _context(
        form_snapshot=snapshot,
        prompt_version=mig.CRITERION_AGNOSTIC_ITSO_PROMPT,
    )
    prompt = build_prompt(
        context,
        ordered_criteria=criteria,
        reference_context=["ref doc content"],
    )
    # Novel codes are present in the prompt
    assert "NOVEL-ITSO-A" in prompt
    assert "NOVEL-ITSO-B" in prompt
    # Hardcoded legacy codes are NOT present
    for legacy_code in ("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05"):
        assert legacy_code not in prompt


def test_grounding_map_excludes_packer_added_omission_suffix():
    original = "A" * 200
    packed, packed_map, _, excerpted = pack_itso_chunks(
        ({"chunk_id": "chunk-1", "text": original},),
        max_chunks=1,
        max_excerpt_chars=200,
        prompt_budget_chars=160,
        small_doc_threshold=10,
    )

    assert excerpted is True
    assert packed[0]["text"].endswith("...")
    assert not packed_map["chunk-1"].endswith("...")
    assert packed_map["chunk-1"] in original
