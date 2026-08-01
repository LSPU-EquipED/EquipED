import json

from server.modules.agents import syllabus_alignment
from server.modules.embeddings.retrieval import RetrievedChunk


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)

    def generate(self, *_args, **_kwargs):
        return json.dumps(next(self.responses))


def _chunks():
    return [
        {
            "chunk_id": "11111111-1111-1111-1111-111111111111",
            "page_number": 3,
            "text": (
                "Students configure a secure local area network using managed "
                "switches."
            ),
        },
        {
            "chunk_id": "22222222-2222-2222-2222-222222222222",
            "page_number": 4,
            "text": "Students create an unrelated mobile game prototype.",
        },
    ]


def test_alignment_is_partial_and_uses_selected_syllabus_filter(monkeypatch):
    calls = []

    def retrieve(query, collection, n_results, document_id_filter):
        calls.append((query, document_id_filter))
        return [
            RetrievedChunk(
                text="Configure secure local area networks.",
                distance=0.1,
                document_id=document_id_filter,
                source_type="syllabus",
                page_number=2,
                is_ocr=False,
                token_count=6,
                chunk_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                section_ref="syllabus_outcome:CLO2",
                chunk_index=1,
            )
        ]

    monkeypatch.setattr(syllabus_alignment, "retrieve_context", retrieve)
    client = Client(
        [
            {
                "topics": [
                    {
                        "topic_id": "ignored",
                        "topic": "Secure network configuration",
                        "slm_chunk_id": _chunks()[0]["chunk_id"],
                        "slm_evidence": "configure a secure local area network",
                    },
                    {
                        "topic_id": "ignored",
                        "topic": "Mobile game development",
                        "slm_chunk_id": _chunks()[1]["chunk_id"],
                        "slm_evidence": "create an unrelated mobile game prototype",
                    },
                ]
            },
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "ALIGNED",
                        "syllabus_chunk_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "rationale": (
                            "The outcome explicitly includes secure LAN configuration."
                        ),
                    },
                    {
                        "topic_id": "T2",
                        "status": "NOT_ALIGNED",
                        "syllabus_chunk_id": None,
                        "rationale": "No candidate outcome includes game development.",
                    },
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(client, _chunks(), "syllabus-123")

    assert result["status"] == "PARTIALLY_MEETS"
    assert result["aligned_topics"] == 1
    assert len(result["unmatched_topics"]) == 1
    assert calls == [
        ("Secure network configuration", "syllabus-123"),
        ("Mobile game development", "syllabus-123"),
    ]


def test_rejects_invented_evidence_before_retrieval(monkeypatch):
    monkeypatch.setattr(
        syllabus_alignment,
        "retrieve_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not retrieve")
        ),
    )
    client = Client(
        [
            {
                "topics": [
                    {
                        "topic": "Invented topic",
                        "slm_chunk_id": _chunks()[0]["chunk_id"],
                        "slm_evidence": "This quote is not in the SLM.",
                    }
                ]
            }
        ]
    )

    result = syllabus_alignment.evaluate(client, _chunks(), "syllabus-123")

    assert result["status"] == "UNAVAILABLE"
    assert result["total_topics"] == 0


def test_no_syllabus_is_unavailable_without_model_call():
    result = syllabus_alignment.evaluate(None, _chunks(), None)
    assert result["status"] == "UNAVAILABLE"
    assert "no syllabus" in result["statement"]
