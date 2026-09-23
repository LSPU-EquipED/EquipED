"""Integration tests for monitoring matrix queries, search, and pagination."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from server.modules.documents.models import Document
from server.modules.synthesis.models import MonitoringMatrix
from server.tests.synthesis.conftest import _login


def _add_matrix(db_session, user_id, title: str, program: str) -> None:
    document = Document(
        title=title,
        program=program,
        source_type="slm",
        file_path=f"/tmp/{title}.pdf",
        uploaded_by=user_id,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(MonitoringMatrix(document_id=document.document_id, program=program))


@pytest.fixture()
def matrix_client_data(client, db_session, seeded_user):
    for title, program in (
        ("modern", "BSInfoTech"),
        ("legacy", "BSIT"),
        ("computer science", "BSCS"),
        ("historical", "BSN"),
    ):
        _add_matrix(db_session, seeded_user.user_id, title, program)
    db_session.commit()
    _login(client, seeded_user)
    return client


@pytest.mark.parametrize("program", ["BSInfoTech", "bsit"])
def test_matrix_canonicalizes_bsit_aliases(matrix_client_data, program: str) -> None:
    response = matrix_client_data.get(f"/api/v1/evaluations/matrix?program={program}")
    assert response.status_code == 200
    assert {item["document_title"] for item in response.json()["items"]} == {
        "modern",
        "legacy",
    }


def test_matrix_bscs_filter(matrix_client_data) -> None:
    response = matrix_client_data.get("/api/v1/evaluations/matrix?program=BSCS")
    assert response.status_code == 200
    assert {item["document_title"] for item in response.json()["items"]} == {
        "computer science",
    }


def test_matrix_rejects_unsupported_program(matrix_client_data) -> None:
    response = matrix_client_data.get("/api/v1/evaluations/matrix?program=BSEd")
    assert response.status_code == 422


def test_matrix_preserves_historical_program_rows(matrix_client_data) -> None:
    response = matrix_client_data.get("/api/v1/evaluations/matrix")
    assert response.status_code == 200
    assert "historical" in {item["document_title"] for item in response.json()["items"]}


def test_matrix_search_filtering(client, db_session, seeded_user):
    _login(client, seeded_user)

    # 1. Row matching document title (case-insensitive substring)
    doc1 = Document(
        document_id=uuid.uuid4(),
        title="Advanced Algorithms and Complexity",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/alg.pdf",
        uploaded_by=seeded_user.user_id,
    )
    db_session.add(doc1)
    db_session.flush()
    m1 = MonitoringMatrix(
        document_id=doc1.document_id,
        program="BSCS",
        faculty_name="Dr. Alan Turing",
        evaluation_status="COMPLETED",
    )
    db_session.add(m1)

    # 2. Row matching faculty_name (case-insensitive substring)
    doc2 = Document(
        document_id=uuid.uuid4(),
        title="Web Systems and Technologies",
        program="BSInfoTech",
        source_type="slm",
        file_path="/tmp/web.pdf",
        uploaded_by=seeded_user.user_id,
    )
    db_session.add(doc2)
    db_session.flush()
    m2 = MonitoringMatrix(
        document_id=doc2.document_id,
        program="BSInfoTech",
        faculty_name="Prof. Ada Lovelace",
        evaluation_status="IN_PROGRESS",
    )
    db_session.add(m2)

    # 3. Row matching program
    doc3 = Document(
        document_id=uuid.uuid4(),
        title="Introduction to Computing",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/intro.pdf",
        uploaded_by=seeded_user.user_id,
    )
    db_session.add(doc3)
    db_session.flush()
    m3 = MonitoringMatrix(
        document_id=doc3.document_id,
        program="BSCS",
        faculty_name="John von Neumann",
        evaluation_status="SUBMITTED",
    )
    db_session.add(m3)

    # 4. Row with NO Document record (orphan matrix row) matching faculty_name
    orphan_doc_id = uuid.uuid4()
    m4 = MonitoringMatrix(
        document_id=orphan_doc_id,
        program="BSCS",
        faculty_name="Grace Hopper Specialist",
        evaluation_status="COMPLETED",
    )
    db_session.add(m4)

    # 5. Row with NO Document record matching program
    orphan_doc_id2 = uuid.uuid4()
    m5 = MonitoringMatrix(
        document_id=orphan_doc_id2,
        program="SpecialProgramXYZ",
        faculty_name="Claude Shannon",
        evaluation_status="COMPLETED",
    )
    db_session.add(m5)

    db_session.commit()

    # Search document title with whitespace padding and lowercase
    res = client.get("/api/v1/evaluations/matrix?search=  algo  ")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["document_title"] == "Advanced Algorithms and Complexity"

    # Search faculty_name
    res = client.get("/api/v1/evaluations/matrix?search=lovelace")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["faculty_name"] == "Prof. Ada Lovelace"

    # Search orphan row matching faculty_name (preserves rows without Document)
    res = client.get("/api/v1/evaluations/matrix?search=hopper")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["document_id"] == str(orphan_doc_id)
    assert data["items"][0]["document_title"] is None
    assert data["items"][0]["faculty_name"] == "Grace Hopper Specialist"

    # Search orphan row matching program
    res = client.get("/api/v1/evaluations/matrix?search=specialprogram")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["document_id"] == str(orphan_doc_id2)

    # Combined with program filter and status filter
    res = client.get(
        "/api/v1/evaluations/matrix?search=Alan&program=BSCS&status=COMPLETED"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["faculty_name"] == "Dr. Alan Turing"

    # Search matches Alan, but status doesn't match
    res = client.get(
        "/api/v1/evaluations/matrix?search=Alan&program=BSCS&status=IN_PROGRESS"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0

    # Blank/whitespace search returns all rows (same as no search)
    res_blank = client.get("/api/v1/evaluations/matrix?search=   ")
    assert res_blank.status_code == 200
    res_none = client.get("/api/v1/evaluations/matrix")
    assert res_none.status_code == 200
    assert res_blank.json()["total"] == res_none.json()["total"]


def test_matrix_search_pagination_and_beyond_first_page(
    client, db_session, seeded_user
):
    _login(client, seeded_user)

    # Create 5 rows matching search term "PaginationTarget"
    for i in range(5):
        doc = Document(
            document_id=uuid.uuid4(),
            title=f"PaginationTarget Document {i}",
            program="BSCS",
            source_type="slm",
            file_path=f"/tmp/p{i}.pdf",
            uploaded_by=seeded_user.user_id,
        )
        db_session.add(doc)
        db_session.flush()
        db_session.add(
            MonitoringMatrix(
                document_id=doc.document_id,
                program="BSCS",
                faculty_name=f"Faculty {i}",
                evaluation_status="COMPLETED",
            )
        )
    db_session.commit()

    # Page 1 with page_size=2
    res_p1 = client.get(
        "/api/v1/evaluations/matrix?search=paginationtarget&page=1&page_size=2"
    )
    assert res_p1.status_code == 200
    d1 = res_p1.json()
    assert d1["total"] == 5
    assert len(d1["items"]) == 2
    assert d1["page"] == 1
    assert d1["page_size"] == 2

    # Beyond-first-page: Page 2 with page_size=2
    res_p2 = client.get(
        "/api/v1/evaluations/matrix?search=paginationtarget&page=2&page_size=2"
    )
    assert res_p2.status_code == 200
    d2 = res_p2.json()
    assert d2["total"] == 5
    assert len(d2["items"]) == 2
    assert d2["page"] == 2

    # Page 3 with page_size=2 (last item)
    res_p3 = client.get(
        "/api/v1/evaluations/matrix?search=paginationtarget&page=3&page_size=2"
    )
    assert res_p3.status_code == 200
    d3 = res_p3.json()
    assert d3["total"] == 5
    assert len(d3["items"]) == 1
    assert d3["page"] == 3

    # Items across pages should not overlap
    ids_p1 = {item["document_id"] for item in d1["items"]}
    ids_p2 = {item["document_id"] for item in d2["items"]}
    ids_p3 = {item["document_id"] for item in d3["items"]}
    assert ids_p1.isdisjoint(ids_p2)
    assert ids_p2.isdisjoint(ids_p3)
    assert ids_p1.isdisjoint(ids_p3)


def test_matrix_search_escapes_sql_wildcards(client, db_session, seeded_user):
    """Ensure '%' and '_' in search queries are matched literally, not as wildcards."""
    _login(client, seeded_user)

    doc_literal_percent = Document(
        document_id=uuid.uuid4(),
        title="Accuracy at 100% Performance",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/100pct.pdf",
        uploaded_by=seeded_user.user_id,
    )
    doc_other = Document(
        document_id=uuid.uuid4(),
        title="Accuracy at 1000 Performance",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/1000.pdf",
        uploaded_by=seeded_user.user_id,
    )
    doc_literal_underscore = Document(
        document_id=uuid.uuid4(),
        title="Module_01 Overview",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/mod_01.pdf",
        uploaded_by=seeded_user.user_id,
    )
    doc_other_underscore = Document(
        document_id=uuid.uuid4(),
        title="ModuleA01 Overview",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/moda01.pdf",
        uploaded_by=seeded_user.user_id,
    )
    db_session.add_all(
        [
            doc_literal_percent,
            doc_other,
            doc_literal_underscore,
            doc_other_underscore,
        ]
    )
    db_session.flush()

    for doc in (
        doc_literal_percent,
        doc_other,
        doc_literal_underscore,
        doc_other_underscore,
    ):
        db_session.add(
            MonitoringMatrix(
                document_id=doc.document_id,
                program="BSCS",
                evaluation_status="COMPLETED",
            )
        )
    db_session.commit()

    # Searching for literal "%" should only match "100%", not "1000"
    res_percent = client.get("/api/v1/evaluations/matrix?search=100%")
    assert res_percent.status_code == 200
    data_percent = res_percent.json()
    assert data_percent["total"] == 1
    assert data_percent["items"][0]["document_title"] == "Accuracy at 100% Performance"

    # Searching for literal "_" should only match "Module_01", not "ModuleA01"
    res_under = client.get("/api/v1/evaluations/matrix?search=Module_01")
    assert res_under.status_code == 200
    data_under = res_under.json()
    assert data_under["total"] == 1
    assert data_under["items"][0]["document_title"] == "Module_01 Overview"


def test_matrix_search_length_boundary_422(client, db_session, seeded_user):
    """Search queries exceeding 100 characters must return 422 Unprocessable Entity."""
    _login(client, seeded_user)

    # Valid: 100 characters
    res_valid = client.get(f"/api/v1/evaluations/matrix?search={'a' * 100}")
    assert res_valid.status_code == 200

    # Invalid: 101 characters
    res_invalid = client.get(f"/api/v1/evaluations/matrix?search={'a' * 101}")
    assert res_invalid.status_code == 422


def test_matrix_search_blank_behavior(client, db_session, seeded_user):
    """Empty or whitespace-only search string should behave like no search."""
    _login(client, seeded_user)

    doc = Document(
        document_id=uuid.uuid4(),
        title="Blank Search Test Doc",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/blank.pdf",
        uploaded_by=seeded_user.user_id,
    )
    db_session.add(doc)
    db_session.flush()
    matrix = MonitoringMatrix(
        document_id=doc.document_id,
        program="BSCS",
        evaluation_status="COMPLETED",
    )
    db_session.add(matrix)
    db_session.commit()

    res_empty = client.get("/api/v1/evaluations/matrix?search=")
    assert res_empty.status_code == 200
    assert res_empty.json()["total"] >= 1

    res_whitespace = client.get("/api/v1/evaluations/matrix?search=   ")
    assert res_whitespace.status_code == 200
    assert res_whitespace.json()["total"] == res_empty.json()["total"]


def test_matrix_metrics_and_classifier_aggregations(client, db_session, seeded_user):
    """Test full metrics contract:
    - Pre-pagination identical filtered set
    - completed_count, passing_count, flagged_count, total_flags, quality_pass_rate
    - Mixed scores: modern percent, domain subtotals, legacy 1-4, unknown score
    - Rating helper and adjectival rating consistency
    - Metrics remain constant across pagination
    - Filtered by program, status, search
    - Zero completed yields quality_pass_rate=null
    """
    _login(client, seeded_user)

    # Clean test isolate: create distinct set with unique program / marker
    # We will test using program=BSCS or search marker
    marker = "mtxmetricstest"

    # Row 1: COMPLETED, progressive domain subtotals
    # (sme=3.5, coord=3.0, gad=3.0, itso=2.5)
    # Overall: 0.35*3.5 + 0.30*3.0 + 0.20*3.0 + 0.15*2.5 = 3.10
    # Rating: Satisfactory, Passing: True, Flag count: 2
    doc1 = Document(
        document_id=uuid.uuid4(),
        title=f"{marker} Row 1 Progressive Passing",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/r1.pdf",
        uploaded_by=seeded_user.user_id,
    )
    m1 = MonitoringMatrix(
        document_id=doc1.document_id,
        program="BSCS",
        evaluation_status="COMPLETED",
        synthesized_score=77.5,  # progressive %
        domain_scores_json={
            "sme": {"subtotal": 3.5, "status": "OK", "criteria": [], "max_score": 4},
            "coordinator": {
                "subtotal": 3.0,
                "status": "OK",
                "criteria": [],
                "max_score": 4,
            },
            "gad": {"subtotal": 3.0, "status": "OK", "criteria": [], "max_score": 4},
            "itso": {"subtotal": 2.5, "status": "OK", "criteria": [], "max_score": 4},
        },
        flag_count=2,
    )

    # Row 2: COMPLETED, modern progressive percentage fallback (80.0%)
    # Overall = (80 / 100) * 4 = 3.20 -> Satisfactory, Passing: True, Flag count: 0
    doc2 = Document(
        document_id=uuid.uuid4(),
        title=f"{marker} Row 2 Pct Fallback Passing",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/r2.pdf",
        uploaded_by=seeded_user.user_id,
    )
    m2 = MonitoringMatrix(
        document_id=doc2.document_id,
        program="BSCS",
        evaluation_status="COMPLETED",
        synthesized_score=80.0,
        domain_scores_json=None,
        flag_count=0,
    )

    # Row 3: COMPLETED, modern progressive percentage failing (fallback: 40.0%)
    # Overall = (40 / 100) * 4 = 1.60 -> Needs Improvement, Passing: False
    doc3 = Document(
        document_id=uuid.uuid4(),
        title=f"{marker} Row 3 Pct Fallback Failing",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/r3.pdf",
        uploaded_by=seeded_user.user_id,
    )
    m3 = MonitoringMatrix(
        document_id=doc3.document_id,
        program="BSCS",
        evaluation_status="COMPLETED",
        synthesized_score=40.0,
        domain_scores_json=None,
        flag_count=3,
    )

    # Row 4: COMPLETED, modern progressive percentage passing (85.0%)
    # Overall = (85 / 100) * 4 = 3.40 -> Satisfactory, Passing: True, Flag count: 1
    doc4 = Document(
        document_id=uuid.uuid4(),
        title=f"{marker} Row 4 Pct Passing",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/r4.pdf",
        uploaded_by=seeded_user.user_id,
    )
    m4 = MonitoringMatrix(
        document_id=doc4.document_id,
        program="BSCS",
        evaluation_status="COMPLETED",
        synthesized_score=85.0,
        domain_scores_json=None,
        flag_count=1,
    )

    # Row 5: COMPLETED, unknown/missing score (synthesized_score=None)
    # completed_count counts it, but NOT passing; rating=None. Flag count: 0
    doc5 = Document(
        document_id=uuid.uuid4(),
        title=f"{marker} Row 5 Completed Missing Score",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/r5.pdf",
        uploaded_by=seeded_user.user_id,
    )
    m5 = MonitoringMatrix(
        document_id=doc5.document_id,
        program="BSCS",
        evaluation_status="COMPLETED",
        synthesized_score=None,
        domain_scores_json=None,
        flag_count=0,
    )

    # Row 6: IN_PROGRESS (not completed), has flags (flag_count: 4)
    doc6 = Document(
        document_id=uuid.uuid4(),
        title=f"{marker} Row 6 In Progress",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/r6.pdf",
        uploaded_by=seeded_user.user_id,
    )
    m6 = MonitoringMatrix(
        document_id=doc6.document_id,
        program="BSCS",
        evaluation_status="IN_PROGRESS",
        synthesized_score=None,
        domain_scores_json=None,
        flag_count=4,
    )

    # Row 7: FAILED (not completed), flag_count: 0
    doc7 = Document(
        document_id=uuid.uuid4(),
        title=f"{marker} Row 7 Failed",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/r7.pdf",
        uploaded_by=seeded_user.user_id,
    )
    m7 = MonitoringMatrix(
        document_id=doc7.document_id,
        program="BSCS",
        evaluation_status="FAILED",
        synthesized_score=None,
        domain_scores_json=None,
        flag_count=0,
    )

    # Row 8: Orphan matrix row (no document), COMPLETED, ambiguous score <= 4.0
    # Synthesized score = 3.5 (ambiguous without 4-domain breakdown):
    # NOT passing, adjectival_rating=None, but completed_count includes it.
    # flag_count: 0
    m8 = MonitoringMatrix(
        document_id=uuid.uuid4(),
        faculty_name=f"{marker} Faculty",
        program="BSCS",
        evaluation_status="COMPLETED",
        synthesized_score=3.50,
        domain_scores_json=None,
        flag_count=0,
    )

    db_session.add_all([doc1, doc2, doc3, doc4, doc5, doc6, doc7])
    db_session.add_all([m1, m2, m3, m4, m5, m6, m7, m8])
    db_session.commit()

    # Search for marker: all 8 rows match!
    # Expected metrics over all 8 rows:
    # completed_count = 6 (rows 1, 2, 3, 4, 5, 8)
    # passing_count = 3 (row 1: 3.10, row 2: 3.20, row 4: 3.40)
    # failing completed: row 3 (1.60), row 5 (None), row 8 (3.50 ambiguous)
    # flagged_count = 4 (rows 1, 3, 4, 6)
    # total_flags = 2 + 3 + 1 + 4 = 10
    # quality_pass_rate = round(100.0 * 3 / 6, 2) = 50.00
    # total = 8
    res_p1 = client.get(
        f"/api/v1/evaluations/matrix?search={marker}&page=1&page_size=3"
    )
    assert res_p1.status_code == 200
    d1 = res_p1.json()
    assert d1["total"] == 8
    assert len(d1["items"]) == 3
    assert d1["metrics"] == {
        "completed_count": 6,
        "passing_count": 3,
        "flagged_count": 4,
        "total_flags": 10,
        "quality_pass_rate": 50.0,
    }

    # Verify metrics remain invariant across pages
    res_p2 = client.get(
        f"/api/v1/evaluations/matrix?search={marker}&page=2&page_size=3"
    )
    assert res_p2.status_code == 200
    d2 = res_p2.json()
    assert d2["page"] == 2
    assert d2["metrics"] == d1["metrics"]

    res_p3 = client.get(
        f"/api/v1/evaluations/matrix?search={marker}&page=3&page_size=3"
    )
    assert res_p3.status_code == 200
    d3 = res_p3.json()
    assert d3["page"] == 3
    assert d3["metrics"] == d1["metrics"]

    all_items = d1["items"] + d2["items"] + d3["items"]
    # Verify row adjectival_rating consistency:
    # Row 1: domain subtotals -> 3.10 => "Satisfactory" (NOT "Very Satisfactory")
    row1_item = next(
        it for it in all_items if it["document_id"] == str(doc1.document_id)
    )
    assert row1_item["synthesized_score"] == 77.5
    assert row1_item["adjectival_rating"] == "Satisfactory"

    # Row 5 (unknown/null score) -> adjectival_rating is None
    row5_item = next(
        it for it in all_items if it["document_id"] == str(doc5.document_id)
    )
    assert row5_item["synthesized_score"] is None
    assert row5_item["adjectival_rating"] is None

    # Row 8 (ambiguous <= 4.0 without domain breakdown) -> adjectival_rating is None
    row8_item = next(it for it in all_items if it["matrix_id"] == str(m8.matrix_id))
    assert row8_item["synthesized_score"] == 3.50
    assert row8_item["adjectival_rating"] is None

    # Filter with status=IN_PROGRESS: only 1 row (row 6)
    # completed_count = 0 -> quality_pass_rate MUST be null, not 100.0 or 0.0
    res_inprogress = client.get(
        f"/api/v1/evaluations/matrix?search={marker}&status=IN_PROGRESS"
    )
    assert res_inprogress.status_code == 200
    dinprogress = res_inprogress.json()
    assert dinprogress["total"] == 1
    assert dinprogress["metrics"] == {
        "completed_count": 0,
        "passing_count": 0,
        "flagged_count": 1,
        "total_flags": 4,
        "quality_pass_rate": None,
    }

    # Empty result set: search for non-existent term
    res_empty = client.get(
        "/api/v1/evaluations/matrix?search=thisdoesnotexistanywhereinmatrix"
    )
    assert res_empty.status_code == 200
    dempty = res_empty.json()
    assert dempty["total"] == 0
    assert dempty["items"] == []
    assert dempty["metrics"] == {
        "completed_count": 0,
        "passing_count": 0,
        "flagged_count": 0,
        "total_flags": 0,
        "quality_pass_rate": None,
    }


def test_matrix_pagination_deterministic_with_identical_timestamps(
    client, db_session, seeded_user
):
    """Ensure equal last_updated timestamps paginate deterministically."""
    _login(client, seeded_user)

    fixed_time = datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC)
    marker = "timestamptiebreak"

    created_ids = []
    for i in range(6):
        doc = Document(
            document_id=uuid.uuid4(),
            title=f"{marker} Doc {i}",
            program="BSCS",
            source_type="slm",
            file_path=f"/tmp/tie_{i}.pdf",
            uploaded_by=seeded_user.user_id,
        )
        db_session.add(doc)
        db_session.flush()

        matrix = MonitoringMatrix(
            document_id=doc.document_id,
            program="BSCS",
            faculty_name=f"Faculty {i}",
            evaluation_status="COMPLETED",
            synthesized_score=80.0,
            last_updated=fixed_time,
        )
        db_session.add(matrix)
        db_session.flush()
        created_ids.append(str(matrix.matrix_id))

    db_session.commit()

    # Query page 1 and page 2 with page_size=3
    res_p1 = client.get(
        f"/api/v1/evaluations/matrix?search={marker}&page=1&page_size=3"
    )
    assert res_p1.status_code == 200
    p1_items = res_p1.json()["items"]
    assert len(p1_items) == 3

    res_p2 = client.get(
        f"/api/v1/evaluations/matrix?search={marker}&page=2&page_size=3"
    )
    assert res_p2.status_code == 200
    p2_items = res_p2.json()["items"]
    assert len(p2_items) == 3

    p1_matrix_ids = [item["matrix_id"] for item in p1_items]
    p2_matrix_ids = [item["matrix_id"] for item in p2_items]

    # Verify disjointness and deterministic membership
    assert set(p1_matrix_ids).isdisjoint(set(p2_matrix_ids))
    assert len(p1_matrix_ids + p2_matrix_ids) == 6
    assert set(p1_matrix_ids + p2_matrix_ids) == set(created_ids)

    # Submitting the request again yields the exact same ordering
    res_p1_repeat = client.get(
        f"/api/v1/evaluations/matrix?search={marker}&page=1&page_size=3"
    )
    assert [
        item["matrix_id"] for item in res_p1_repeat.json()["items"]
    ] == p1_matrix_ids
