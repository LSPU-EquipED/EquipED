"""Public ITSO v3 result presentation uses only saved, bounded evidence."""

import json
from dataclasses import replace
from types import SimpleNamespace

from equiped_harness.itso.document_review import unquoted_review_status
from equiped_harness.itso.response import ITSO_CRITERIA_TITLES
from equiped_harness.result_contracts import (
    AdvisoryOutput,
    CapturedGeneration,
    UngroundedCriterionAdvisory,
)
from equiped_harness.result_contracts import (
    CriterionScore as HarnessCriterionScore,
)
from server.modules.rubrics.models import EvaluationFormSnapshot
from server.modules.synthesis.evaluation_results import (
    _captured_criterion_justification,
    _captured_itso_context,
    _itso_reference_check_note,
    _itso_result_evidence_status,
    _itso_v3_summary,
    _public_itso_sources,
    _usable_itso_source,
)
from server.modules.synthesis.models import EvaluationFlag
from server.modules.synthesis.schemas import CriterionScoreItem
from server.modules.synthesis.service import (
    get_evaluation_results,
    persist_agent_outputs,
)
from server.tests.agents.itso.conftest_helper import make_itso_test_snapshot
from server.tests.evaluations.snapshot_test_helpers import make_scheduled_agent_results
from server.tests.evaluations.test_persistence_integrity import _setup_evaluation


def _report():
    return {
        "references": [
            {
                "status": "matched",
                "source_url": "https://example.org/one",
                "title": "First source",
                "excerpt": "First retrieved passage.",
                "unverified_fields": [],
            },
            {
                "status": "ambiguous",
                "source_url": "https://example.org/two",
                "title": "Second source",
                "excerpt": "Second retrieved passage.",
                "unverified_fields": ["author", "year"],
            },
            {
                "status": "unavailable",
                "source_url": "https://example.org/missing",
                "title": "Unavailable source",
                "excerpt": "",
                "unverified_fields": [],
            },
        ],
        "coverage": {"skipped": 1},
    }


def test_result_presentation_projects_only_cited_usable_public_passages():
    sources = _public_itso_sources(
        _report(), "[source 2] See https://example.org/one for context."
    )

    assert [source["number"] for source in sources] == [1, 2]
    assert sources[0]["excerpt"] == "First retrieved passage."
    assert sources[1]["title"] == "Second source"
    assert len(sources) <= 5


def test_result_presentation_rejects_unsafe_or_unusable_urls():
    assert not _usable_itso_source(
        {"status": "matched", "source_url": "http://example.org", "excerpt": "x"}
    )
    assert not _usable_itso_source(
        {
            "status": "matched",
            "source_url": "https://user:secret@example.org/source",
            "excerpt": "x",
        }
    )
    assert not _usable_itso_source(
        {"status": "unavailable", "source_url": "https://example.org", "excerpt": "x"}
    )
    homepage_report = {
        "references": [
            {
                "status": "matched",
                "source_url": "https://example.org/",
                "excerpt": "Homepage passage.",
            }
        ]
    }
    assert (
        _public_itso_sources(homepage_report, "The cited publisher is example.org.")[0][
            "number"
        ]
        == 1
    )


def test_reference_note_and_summary_are_readable_and_aggregate_only():
    report = _report()
    note = _itso_reference_check_note(report)
    summary = _itso_v3_summary(
        report,
        {
            "document_review_coverage": {
                "reviewed_chunk_count": 2,
                "supplied_chunk_count": 3,
                "reviewed_text_characters": 120,
                "supplied_text_characters": 180,
            },
            "local_policy_status": "unavailable",
            "private_slm_text": "must never appear",
        },
    )

    assert note == (
        "Readable source text was found for 2 of 3 searched references. "
        "1 additional reference was not searched. "
        "Author and year details remain unconfirmed."
    )
    assert summary is not None
    assert "2 of 3 searched references" in summary
    assert "2 of 3 text sections" in summary
    assert "Institutional policy text was unavailable" in summary
    assert "must never appear" not in summary
    assert "unverified_fields" not in summary
    assert "found=2" not in summary


def test_captured_reference_report_comes_only_from_saved_user_json():
    payload = {
        "public_reference_verification": _report(),
        "document_review_coverage": {"reviewed_chunk_count": 1},
    }
    generation = SimpleNamespace(
        agent_id="itso",
        prompt_messages=[
            {"role": "user", "content": json.dumps(payload)},
            {"role": "assistant", "content": "not source data"},
        ],
    )

    report, context = _captured_itso_context([generation])

    assert report == payload["public_reference_verification"]
    assert context == {"document_review_coverage": {"reviewed_chunk_count": 1}}
    assert _captured_itso_context([]) == (None, None)


