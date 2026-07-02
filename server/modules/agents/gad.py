"""GAD domain agent."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from server.core.config import get_settings

from .base import BaseAgent
from .contracts import AgentEvaluationResult, CriterionScore
from .exceptions import AgentExecutionError
from .gad_prompts import (
    GAD_CRITERIA,
    GAD_CRITERIA_BY_TITLE,
    GAD_ROW_1_PROMPT,
    GAD_ROW_2_PROMPT,
    GAD_ROW_3_PROMPT,
    GAD_ROW_4_PROMPT,
    GAD_ROW_5_PROMPT,
    GadCriterion,
    score_life_experience_instances,
    score_peace_equality_instances,
    score_representation_balance,
    score_respect_potential_instances,
    score_stereotype_instances,
)


class GAD(BaseAgent):
    agent_name = "gad"
    rubric_source_type = "rubric_gad"
    domain_keywords = (
        "gender", "inclusion", "diversity", "equity", "accessibility",
        "representation", "inclusive", "fair", "bias", "equal",
        "marginalized", "sensitivity",
    )

    def __init__(self, *, llm_client: Any | None = None) -> None:
        super().__init__(llm_client=llm_client)
        self._active_criterion = GAD_CRITERIA[0]

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        reference_text: str | None = None,
        prompt_version: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        reference_document_ids: dict[str, uuid.UUID] | None = None,
        precomputed_context: dict[str, list[str]] | None = None,
        db: Any | None = None,
    ) -> AgentEvaluationResult:
        start = time.perf_counter()
        previous_criterion = self._active_criterion
        results: list[AgentEvaluationResult] = []
        try:
            for criterion in GAD_CRITERIA:
                self._active_criterion = criterion
                results.append(
                    super().run(
                        evaluation_id=evaluation_id,
                        document_id=document_id,
                        chunk_infos=chunk_infos,
                        context_text=context_text,
                        reference_text=reference_text,
                        prompt_version=prompt_version,
                        prompt_version_id=prompt_version_id,
                        reference_document_ids=reference_document_ids,
                        precomputed_context=precomputed_context,
                        db=db,
                    )
                )
        finally:
            self._active_criterion = previous_criterion

        criterion_scores = tuple(
            score
            for result in results
            for score in result.criterion_scores
        )
        subtotal = (
            sum(score.score for score in criterion_scores) / len(criterion_scores)
            if criterion_scores
            else 0.0
        )
        raw_responses = {
            result.criterion_scores[0].criterion_id: result.raw_response
            for result in results
            if result.criterion_scores
        }

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            prompt_version_id=prompt_version_id,
            summary=" ".join(result.summary for result in results if result.summary),
            model_name=results[0].model_name,
            processing_seconds=time.perf_counter() - start,
            token_count=sum(result.token_count for result in results),
            success=True,
            raw_response=json.dumps(raw_responses, ensure_ascii=False),
            metadata={
                "criteria_evaluated": [
                    score.criterion_id for score in criterion_scores
                ],
                "criterion_metadata": {
                    result.criterion_scores[0].criterion_id: result.metadata
                    for result in results
                    if result.criterion_scores
                },
            },
        )

    def _build_prompt(
        self,
        *,
        chunk_infos: list[dict[str, Any]],
        rubric_context: list[str],
        reference_context: list[str],
        reference_text: str | None,
        prompt_version: str | None,
    ) -> str:
        settings = get_settings()
        packed_chunks, chunks_dropped, text_excerpted = self._pack_chunks(
            chunk_infos,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
        )
        criterion = self._active_criterion
        payload = {
            "agent": self.agent_name,
            "prompt_version": prompt_version,
            "criterion_id": criterion.criterion_id,
            "criterion_prompt": criterion.prompt,
            "document_chunks": packed_chunks,
            "rubric_context": rubric_context,
            "reference_context": reference_context,
            "reference_text": reference_text,
            "instructions": [
                f"Evaluate only {criterion.criterion_id}: {criterion.title}.",
                "Use the criterion_prompt exactly as the scoring task.",
                "Return only the JSON object requested by criterion_prompt.",
                "Do not include markdown or text outside JSON.",
            ],
        }
        if chunks_dropped or text_excerpted:
            parts = []
            if chunks_dropped:
                parts.append(
                    "Only a subset of chunks was included due to document size."
                )
            if text_excerpted:
                parts.append(
                    "Some chunk texts were excerpted (truncated) to fit context limits."
                )
            parts.append("Focus on the provided excerpts.")
            payload["note"] = " ".join(parts)
        return json.dumps(payload, ensure_ascii=False)

    def _validate_response(self, parsed: Any) -> dict[str, Any]:
        if isinstance(parsed, dict) and "criterion_scores" in parsed:
            return super()._validate_response(parsed)
        if not isinstance(parsed, dict):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned an invalid response structure"
            )

        criterion_title = parsed.get("criterion")
        criterion = GAD_CRITERIA_BY_TITLE.get(criterion_title)
        if criterion is None:
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned an invalid criterion"
            )
        if criterion != self._active_criterion:
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned a mismatched criterion"
            )

        if criterion.kind == "representation_balance":
            return self._validate_representation_response(parsed, criterion)
        return self._validate_instance_response(parsed, criterion)

    def _validate_instance_response(
        self, parsed: dict[str, Any], criterion: GadCriterion
    ) -> dict[str, Any]:
        instance_count = parsed.get("instance_count")
        instances = parsed.get("instances")
        summary = parsed.get("summary", "")

        self._validate_non_negative_int(instance_count, "instance_count")
        if not isinstance(instances, list):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned invalid instances"
            )
        if not isinstance(summary, str):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned an invalid summary"
            )
        for index, instance in enumerate(instances):
            if not isinstance(instance, dict):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid instance "
                    f"at index {index}"
                )
            if not isinstance(instance.get("excerpt", ""), str):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid excerpt "
                    f"at index {index}"
                )
            if not isinstance(instance.get("explanation", ""), str):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid explanation "
                    f"at index {index}"
                )
            if (
                criterion.kind == "peace_equality_instances"
                and not isinstance(instance.get("category", ""), str)
            ):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid category "
                    f"at index {index}"
                )

        return {
            "criterion_id": criterion.criterion_id,
            "criterion": criterion.title,
            "instance_count": instance_count,
            "instances": instances,
            "summary": summary,
        }

    def _validate_representation_response(
        self, parsed: dict[str, Any], criterion: GadCriterion
    ) -> dict[str, Any]:
        female_count = parsed.get("female_count")
        male_count = parsed.get("male_count")
        summary = parsed.get("summary", "")

        self._validate_non_negative_int(female_count, "female_count")
        self._validate_non_negative_int(male_count, "male_count")
        if not isinstance(summary, str):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned an invalid summary"
            )

        return {
            "criterion_id": criterion.criterion_id,
            "criterion": criterion.title,
            "female_count": female_count,
            "male_count": male_count,
            "summary": summary,
        }

    def _build_criterion_scores(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        if "criterion_scores" in parsed:
            return super()._build_criterion_scores(parsed)

        criterion_id = parsed["criterion_id"]
        if criterion_id == "GAD-01":
            return self._build_stereotype_score(parsed)
        if criterion_id == "GAD-02":
            return self._build_representation_score(parsed)
        if criterion_id == "GAD-03":
            return self._build_respect_potential_score(parsed)
        if criterion_id == "GAD-04":
            return self._build_life_experience_score(parsed)
        if criterion_id == "GAD-05":
            return self._build_peace_equality_score(parsed)
        raise AgentExecutionError(
            f"Agent {self.agent_name} returned an unsupported criterion"
        )

    def _build_stereotype_score(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        instances = parsed["instances"]
        evidence = tuple(
            str(instance.get("excerpt", ""))
            for instance in instances
            if str(instance.get("excerpt", "")).strip()
        )
        explanations = [
            str(instance.get("explanation", ""))
            for instance in instances
            if str(instance.get("explanation", "")).strip()
        ]
        justification = parsed["summary"]
        if explanations:
            justification = f"{justification} Findings: {'; '.join(explanations)}"

        score = score_stereotype_instances(parsed["instance_count"])
        return self._to_criterion_scores(parsed, score, justification, evidence)

    def _build_respect_potential_score(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        score = score_respect_potential_instances(parsed["instance_count"])
        return self._build_instance_count_score(parsed, score)

    def _build_life_experience_score(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        score = score_life_experience_instances(parsed["instance_count"])
        return self._build_instance_count_score(parsed, score)

    def _build_peace_equality_score(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        score = score_peace_equality_instances(parsed["instance_count"])
        return self._build_instance_count_score(parsed, score)

    def _build_instance_count_score(
        self, parsed: dict[str, Any], score: int
    ) -> list[CriterionScore]:
        instances = parsed["instances"]
        evidence = tuple(
            str(instance.get("excerpt", ""))
            for instance in instances
            if str(instance.get("excerpt", "")).strip()
        )
        explanations = [
            self._format_instance_explanation(instance)
            for instance in instances
            if self._format_instance_explanation(instance).strip()
        ]
        justification = parsed["summary"]
        if explanations:
            justification = f"{justification} Findings: {'; '.join(explanations)}"
        return self._to_criterion_scores(parsed, score, justification, evidence)

    def _build_representation_score(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        female_count = parsed["female_count"]
        male_count = parsed["male_count"]
        difference = abs(female_count - male_count)
        score = score_representation_balance(female_count, male_count)
        justification = (
            f"{parsed['summary']} Female representations: {female_count}. "
            f"Male representations: {male_count}. Difference: {difference}."
        )
        return self._to_criterion_scores(parsed, score, justification, ())

    def _to_criterion_scores(
        self,
        parsed: dict[str, Any],
        score: int,
        justification: str,
        evidence: tuple[str, ...],
    ) -> list[CriterionScore]:
        return super()._build_criterion_scores(
            {
                "summary": parsed["summary"],
                "criterion_scores": [
                    {
                        "criterion_id": parsed["criterion_id"],
                        "criterion_title": parsed["criterion"],
                        "score": score,
                        "justification": justification,
                        "evidence": evidence,
                        "chunk_ids": (),
                    }
                ],
            }
        )

    def _validate_non_negative_int(self, value: Any, field_name: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned an invalid {field_name}"
            )

    @staticmethod
    def _format_instance_explanation(instance: dict[str, Any]) -> str:
        explanation = str(instance.get("explanation", ""))
        category = str(instance.get("category", "")).strip()
        if category:
            return f"{category}: {explanation}"
        return explanation


GADAgent = GAD


__all__ = [
    "GAD",
    "GADAgent",
    "GAD_ROW_1_PROMPT",
    "GAD_ROW_2_PROMPT",
    "GAD_ROW_3_PROMPT",
    "GAD_ROW_4_PROMPT",
    "GAD_ROW_5_PROMPT",
]
