"""Service-layer tests for the curriculum alignment check orchestration.

The typed LLM boundary (``run_alignment_check``) is exercised with fake
clients so these tests cover only the service's own validation gates, page
loading, grounding, coverage accounting, and persistence against a real
(in-memory sqlite) db_session. No live provider or real PDF is ever touched.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from server.modules.alignment.curriculum import service
from server.modules.alignment.curriculum.alignment_check import (
    PROMPT_VERSION,
    AlignmentCheckOutcome,
    AlignmentProvenance,
    AlignmentResultItem,
)
from server.modules.alignment.curriculum.exceptions import (
    AlignmentCheckCooldownError,
    AlignmentCheckNotFoundError,
    CourseNotFoundError,
    CourseProgramMismatchError,
    CurriculumMapProgramError,
    DocumentAccessDeniedError,
    DocumentNotReadyError,
    DocumentProgramError,
    DocumentSourceTypeError,
    NoCurriculumMapError,
    NoUsableDocumentTextError,
)
from server.modules.alignment.curriculum.models import CurriculumAlignmentCheck
from server.modules.curriculum import service as curriculum_map_service
from server.modules.curriculum.models import (
    Course,
    CurriculumMapCell,
    CurriculumObjective,
)
from server.modules.documents.models import Document, DocumentChunk

_PAGE_TEXT = "Students demonstrate teamwork in a capstone project."
_PAGE_TEXT_D = "Students independently design a full capstone project system."


def _make_course_with_map(
    db_session, program: str = "BSInfoTech"
) -> tuple[Course, CurriculumObjective]:
    course = Course(
        course_code="IT301", course_title="Data Structures", program=program
    )
    objective = CurriculumObjective(
        code="IT08", description="Teamwork", program=program
    )
    db_session.add_all([course, objective])
    db_session.flush()
    cell = CurriculumMapCell(
        course_id=course.course_id, objective_id=objective.objective_id, level="D"
    )
    db_session.add(cell)
    db_session.commit()
    return course, objective


def _make_document(
    db_session,
    *,
    uploaded_by: uuid.UUID | None = None,
    source_type: str = "slm",
    program: str | None = "BSInfoTech",
    status: str = "PROCESSED",
    policy_area: str | None = None,
) -> Document:
    document = Document(
        title="Sample SLM",
        source_type=source_type,
        program=program,
        processing_status=status,
        policy_area=policy_area,
        file_path="/tmp/does-not-exist.pdf",
        uploaded_by=uploaded_by or uuid.uuid4(),
    )
    db_session.add(document)
    db_session.commit()
    return document


def _add_chunks(
    db_session,
    document_id: uuid.UUID,
    pages: list[tuple[int, str]],
    *,
    source_type: str = "slm",
    is_ocr: bool = False,
) -> None:
    for chunk_index, (page_number, text) in enumerate(pages):
        db_session.add(
            DocumentChunk(
                document_id=document_id,
                source_type=source_type,
                agent_domain="all",
                page_number=page_number,
                chunk_index=chunk_index,
                text=text,
                is_ocr=is_ocr,
            )
        )
    db_session.commit()


class FakeClient:
    """Duck-typed alignment client: fixed payload, records calls."""

    provider = "fake-provider"
    model = "fake-model"

    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def generate(self, prompt: str, **_: object) -> str:
        self.calls.append(prompt)
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


class BoomClient:
    """Fails loudly if the LLM is ever contacted (validation-gate tests)."""

    model = "fake-model"

    def generate(self, prompt: str, **_: object) -> str:
        raise AssertionError("LLM must not be called before validation passes")


class TransientClient:
    """Always raises a retryable transport timeout."""

    provider = "fake-provider"
    model = "fake-model"

    def generate(self, prompt: str, **_: object) -> str:
        raise TimeoutError("simulated transport timeout")


def _ok_payload(
    code: str = "IT08",
    addressed: bool = True,
    level: str | None = "D",
    evidence: str | None = _PAGE_TEXT,
) -> dict[str, object]:
    return {
        "results": [
            {
                "objective_code": code,
                "is_addressed": addressed,
                "observed_level": level,
                "evidence": evidence,
            }
        ]
    }


def _success_outcome(results: list[AlignmentResultItem]) -> AlignmentCheckOutcome:
    return AlignmentCheckOutcome(
        success=True,
        results=tuple(results),
        provenance=AlignmentProvenance(
            prompt_version=PROMPT_VERSION,
            provider="fake-provider",
            model="fake-model",
            prompt_chars=1000,
            completion_cap=1200,
            retry_count=0,
            retry_outcome="success",
        ),
    )


def test_list_courses_returns_seeded_courses(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    courses = curriculum_map_service.list_courses(db_session)
    assert [c.course_id for c in courses] == [course.course_id]


# ── Validation gates (all before any LLM acquisition/call) ────────────────


def test_run_check_raises_when_document_missing(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    with pytest.raises(DocumentAccessDeniedError):
        service.run_curriculum_alignment_check(
            document_id=uuid.uuid4(),
            course_id=course.course_id,
            current_user_id=uuid.uuid4(),
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_raises_when_not_document_owner(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    document = _make_document(db_session, uploaded_by=uuid.uuid4())
    with pytest.raises(DocumentAccessDeniedError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=uuid.uuid4(),
            db=db_session,
            llm_client=BoomClient(),
        )


@pytest.mark.parametrize(
    "source_type", ["policy", "syllabus", "curriculum", "rubric_sme"]
)
def test_run_check_rejects_non_slm_source_before_llm(db_session, source_type) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(
        db_session,
        uploaded_by=owner,
        source_type=source_type,
        policy_area="general_itso" if source_type == "policy" else None,
    )

    with pytest.raises(DocumentSourceTypeError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_rejects_unprocessed_document_before_llm(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner, status="PENDING")

    with pytest.raises(DocumentNotReadyError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_rejects_document_without_usable_chunks(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

    with pytest.raises(NoUsableDocumentTextError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_rejects_unsupported_document_program(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner, program="BSCS")
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    with pytest.raises(DocumentProgramError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_rejects_missing_document_program(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner, program=None)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    with pytest.raises(DocumentProgramError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_raises_when_course_not_found(db_session) -> None:
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    with pytest.raises(CourseNotFoundError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=uuid.uuid4(),
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_rejects_unsupported_course_program(db_session) -> None:
    # Document is a valid BSInfoTech SLM; the course is owned by BSCS.
    course, _ = _make_course_with_map(db_session, program="BSCS")
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner, program="BSInfoTech")
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    with pytest.raises(CourseProgramMismatchError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_course_document_program_mismatch_is_refused(db_session) -> None:
    # Defensive invariant of _validate_course_program: even though the public
    # flow normalizes the document gate to BSInfoTech before reaching this
    # check, an explicit mismatch is still refused rather than assumed equal.
    class StubCourse:
        course_code = "IT301"
        program = "BSInfoTech"

    class StubDocument:
        document_id = uuid.uuid4()
        program = "BSCS"

    with pytest.raises(CourseProgramMismatchError):
        service._validate_course_program(StubCourse(), StubDocument())


def test_run_check_accepts_legacy_bsit_alias_program(db_session) -> None:
    course, _ = _make_course_with_map(db_session, program="BSIT")
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner, program="BSIT")
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(_ok_payload()),
    )
    assert check.success is True


def test_run_check_rejects_foreign_objective_program(db_session) -> None:
    course, _ = _make_course_with_map(db_session, program="BSInfoTech")
    # A BSCS objective leaked into the BSInfoTech map must be rejected.
    foreign_objective = CurriculumObjective(
        code="CS101", description="CS topic", program="BSCS"
    )
    db_session.add(foreign_objective)
    db_session.flush()
    db_session.add(
        CurriculumMapCell(
            course_id=course.course_id,
            objective_id=foreign_objective.objective_id,
            level="I",
        )
    )
    db_session.commit()

    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    with pytest.raises(CurriculumMapProgramError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_raises_when_no_curriculum_map(db_session) -> None:
    course = Course(course_code="IT999", course_title="Unmapped", program="BSInfoTech")
    db_session.add(course)
    db_session.commit()
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    with pytest.raises(NoCurriculumMapError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=BoomClient(),
        )


def test_run_check_rejects_duplicate_request_within_cooldown(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    db_session.add(
        CurriculumAlignmentCheck(
            document_id=document.document_id,
            course_id=course.course_id,
            objective_results=[],
            summary={
                "total_mapped_objectives": 0,
                "match": 0,
                "under_developed": 0,
                "over_developed": 0,
                "not_addressed": 0,
            },
            success=True,
            run_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    with pytest.raises(AlignmentCheckCooldownError) as exc:
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
            llm_client=FakeClient(_ok_payload()),
        )

    assert exc.value.retry_after_seconds > 0


def test_run_check_allows_request_after_cooldown_window(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    db_session.add(
        CurriculumAlignmentCheck(
            document_id=document.document_id,
            course_id=course.course_id,
            objective_results=[],
            summary={
                "total_mapped_objectives": 0,
                "match": 0,
                "under_developed": 0,
                "over_developed": 0,
                "not_addressed": 0,
            },
            success=True,
            run_at=datetime.now(UTC) - timedelta(seconds=45),
        )
    )
    db_session.commit()

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(_ok_payload()),
    )
    assert check.success is True


# ── Happy path: persisted (even OCR) chunks, no PDF on disk ────────────────


def test_run_check_happy_path_persists_result_from_chunks(
    db_session, monkeypatch
) -> None:
    course, objective = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    # The file path intentionally does not exist: only persisted chunks are
    # read, and OCR'd text is fine -- nothing reopens the raw PDF.
    _add_chunks(
        db_session,
        document.document_id,
        [(1, "Intro."), (2, _PAGE_TEXT)],
        is_ocr=True,
    )

    client = FakeClient(_ok_payload(evidence=_PAGE_TEXT))
    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=client,
    )

    assert check.success is True
    assert check.model_name == "fake-model"
    assert check.summary == {
        "total_mapped_objectives": 1,
        "match": 1,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
        "not_observed": 0,
    }
    assert len(check.objective_results) == 1
    result = check.objective_results[0]
    assert result["code"] == "IT08"
    assert result["status"] == "match"
    assert result["evidence_page"] == 2

    fetched = service.get_alignment_check(check.check_id, owner, db_session)
    assert fetched.check_id == check.check_id


def test_run_check_persists_safe_provenance_without_document_text(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    client = FakeClient(_ok_payload())
    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=client,
    )

    provenance = check.provenance
    assert provenance["prompt_version"] == PROMPT_VERSION
    assert provenance["provider"] == "fake-provider"
    assert provenance["model"] == "fake-model"
    assert provenance["text_source"] == {
        "source": "persisted_chunks",
        "ocr_aware": True,
    }
    assert provenance["coverage"]["scope"] == "full"
    assert provenance["failure"] == "none"
    serialized = json.dumps(provenance)
    assert _PAGE_TEXT not in serialized
    assert "CURRICULUM AND DOCUMENT DATA" not in serialized
    assert str(document.document_id) not in serialized
    assert str(check.check_id) not in serialized


# ── Coverage: full vs bounded, evaluated-page-only grounding ──────────────


def test_full_coverage_grounds_against_all_pages(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, "intro"), (2, _PAGE_TEXT)])

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(_ok_payload(evidence=_PAGE_TEXT)),
    )

    assert check.provenance["coverage"] == {
        "scope": "full",
        "total_pages": 2,
        "evaluated_pages": 2,
        "total_chars": len("intro") + len(_PAGE_TEXT),
        "evaluated_chars": len("intro") + len(_PAGE_TEXT),
        "strategy": "all_pages",
    }
    assert check.objective_results[0]["evidence_page"] == 2


def test_bounded_scope_records_not_observed_for_absence(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    big = "x" * (service._MAX_SLM_TEXT_CHARS // 2)
    _add_chunks(db_session, document.document_id, [(1, big), (2, big), (3, big)])

    # The model reports the objective as NOT addressed within the bounded
    # window: that is "not observed", never a whole-document "not_addressed".
    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(_ok_payload(addressed=False, level=None, evidence=None)),
    )

    assert check.provenance["coverage"]["scope"] == "bounded"
    assert check.provenance["coverage"]["evaluated_pages"] == 2
    assert check.provenance["coverage"]["total_pages"] == 3
    result = check.objective_results[0]
    assert result["status"] == "not_observed"
    assert check.summary == {
        "total_mapped_objectives": 1,
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
        "not_observed": 1,
    }


def test_bounded_scope_preserves_grounded_positive_result(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    big = "x" * 2000
    _add_chunks(
        db_session,
        document.document_id,
        [(1, big), (2, f"{big} {_PAGE_TEXT}"), (3, big)],
    )

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(_ok_payload(evidence=_PAGE_TEXT)),
    )

    assert check.provenance["coverage"]["scope"] == "bounded"
    result = check.objective_results[0]
    assert result["status"] == "match"  # grounded positive preserved
    assert result["evidence_page"] == 2
    assert check.summary["match"] == 1
    assert check.summary["not_observed"] == 0


def test_bounded_scope_downgrades_evidence_from_excluded_page(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    big = "x" * (service._MAX_SLM_TEXT_CHARS // 2)
    # The quote only exists on page 3, which is NOT part of the evaluated
    # prefix (pages 1-2). Grounding happens against evaluated pages only.
    _add_chunks(
        db_session,
        document.document_id,
        [(1, big), (2, big), (3, _PAGE_TEXT)],
    )

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(_ok_payload(evidence=_PAGE_TEXT)),
    )

    assert check.provenance["coverage"]["scope"] == "bounded"
    result = check.objective_results[0]
    assert result["status"] == "not_observed"
    assert result["evidence_page"] is None
    assert result["evidence"] is None


def test_ungrounded_evidence_is_downgraded_to_not_addressed_full_scope(
    db_session,
) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, "Unrelated page text.")])

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(
            _ok_payload(evidence="text that does not appear in the document")
        ),
    )

    result = check.objective_results[0]
    assert result["status"] == "not_addressed"
    assert result["evidence_page"] is None
    assert check.summary["not_addressed"] == 1


# ── Typed outcome failure paths (strict, atomic, safe) ─────────────────────


def test_malformed_model_response_fails_atomically(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient("not valid json"),
    )

    assert check.success is False
    assert check.objective_results == []
    assert check.summary == {
        "total_mapped_objectives": 1,
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
        "not_observed": 0,
    }
    assert "rejected" in check.error_message
    assert check.provenance["failure"] == "rejected_response"
    assert check.provenance["error_kind"] == "response_schema"


def test_partial_objective_coverage_rejects_whole_response(db_session) -> None:
    course, objective = _make_course_with_map(db_session)
    second = CurriculumObjective(code="IT09", description="Tools", program="BSInfoTech")
    db_session.add(second)
    db_session.flush()
    db_session.add(
        CurriculumMapCell(
            course_id=course.course_id, objective_id=second.objective_id, level="E"
        )
    )
    db_session.commit()

    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    # Response only covers IT08 -- IT09 is missing, so the WHOLE response is
    # rejected. No silent partial-to-negative conversion.
    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(_ok_payload()),
    )

    assert check.success is False
    assert check.objective_results == []
    assert check.provenance["failure"] == "rejected_response"
    assert check.provenance["error_kind"] == "response_coverage"


def test_configuration_failure_message_is_concise(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    class NoGenerateClient:  # preflight rejects: no callable generate()
        model = "fake-model"

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=NoGenerateClient(),
    )

    assert check.success is False
    assert "configuration" in check.error_message
    assert check.provenance["failure"] == "configuration"
    assert check.provenance["error_kind"] == "config"


def test_transient_failure_message_is_concise(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=TransientClient(),
        backoff_seconds=0,
    )

    assert check.success is False
    assert "transiently" in check.error_message
    assert check.provenance["failure"] == "transient"
    assert check.provenance["error_kind"] == "timeout"


def test_permanent_call_failure_message_is_concise(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])

    from email.message import Message
    from urllib import error as urllib_error

    class Http400Client:
        provider = "fake-provider"
        model = "fake-model"

        def generate(self, prompt: str, **_: object) -> str:
            raise urllib_error.HTTPError(
                "http://llm.local", 400, "bad request", Message(), None
            )

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=Http400Client(),
    )

    assert check.success is False
    assert "LLM call failed" in check.error_message
    assert "http://llm.local" not in check.error_message
    assert check.provenance["failure"] == "call_failed"
    assert check.provenance["error_kind"] == "http_400"


def test_prompt_input_uses_only_evaluated_pages(db_session, monkeypatch) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    big_len = service._MAX_SLM_TEXT_CHARS // 2
    _add_chunks(
        db_session,
        document.document_id,
        [(1, "a" * big_len), (2, "b" * big_len), (3, "c" * big_len)],
    )

    captured: dict[str, str] = {}

    def _stub(client, mapped, slm_text, **kwargs):
        captured["slm_text"] = slm_text
        return _success_outcome(
            [
                AlignmentResultItem(
                    objective_code="IT08",
                    is_addressed=False,
                    observed_level=None,
                    evidence=None,
                )
            ]
        )

    monkeypatch.setattr(service, "run_alignment_check", _stub)
    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(_ok_payload()),
    )

    assert check.provenance["coverage"]["scope"] == "bounded"
    # Page 3's distinct content must never reach the prompt: only evaluated
    # pages 1-2 are sent.
    assert "a" * 50 in captured["slm_text"]
    assert "b" * 50 in captured["slm_text"]
    assert "c" * 50 not in captured["slm_text"]


# ── Read paths: legacy checks keep working ─────────────────────────────────


def test_get_alignment_check_raises_when_missing(db_session) -> None:
    with pytest.raises(AlignmentCheckNotFoundError):
        service.get_alignment_check(uuid.uuid4(), uuid.uuid4(), db_session)


def test_get_alignment_check_raises_for_non_owner(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    with pytest.raises(DocumentAccessDeniedError):
        service.get_alignment_check(check.check_id, uuid.uuid4(), db_session)


def test_legacy_check_without_provenance_reports_legacy_unknown_coverage(
    db_session,
) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(1, _PAGE_TEXT)])
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 1},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    fetched = service.get_alignment_check(check.check_id, owner, db_session)
    assert fetched.provenance is None
    assert service.get_coverage_metadata(fetched) == {
        "scope": "legacy_unknown",
        "total_pages": None,
        "evaluated_pages": None,
        "total_chars": None,
        "evaluated_chars": None,
        "strategy": None,
    }


def test_legacy_check_document_pages_still_load_from_chunks(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    _add_chunks(db_session, document.document_id, [(2, _PAGE_TEXT), (1, "intro")])
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 1},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    pages = service.get_document_pages_for_check(check.check_id, owner, db_session)

    assert [(p.page_number, p.text) for p in pages] == [
        (1, "intro"),
        (2, _PAGE_TEXT),
    ]


def test_get_document_pages_raises_for_non_owner(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    with pytest.raises(DocumentAccessDeniedError):
        service.get_document_pages_for_check(check.check_id, uuid.uuid4(), db_session)


def test_list_checks_returns_only_current_users_checks_newest_first(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    other_owner = uuid.uuid4()

    mine_doc = _make_document(db_session, uploaded_by=owner)
    other_doc = _make_document(db_session, uploaded_by=other_owner)

    older = CurriculumAlignmentCheck(
        document_id=mine_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    older.run_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
    db_session.add(older)
    db_session.commit()

    newer = CurriculumAlignmentCheck(
        document_id=mine_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    newer.run_at = datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)
    db_session.add(newer)
    db_session.commit()

    not_mine = CurriculumAlignmentCheck(
        document_id=other_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(not_mine)
    db_session.commit()

    items, total = service.list_alignment_checks(
        current_user_id=owner, page=1, page_size=20, db=db_session
    )
    assert total == 2
    assert [i["check_id"] for i in items] == [newer.check_id, older.check_id]
    assert items[0]["document_title"] == "Sample SLM"
    assert items[0]["course_title"] == "Data Structures"


def test_list_checks_paginates(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

    for _ in range(3):
        db_session.add(
            CurriculumAlignmentCheck(
                document_id=document.document_id,
                course_id=course.course_id,
                objective_results=[],
                summary={"total_mapped_objectives": 0},
                success=True,
            )
        )
        db_session.commit()

    page_1, total = service.list_alignment_checks(
        current_user_id=owner, page=1, page_size=2, db=db_session
    )
    page_2, _ = service.list_alignment_checks(
        current_user_id=owner, page=2, page_size=2, db=db_session
    )
    assert total == 3
    assert len(page_1) == 2
    assert len(page_2) == 1


def test_list_checks_returns_empty_for_user_with_none(db_session) -> None:
    items, total = service.list_alignment_checks(
        current_user_id=uuid.uuid4(), page=1, page_size=20, db=db_session
    )
    assert items == []
    assert total == 0


def test_delete_check_removes_row(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()
    check_id = check.check_id

    service.delete_alignment_check(check_id, owner, db_session)

    assert db_session.get(CurriculumAlignmentCheck, check_id) is None


def test_delete_check_raises_for_nonexistent_check(db_session) -> None:
    with pytest.raises(AlignmentCheckNotFoundError):
        service.delete_alignment_check(uuid.uuid4(), uuid.uuid4(), db_session)


def test_delete_check_raises_for_non_owner(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    other_user = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    with pytest.raises(DocumentAccessDeniedError):
        service.delete_alignment_check(check.check_id, other_user, db_session)
