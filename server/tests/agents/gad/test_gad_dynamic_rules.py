"""Dynamic per-criterion counting rules for the GAD extraction prompt."""

from __future__ import annotations

import json
import uuid

from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.gad.agent import GAD
from server.modules.agents.gad.prompt import (
    FALLBACK_GAD_INSTRUCTIONS,
    build_combined_prompt,
)

_CHUNKS = [{"chunk_id": "c1", "text": "Sample learning material text."}]


def _instructions(prompt: str) -> str:
    return "\n".join(json.loads(prompt)["instructions"])


def test_fallback_covers_every_registered_criterion() -> None:
    from server.modules.agents.gad import registry

    assert set(FALLBACK_GAD_INSTRUCTIONS) == {
        d.criterion_id for d in registry.CRITERIA
    }
    assert all(v.strip() for v in FALLBACK_GAD_INSTRUCTIONS.values())


def test_seed_json_matches_fallback_constant() -> None:
    import json as _json
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    payload = _json.loads(
        (root / "data" / "rubrics" / "rubrics.json").read_text(encoding="utf-8")
    )
    gad_set = next(s for s in payload["rubric_sets"] if s["agent_id"] == "gad")
    seeded = {
        c["criterion_code"]: c["scoring_rule"]
        for d in gad_set["domains"]
        for c in d["criteria"]
    }
    assert seeded == FALLBACK_GAD_INSTRUCTIONS


def test_prompt_uses_fallback_when_no_rules_supplied() -> None:
    text = _instructions(
        build_combined_prompt(packed_chunks=_CHUNKS, prompt_version="v1")
    )
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-01"] in text
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-05"] in text


def test_supplied_rule_overrides_fallback_per_criterion() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={"GAD-01": "EDITED GAD-01 COUNTING RULE"},
        )
    )
    assert "EDITED GAD-01 COUNTING RULE" in text
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-01"] not in text
    # untouched criteria still use the fallback
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-02"] in text


def test_structural_scaffold_survives_rule_injection() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={c: f"rule {c}" for c in FALLBACK_GAD_INSTRUCTIONS},
        )
    )
    assert '"excerpt"' in text
    assert '"chunk_id"' in text
    assert "Do not include" in text and "score" in text
    assert "10" in text  # MAX_INSTANCES_PER_CRITERION still stated
    # GAD-02 balance scaffold still present
    assert "female_count" in text and "male_count" in text


def test_scaffold_names_required_output_fields_explicitly() -> None:
    text = _instructions(
        build_combined_prompt(packed_chunks=_CHUNKS, prompt_version="v1")
    )
    # instance criteria must spell out the required fields as named JSON keys
    assert '"instance_count"' in text
    assert '"instances"' in text
    assert '"summary"' in text
    assert '"excerpt"' in text and '"chunk_id"' in text
    # balance criterion
    assert '"female_count"' in text and '"male_count"' in text
    # the wording must frame these as REQUIRED output fields, not just a task
    assert "EXACTLY these fields" in text
    # each instance criterion still tells the model to use 0 when none found
    assert "use 0 if none" in text


def test_blank_rule_falls_back() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={"GAD-03": "   "},
        )
    )
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-03"] in text


_FIVE_SECTION_RESPONSE = {
    "gad-01": {"criterion": "x", "instance_count": 0, "instances": [],
               "summary": "none."},
    "gad-02": {"criterion": "x", "female_count": 0, "male_count": 0,
               "summary": "balanced."},
    "gad-03": {"criterion": "x", "instance_count": 0, "instances": [],
               "summary": "none."},
    "gad-04": {"criterion": "x", "instance_count": 0, "instances": [],
               "summary": "none."},
    "gad-05": {"criterion": "x", "instance_count": 0, "instances": [],
               "summary": "none."},
}


class _SequenceLLM:
    model = "gad-test-model"

    def __init__(self) -> None:
        self.prompts: list[dict] = []

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        del temperature, max_new_tokens
        self.prompts.append(json.loads(prompt))
        return json.dumps(_FIVE_SECTION_RESPONSE)

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        del deadline
        assert response_contract.mode == "json_object"
        return CompletionResult(
            content=self.generate(
                prompt, temperature=temperature, max_new_tokens=max_new_tokens
            ),
            served_model=self.model,
            finish_reason="stop",
        )


_DOC_CHUNKS = [
    {"chunk_id": "c1", "page_number": 1,
     "text": "The learning material discusses community roles and helpers."}
]


def _run_gad(monkeypatch, rules: dict[str, str]) -> str:
    monkeypatch.setattr(
        "server.modules.agents.gad.pipeline.GADScoredAgent._rubric_scoring_rules",
        lambda self, db=None: rules,
    )
    fake = _SequenceLLM()
    GAD(llm_client=fake).run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_DOC_CHUNKS,
    )
    return "\n".join(fake.prompts[0]["instructions"])


def test_db_rule_reaches_the_extraction_prompt(monkeypatch) -> None:
    text = _run_gad(monkeypatch, {"GAD-01": "EDITED GAD-01 COUNTING RULE"})
    assert "EDITED GAD-01 COUNTING RULE" in text
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-02"] in text


def test_empty_db_rules_fall_back(monkeypatch) -> None:
    text = _run_gad(monkeypatch, {})
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-01"] in text


def _trim_migration():
    import importlib

    return importlib.import_module(
        "server.alembic.versions.20260829_0003_trim_gad_managed_prompt"
    )


def test_trimmed_managed_prompt_is_framing_only() -> None:
    p = _trim_migration().TRIMMED_GAD_PROMPT
    assert "OUTPUT FORMAT:" in p and "TASK:" in p
    assert "CRITERIA:" not in p
    assert "Count each unique instance" not in p
    assert "CRITICAL RULES:" not in p


def test_managed_prompt_and_rules_do_not_both_carry_criteria() -> None:
    """With the trimmed framing as the managed prompt, per-criterion guidance
    appears once (from the injected rule), not twice."""
    rendered = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            gad_managed_prompt=_trim_migration().TRIMMED_GAD_PROMPT,
        )
    )
    assert rendered.count(FALLBACK_GAD_INSTRUCTIONS["GAD-01"]) == 1
