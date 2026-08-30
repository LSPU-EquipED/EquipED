"""Gender and Development domain agent."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.rubrics.contracts import CountBandConfig, RatioBandConfig
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
        if form_snapshot.adapter_key != "gad" or form_snapshot.adapter_version != 1:
            raise AgentExecutionError(
                f"form_snapshot adapter mismatch: expected 'gad' v1, "
                f"got '{form_snapshot.adapter_key}' v{form_snapshot.adapter_version}"
            )

        criteria = [c for d in form_snapshot.form.domains for c in d.criteria]
        if not criteria:
            raise AgentExecutionError("form_snapshot contains no criteria")
        if len(criteria) > 10:
            raise AgentExecutionError(
                f"form_snapshot criteria count {len(criteria)} exceeds maximum 10"
            )

        seen_keys: set[str] = set()
        for crit in criteria:
            k = crit.criterion_code.strip().lower()
            if k in seen_keys:
                raise AgentExecutionError(
                    f"Duplicate criterion section key in form_snapshot: '{k}'"
                )
            seen_keys.add(k)

            config = crit.strategy_config
            if isinstance(config, CountBandConfig):
                if config.mode != "maximum_count":
                    raise AgentExecutionError(
                        f"Unsupported count mode '{config.mode}' for GAD criterion "
                        f"'{crit.criterion_code}' (only 'maximum_count' supported)"
                    )
            elif isinstance(config, RatioBandConfig):
                if config.mode != "absolute_difference":
                    raise AgentExecutionError(
                        f"Unsupported ratio mode '{config.mode}' for GAD criterion "
                        f"'{crit.criterion_code}'"
                    )
            else:
                strat_name = getattr(config, "strategy", type(config).__name__)
                raise AgentExecutionError(
                    f"Unsupported strategy config '{strat_name}' "
                    f"for GAD criterion '{crit.criterion_code}'"
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
