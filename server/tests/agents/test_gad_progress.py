"""Tests for row-by-row GAD progress callbacks."""

from __future__ import annotations

import json
import time
from threading import Lock
from uuid import uuid4

from server.core.llm import LocalLLMClient
from server.modules.agents.gad import GAD
from server.modules.agents.gad_prompts import GAD_CRITERIA


class _CriterionAwareLLM:
    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        payload = json.loads(prompt)
        criterion_id = payload["criterion_id"]

        if criterion_id == "GAD-01":
            return json.dumps(
                {
                    "criterion": "The material is free from gender stereotypes",
                    "instance_count": 1,
                    "instances": [
                        {
                            "excerpt": "women should stay home",
                            "explanation": "stereotype",
                        }
                    ],
                    "summary": "criterion 1",
                }
            )
        if criterion_id == "GAD-02":
            return json.dumps(
                {
                    "criterion": (
                        "The material shows females and males an equal number "
                        "of times"
                    ),
                    "female_count": 4,
                    "male_count": 2,
                    "summary": "criterion 2",
                }
            )
        if criterion_id == "GAD-03":
            return json.dumps(
                {
                    "criterion": (
                        "The material shows females and males with equal "
                        "respect and potential"
                    ),
                    "instance_count": 0,
                    "instances": [],
                    "summary": "criterion 3",
                }
            )
        if criterion_id == "GAD-04":
            return json.dumps(
                {
                    "criterion": (
                        "The material reflects the needs and life experiences "
                        "of both male and female students"
                    ),
                    "instance_count": 2,
                    "instances": [
                        {
                            "excerpt": "boys are leaders",
                            "explanation": "bias",
                        }
                    ],
                    "summary": "criterion 4",
                }
            )
        if criterion_id == "GAD-05":
            return json.dumps(
                {
                    "criterion": (
                        "The material promotes peace and equality regardless "
                        "of gender, race, class, disability, religion, sexual "
                        "orientation, or ethnic background"
                    ),
                    "instance_count": 3,
                    "instances": [
                        {
                            "excerpt": "exclude by religion",
                            "explanation": "prejudice",
                            "category": "religion",
                        }
                    ],
                    "summary": "criterion 5",
                }
            )

        raise AssertionError(f"unexpected criterion id: {criterion_id}")


class _ParallelCriterionAwareLLM(_CriterionAwareLLM, LocalLLMClient):
    def __init__(self) -> None:
        self._lock = Lock()
        self._active_calls = 0
        self.max_active_calls = 0

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        payload = json.loads(prompt)
        delay = {
            "GAD-01": 0.05,
            "GAD-02": 0.04,
            "GAD-03": 0.03,
            "GAD-04": 0.02,
            "GAD-05": 0.01,
        }[payload["criterion_id"]]
        with self._lock:
            self._active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self._active_calls)
        try:
            time.sleep(delay)
            return super().generate(
                prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            )
        finally:
            with self._lock:
                self._active_calls -= 1


class _BlankSummaryLLM(_CriterionAwareLLM):
    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        payload = json.loads(prompt)
        criterion_id = payload["criterion_id"]
        if criterion_id == "GAD-01":
            return json.dumps(
                {
                    "criterion": "The material is free from gender stereotypes",
                    "instance_count": 0,
                    "instances": [],
                    "summary": "",
                }
            )
        return super().generate(
            prompt, temperature=temperature, max_new_tokens=max_new_tokens
        )


class _ZeroRepresentationLLM(_CriterionAwareLLM):
    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        payload = json.loads(prompt)
        criterion_id = payload["criterion_id"]
        if criterion_id == "GAD-02":
            return json.dumps(
                {
                    "criterion": (
                        "The material shows females and males an equal number "
                        "of times"
                    ),
                    "female_count": 0,
                    "male_count": 0,
                    "summary": "No representations were identified.",
                }
            )
        return super().generate(
            prompt, temperature=temperature, max_new_tokens=max_new_tokens
        )


def test_gad_prompts_request_human_reviewer_summaries() -> None:
    for criterion in GAD_CRITERIA:
        assert "human reviewer comment" in criterion.prompt
        assert "what should be improved" in criterion.prompt
        assert "what should be retained" in criterion.prompt


