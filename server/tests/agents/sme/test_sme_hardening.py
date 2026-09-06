"""Characterization tests for the hardened SME snapshot boundary."""

from __future__ import annotations

import json
import uuid

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme.agent import SME
from server.modules.agents.sme.fallback import registry
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot

PREAMBLE = "MANAGED SME PREAMBLE -- causal-test"
PROMPT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_managed_preamble_is_consumed_by_criterion_fallback():
    calls = []

    class Client:
        primary_client = None

        def generate(self, prompt, **kwargs):
            calls.append((prompt, kwargs["response_contract"]))
            return json.dumps({"mechanisms": []})

    registry.run_criterion("A-03", Client(), "canonical text", prompt_preamble=PREAMBLE)
    assert calls and calls[0][0].startswith(PREAMBLE + "\n\n")


def test_prompt_version_and_id_are_passed_and_preserved():
    c1 = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="OP-02",
        title="Interactive Elements",
        description="Desc",
        display_order=0,
        strategy_config=CountBandConfig(
            mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Hardening Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="D1",
                title="Domain 1",
                display_order=0,
                criteria=(c1,),
            ),
        ),
    )
    eval_id = uuid.uuid4()
    snap = build_evaluation_form_snapshot(eval_id, form)

    captured_prompt = []

    class Client:
        def generate_result(self, prompt, **kwargs):
            captured_prompt.append(prompt)
            payload = json.dumps(
                {
                    "summary": "ok",
                    "criterion_measurements": [
                        {
                            "criterion_id": "OP-02",
                            "criterion_title": "Interactive Elements",
                            "instances": [{"excerpt": "canonical text"}],
                        }
                    ],
                }
            )
            return CompletionResult(payload, "model", 10, 20, 30, "stop", attempts=1)

    result = SME(llm_client=Client()).run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=[{"text": "chunk"}],
        canonical_source_text="canonical text",
        prompt_version=PREAMBLE,
        prompt_version_id=PROMPT_ID,
    )

    assert result.prompt_version_id == PROMPT_ID
    assert captured_prompt and PREAMBLE in captured_prompt[0].system_instruction


def test_sme_uses_canonical_text_only():
    with pytest.raises(AgentExecutionError, match="canonical source text"):
        SME()._resolve_full_text(None)
