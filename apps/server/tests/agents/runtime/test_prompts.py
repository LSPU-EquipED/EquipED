"""Tests for the runtime/prompts subsystem and polymorphic transport."""

from __future__ import annotations

from server.modules.agents.runtime.prompts import (
    AgentPrompt,
    ChatMessage,
    PromptEnvelopeBuilder,
    build_diagnostic_repair_prompt,
)


def test_agent_prompt_messages_and_flat_rendering():
    system = "You are an evaluator."
    user = "Here is the document."
    prompt = AgentPrompt(system_instruction=system, user_context=user)

    assert len(prompt.messages) == 2
    assert prompt.messages[0] == ChatMessage(role="system", content=system)
    assert prompt.messages[1] == ChatMessage(role="user", content=user)
    assert prompt.render_flat() == f"{system}\n\n{user}"
    assert str(prompt) == prompt.render_flat()
    assert len(prompt) == len(prompt.render_flat())


def test_prompt_envelope_builder_assembles_system_and_user_turns():
    builder = PromptEnvelopeBuilder(
        evaluator_preamble="You are the Coordinator.",
        criteria_blocks="CRITERION: OP-01\nTitle: Topic Coherence",
        example_json='{"summary": "ok"}',
        total_budget=1000,
        reserved_repair_chars=100,
        gap_marker_warning="[...] marks an omitted section.",
    )

    doc = "This is a short student learning module text."
    prompt, source_packet = builder.build(
        doc,
        reference_context="Curriculum roadmap text",
        reference_heading="CURRICULUM CONTEXT",
    )

    assert isinstance(prompt, AgentPrompt)
    assert "You are the Coordinator." in prompt.system_instruction
    assert "CRITERION: OP-01" in prompt.system_instruction
    assert '{"summary": "ok"}' in prompt.system_instruction
    assert "[...] marks an omitted section." in prompt.system_instruction

    # User context contains untrusted source text and curriculum context
    assert "=== UNTRUSTED SOURCE TEXT ===" in prompt.user_context
    assert source_packet in prompt.user_context
    assert "=== CURRICULUM CONTEXT ===" in prompt.user_context
    assert "Curriculum roadmap text" in prompt.user_context

    # Budget strictly respected
    assert len(prompt) + 100 <= 1000


def test_diagnostic_repair_prompt_embeds_error_message():
    base = AgentPrompt(
        system_instruction="System instructions",
        user_context="=== UNTRUSTED SOURCE TEXT ===\nDoc text\n=== END SOURCE TEXT ===",
    )
    error = ValueError("Measurement 'A-01' unit[2] evidence is not an exact substring")
    repaired = build_diagnostic_repair_prompt(base, error, total_budget=2000)

    assert isinstance(repaired, AgentPrompt)
    assert repaired.system_instruction == base.system_instruction
    assert "VALIDATION FAILURE" in repaired.user_context
    assert "Measurement 'A-01' unit[2]" in repaired.user_context
    assert len(repaired) <= 2000
