"""Program coordinator domain agent.

Adapter v2 scores all ten rubric criteria (five Organization and Presentation
OP-* and five Assessment A-*). Recovery also executes historical adapter-v1
snapshots containing the single A-05 criterion through this same pipeline.
Coordinator always scores independently and never inherits or merges Subject
Matter Expert (SME) scores.

Entry point:
- run() -- called by Supervisor in parallel with every other agent. It packs
  frozen snapshot domains into at most three grouped LLM calls, extracts
  grounded measurements per criterion, scores each measurement
  deterministically, and returns a snapshot-shaped AgentEvaluationResult.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from server.core.llm import get_llm_model_name
from server.modules.rubrics.contracts import DomainDefinition
from server.modules.rubrics.manifests import get_agent_manifest, validate_form
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

from ..contracts import AgentEvaluationResult, CriterionScore
from ..exceptions import AgentExecutionError
from ..provenance import sanitize_provenance
from ..runtime.llm import RunLLMClient
from .execution import execute_envelope
from .packing import pack_domains
from .summary import build_alignment_summary

logger = logging.getLogger(__name__)


def _format_roadmap_note(roadmap_context: dict[str, Any] | None) -> str:
    """Render only the bounded, canonical roadmap fields for Coordinator."""
    if not isinstance(roadmap_context, dict):
        return ""
    fields = (
        ("course_code", "Course code"),
        ("course_title", "Title"),
        ("year", "Year"),
        ("semester", "Semester"),
        ("tech_stack", "Tech stack"),
        ("competency_stage", "Competency stage"),
        ("course_status", "Course status"),
    )
    values: list[str] = []
    for key, label in fields:
        value = roadmap_context.get(key)
        if value is None or value == "" or isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value).strip()
        if text:
            values.append(f"{label}: {text}")
    if not values:
        return ""
    # Keep this advisory insertion compact and bounded independently of source text.
    return "Program roadmap context (advisory): " + "; ".join(values)[:1000]


def _validate_coordinator_snapshot(
    form_snapshot: EvaluationFormSnapshotDTO,
    evaluation_id: uuid.UUID,
    agent_name: str,
) -> tuple[DomainDefinition, ...]:
    """Validate the snapshot against its exact Coordinator adapter contract."""
    if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
        raise AgentExecutionError(
            "Coordinator requires a valid EvaluationFormSnapshotDTO"
        )
    if form_snapshot.agent_id != agent_name:
        raise AgentExecutionError(
            f"Snapshot agent_id '{form_snapshot.agent_id}' does not match "
            f"'{agent_name}'"
        )
    if form_snapshot.evaluation_id != evaluation_id:
        raise AgentExecutionError(
            f"Snapshot evaluation_id '{form_snapshot.evaluation_id}' does not "
            f"match '{evaluation_id}'"
        )
    if form_snapshot.adapter_key != agent_name:
        raise AgentExecutionError(
            f"Invalid snapshot adapter key '{form_snapshot.adapter_key}' or "
            f"version {form_snapshot.adapter_version}"
        )
    try:
        manifest = get_agent_manifest(agent_name, form_snapshot.adapter_version)
    except ValueError as exc:
        raise AgentExecutionError(
            f"Unsupported Coordinator adapter version {form_snapshot.adapter_version}"
        ) from exc
    report = validate_form(form_snapshot.form, manifest)
    if not report.is_valid:
        codes = ", ".join(
            issue.code for issue in report.issues if issue.severity == "error"
        )
        raise AgentExecutionError(
            f"Coordinator snapshot violates adapter {form_snapshot.adapter_version}: "
            f"{codes}"
        )
    return form_snapshot.form.domains


class Coordinator:
    agent_name = "coordinator"
    rubric_source_type = "rubric_coord"
    reference_source_types = ("syllabus",)
    domain_keywords = (
        "program",
        "outcomes",
        "objectives",
        "curriculum",
        "alignment",
        "competencies",
        "learning outcomes",
        "course",
        "standards",
        "assessment",
        "goals",
    )

    def __init__(self, *, llm_client: Any | None = None) -> None:
        self._default_llm_client = llm_client

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        form_snapshot: EvaluationFormSnapshotDTO,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        llm_client: Any | None = None,
        reference_document_ids: dict[str, Any] | None = None,
        roadmap_context: dict[str, Any] | None = None,
        canonical_source_text: str | None = None,
        curriculum_id: uuid.UUID | None = None,
        curriculum_context: str | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Score the frozen Coordinator form via grouped measurement extraction."""
        del kwargs, context_text
        domains = _validate_coordinator_snapshot(
            form_snapshot, evaluation_id, self.agent_name
        )
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        full_text = canonical_source_text
        if not full_text or not full_text.strip():
            raise AgentExecutionError("canonical source text is required")

        curriculum_id = curriculum_id or (reference_document_ids or {}).get(
            "curriculum"
        )
        if (
            curriculum_id is None
            or not isinstance(curriculum_context, str)
            or not curriculum_context.strip()
        ):
            raise AgentExecutionError(
                "Coordinator requires curriculum_id and authoritative "
                "curriculum context"
            )
        curriculum_text = curriculum_context.strip()

        client = llm_client or self._default_llm_client
        if client is None:
            raise AgentExecutionError("Coordinator requires an assigned LLM client")
        adapter = (
            client
            if isinstance(client, RunLLMClient)
            else RunLLMClient(
                client,
                self.agent_name,
                requested_model=(
                    getattr(client, "model", None) or get_llm_model_name()
                ),
            )
        )

        start = time.perf_counter()
        roadmap_note = _format_roadmap_note(roadmap_context) or None
        envelopes = pack_domains(domains)
        all_scores: list[CriterionScore] = []
        envelope_prompts: dict[str, str] = {}
        envelope_responses: dict[str, dict[str, Any]] = {}
        any_repair = False
        grounding_rejected = 0

        for idx, env_criteria in enumerate(envelopes):
            env_key = f"envelope_{idx}"
            scores, prompt, parsed, repaired = execute_envelope(
                idx,
                env_criteria,
                adapter,
                full_text,
                curriculum_text,
                prompt_preamble=roadmap_note,
            )
            all_scores.extend(scores)
            envelope_prompts[env_key] = prompt.render_flat()
            envelope_responses[env_key] = parsed
            any_repair = any_repair or repaired
            for m in parsed.get("criterion_measurements", []):
                grounding_rejected += int(m.get("_grounding_rejected_count", 0))
                # Strip the private grounding key so it never leaks into the
                # serialised ``metadata["group_responses"]`` / DPO snapshot.
                m.pop("_grounding_rejected_count", None)

        criterion_scores = tuple(all_scores)
        expected = tuple(c.criterion_code for d in domains for c in d.criteria)
        if tuple(s.criterion_id for s in criterion_scores) != expected:
            raise AgentExecutionError(
                "Coordinator scored criterion order does not match the frozen snapshot"
            )
        subtotal = sum(s.score for s in criterion_scores) / len(criterion_scores)
        total_seconds = time.perf_counter() - start
        actual_model = (
            adapter.actual_model
            if adapter.actual_model != "unknown"
            else adapter.requested_model
        )

        provenance = {
            "requested_model": adapter.requested_model,
            "actual_model": actual_model,
            "fallback_occurred": adapter.fallback_occurred,
            "repair_occurred": any_repair,
            "grouped_calls": len(envelopes),
            "logical_calls": adapter.telemetry.get("call_count", 0),
            "physical_attempts": adapter.telemetry.get("attempt_count", 0),
            "input_tokens": adapter.telemetry.get("prompt_tokens", 0),
            "output_tokens": adapter.telemetry.get("completion_tokens", 0),
            "truncation_count": adapter.telemetry.get("cap_hit_count", 0),
            "cap_hit_count": adapter.telemetry.get("cap_hit_count", 0),
            "provider_seconds_ms": round(
                adapter.telemetry.get("provider_seconds", 0) * 1000
            ),
            "grounding_rejected_count": grounding_rejected,
        }

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            summary=build_alignment_summary(criterion_scores),
            model_name=actual_model,
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
            metadata={
                "group_prompts": envelope_prompts,
                "group_responses": envelope_responses,
            },
            provenance=sanitize_provenance(provenance),
        )


__all__ = ["Coordinator"]