def test_gad_emits_progress_in_criterion_order(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    gad = GAD(llm_client=_CriterionAwareLLM())
    seen: list[str] = []

    result = gad.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "sample text"}],
        reference_document_ids={"syllabus": uuid4(), "curriculum": uuid4()},
        precomputed_context={
            "rubric_gad": ["rubric"],
            "syllabus": ["syllabus context"],
            "curriculum": ["curriculum context"],
        },
        criterion_progress_callback=lambda criterion, criterion_result: seen.append(
            criterion.criterion_id
        ),
    )

    assert seen == ["GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"]
    assert result.criterion_count == 5


def test_gad_parallel_criteria_do_not_share_active_criterion(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    llm = _ParallelCriterionAwareLLM()
    result = GAD(llm_client=llm).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "sample text"}],
        reference_document_ids={"syllabus": uuid4(), "curriculum": uuid4()},
        precomputed_context={
            "rubric_gad": ["rubric"],
            "syllabus": ["syllabus context"],
            "curriculum": ["curriculum context"],
        },
    )

    assert llm.max_active_calls > 1
    assert [score.criterion_id for score in result.criterion_scores] == [
        criterion.criterion_id for criterion in GAD_CRITERIA
    ]


def test_gad_logs_json_before_timing_summary(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    caplog.set_level("INFO", logger="server.modules.agents.base")
    caplog.set_level("INFO", logger="server.modules.agents.gad")

    gad = GAD(llm_client=_CriterionAwareLLM())
    gad.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "sample text"}],
        reference_document_ids={"syllabus": uuid4(), "curriculum": uuid4()},
        precomputed_context={
            "rubric_gad": ["rubric"],
            "syllabus": ["syllabus context"],
            "curriculum": ["curriculum context"],
        },
    )

    messages = [record.message for record in caplog.records]
    first_json_index = next(
        index
        for index, message in enumerate(messages)
        if "[GAD_JSON_RESPONSE]" in message
    )
    first_timing_index = next(
        index for index, message in enumerate(messages) if "[EVAL_TIMING]" in message
    )
    assert first_json_index < first_timing_index


def test_gad_prints_json_to_stdout(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    gad = GAD(llm_client=_CriterionAwareLLM())
    gad.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "sample text"}],
        reference_document_ids={"syllabus": uuid4(), "curriculum": uuid4()},
        precomputed_context={
            "rubric_gad": ["rubric"],
            "syllabus": ["syllabus context"],
            "curriculum": ["curriculum context"],
        },
    )

    stdout = capsys.readouterr().out
    assert "[GAD_JSON_RESPONSE]" in stdout
    assert '"criterion_id": "GAD-01"' in stdout or "criterion_id=GAD-01" in stdout


def test_gad_printed_json_matches_corrected_representation_counts(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    gad = GAD(llm_client=_ZeroRepresentationLLM())
    result = gad.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {
                "chunk_id": "chunk-1",
                "page_number": 1,
                "text": (
                    "Female: Ana Cruz, Maria Santos\n"
                    "Male: Juan Dela Cruz, Pedro Ramos"
                ),
            }
        ],
        reference_document_ids={"syllabus": uuid4(), "curriculum": uuid4()},
        precomputed_context={
            "rubric_gad": ["rubric"],
            "syllabus": ["syllabus context"],
            "curriculum": ["curriculum context"],
        },
    )

    stdout = capsys.readouterr().out
    payloads = [
        json.loads(line.removeprefix("[GAD_JSON_RESPONSE] "))
        for line in stdout.splitlines()
        if line.startswith("[GAD_JSON_RESPONSE] ")
    ]
    gad_02_payload = next(
        payload for payload in payloads if payload["criterion_id"] == "GAD-02"
    )
    gad_02_score = next(
        score for score in result.criterion_scores if score.criterion_id == "GAD-02"
    )

    assert gad_02_payload["female_count"] == 2
    assert gad_02_payload["male_count"] == 2
    assert gad_02_payload["score"] == gad_02_score.score
    assert gad_02_payload["summary"] == gad_02_score.justification
    assert gad_02_payload["evidence"] == list(gad_02_score.evidence)
    assert "No representations were identified" not in gad_02_payload["summary"]


def test_gad_fills_empty_summary_with_helpful_comment(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    gad = GAD(llm_client=_BlankSummaryLLM())
    result = gad.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "sample text"}],
        reference_document_ids={"syllabus": uuid4(), "curriculum": uuid4()},
        precomputed_context={
            "rubric_gad": ["rubric"],
            "syllabus": ["syllabus context"],
            "curriculum": ["curriculum context"],
        },
    )

    assert "No qualifying instances were detected." in result.summary
    assert "This suggests" in result.summary
