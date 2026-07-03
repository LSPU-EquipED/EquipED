"""GAD domain agent."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Callable

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

logger = logging.getLogger(__name__)


class GAD(BaseAgent):
    agent_name = "gad"
    rubric_source_type = "rubric_gad"
    domain_keywords = (
        "gender", "inclusion", "diversity", "equity", "accessibility",
        "representation", "inclusive", "fair", "bias", "equal",
        "marginalized", "sensitivity",
    )
    _FEMALE_LABELS = (
        r"female|females|woman|women|girl|girls|mother|mothers|sister|"
        r"sisters|daughter|daughters"
    )
    _MALE_LABELS = (
        r"male|males|man|men|boy|boys|father|fathers|brother|brothers|"
        r"son|sons"
    )
    _FEMALE_PRONOUNS = r"she|her|hers|herself"
    _MALE_PRONOUNS = r"he|him|his|himself"
    _FEMALE_TITLES = r"ms\.?|mrs\.?|miss"
    _MALE_TITLES = r"mr\.?"

    def __init__(self, *, llm_client: Any | None = None) -> None:
        super().__init__(llm_client=llm_client)
        self._active_criterion = GAD_CRITERIA[0]
        self._active_chunk_infos: list[dict[str, Any]] = []

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
        criterion_progress_callback: Callable[
            [GadCriterion, AgentEvaluationResult], None
        ] | None = None,
    ) -> AgentEvaluationResult:
        start = time.perf_counter()
        previous_criterion = self._active_criterion
        previous_chunk_infos = self._active_chunk_infos
        self._active_chunk_infos = chunk_infos
        results: list[AgentEvaluationResult] = []
        try:
            for criterion in GAD_CRITERIA:
                self._active_criterion = criterion
                criterion_result = super().run(
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
                results.append(criterion_result)
                if criterion_progress_callback is not None:
                    criterion_progress_callback(criterion, criterion_result)
        finally:
            self._active_criterion = previous_criterion
            self._active_chunk_infos = previous_chunk_infos

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

    def _emit_gad_json_response(self, payload: dict[str, Any]) -> None:
        message = (
            "[GAD_JSON_RESPONSE] "
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        )
        print(message, flush=True)
        logger.info(message)

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
        summary = self._normalize_summary(
            parsed.get("summary", ""),
            criterion=criterion,
            instance_count=instance_count,
        )

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
        summary = self._normalize_summary(
            parsed.get("summary", ""),
            criterion=criterion,
            female_count=female_count,
            male_count=male_count,
        )

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
        evidence = self._build_instance_evidence(parsed)
        explanations = [
            str(instance.get("explanation", ""))
            for instance in instances
            if str(instance.get("explanation", "")).strip()
        ]
        if explanations:
            evidence = (
                *evidence,
                f"Findings: {'; '.join(explanations)}",
            )

        score = score_stereotype_instances(parsed["instance_count"])
        return self._to_criterion_scores(parsed, score, parsed["summary"], evidence)

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
        evidence = self._build_instance_evidence(parsed)
        explanations = [
            self._format_instance_explanation(instance)
            for instance in instances
            if self._format_instance_explanation(instance).strip()
        ]
        if explanations:
            evidence = (
                *evidence,
                f"Findings: {'; '.join(explanations)}",
            )
        return self._to_criterion_scores(parsed, score, parsed["summary"], evidence)

    def _build_representation_score(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        original_female_count = parsed["female_count"]
        original_male_count = parsed["male_count"]
        female_count, male_count, count_note = self._resolve_representation_counts(
            original_female_count,
            original_male_count,
        )
        difference = abs(female_count - male_count)
        score = score_representation_balance(female_count, male_count)
        summary = parsed["summary"].strip() or (
            "Female and male representations were counted from explicit "
            "gender labels and references in the submitted material."
        )
        if count_note and (
            (original_female_count, original_male_count) == (0, 0)
            or summary == self._empty_representation_summary()
            or "no representation" in summary.lower()
            or "no meaningful" in summary.lower()
        ):
            summary = (
                "Female and male representations were counted from explicit "
                "gender labels and references in the submitted material."
            )
        evidence = (
            f"Representation counts: "
            f"Female representations: {female_count}. "
            f"Male representations: {male_count}. Difference: {difference}."
        )
        if count_note:
            evidence = f"{evidence} {count_note}"
        return self._to_criterion_scores(parsed, score, summary, (evidence,))

    def _build_instance_evidence(self, parsed: dict[str, Any]) -> tuple[str, ...]:
        instances = parsed["instances"]
        evidence = [f"Instance count: {parsed['instance_count']}"]
        evidence.extend(
            str(instance.get("excerpt", ""))
            for instance in instances
            if str(instance.get("excerpt", "")).strip()
        )
        return tuple(evidence)

    def _resolve_representation_counts(
        self,
        female_count: int,
        male_count: int,
    ) -> tuple[int, int, str]:
        fallback_female, fallback_male = self._count_labeled_representations()
        resolved_female = max(female_count, fallback_female)
        resolved_male = max(male_count, fallback_male)
        if (resolved_female, resolved_male) == (female_count, male_count):
            return female_count, male_count, ""
        return (
            resolved_female,
            resolved_male,
            (
                "Explicit gender-labeled names/references in the document "
                "were used to correct the representation counts."
            ),
        )

    def _count_labeled_representations(self) -> tuple[int, int]:
        female_total = 0
        male_total = 0
        for info in self._active_chunk_infos:
            text = str(info.get("text", ""))
            for line in text.splitlines():
                line_female = self._count_gender_labeled_line(line, "female")
                line_male = self._count_gender_labeled_line(line, "male")
                if line_female or line_male:
                    female_total += line_female
                    male_total += line_male
                    continue
                female_total += self._count_gender_references_in_line(
                    line,
                    "female",
                )
                male_total += self._count_gender_references_in_line(line, "male")
        return female_total, male_total

    def _count_gender_labeled_line(self, line: str, gender: str) -> int:
        labels = self._FEMALE_LABELS if gender == "female" else self._MALE_LABELS
        opposite_labels = (
            self._MALE_LABELS if gender == "female" else self._FEMALE_LABELS
        )
        count = 0
        label_first = re.search(
            rf"\b(?:{labels})\b\s*(?:representations?|students?|learners?|names?)?\s*[:\-]\s*(.+)",
            line,
            flags=re.IGNORECASE,
        )
        if label_first:
            count += self._count_people_items(
                self._trim_at_next_gender_label(
                    label_first.group(1),
                    opposite_labels,
                )
            )

        label_last = re.search(
            rf"(.+?)\s*(?:\||,|;|:|-)\s*\b(?:{labels})\b\s*$",
            line,
            flags=re.IGNORECASE,
        )
        if label_last:
            count += self._count_people_items(label_last.group(1))
        return count

    def _count_gender_references_in_line(self, line: str, gender: str) -> int:
        labels = self._FEMALE_LABELS if gender == "female" else self._MALE_LABELS
        pronouns = (
            self._FEMALE_PRONOUNS if gender == "female" else self._MALE_PRONOUNS
        )
        titles = self._FEMALE_TITLES if gender == "female" else self._MALE_TITLES
        total = 0
        for segment in self._split_countable_segments(line):
            explicit_count = self._count_explicit_gender_terms(segment, labels)
            title_count = len(
                re.findall(rf"\b(?:{titles})\b", segment, flags=re.IGNORECASE)
            )
            pronoun_seen = re.search(
                rf"\b(?:{pronouns})\b",
                segment,
                flags=re.IGNORECASE,
            )
            segment_total = explicit_count + title_count
            if pronoun_seen and segment_total == 0:
                segment_total = 1
            total += segment_total
        return total

    @staticmethod
    def _split_countable_segments(text: str) -> list[str]:
        return [
            segment.strip()
            for segment in re.split(r"(?<=[.!?])\s+|[;|]", text)
            if segment.strip()
        ]

    @staticmethod
    def _count_explicit_gender_terms(segment: str, labels: str) -> int:
        count = 0
        numeric_mentions = re.findall(
            rf"\b(\d+)\s+(?:{labels})\b",
            segment,
            flags=re.IGNORECASE,
        )
        for value in numeric_mentions:
            count += int(value)

        without_numeric_mentions = re.sub(
            rf"\b\d+\s+(?:{labels})\b",
            " ",
            segment,
            flags=re.IGNORECASE,
        )
        count += len(
            re.findall(
                rf"\b(?:{labels})\b",
                without_numeric_mentions,
                flags=re.IGNORECASE,
            )
        )
        return count

    @staticmethod
    def _trim_at_next_gender_label(text: str, labels: str) -> str:
        next_label = re.search(
            rf"(?:^|[.;|]\s*)\b(?:{labels})\b\s*"
            rf"(?:representations?|students?|learners?|names?)?\s*[:\-]",
            text,
            flags=re.IGNORECASE,
        )
        if next_label:
            return text[: next_label.start()]
        return text

    @staticmethod
    def _count_people_items(text: str) -> int:
        cleaned = re.sub(r"\([^)]*\)", " ", text)
        cleaned = re.sub(r"\.\s+", ",", cleaned)
        cleaned = re.sub(r"\b(?:and|or)\b", ",", cleaned, flags=re.IGNORECASE)
        parts = [
            part.strip(" \t\r\n-*0123456789.)(")
            for part in re.split(r"[,;|/]+", cleaned)
        ]
        return sum(
            1
            for part in parts
            if part
            and not part.isdigit()
            and re.search(r"[A-Za-z]", part)
        )

    def _to_criterion_scores(
        self,
        parsed: dict[str, Any],
        score: int,
        justification: str,
        evidence: tuple[str, ...],
    ) -> list[CriterionScore]:
        criterion_scores = super()._build_criterion_scores(
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
        self._emit_gad_json_response(
            self._build_display_json_payload(parsed, criterion_scores[0])
        )
        return criterion_scores

    def _build_display_json_payload(
        self,
        parsed: dict[str, Any],
        score: CriterionScore,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "criterion_id": score.criterion_id,
            "criterion": score.criterion_title,
            "score": score.score,
            "summary": score.justification,
            "justification": score.justification,
            "evidence": list(score.evidence),
            "chunk_ids": list(score.chunk_ids),
        }
        if parsed["criterion_id"] == "GAD-02":
            female_count, male_count = self._extract_representation_counts(
                score.evidence,
            )
            payload["female_count"] = female_count
            payload["male_count"] = male_count
            payload["difference"] = abs(female_count - male_count)
        else:
            payload["instance_count"] = parsed.get("instance_count", 0)
            payload["instances"] = parsed.get("instances", [])
        return payload

    @staticmethod
    def _extract_representation_counts(evidence: tuple[str, ...]) -> tuple[int, int]:
        evidence_text = " ".join(evidence)
        female_match = re.search(
            r"Female representations:\s*(\d+)",
            evidence_text,
            flags=re.IGNORECASE,
        )
        male_match = re.search(
            r"Male representations:\s*(\d+)",
            evidence_text,
            flags=re.IGNORECASE,
        )
        female_count = int(female_match.group(1)) if female_match else 0
        male_count = int(male_match.group(1)) if male_match else 0
        return female_count, male_count

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

    def _normalize_summary(self, summary: Any, *, criterion: GadCriterion, **values: Any) -> str:
        text = str(summary).strip()
        if text:
            return text

        if criterion.kind == "representation_balance":
            female_count = int(values.get("female_count", 0) or 0)
            male_count = int(values.get("male_count", 0) or 0)
            difference = abs(female_count - male_count)
            if female_count == 0 and male_count == 0:
                return self._empty_representation_summary()
            if difference <= 2:
                return (
                    "Female and male representations are approximately balanced. "
                    "No immediate change is needed."
                )
            return (
                "Female and male representations are imbalanced. This section "
                "should be revised for better balance."
            )

        instance_count = int(values.get("instance_count", 0) or 0)
        if instance_count == 0:
            if criterion.kind == "stereotype_instances":
                return (
                    "No qualifying instances were detected. This "
                    "suggests the material is acceptable for this criterion."
                )
            if criterion.kind == "respect_potential_instances":
                return (
                    "No qualifying instances were detected. This "
                    "suggests the material appears fair for this criterion."
                )
            if criterion.kind == "life_experience_instances":
                return (
                    "No qualifying instances were detected. This "
                    "suggests the material covers both male and female students' "
                    "experiences well."
                )
            if criterion.kind == "peace_equality_instances":
                return (
                    "No qualifying instances were detected. This "
                    "suggests the section does not show obvious discriminatory "
                    "content."
                )

        return (
            f"{instance_count} qualifying instance(s) were detected. The section "
            f"should be reviewed and improved for {criterion.title.lower()}."
        )

    @staticmethod
    def _empty_representation_summary() -> str:
        return (
            "No meaningful female or male representations were detected. "
            "Representation coverage is not demonstrated in this section."
        )


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
