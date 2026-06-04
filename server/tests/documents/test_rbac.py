"""Documents upload RBAC tests — role-based source type restrictions."""

from __future__ import annotations

from fastapi.testclient import TestClient
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import create_user


def test_faculty_cannot_upload_syllabus(
    client: TestClient,
    db_session,
) -> None:
    """Verify that faculty users cannot upload syllabus documents."""
    faculty = create_user(
        db_session,
        name="Faculty RBAC Test",
        email="faculty-rbac@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    login = client.post(
        '/api/v1/auth/login',
        json={'email': faculty.email, 'password': 'password123'},
    )
    assert login.status_code == 200

    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('syllabus.pdf', b'%PDF-1.4\n%syllabus', 'application/pdf')},
        data={
            'source_type': 'syllabus',
            'title': 'Test Syllabus',
        },
    )
    assert response.status_code == 403
    assert 'Only administrators' in response.json()['detail']


def test_faculty_cannot_upload_curriculum(
    client: TestClient,
    db_session,
) -> None:
    """Verify that faculty users cannot upload curriculum documents."""
    faculty = create_user(
        db_session,
        name="Faculty Curriculum Test",
        email="faculty-curr@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    login = client.post(
        '/api/v1/auth/login',
        json={'email': faculty.email, 'password': 'password123'},
    )
    assert login.status_code == 200

    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('curriculum.pdf', b'%PDF-1.4\n%curriculum', 'application/pdf')},
        data={
            'source_type': 'curriculum',
            'title': 'Test Curriculum',
        },
    )
    assert response.status_code == 403


def test_faculty_cannot_upload_rubric(
    client: TestClient,
    db_session,
) -> None:
    """Verify that faculty users cannot upload rubric documents."""
    faculty = create_user(
        db_session,
        name="Faculty Rubric Test",
        email="faculty-rubric@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    login = client.post(
        '/api/v1/auth/login',
        json={'email': faculty.email, 'password': 'password123'},
    )
    assert login.status_code == 200

    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('rubric.pdf', b'%PDF-1.4\n%rubric', 'application/pdf')},
        data={
            'source_type': 'rubric_sme',
            'title': 'Test Rubric',
        },
    )
    assert response.status_code == 403


def test_admin_can_upload_syllabus(
    client: TestClient,
    db_session,
) -> None:
    """Verify that admin users can upload syllabus documents."""
    admin = create_user(
        db_session,
        name="Admin Upload Test",
        email="admin-upload@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    login = client.post(
        '/api/v1/auth/login',
        json={'email': admin.email, 'password': 'password123'},
    )
    assert login.status_code == 200

    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('syllabus.pdf', b'%PDF-1.4\n%syllabus', 'application/pdf')},
        data={
            'source_type': 'syllabus',
            'title': 'Admin Syllabus',
        },
    )
    # Should not be 403 - may be 201 or processing failure, but not forbidden
    assert response.status_code != 403


def test_faculty_can_upload_slm(
    client: TestClient,
    db_session,
) -> None:
    """Verify that faculty users can still upload SLM documents."""
    faculty = create_user(
        db_session,
        name="Faculty SLM Test",
        email="faculty-slm@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    login = client.post(
        '/api/v1/auth/login',
        json={'email': faculty.email, 'password': 'password123'},
    )
    assert login.status_code == 200

    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('slm.pdf', b'%PDF-1.4\n%slm', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Test SLM',
            'program': 'bsit',
        },
    )
    assert response.status_code == 201
