"""Validation tasks 5.3 and 5.4 — service-level metadata detection smoke test.

Creates real PDFs with known patterns, uploads via TestClient, and
verifies that:
- Metadata is detected and populated when patterns exist (5.3)
- Preprocessing still completes normally when no patterns match (5.4)
"""

from __future__ import annotations

import uuid
from io import BytesIO

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import User


def _make_pdf(text: str) -> bytes:
    """Create a single-page PDF containing the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), text, fontsize=11)
    buf = BytesIO()
    doc.save(buf, garbage=4, deflate=True)
    buf.seek(0)
    pdf_bytes = buf.read()
    doc.close()
    return pdf_bytes


# ── Test document with detectable metadata ──────────────────────────

_DETECTABLE_TEXT = """\
LSPU SCC
COLLEGE OF COMPUTER STUDIES

Course Syllabus: CCS 101 – Introduction to Computing
School Year 2025-2026

This course provides an overview of computing fundamentals.

Program: BSIT
"""


def test_upload_detects_metadata_when_patterns_exist(
    client: TestClient,
    seeded_user: User,
) -> None:
    """5.3 — Upload a PDF with known patterns and verify metadata is detected."""
    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"

    pdf_bytes = _make_pdf(_DETECTABLE_TEXT)

    upload_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test_detectable.pdf", pdf_bytes, "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Detection Test SLM",
            # program is required for SLM; we provide one manually
            "program": "bsit",
        },
    )

    # Precondition: upload succeeded
    assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
    body = upload_resp.json()

    # Processing must have completed
    assert body["processing_status"] == "PROCESSED", f"Preprocessing failed: {body}"

    # Metadata detection assertions (DocumentUploadResponse fields)
    assert body["academic_year"] == "2025-2026", \
        f"Expected 2025-2026, got {body['academic_year']}"
    assert body["course_code"] == "CCS 101", \
        f"Expected CCS 101, got {body['course_code']}"

    # Verify via GET — DocumentResponse includes program
    doc_id = body["document_id"]
    get_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["academic_year"] == "2025-2026"
    assert get_body["course_code"] == "CCS 101"
    assert get_body["program"] == "bsit"


def test_upload_with_manual_program_not_overridden(
    client: TestClient,
    seeded_user: User,
) -> None:
    """5.3 variant — Manual program must not be overwritten by auto-detection."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )
    assert login_resp.status_code == 200

    pdf_bytes = _make_pdf(_DETECTABLE_TEXT)

    upload_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test_manual_program.pdf", pdf_bytes, "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Manual Program Test",
            "program": "bscs",  # Manual value — must NOT be overridden to BSIT
        },
    )

    assert upload_resp.status_code == 201
    body = upload_resp.json()
    assert body["processing_status"] == "PROCESSED"

    # academic_year and course_code should still be detected from text
    assert body["academic_year"] == "2025-2026"
    assert body["course_code"] == "CCS 101"

    # Verify via GET — DocumentResponse includes program
    doc_id = body["document_id"]
    get_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["program"] == "bscs", \
        f"Manual program was overridden: {get_body['program']}"
    assert get_body["academic_year"] == "2025-2026"
    assert get_body["course_code"] == "CCS 101"


# ── Test document with NO detectable metadata ───────────────────────

_NOISE_TEXT = """\
The quick brown fox jumps over the lazy dog.
This document contains no program codes, academic years, or course codes.
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
Some random numbers: 42, 100, 999. But no recognizable patterns.
All references use generic identifiers like RFC-2119 and ISO-9001.
"""


def test_upload_without_metadata_still_completes(
    client: TestClient,
    seeded_user: User,
) -> None:
    """5.4 — Upload a PDF with no matching patterns; preprocessing completes normally."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )
    assert login_resp.status_code == 200

    pdf_bytes = _make_pdf(_NOISE_TEXT)

    upload_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test_no_metadata.pdf", pdf_bytes, "application/pdf")},
        data={
            "source_type": "slm",
            "title": "No Metadata SLM",
            "program": "bsit",  # Manual program
        },
    )

    assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
    body = upload_resp.json()

    # Processing must complete normally even without patterns
    assert body["processing_status"] == "PROCESSED", \
        f"Preprocessing failed: {body}"

    # Metadata fields should be None (no patterns matched)
    assert body["academic_year"] is None, \
        f"Expected None academic_year, got {body['academic_year']}"
    assert body["course_code"] is None, \
        f"Expected None course_code, got {body['course_code']}"

    # Verify via GET — DocumentResponse includes program
    doc_id = body["document_id"]
    get_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["academic_year"] is None
    assert get_body["course_code"] is None
    assert get_body["program"] == "bsit"


__all__: list[str] = []
