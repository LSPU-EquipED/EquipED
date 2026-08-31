"""Registration and OTP verification coverage."""

from server.modules.auth.models import AccountStatus, PendingRegistration, User


def test_registration_verifies_otp_before_creating_user(
    client, db_session, monkeypatch
):
    sent = {}

    def capture_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)
    response = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "New Faculty",
            "email": "new.faculty@lspu.edu.ph",
            "password": "secure-password",
            "faculty_id": "FAC-100",
            "department": "College of Computer Studies",
            "program": "BSCS",
        },
    )
    assert response.status_code == 202
    assert (
        db_session.query(User).filter_by(email="new.faculty@lspu.edu.ph").first()
        is None
    )
    assert db_session.query(PendingRegistration).count() == 1

    verify = client.post(
        f"/api/v1/auth/registrations/{response.json()['registration_token']}/verify",
        json={"otp": sent["otp"]},
    )
    assert verify.status_code == 200
    user = db_session.query(User).filter_by(email="new.faculty@lspu.edu.ph").one()
    assert user.account_status == AccountStatus.PENDING
    assert user.is_active is False


def test_registration_rejects_non_lspu_email(client):
    response = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "External User",
            "email": "external@example.com",
            "password": "secure-password",
            "faculty_id": "FAC-101",
            "department": "Office",
            "program": "BSCS",
        },
    )
    assert response.status_code == 422
