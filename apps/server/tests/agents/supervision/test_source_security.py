from uuid import uuid4

import pytest
from server.modules.agents.exceptions import SupervisorExecutionError
from server.modules.agents.supervision.context import EvaluationContextBuilder


def test_invalid_document_path_stops_before_source_or_agent_work(monkeypatch, caplog):
    document_id = uuid4()
    source = "/tmp/private-source.pdf"
    document = type("Doc", (), {"file_path": source})()
    db = type("DB", (), {"get": lambda self, model, key: document})()
    source_calls = []
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.resolve_document_pdf_path",
        lambda value: (_ for _ in ()).throw(
            SupervisorExecutionError("invalid document source")
        ),
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.prepare_canonical_source",
        lambda value: source_calls.append(value),
    )

    with caplog.at_level("INFO"):
        with pytest.raises(SupervisorExecutionError):
            EvaluationContextBuilder(db, []).build(
                chunks=[
                    type(
                        "Chunk",
                        (),
                        {"chunk_id": uuid4(), "page_number": 1, "text": "text"},
                    )()
                ],
                query_text="text",
                context={"document_id": document_id},
            )

    assert source_calls == []
    assert source not in caplog.text
