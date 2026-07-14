"""Tests for criterion-specific GAD extraction and code-side scoring."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from server.modules.agents.gad import GAD
from server.modules.agents.gad_scoring.female_male_count import (
    score_representation_balance,
)
from server.modules.agents.gad_scoring.life_experiences import (
    score_life_experience_instances,
)
from server.modules.agents.gad_scoring.peace_and_equality import (
    score_peace_equality_instances,
)
from server.modules.agents.gad_scoring.potential import (
    score_respect_potential_instances,
)
from server.modules.agents.gad_scoring.stereotypes import (
    score_stereotype_instances,
)


class _SequenceLLM:
    model = "gad-test-model"

    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.prompts: list[dict[str, object]] = []
        self.temperatures: list[float] = []

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        del max_new_tokens
        self.prompts.append(json.loads(prompt))
        self.temperatures.append(temperature)
        if not self.responses:
            raise AssertionError("GAD made more LLM calls than expected")
        return json.dumps(self.responses.pop(0))


def _instance_response(
    summary: str,
    excerpts: list[str],
    *,
    reported_count: int | None = None,
) -> dict[str, object]:
    return {
        "criterion": "criterion",
        "instance_count": (
            len(excerpts) if reported_count is None else reported_count
        ),
        "instances": [
            {"excerpt": excerpt, "explanation": "finding"}
            for excerpt in excerpts
        ],
        "summary": summary,
    }


def test_gad_runs_five_prompts_and_scores_grounded_measurements() -> None:
    fake = _SequenceLLM(
        [
            _instance_response(
                "One supported stereotype needs revision.",
                ["Women cannot lead teams.", "Invented unsupported quotation."],
                reported_count=2,
            ),
            {
                "criterion": "representation",
                "female_count": 4,
                "male_count": 1,
                "summary": "Representation should be more balanced.",
            },
            _instance_response(
                "Respect and potential are presented fairly.",
                [],
            ),
            _instance_response(
                "Two examples favor one gender's experience.",
                ["Only boys should repair computers.", "Girls should only take notes."],
            ),
            _instance_response(
                "No discriminatory content was grounded.",
                [],
            ),
        ]
    )
    chunks = [
        {
            "chunk_id": "chunk-1",
            "page_number": 1,
            "text": "Women cannot lead teams. Only boys should repair computers.",
        },
        {
            "chunk_id": "chunk-2",
            "page_number": 2,
            "text": "Girls should only take notes.",
        },
    ]

    result = GAD(llm_client=fake).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        llm_temperature=0.8,
    )

    assert [score.criterion_id for score in result.criterion_scores] == [
        "GAD-01",
        "GAD-02",
        "GAD-03",
        "GAD-04",
        "GAD-05",
    ]
    assert [score.score for score in result.criterion_scores] == [3, 3, 4, 3, 4]
    assert result.subtotal == pytest.approx(3.4)
    assert len(fake.prompts) == 5
    assert [prompt["criterion_id"] for prompt in fake.prompts] == [
        "GAD-01",
        "GAD-02",
        "GAD-03",
        "GAD-04",
        "GAD-05",
    ]
    assert fake.temperatures == [0.0] * 5
    assert result.metadata["scoring_mode"] == "criterion_specific_code_bands"
    assert result.metadata["llm_call_count"] == 5

    stereotype = result.criterion_scores[0]
    assert stereotype.evidence == ("Women cannot lead teams.",)
    assert stereotype.chunk_ids == ("chunk-1",)
    assert "1 unsupported" in stereotype.justification


@pytest.mark.parametrize(
    ("scorer", "values", "expected"),
    [
        (score_stereotype_instances, (0, 1, 2, 4), (4, 3, 2, 1)),
        (score_respect_potential_instances, (0, 1, 3, 6), (4, 3, 2, 1)),
        (score_life_experience_instances, (0, 2, 5, 6), (4, 3, 2, 1)),
        (score_peace_equality_instances, (0, 2, 5, 6), (4, 3, 2, 1)),
    ],
)
def test_instance_scoring_boundaries(scorer, values, expected) -> None:
    assert tuple(scorer(value) for value in values) == expected


def test_representation_balance_boundaries() -> None:
    assert score_representation_balance(5, 5) == 4
    assert score_representation_balance(5, 2) == 3
    assert score_representation_balance(10, 2) == 2
    assert score_representation_balance(12, 1) == 1
