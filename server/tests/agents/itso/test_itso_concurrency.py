"""Request isolation tests for a shared ITSO instance."""

import json
from threading import Barrier, Thread
from uuid import uuid4

from server.modules.agents.itso.agent import ITSO


class BarrierClient:
    def __init__(self, model, summary, barrier, prompts):
        self.model = model
        self.summary = summary
        self.barrier = barrier
        self.prompts = prompts

    def generate(self, prompt, *, temperature, max_new_tokens):
        self.prompts[self.model] = prompt
        self.barrier.wait(timeout=3)
        return json.dumps({"summary": self.summary, "criterion_scores": []})


def test_shared_instance_real_runs_are_isolated(monkeypatch):
    settings = type(
        "Settings",
        (),
        {
            "agent_max_chunks": 10,
            "agent_max_excerpt_chars": 1000,
            "agent_prompt_budget_chars": 10000,
            "agent_small_doc_threshold": 20,
            "agent_total_prompt_budget_chars": 10000,
            "agent_temperature": 0.0,
            "llm_max_new_tokens": 2048,
            "get_agent_temperature": lambda self, name: 0.0,
        },
    )()
    monkeypatch.setattr(
        "server.modules.agents.itso.execution.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "server.modules.agents.itso.prompt.get_settings", lambda: settings
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
            results.append(
                agent.run(
                    evaluation_id=uuid4(),
                    document_id=uuid4(),
                    chunk_infos=({"chunk_id": label, "text": f"marker-{label}"},),
                    provenance={"precheck_version": label},
                    policy_evidence={"delivery_state": "blocked"},
                    precomputed_context={
                        "rubric_itso": [],
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
    assert by_model["model-one"].summary == "summary-one"
    assert by_model["model-two"].summary == "summary-two"
    assert by_model["model-one"].provenance["precheck_version"] == "one"
    assert by_model["model-two"].provenance["precheck_version"] == "two"
    assert "marker-one" in prompts["model-one"]
    assert "marker-two" not in prompts["model-one"]
    assert "marker-two" in prompts["model-two"]
    assert "marker-one" not in prompts["model-two"]
    assert not any(name.startswith("_current") for name in vars(agent))
