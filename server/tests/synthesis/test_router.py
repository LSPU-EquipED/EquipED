"""HTTP-level monitoring matrix filter regression coverage."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import User
from server.modules.documents.models import Document
from server.modules.synthesis.models import MonitoringMatrix


def _login(client: TestClient, user: User) -> None:
    response = client.post(
        '/api/v1/auth/login',
        json={'email': user.email, 'password': 'correct-horse-battery'},
    )
    assert response.status_code == 200


def _add_matrix(db_session, user_id, title: str, program: str) -> None:
    document = Document(
        title=title,
        program=program,
        source_type='slm',
        file_path=f'/tmp/{title}.pdf',
        uploaded_by=user_id,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(MonitoringMatrix(document_id=document.document_id, program=program))


@pytest.fixture()
def matrix_client_data(client, db_session, seeded_user):
    for title, program in (
        ('modern', 'BSInfoTech'),
        ('legacy', 'BSIT'),
        ('computer science', 'BSCS'),
        ('historical', 'BSN'),
    ):
        _add_matrix(db_session, seeded_user.user_id, title, program)
    db_session.commit()
    _login(client, seeded_user)
    return client


@pytest.mark.parametrize('program', ['BSInfoTech', 'bsit'])
def test_matrix_canonicalizes_bsit_aliases(matrix_client_data, program: str) -> None:
    response = matrix_client_data.get(f'/api/v1/evaluations/matrix?program={program}')
    assert response.status_code == 200
    assert {item['document_title'] for item in response.json()['items']} == {
        'modern', 'legacy',
    }


def test_matrix_bscs_filter(matrix_client_data) -> None:
    response = matrix_client_data.get('/api/v1/evaluations/matrix?program=BSCS')
    assert response.status_code == 200
    assert {item['document_title'] for item in response.json()['items']} == {
        'computer science',
    }


def test_matrix_rejects_unsupported_program(matrix_client_data) -> None:
    response = matrix_client_data.get('/api/v1/evaluations/matrix?program=BSEd')
    assert response.status_code == 422


def test_matrix_preserves_historical_program_rows(matrix_client_data) -> None:
    response = matrix_client_data.get('/api/v1/evaluations/matrix')
    assert response.status_code == 200
    assert 'historical' in {item['document_title'] for item in response.json()['items']}