def test_model_source_citations_do_not_come_from_appended_receipts():
    generation = SimpleNamespace(
        response_json={
            "criterion_scores": [
                {
                    "criterion_id": "ITSO-02",
                    "justification": "Model rationale without a source citation.",
                }
            ]
        }
    )
    saved = (
        "Model rationale without a source citation. "
        "Tool-derived public reference verification ([source 3] "
        "https://example.org/receipt)."
    )

    assert (
        _captured_criterion_justification([generation], "ITSO-02", saved)
        == "Model rationale without a source citation."
    )
    assert _public_itso_sources(_report(), saved) == []
    assert (
        _captured_criterion_justification(
            [SimpleNamespace(response_json={})],
            "ITSO-02",
            "[source 2]: Saved rationale. "
            "Tool-derived public reference verification (receipt)",
        )
        == "[source 2]: Saved rationale."
    )


def test_result_contract_adds_optional_itso_presentation_fields():
    item = CriterionScoreItem(
        criterion_id="ITSO-04",
        criterion_text="Student confidentiality",
        score=4,
        justification="No issue detected in the reviewed text.",
        evidence_status="no_concern_detected",
    )

    assert item.evidence_status == "no_concern_detected"
    assert item.public_sources == []
    assert item.reference_check_note is None


def test_empty_quote_status_is_limited_to_defined_itso_bands():
    assert (
        unquoted_review_status(
            SimpleNamespace(criterion_code="ITSO-04", scoring_rule="Frozen rule."),
            4,
        )
        == "no_concern_detected"
    )
    assert (
        unquoted_review_status(
            SimpleNamespace(criterion_code="ITSO-05", scoring_rule="Frozen rule."),
            3,
        )
        == "rights_unverified"
    )
    assert (
        unquoted_review_status(
            SimpleNamespace(criterion_code="ITSO-04", scoring_rule="Frozen rule."),
            3,
        )
        is None
    )
    assert (
        unquoted_review_status(
            SimpleNamespace(criterion_code="ITSO-05", scoring_rule=None), 3
        )
        is None
    )


def test_result_status_requires_v3_unquoted_nonempty_reasoning():
    criterion = SimpleNamespace(criterion_code="ITSO-04", scoring_rule="Defined")
    base = {
        "score": 4,
        "evidence": None,
        "chunk_ids": None,
        "justification": "The reviewed passages show no concern.",
        "is_itso_v3": True,
    }
    assert _itso_result_evidence_status(criterion, **base) == "no_concern_detected"
    assert (
        _itso_result_evidence_status(
            criterion, **{**base, "evidence": "[]", "chunk_ids": "[]"}
        )
        == "no_concern_detected"
    )
    assert (
        _itso_result_evidence_status(
            criterion, **{**base, "evidence": '["quoted text"]'}
        )
        is None
    )
    assert (
        _itso_result_evidence_status(criterion, **{**base, "chunk_ids": '["chunk"]'})
        is None
    )
    assert (
        _itso_result_evidence_status(criterion, **{**base, "justification": "   "})
        is None
    )
    assert (
        _itso_result_evidence_status(criterion, **{**base, "is_itso_v3": False}) is None
    )
    assert (
        _itso_result_evidence_status(
            SimpleNamespace(criterion_code="ITSO-04", scoring_rule=None), **base
        )
        is None
    )


