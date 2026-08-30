"""Execution pipeline for SME strategy-shaped snapshot evaluation."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from server.core.llm import ResponseContract, get_llm_client, get_llm_model_name
from server.modules.rubrics.contracts import (
    CountBandConfig,
    DomainDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

from ..contracts import AgentEvaluationResult, CriterionScore
from ..exceptions import AgentExecutionError
from ..provenance import sanitize_provenance
from ..runtime.llm import RunLLMClient
from .execution import execute_envelope
from .packing import pack_domains

logger = logging.getLogger(__name__)

_IMPROVEMENT_THRESHOLD = 2
_IMPROVEMENT_SUGGESTIONS: dict[str, str] = {
    "A-01": "incorporating more higher-order thinking tasks",
    "A-02": "diversifying the types of assessments used",
    "A-03": "adding more checkpoints or reflection activities",
    "A-04": "providing more varied feedback or intervention mechanisms",
    "A-05": "aligning more assessments directly to the stated objectives",
    "OP-01": "adding clearer transitions between topics",
    "OP-02": "adding more interactive elements with real task content",
    "OP-03": "providing clearer, more complete task directions",
    "OP-04": "reviewing sections for clarity and internal consistency",
    "OP-05": "adding more enrichment activities beyond the core content",
}
_DEFAULT_SUGGESTION = "revisiting this criterion"


def _join_with_and(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def build_improvement_summary(criterion_scores: tuple[CriterionScore, ...]) -> str:
    """Deterministic, code-computed summary with generic fallback for novel codes."""
    if not criterion_scores:
        return ""

    strongest = max(criterion_scores, key=lambda c: c.score)
    positive = f"{strongest.criterion_title} is the strongest area."

    weak = sorted(
        (c for c in criterion_scores if c.score <= _IMPROVEMENT_THRESHOLD),
        key=lambda c: c.score,
    )
    if weak:
        titles = _join_with_and([c.criterion_title for c in weak])
        verb = "needs" if len(weak) == 1 else "need"
        suggestions = _join_with_and(
            [
                _IMPROVEMENT_SUGGESTIONS.get(c.criterion_id, _DEFAULT_SUGGESTION)
                for c in weak
            ]
        )
        improvement = f"{titles} {verb} improvement; consider {suggestions}."
    else:
        improvement = "No areas need improvement."

    return f"{positive} {improvement}"


def validate_sme_snapshot(
    form_snapshot: EvaluationFormSnapshotDTO,
    evaluation_id: uuid.UUID,
    agent_name: str,
) -> tuple[DomainDefinition, ...]:
    """Validate snapshot invariants and supported strategies before LLM execution."""
    if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
        raise AgentExecutionError("SME requires a valid EvaluationFormSnapshotDTO")

    if form_snapshot.agent_id != agent_name:
        raise AgentExecutionError(
            f"Snapshot agent_id '{form_snapshot.agent_id}' does not "
            f"match '{agent_name}'"
        )
    if form_snapshot.evaluation_id != evaluation_id:
        raise AgentExecutionError(
            f"Snapshot evaluation_id '{form_snapshot.evaluation_id}' does not "
            f"match '{evaluation_id}'"
        )
    if form_snapshot.adapter_key != agent_name or form_snapshot.adapter_version != 1:
        raise AgentExecutionError(
            f"Invalid snapshot adapter key '{form_snapshot.adapter_key}' "
            f"or version {form_snapshot.adapter_version}"
        )

    domains = form_snapshot.form.domains
    total_criteria = sum(len(d.criteria) for d in domains)
    if total_criteria < 1:
        raise AgentExecutionError("SME snapshot contains no criteria")
    if total_criteria > 20:
        raise AgentExecutionError(
            f"SME snapshot exceeds 20 criteria ({total_criteria})"
        )

    for d in domains:
        for c in d.criteria:
            cfg = c.strategy_config
            if isinstance(cfg, LlmRubricGuidanceConfig):
                pass
            elif isinstance(cfg, CountBandConfig):
                if cfg.mode != "minimum_count":
                    raise AgentExecutionError(
                        f"SME criterion '{c.criterion_code}' has unsupported "
                        f"count mode '{cfg.mode}'"
                    )
            elif isinstance(cfg, RatioBandConfig):
                if cfg.mode != "coverage_percentage":
                    raise AgentExecutionError(
                        f"SME criterion '{c.criterion_code}' has unsupported "
                        f"ratio mode '{cfg.mode}'"
                    )
            else:
                raise AgentExecutionError(
                    f"SME criterion '{c.criterion_code}' has unsupported "
                    f"strategy '{cfg.strategy}'"
                )

    return domains


class EngineScoredAgent:
    """Base scoring agent driven exclusively by evaluation form snapshots."""

    agent_name = "sme"
    rubric_source_type = "rubric_sme"

    def __init__(self, *, llm_client: Any | None = None) -> None:
        self._default_llm_client = llm_client

    def _resolve_full_text(
        self,
        canonical_source_text: str | None = None,
    ) -> str:
        if not canonical_source_text or not canonical_source_text.strip():
            raise AgentExecutionError("canonical source text is required")
        return canonical_source_text

    def _run_snapshot_scoring(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        form_snapshot: EvaluationFormSnapshotDTO,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        canonical_source_text: str | None = None,
        llm_client: Any | None = None,
        prompt_preamble: str | None = None,
    ) -> AgentEvaluationResult:
        domains = validate_sme_snapshot(form_snapshot, evaluation_id, self.agent_name)
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        full_text = self._resolve_full_text(canonical_source_text)

        start = time.perf_counter()
        primary_client = llm_client or self._default_llm_client or get_llm_client()
        client = (
            primary_client
            if isinstance(primary_client, RunLLMClient)
            else RunLLMClient(
                primary_client,
                self.agent_name,
                requested_model=(
                    getattr(primary_client, "model", None) or get_llm_model_name()
                ),
                default_response_contract=ResponseContract.json_object(),
            )
        )

        envelopes = pack_domains(domains)
        all_scores: list[CriterionScore] = []
        envelope_prompts: dict[str, str] = {}
        envelope_responses: dict[str, dict[str, Any]] = {}
        any_repair_occurred = False

        for idx, env_criteria in enumerate(envelopes):
            env_key = f"envelope_{idx}"
            scores, prompt_text, response_dict, repair_occurred = execute_envelope(
                idx,
                env_criteria,
                client,
                full_text,
                prompt_preamble=prompt_preamble,
            )
            all_scores.extend(scores)
            envelope_prompts[env_key] = prompt_text
            envelope_responses[env_key] = response_dict
            if repair_occurred:
                any_repair_occurred = True

        criterion_scores = tuple(all_scores)
        expected_codes = tuple(
            criterion.criterion_code
            for domain in domains
            for criterion in domain.criteria
        )
        actual_codes = tuple(score.criterion_id for score in criterion_scores)
        if actual_codes != expected_codes:
            raise AgentExecutionError(
                "SME scored criterion order does not match the frozen form snapshot"
            )
        subtotal = (
            sum(s.score for s in criterion_scores) / len(criterion_scores)
            if criterion_scores
            else 0.0
        )
        total_seconds = time.perf_counter() - start
        actual_model = (
            client.actual_model
            if client.actual_model != "unknown"
            else client.requested_model
        )

        provenance_dict: dict[str, Any] = {
            "requested_model": client.requested_model,
            "actual_model": actual_model,
            "fallback_occurred": client.fallback_occurred,
            "repair_occurred": any_repair_occurred,
            "logical_calls": client.telemetry.get("call_count", 0),
            "physical_attempts": client.telemetry.get("attempt_count", 0),
            "input_tokens": client.telemetry.get("prompt_tokens", 0),
            "output_tokens": client.telemetry.get("completion_tokens", 0),
            "truncation_count": client.telemetry.get("cap_hit_count", 0),
            "cap_hit_count": client.telemetry.get("cap_hit_count", 0),
            "grouped_calls": len(envelopes),
            "provider_seconds_ms": round(
                client.telemetry.get("provider_seconds", 0) * 1000
            ),
            "trim_count": client.telemetry.get("cap_hit_count", 0),
        }

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            summary=build_improvement_summary(criterion_scores),
            model_name=actual_model,
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
            metadata={
                "group_prompts": envelope_prompts,
                "group_responses": envelope_responses,
            },
            provenance=sanitize_provenance(provenance_dict),
        )


__all__ = [
    "EngineScoredAgent",
    "build_improvement_summary",
    "validate_sme_snapshot",
]
