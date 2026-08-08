import json

import pytest
from server.modules.alignment.syllabus import evaluator as syllabus_alignment


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate(self, prompt, **_kwargs):
        self.prompts.append(json.loads(prompt))
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


def _syllabus_contents(count=1):
    return [
        {
            "chunk_id": f"syllabus-{index}",
            "content_ref": f"{index}:1",
            "content_text": (
                "Configure secure local area networks."
                if index == 1
                else f"Approved course topic {index}."
            ),
            "page_number": index + 1,
        }
        for index in range(1, count + 1)
    ]


def _two_topic_extraction():
    return {
        "topics": [
            {
                "topic": "Secure network configuration",
                "slm_chunk_id": _chunks()[0]["chunk_id"],
                "slm_evidence": "configure a secure local area network",
                "coverage_reason": "The SLM teaches the configuration skill.",
            },
            {
                "topic": "Mobile game development",
                "slm_chunk_id": _chunks()[1]["chunk_id"],
                "slm_evidence": "create an unrelated mobile game prototype",
                "coverage_reason": "The SLM assigns a development task.",
            },
        ]
    }


def _keep_two_topics():
    return {
        "topics": [
            {
                "canonical_topic": "Secure network configuration",
                "representative_candidate_id": "B1C1",
                "merged_candidate_ids": ["B1C1"],
            },
            {
                "canonical_topic": "Mobile game development",
                "representative_candidate_id": "B1C2",
                "merged_candidate_ids": ["B1C2"],
            },
        ]
    }


def _substantive(*candidate_ids):
    return {
        "decisions": [
            {
                "candidate_id": candidate_id,
                "coverage": "SUBSTANTIVE",
                "rationale": "The surrounding context teaches this concept.",
            }
            for candidate_id in candidate_ids
        ]
    }


