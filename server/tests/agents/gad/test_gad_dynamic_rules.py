"""Dynamic per-criterion counting rules for the GAD extraction prompt."""

from __future__ import annotations

import json
import uuid

from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.gad.agent import GAD
from server.modules.agents.gad.prompt import (
    build_combined_prompt,
)
from server.modules.rubrics.contracts import (
    CriterionDefinition,
)
from server.tests.agents.gad.conftest import (
    REVISION_1_GAD_CRITERIA,
    REVISION_1_GAD_RULES,
    make_gad_snapshot,
)

_CHUNKS = [{"chunk_id": "c1", "text": "Sample learning material text."}]


def _instructions(prompt) -> str:
    return prompt.system_instruction


def test_seed_json_matches_revision_1_fixture_constant() -> None:
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
    assert seeded == REVISION_1_GAD_RULES


def test_prompt_uses_snapshot_rules() -> None:
    snap = make_gad_snapshot()
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS, form_snapshot=snap, prompt_version="v1"
        )
    )
    assert REVISION_1_GAD_RULES["GAD-01"] in text
    assert REVISION_1_GAD_RULES["GAD-05"] in text


def test_custom_snapshot_rule_reaches_prompt() -> None:
    custom_c0 = REVISION_1_GAD_CRITERIA[0].model_copy(
        update={"scoring_rule": "EDITED GAD-01 COUNTING RULE"}
    )
    custom_criteria = (custom_c0,) + REVISION_1_GAD_CRITERIA[1:]
    snap = make_gad_snapshot(criteria=custom_criteria)
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            form_snapshot=snap,
            prompt_version="v1",
        )
    )
    assert "EDITED GAD-01 COUNTING RULE" in text
    assert REVISION_1_GAD_RULES["GAD-01"] not in text
    assert REVISION_1_GAD_RULES["GAD-02"] in text


def test_structural_scaffold_survives_rule_injection() -> None:
    snap = make_gad_snapshot()
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            form_snapshot=snap,
            prompt_version="v1",
        )
    )
    assert '"excerpt"' in text
    assert '"chunk_id"' in text
    assert "Do not include" in text and "score" in text
    assert "10" in text
    assert "female_count" in text and "male_count" in text


def test_scaffold_names_required_output_fields_explicitly() -> None:
    snap = make_gad_snapshot()
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS, form_snapshot=snap, prompt_version="v1"
        )
    )
    assert '"instance_count"' in text
    assert '"instances"' in text
    assert '"summary"' in text
    assert '"excerpt"' in text and '"chunk_id"' in text
    assert '"female_count"' in text and '"male_count"' in text
    assert "EXACTLY these fields" in text
    assert "use 0 if none" in text


def test_blank_snapshot_rule_falls_back_to_description() -> None:
    custom_c2 = REVISION_1_GAD_CRITERIA[2].model_copy(
        update={"scoring_rule": "   ", "description": "Custom fallback description."}
    )
    custom_criteria = (
        REVISION_1_GAD_CRITERIA[0],
        REVISION_1_GAD_CRITERIA[1],
        custom_c2,
        REVISION_1_GAD_CRITERIA[3],
        REVISION_1_GAD_CRITERIA[4],
    )
    snap = make_gad_snapshot(criteria=custom_criteria)
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            form_snapshot=snap,
            prompt_version="v1",
        )
    )
    assert "Custom fallback description." in text


_FIVE_SECTION_RESPONSE = {
    "gad-01": {
        "instance_count": 0,
        "instances": [],
        "summary": "none.",
    },
    "gad-02": {
        "female_count": 0,
        "male_count": 0,
        "summary": "balanced.",
    },
    "gad-03": {
        "instance_count": 0,
        "instances": [],
        "summary": "none.",
    },
    "gad-04": {
        "instance_count": 0,
        "instances": [],
        "summary": "none.",
    },
    "gad-05": {
        "instance_count": 0,
        "instances": [],
        "summary": "none.",
    },
}


class _SequenceLLM:
    model = "gad-test-model"

    def __init__(self) -> None:
        self.prompts: list[dict] = []

    def generate(self, prompt, *, temperature: float, max_new_tokens: int) -> str:
        del temperature, max_new_tokens
        self.prompts.append(prompt)
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
    {
        "chunk_id": "c1",
        "page_number": 1,
        "text": "The learning material discusses community roles and helpers.",
    }
]


def _run_gad_with_snapshot(criteria: tuple[CriterionDefinition, ...]) -> str:
    eval_id = uuid.uuid4()
    snap = make_gad_snapshot(eval_id, criteria=criteria)
    fake = _SequenceLLM()
    GAD(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        chunk_infos=_DOC_CHUNKS,
        form_snapshot=snap,
    )
    return fake.prompts[0].system_instruction


def test_snapshot_rule_reaches_the_extraction_prompt() -> None:
    custom_c0 = REVISION_1_GAD_CRITERIA[0].model_copy(
        update={"scoring_rule": "EDITED GAD-01 COUNTING RULE"}
    )
    custom_criteria = (custom_c0,) + REVISION_1_GAD_CRITERIA[1:]
    text = _run_gad_with_snapshot(custom_criteria)
    assert "EDITED GAD-01 COUNTING RULE" in text
    assert REVISION_1_GAD_RULES["GAD-02"] in text


def test_empty_snapshot_rules_fall_back() -> None:
    custom_c0 = REVISION_1_GAD_CRITERIA[0].model_copy(
        update={"scoring_rule": None, "description": "Fallback description"}
    )
    custom_criteria = (custom_c0,) + REVISION_1_GAD_CRITERIA[1:]
    text = _run_gad_with_snapshot(custom_criteria)
    assert "Fallback description" in text


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
    snap = make_gad_snapshot()
    rendered = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            form_snapshot=snap,
            prompt_version="v1",
            gad_managed_prompt=_trim_migration().TRIMMED_GAD_PROMPT,
        )
    )
    assert rendered.count(REVISION_1_GAD_RULES["GAD-01"]) == 1


def test_criterion_agnostic_gad_prompt_with_novel_codes():
    """Criterion-agnostic GAD prompt formats arbitrary criteria without legacy codes."""
    import importlib

    from server.modules.rubrics.contracts import CountBandConfig

    mig = importlib.import_module(
        "server.alembic.versions.20260829_0005_criterion_agnostic_agent_prompts"
    )

    novel_c0 = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="NOVEL-G-01",
        title="Novel Inclusivity",
        description="Check novel inclusivity aspects.",
        scoring_rule="Count instances of novel terminology.",
        display_order=1,
        strategy_config=CountBandConfig(
            strategy="count_band",
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=3,
        ),
    )
    snap = make_gad_snapshot(criteria=(novel_c0,))
    rendered = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            form_snapshot=snap,
            prompt_version="v1",
            gad_managed_prompt=mig.CRITERION_AGNOSTIC_GAD_PROMPT,
        )
    )
    assert "NOVEL-G-01" in rendered
    assert "Novel Inclusivity" in rendered
    assert "Count instances of novel terminology." in rendered
    for legacy_code in ("GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"):
        assert legacy_code not in rendered