def test_result_reader_projects_captured_sources_and_preserves_flags(db_session):
    owner, doc, job, chunk = _setup_evaluation(db_session)
    row = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=job.evaluation_id, agent_id="itso")
        .one()
    )
    snapshot = make_itso_test_snapshot(
        evaluation_id=job.evaluation_id,
        adapter_version=3,
    )
    row.snapshot_id = snapshot.snapshot_id
    row.rubric_set_id = snapshot.rubric_set_id
    row.adapter_key = snapshot.adapter_key
    row.adapter_version = snapshot.adapter_version
    row.snapshot_hash = snapshot.snapshot_hash
    row.snapshot_payload = snapshot.snapshot_payload.model_dump(mode="json")
    db_session.flush()

    report = {
        "references": [
            {
                "status": "matched",
                "source_url": "https://example.org/one",
                "title": "First public source",
                "excerpt": "The first retrieved public passage.",
                "unverified_fields": [],
            },
            {
                "status": "ambiguous",
                "source_url": "https://example.org/two",
                "title": "Second public source",
                "excerpt": "The second retrieved public passage.",
                "unverified_fields": ["author", "year"],
            },
        ],
        "coverage": {"skipped": 1},
    }
    model_rows = [
        {
            "criterion_id": "ITSO-01",
            "justification": "[source 2]: The model cited this second source.",
        },
        {
            "criterion_id": "ITSO-02",
            "justification": "The model cited https://example.org/one.",
        },
        {
            "criterion_id": "ITSO-03",
            "justification": "Ownership requires review of the supplied text.",
        },
        {
            "criterion_id": "ITSO-04",
            "justification": "No concern appears in the reviewed text.",
        },
        {
            "criterion_id": "ITSO-05",
            "justification": "Rights remain unverified without quoted text.",
        },
    ]
    source_generation = CapturedGeneration(
        unit_key="source-check",
        criterion_ids=("ITSO-01", "ITSO-02"),
        prompt_text="source prompt",
        prompt_messages=(
            {
                "role": "user",
                "content": json.dumps({"public_reference_verification": report}),
            },
        ),
        response_text="source response",
        response_json={"criterion_scores": model_rows[:2]},
        response_contract_key="itso_scores.v1",
        response_contract_version=1,
        model_name="test-model",
    )
    document_generation = CapturedGeneration(
        unit_key="document-review",
        criterion_ids=("ITSO-03", "ITSO-04", "ITSO-05"),
        prompt_text="document prompt",
        prompt_messages=(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "document_review_coverage": {
                            "reviewed_chunk_count": 2,
                            "supplied_chunk_count": 3,
                            "reviewed_text_characters": 120,
                            "supplied_text_characters": 180,
                        },
                        "local_policy_status": "unavailable",
                        "private_slm_text": "never return this",
                    }
                ),
            },
        ),
        response_text="document response",
        response_json={"criterion_scores": model_rows[2:]},
        response_contract_key="itso_scores.v1",
        response_contract_version=1,
        model_name="test-model",
    )

    generated_scores = []
    for code, title in ITSO_CRITERIA_TITLES.items():
        index = int(code[-2:]) - 1
        quoted = index < 3
        generated_scores.append(
            HarnessCriterionScore(
                criterion_id=code,
                criterion_title=title,
                score=4 if code == "ITSO-04" else 3,
                justification=(
                    model_rows[index]["justification"]
                    + " Tool-derived public reference verification "
                    "(source 1 and source 2 URLs)."
                    + " Reviewed extracted-text coverage: 2 of 3 chunks."
                ),
                chunk_ids=(str(chunk.chunk_id),) if quoted else (),
                evidence=("Document quotation.",) if quoted else (),
            )
        )
    itso_base = next(
        result
        for result in make_scheduled_agent_results(job.evaluation_id, doc.document_id)
        if result.agent_name == "itso"
    )
    itso_result = replace(
        itso_base,
        criterion_scores=tuple(generated_scores),
        subtotal=sum(score.score for score in generated_scores) / 5,
        summary=(
            "Public reference checks: tool receipt. "
            "Reviewed extracted-text coverage: receipt."
        ),
        advisory_outputs=AdvisoryOutput(
            ungrounded_criteria=(
                UngroundedCriterionAdvisory(
                    criterion_id="ITSO-04", reason="No quote provided."
                ),
                UngroundedCriterionAdvisory(
                    criterion_id="ITSO-05", reason="No quote provided."
                ),
            )
        ),
        # Put the document envelope first: capture queries have no ordering
        # guarantee, and it must not prevent a later matching source response.
        generations=(document_generation, source_generation),
    )
    all_results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)
    results = [
        itso_result if result.agent_name == "itso" else result for result in all_results
    ]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda _db: None,
    )
    db_session.flush()

    before_flags = (
        db_session.query(EvaluationFlag)
        .filter_by(evaluation_id=job.evaluation_id)
        .order_by(EvaluationFlag.evaluation_flag_id)
        .all()
    )
    before = [
        (flag.evaluation_flag_id, flag.criterion_id, flag.reason)
        for flag in before_flags
    ]
    result = get_evaluation_results(job.evaluation_id, owner.user_id, db_session)
    criteria = result.domain_scores["itso"].criteria
    by_code = {criterion.criterion_id: criterion for criterion in criteria}

    assert [source.number for source in by_code["ITSO-01"].public_sources] == [2]
    assert by_code["ITSO-01"].public_sources[0].title == "Second public source"
    assert [source.number for source in by_code["ITSO-02"].public_sources] == [1]
    assert by_code["ITSO-01"].justification == "The model cited this second source."
    assert (
        by_code["ITSO-02"].justification == "The model cited https://example.org/one."
    )
    assert "Tool-derived" not in by_code["ITSO-01"].justification
    assert by_code["ITSO-01"].reference_check_note.startswith(
        "Readable source text was found for 2 of 2 searched references."
    )
    assert by_code["ITSO-04"].evidence_status == "no_concern_detected"
    assert by_code["ITSO-05"].evidence_status == "rights_unverified"
    assert by_code["ITSO-04"].is_ungrounded is True
    assert by_code["ITSO-05"].is_ungrounded is True
    assert "2 of 3 text sections" in result.domain_scores["itso"].summary
    assert (
        "Institutional policy text was unavailable"
        in result.domain_scores["itso"].summary
    )
    assert "never return this" not in result.model_dump_json()
    assert "tool receipt" not in result.domain_scores["itso"].summary.casefold()

    after_flags = (
        db_session.query(EvaluationFlag)
        .filter_by(evaluation_id=job.evaluation_id)
        .order_by(EvaluationFlag.evaluation_flag_id)
        .all()
    )
    after = [
        (flag.evaluation_flag_id, flag.criterion_id, flag.reason)
        for flag in after_flags
    ]
    assert after == before
    assert {flag.criterion_id for flag in after_flags if flag.chunk_id is None} >= {
        "ITSO-04",
        "ITSO-05",
    }
