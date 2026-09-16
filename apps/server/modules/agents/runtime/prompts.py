"""Structured, role-separated agent prompts and envelope builder."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime.slicing import downsample_source_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """Single chat turn in an OpenAI-compatible /v1/chat/completions payload."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class AgentPrompt:
    """Structured prompt cleanly separating system instructions from user context.

    - system_instruction: Persona, rubric criteria, scoring guidance, JSON schema.
      Static across evaluations for a given rubric version (KV-cacheable).
    - user_context: Untrusted SLM source text, chunks, curriculum, or reference context.
    """

    system_instruction: str
    user_context: str

    @property
    def messages(self) -> tuple[ChatMessage, ...]:
        """Convert into role-separated ChatMessage turns."""
        return (
            ChatMessage(role="system", content=self.system_instruction),
            ChatMessage(role="user", content=self.user_context),
        )

    def render_flat(self) -> str:
        """Render flat text for storage, DPO export, and string-only telemetry."""
        return f"{self.system_instruction}\n\n{self.user_context}"

    def __str__(self) -> str:
        return self.render_flat()

    def __len__(self) -> int:
        return len(self.system_instruction) + len(self.user_context) + 2

class PromptEnvelopeBuilder:
    """Encapsulates instruction assembly, budgeting, and downsampling."""
    def __init__(
        self,
        *,
        evaluator_preamble: str,
        criteria_blocks: str,
        example_json: str,
        total_budget: int = 32000,
        reserved_repair_chars: int = 600,
        gap_marker_warning: str | None = None,
    ) -> None:
        self.evaluator_preamble = evaluator_preamble.strip()
        self.criteria_blocks = criteria_blocks.strip()
        self.example_json = example_json.strip()
        self.total_budget = total_budget
        self.reserved_repair_chars = reserved_repair_chars
        self.gap_marker_warning = (
            gap_marker_warning.strip() if gap_marker_warning else None
        )

    def assemble_system_instruction(self, *, managed_prompt: str | None = None) -> str:
        parts = []
        if managed_prompt and managed_prompt.strip():
            parts.append(managed_prompt.strip())
        parts.extend(["=== EVALUATOR INSTRUCTIONS ===", self.evaluator_preamble])
        if self.gap_marker_warning:
            parts.append(self.gap_marker_warning)
        parts.extend(
            [
                "CRITERIA TO EVALUATE:",
                self.criteria_blocks,
                "REQUIRED JSON OUTPUT STRUCTURE:",
                self.example_json,
                "=== END EVALUATOR INSTRUCTIONS ===",
            ]
        )
        return "\n\n".join(parts)

    def build(
        self,
        source_text: str,
        *,
        reference_context: str | None = None,
        reference_heading: str = "REFERENCE CONTEXT",
        managed_prompt: str | None = None,
        source_heading: str = "UNTRUSTED SOURCE TEXT",
        windows: int = 6,
    ) -> tuple[AgentPrompt, str]:
        """Construct role-separated AgentPrompt and downsampled source packet.

        Guarantees:
        1. system_instruction contains evaluator instructions, criteria, and schema.
        2. user_context contains delimited untrusted source and reference text.
        3. len(system) + len(user) + reserved_repair_chars <= total_budget.
        4. returned source_packet is exact span to ground extractions against.
        """
        system_instruction = self.assemble_system_instruction(
            managed_prompt=managed_prompt
        )

        ref_block = ""
        if reference_context and reference_context.strip():
            ref_block = (
                f"\n\n=== {reference_heading} ===\n"
                f"{reference_context.strip()}\n"
                f"=== END {reference_heading} ==="
            )

        source_delimiters = f"=== {source_heading} ===\n\n=== END {source_heading} ==="
        fixed_overhead = (
            len(system_instruction)
            + len(ref_block)
            + len(source_delimiters)
            + self.reserved_repair_chars
            + 4  # separator spacing
        )

        available_for_source = self.total_budget - fixed_overhead
        if available_for_source <= 0:
            raise AgentExecutionError(
                "Agent prompt instructions and reference context exceed total budget"
            )

        source_packet = downsample_source_text(
            source_text, budget=available_for_source, windows=windows
        )

        user_context_parts = [
            f"=== {source_heading} ===\n{source_packet}\n=== END {source_heading} ==="
        ]
        if ref_block:
            user_context_parts.append(ref_block.strip())

        user_context = "\n\n".join(user_context_parts)
        prompt = AgentPrompt(
            system_instruction=system_instruction, user_context=user_context
        )

        if len(prompt) + self.reserved_repair_chars > self.total_budget:
            raise AgentExecutionError("Agent prompt exceeds total prompt budget")

        return prompt, source_packet


def build_diagnostic_repair_prompt(
    base_prompt: AgentPrompt,
    validation_error: Any,
    *,
    total_budget: int = 32000,
) -> AgentPrompt:
    """Return an AgentPrompt with diagnostic error feedback in user context."""
    detail = str(validation_error).strip()[:500]
    diagnostic_suffix = (
        f"\n\n=== VALIDATION FAILURE ===\n"
        f"The previous output failed validation: {detail}\n"
        f"Regenerate ONLY the complete JSON response matching the required schema, "
        f"criteria order, and exact field set: no extra or missing fields. "
        f"All quotes and evidence MUST be exact verbatim substrings copied from the "
        f"provided context. Do not include commentary."
    )

    candidate_user = base_prompt.user_context + diagnostic_suffix
    candidate_prompt = AgentPrompt(
        system_instruction=base_prompt.system_instruction,
        user_context=candidate_user,
    )
    if len(candidate_prompt) <= total_budget:
        return candidate_prompt

    # Fallback to compact repair if budget is tight
    compact_suffix = (
        "\n\n=== VALIDATION FAILURE ===\n"
        "Regenerate ONLY the complete JSON response matching the required schema. "
        "All quotes MUST be exact verbatim substrings."
    )
    fallback_user = base_prompt.user_context + compact_suffix
    fallback_prompt = AgentPrompt(
        system_instruction=base_prompt.system_instruction,
        user_context=fallback_user,
    )
    if len(fallback_prompt) <= total_budget:
        return fallback_prompt

    raise AgentExecutionError("Agent repair prompt exceeds total prompt budget")


__all__ = [
    "AgentPrompt",
    "ChatMessage",
    "PromptEnvelopeBuilder",
    "build_diagnostic_repair_prompt",
]
