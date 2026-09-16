"""Gender and Development domain agent."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.rubrics.manifests import get_agent_manifest, validate_form
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

from ..contracts import AgentEvaluationResult
from ..exceptions import AgentExecutionError
from .pipeline import GADScoredAgent


class GAD(GADScoredAgent):
    agent_name = "gad"
    rubric_source_type = "rubric_gad"
    domain_keywords = (
        "gender",
        "inclusion",
        "diversity",
        "equity",
        "accessibility",
        "representation",
        "inclusive",
        "fair",
        "bias",
        "equal",
        "marginalized",
        "sensitivity",
    )

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        form_snapshot: EvaluationFormSnapshotDTO,
        prompt_version: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        llm_client: Any | None = None,
        provenance: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Score all GAD criteria from snapshot form through code-side GAD engine."""
        del kwargs
        if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
            raise AgentExecutionError(
                "GAD evaluation requires a valid EvaluationFormSnapshotDTO"
            )
        if form_snapshot.agent_id != self.agent_name:
            raise AgentExecutionError(
                f"form_snapshot agent_id mismatch: expected '{self.agent_name}', "
                f"got '{form_snapshot.agent_id}'"
            )
        if form_snapshot.evaluation_id != evaluation_id:
            raise AgentExecutionError(
                f"form_snapshot evaluation_id mismatch: expected '{evaluation_id}', "
                f"got '{form_snapshot.evaluation_id}'"
            )
        if form_snapshot.adapter_key != self.agent_name:
            raise AgentExecutionError(
                f"form_snapshot adapter_key mismatch: expected "
                f"'{self.agent_name}', got '{form_snapshot.adapter_key}'"
            )
        try:
            manifest = get_agent_manifest(
                self.agent_name, form_snapshot.adapter_version
            )
        except ValueError as exc:
            raise AgentExecutionError(
                f"Unsupported GAD adapter version {form_snapshot.adapter_version}"
            ) from exc
        report = validate_form(form_snapshot.form, manifest)
        if not report.is_valid:
            codes = ", ".join(
                issue.code for issue in report.issues if issue.severity == "error"
            )
            raise AgentExecutionError(
                f"GAD snapshot violates adapter {form_snapshot.adapter_version}: "
                f"{codes}"
            )

        criteria = [c for d in form_snapshot.form.domains for c in d.criteria]
        if not criteria:
            raise AgentExecutionError("form_snapshot contains no criteria")
        if len(criteria) > 10:
            raise AgentExecutionError(
                f"form_snapshot criteria count {len(criteria)} exceeds maximum 10"
            )

        has_text = any(str(chunk.get("text", "")).strip() for chunk in chunk_infos)
        if not chunk_infos or not has_text:
            raise AgentExecutionError("document chunks are required for evaluation")

        return self._run_gad_scoring(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=chunk_infos,
            form_snapshot=form_snapshot,
            prompt_version=prompt_version,
            prompt_version_id=prompt_version_id,
            provenance=provenance,
            llm_client=llm_client,
        )
