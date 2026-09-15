"""Concurrency and safe-diagnostics tests for the SME snapshot path."""

from __future__ import annotations

import concurrent.futures
import inspect
import json
import threading
import uuid

from server.core.llm import CompletionResult
from server.modules.agents.runtime.llm import error_reference
from server.modules.agents.sme.agent import SME
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot

_SOURCE = "Canonical source text for isolation tests."


def _make_snapshot(eval_id: uuid.UUID):
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
        name="Iso Form",
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
    return build_evaluation_form_snapshot(eval_id, form)


class BarrierClient:
    barrier = threading.Barrier(2)

    def __init__(self, model: str) -> None:
        self.model = model

    def generate_result(self, prompt: str, **kwargs: object) -> CompletionResult:
        self.barrier.wait(timeout=5)
        payload = json.dumps(
            {
                "summary": f"Result from {self.model}",
                "criterion_measurements": [
                    {
                        "criterion_id": "OP-02",
                        "criterion_title": "Interactive Elements",
                        "instances": [{"excerpt": "Canonical source text"}],
                    }
                ],
            }
        )
        return CompletionResult(
            content=payload,
            served_model=self.model,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            finish_reason="stop",
            attempts=1,
        )


def test_same_sme_instance_keeps_injected_clients_isolated() -> None:
    clients = [BarrierClient("model-a"), BarrierClient("model-b")]
    agent = SME(llm_client=clients[0])

    def run(client: BarrierClient):
        eval_id = uuid.uuid4()
        snap = _make_snapshot(eval_id)
        return agent.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=[{"text": "text"}],
            canonical_source_text=_SOURCE,
            llm_client=client,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, clients))

    assert {result.model_name for result in results} == {"model-a", "model-b"}


def test_error_reference_is_deterministic_and_bounded() -> None:
    error = RuntimeError("secret diagnostic")
    reference = error_reference(error)
    assert reference == error_reference(RuntimeError("secret diagnostic"))
    assert len(reference) == 16
    assert reference == reference.lower()
    assert all(character in "0123456789abcdef" for character in reference)


def test_sme_uses_canonical_text_without_pdf_reopening() -> None:
    source = inspect.getsource(SME)
    assert "fitz" not in source.lower()
    assert "pymupdf" not in source.lower()
    assert "_load_document_text" not in source
