"""Request isolation tests for a shared ITSO instance."""

import json
from threading import Barrier, Thread
from uuid import uuid4

from equiped_harness import ExecutionConfig, execution_scope
from equiped_harness.agents.itso.agent import ITSO
from equiped_harness.runtime.model import CompletionResult

from server.tests.agents.itso.conftest_helper import v3_response_for_prompt


class BarrierClient:
    def __init__(self, model, summary, barrier, prompts):
        self.model = model
        self.summary = summary
        self.barrier = barrier
        self.prompts = prompts

    def generate(self, prompt, *, temperature, max_new_tokens):
        previous = self.prompts.get(self.model, "")
        self.prompts[self.model] = previous + str(prompt)
        self.barrier.wait(timeout=3)
        return v3_response_for_prompt(
            prompt, _response(self.summary), generate_valid_evidence=True
        )

    def generate_result(
        self,
        prompt,
        *,
        temperature,
        max_new_tokens,
        deadline=None,
        response_contract=None,
    ):
        assert response_contract is not None
        assert response_contract.mode == "json_schema"
        return CompletionResult(
            content=self.generate(
                prompt, temperature=temperature, max_new_tokens=max_new_tokens
            ),
            served_model=self.model,
        )


def _response(summary):
    return json.dumps(
        {
            "summary": summary,
            "criterion_scores": [
                {
                    "criterion_id": f"ITSO-0{i}",
                    "criterion_title": __import__(
                        "equiped_harness.agents.itso.response",
                        fromlist=["ITSO_CRITERIA_TITLES"],
                    ).ITSO_CRITERIA_TITLES[f"ITSO-0{i}"],
                    "score": 3,
                    "justification": "justification",
                    "chunk_ids": [],
                    "evidence": [],
                }
                for i in range(1, 6)
            ],
        }
    )


def test_shared_instance_real_runs_are_isolated():
    config = ExecutionConfig(
        agent_max_chunks=10,
        agent_max_excerpt_chars=1000,
        agent_small_doc_threshold=20,
        agent_total_prompt_budget_chars=32000,
        agent_prompt_budget_chars=16000,
        llm_max_new_tokens=2048,
        llm_response_mode="json_schema",
    )

    barrier = Barrier(2)
    prompts = {}
    clients = {
        "model-one": BarrierClient("model-one", "summary-one", barrier, prompts),
        "model-two": BarrierClient("model-two", "summary-two", barrier, prompts),
    }
    agent = ITSO()
    results = []
    errors = []

    def run(label, client):
        try:
            eval_id = uuid4()
            from server.tests.agents.itso.conftest_helper import (
                make_itso_test_snapshot,
                public_reference_context,
            )

            crit_specs = tuple((f"ITSO-0{i}", f"Title {i}") for i in range(1, 6))
            snapshot = make_itso_test_snapshot(
                evaluation_id=eval_id, criteria_specs=crit_specs
            )

            with execution_scope(config):
                results.append(
                    agent.run(
                        evaluation_id=eval_id,
                        document_id=uuid4(),
                        chunk_infos=(
                            {
                                "chunk_id": label,
                                "text": (
                                    f"This module contains marker-{label} and "
                                    "describes information security controls."
                                ),
                            },
                        ),
                        form_snapshot=snapshot,
                        provenance={"precheck_version": label},
                        policy_evidence={"delivery_state": "blocked"},
                        precomputed_context={
                            **public_reference_context(),
                            "syllabus": [],
                            "curriculum": [],
                        },
                        llm_client=client,
                    )
                )
        except Exception as exc:  # collected so thread failures are explicit
            errors.append(exc)

    threads = [
        Thread(target=run, args=("one", clients["model-one"])),
        Thread(target=run, args=("two", clients["model-two"])),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 2
    by_model = {result.model_name: result for result in results}
    for model, summary in (("model-one", "summary-one"), ("model-two", "summary-two")):
        assert len(by_model[model].generations) == 2
        assert all(
            generation.response_json["summary"] == summary
            for generation in by_model[model].generations
        )
    assert by_model["model-one"].provenance["actual_model"] == "model-one"
    assert by_model["model-two"].provenance["actual_model"] == "model-two"
    assert "marker-one" in prompts["model-one"]
    assert "marker-two" not in prompts["model-one"]
    assert "marker-two" in prompts["model-two"]
    assert "marker-one" not in prompts["model-two"]
    assert not any(name.startswith("_current") for name in vars(agent))