def test_alignment_is_one_way_partial_against_complete_syllabus_list():
    client = Client(
        [
            _two_topic_extraction(),
            _substantive("B1C1", "B1C2"),
            _keep_two_topics(),
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "ALIGNED",
                        "syllabus_chunk_id": "syllabus-1",
                        "rationale": "The syllabus includes secure LAN configuration.",
                    },
                    {
                        "topic_id": "T2",
                        "status": "NOT_ALIGNED",
                        "syllabus_chunk_id": None,
                        "rationale": "Game development is not listed.",
                    },
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(
        client,
        _chunks(),
        "syllabus-123",
        _syllabus_contents(),
    )

    assert result["status"] == "PARTIALLY_MEETS"
    assert result["aligned_topics"] == 1
    assert result["content_matches"][0]["content_ref"] == "1:1"
    assert result["unmatched_topics"][0]["topic"] == "Mobile game development"
    assert "complete selected syllabus" in client.prompts[-1]["task"]
    assert "one-way" in client.prompts[-1]["task"]


def test_sentence_like_label_is_repaired_to_a_concept():
    client = Client(
        [
            {
                "topics": [
                    {
                        "topic": "Students configure a secure local area network.",
                        "slm_chunk_id": _chunks()[0]["chunk_id"],
                        "slm_evidence": "configure a secure local area network",
                    }
                ]
            },
            {
                "repairs": [
                    {
                        "candidate_id": "B1C1",
                        "topic": "Secure network configuration",
                    }
                ]
            },
            _substantive("B1C1"),
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "ALIGNED",
                        "syllabus_chunk_id": "syllabus-1",
                        "rationale": "The skill is included.",
                    }
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(
        client,
        [_chunks()[0]],
        "syllabus-123",
        _syllabus_contents(),
    )

    assert result["content_matches"][0]["topic"] == "Secure network configuration"
    assert not result["content_matches"][0]["topic"].endswith(".")


def test_invented_evidence_is_rejected_before_classification():
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

    result = syllabus_alignment.evaluate(
        client,
        _chunks(),
        "syllabus-123",
        _syllabus_contents(),
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["total_topics"] == 0
    assert len(client.prompts) == 1


def test_incidental_mention_is_removed_by_context_verification():
    chunk = {
        "chunk_id": "mention-only",
        "page_number": 6,
        "text": "Cloud computing appears in a list of optional readings.",
    }
    client = Client(
        [
            {
                "topics": [
                    {
                        "topic": "Cloud computing",
                        "slm_chunk_id": "mention-only",
                        "slm_evidence": "Cloud computing",
                    }
                ]
            },
            {
                "decisions": [
                    {
                        "candidate_id": "B1C1",
                        "coverage": "MENTION_ONLY",
                        "rationale": "The concept is only named in a reading list.",
                    }
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(
        client,
        [chunk],
        "syllabus-123",
        _syllabus_contents(),
    )

    assert result["status"] == "UNAVAILABLE"
    assert "no substantial SLM topics" in result["statement"]


def test_clause_like_statement_is_not_a_valid_topic_label():
    assert not syllabus_alignment._is_valid_topic_label(
        "Focused attention involves directing cognitive resources",
        "Focused attention involves directing cognitive resources toward a task.",
    )


def test_all_slm_chunks_are_processed_beyond_previous_limit():
    chunks = [
        {
            "chunk_id": f"chunk-{index}",
            "page_number": index + 1,
            "text": f"Instructional content block {index}.",
        }
        for index in range(25)
    ]
    chunks[-1]["text"] = "The lesson explains advanced routing protocols in detail."
    client = Client(
        [
            {"topics": []},
            {"topics": []},
            {"topics": []},
            {
                "topics": [
                    {
                        "topic": "Advanced routing protocols",
                        "slm_chunk_id": "chunk-24",
                        "slm_evidence": "advanced routing protocols",
                    }
                ]
            },
            _substantive("B4C1"),
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "NOT_ALIGNED",
                        "syllabus_chunk_id": None,
                        "rationale": "No syllabus entry covers routing protocols.",
                    }
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(
        client,
        chunks,
        "syllabus-123",
        _syllabus_contents(),
    )

    extraction_prompts = [
        prompt for prompt in client.prompts if "document_chunks" in prompt
    ]
    assert len(extraction_prompts) == 4
    assert result["total_topics"] == 1
    assert result["unmatched_topics"][0]["slm_page_number"] == 25


def test_oversized_chunk_is_segmented_without_dropping_late_content():
    chunk = {
        "chunk_id": "long-chunk",
        "page_number": 12,
        "text": ("Background material " * 90) + "Advanced cryptographic key rotation.",
    }
    client = Client(
        [
            {
                "topics": [
                    {
                        "topic": "Cryptographic key rotation",
                        "slm_segment_id": "long-chunk#S2",
                        "slm_evidence": "Advanced cryptographic key rotation",
                    }
                ]
            },
            _substantive("B1C1"),
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "NOT_ALIGNED",
                        "syllabus_chunk_id": None,
                        "rationale": "The syllabus does not contain this topic.",
                    }
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(
        client,
        [chunk],
        "syllabus-123",
        _syllabus_contents(),
    )

    assert result["unmatched_topics"][0]["slm_chunk_id"] == "long-chunk"
    assert len(client.prompts[0]["document_chunks"]) == 2


def test_complete_syllabus_list_is_checked_in_bounded_batches():
    syllabus = _syllabus_contents(21)
    syllabus[-1]["content_text"] = "Advanced routing protocols and route selection."
    chunk = {
        "chunk_id": "routing-chunk",
        "page_number": 9,
        "text": "The lesson explains advanced routing protocols in detail.",
    }
    client = Client(
        [
            {
                "topics": [
                    {
                        "topic": "Advanced routing protocols",
                        "slm_chunk_id": "routing-chunk",
                        "slm_evidence": "advanced routing protocols",
                    }
                ]
            },
            _substantive("B1C1"),
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "NOT_ALIGNED",
                        "syllabus_chunk_id": None,
                        "rationale": "Not present in this batch.",
                    }
                ]
            },
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "ALIGNED",
                        "syllabus_chunk_id": "syllabus-21",
                        "rationale": "The final syllabus item explicitly includes it.",
                    }
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(client, [chunk], "syllabus-123", syllabus)

    assert result["status"] == "MEETS"
    assert result["content_matches"][0]["chunk_id"] == "syllabus-21"
    classification_prompts = [
        prompt for prompt in client.prompts if "syllabus_course_contents" in prompt
    ]
    assert len(classification_prompts) == 2
    checked_content_count = sum(
        len(prompt["syllabus_course_contents"])
        for prompt in classification_prompts
    )
    assert checked_content_count == 21


def test_duplicate_topics_are_consolidated_across_slm_contexts():
    chunks = [
        {
            "chunk_id": "network-1",
            "page_number": 2,
            "text": "Network configuration includes managed switch setup.",
        },
        {
            "chunk_id": "network-2",
            "page_number": 7,
            "text": "The lesson further explains secure LAN configuration procedures.",
        },
    ]
    client = Client(
        [
            {
                "topics": [
                    {
                        "topic": "Network configuration",
                        "slm_chunk_id": "network-1",
                        "slm_evidence": "managed switch setup",
                    },
                    {
                        "topic": "Secure LAN configuration",
                        "slm_chunk_id": "network-2",
                        "slm_evidence": "secure LAN configuration procedures",
                    },
                ]
            },
            _substantive("B1C1", "B1C2"),
            {
                "topics": [
                    {
                        "canonical_topic": "Network configuration",
                        "representative_candidate_id": "B1C1",
                        "merged_candidate_ids": ["B1C1", "B1C2"],
                    }
                ]
            },
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "ALIGNED",
                        "syllabus_chunk_id": "syllabus-1",
                        "rationale": "The consolidated concept is listed.",
                    }
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(
        client,
        chunks,
        "syllabus-123",
        _syllabus_contents(),
    )

    assert result["total_topics"] == 1
    assert result["content_matches"][0]["topic"] == "Network configuration"


def test_missing_syllabus_topics_do_not_penalize_the_slm():
    client = Client(
        [
            {
                "topics": [
                    {
                        "topic": "Secure network configuration",
                        "slm_chunk_id": _chunks()[0]["chunk_id"],
                        "slm_evidence": "configure a secure local area network",
                    }
                ]
            },
            _substantive("B1C1"),
            {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "ALIGNED",
                        "syllabus_chunk_id": "syllabus-1",
                        "rationale": "The syllabus permits this topic.",
                    }
                ]
            },
        ]
    )

    result = syllabus_alignment.evaluate(
        client,
        [_chunks()[0]],
        "syllabus-123",
        _syllabus_contents(5),
    )

    assert result["status"] == "MEETS"
    assert result["total_topics"] == 1


def test_no_syllabus_is_unavailable_without_model_call():
    result = syllabus_alignment.evaluate(None, _chunks(), None)
    assert result["status"] == "UNAVAILABLE"
    assert "no syllabus" in result["statement"]


@pytest.mark.parametrize(
    ("status", "aligned", "outside", "expected"),
    [
        ("MEETS", ["Networks", "Security"], [], "2 of 2 substantial topics"),
        ("PARTIALLY_MEETS", ["Networks"], ["Games"], "1 of 2 substantial topics"),
        ("DOES_NOT_MEET", [], ["Games", "Animation"], "0 of 2 substantial topics"),
    ],
)
def test_detailed_statement_covers_each_alignment_level(
    status, aligned, outside, expected
):
    statement = syllabus_alignment._detailed_statement(
        status, len(aligned) + len(outside), aligned, outside
    )
    assert expected in statement
    if aligned:
        assert "Aligned topics:" in statement
    if outside:
        assert "Topics outside the syllabus:" in statement
