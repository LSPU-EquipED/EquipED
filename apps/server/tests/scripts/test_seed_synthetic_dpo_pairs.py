"""Tests for synthetic seeder safety guards and run-id scoped operations."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from server.core.config import Settings
from server.modules.auth.models import User, UserRole
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.scripts import seed_synthetic_dpo_pairs as seeder
from server.scripts.seed_rubrics import seed_rubric_set
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_JSON = ROOT / "data" / "rubrics" / "rubrics.json"


@pytest.fixture()
def seeded_sme_rubric(db_session: Session):
    """Seed active SME rubric and convert to valid llm_rubric_guidance if needed."""
    from server.modules.rubrics.models import RubricCriterion, RubricDomain

    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    sme_payload = next(s for s in payload["rubric_sets"] if s["agent_id"] == "sme")
    rubric_set = seed_rubric_set(db_session, sme_payload)
    # Ensure criteria have strategy_config set as valid llm_rubric_guidance in test DB
    criteria = (
        db_session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
        .all()
    )
    for c in criteria:
        c.scoring_strategy = "llm_rubric_guidance"
        c.strategy_config = {
            "strategy": "llm_rubric_guidance",
            "guidance": "Test guidance for criterion.",
            "level_descriptors": [
                {"score": 1, "descriptor": "Beginning"},
                {"score": 2, "descriptor": "Developing"},
                {"score": 3, "descriptor": "Competent"},
                {"score": 4, "descriptor": "Accomplished"},
            ],
        }
    db_session.commit()
    return rubric_set


def test_validate_environment_allows_dev_test_local():
    assert seeder.validate_environment("development") == "development"
    assert seeder.validate_environment("test") == "test"
    assert seeder.validate_environment("local") == "local"
    assert seeder.validate_environment("DEVELOPMENT") == "development"
    assert seeder.validate_environment(" Local ") == "local"


def test_validate_environment_rejects_production():
    with pytest.raises(PermissionError, match="restricted"):
        seeder.validate_environment("production")
    with pytest.raises(PermissionError, match="restricted"):
        seeder.validate_environment("prod")
    with pytest.raises(PermissionError, match="restricted"):
        seeder.validate_environment("PRODUCTION")


def test_validate_environment_rejects_other_or_empty():
    with pytest.raises(PermissionError, match="restricted"):
        seeder.validate_environment("")
    with pytest.raises(PermissionError, match="restricted"):
        seeder.validate_environment("staging")
    with pytest.raises(PermissionError, match="restricted"):
        seeder.validate_environment("preview")


def test_validate_database_target_allows_local_and_sqlite():
    assert seeder.is_local_or_test_target("sqlite:///:memory:") is True
    assert seeder.is_local_or_test_target("sqlite:///some/path/db.sqlite3") is True
    assert (
        seeder.is_local_or_test_target("postgresql://user:pass@localhost:5432/db")
        is True
    )
    assert (
        seeder.is_local_or_test_target("postgresql://user:pass@127.0.0.1:5432/db")
        is True
    )
    assert (
        seeder.is_local_or_test_target("postgresql://user:pass@testserver:5432/db")
        is True
    )
    assert (
        seeder.is_local_or_test_target("postgresql://user:pass@db.local:5432/db")
        is True
    )

    # Remote targets are not local
    neon_url = "postgresql+psycopg://user:pass@ep-cool-fog-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
    prod_url = "postgresql+psycopg://user:pass@prod-db.internal:5432/prod"
    assert seeder.is_local_or_test_target(neon_url) is False
    assert seeder.is_local_or_test_target(prod_url) is False

    # Validation on local targets returns fingerprint without needing allowlist
    sqlite_fp = seeder.validate_database_target("sqlite:///test.db")
    assert sqlite_fp == seeder.compute_target_fingerprint("sqlite:///test.db")

    local_pg_url = "postgresql+psycopg://user:pass@localhost:5432/testdb"
    assert seeder.validate_database_target(
        local_pg_url
    ) == seeder.compute_target_fingerprint(local_pg_url)


@pytest.mark.parametrize(
    "query",
    [
        "host=remote-production-host",
        "HOSTADDR=remote-production-host&host=localhost",
        "%68ost=remote-production-host&host=localhost",
        "host=localhost&host=remote-production-host",
        "servicefile=prod.conf",
        "database=production",
    ],
)
def test_routing_query_overrides_never_pass_local_guard(query):
    url = f"postgresql://user:pass@localhost:5432/test?{query}"
    assert seeder.is_local_or_test_target(url) is False
    with pytest.raises(PermissionError, match="routing query override"):
        seeder.validate_database_target(url)


def test_sslmode_query_remains_valid_and_remote_fingerprint_is_required():
    url = "postgresql://user:pass@neon.example/db?sslmode=require"
    fingerprint = seeder.compute_target_fingerprint(url)
    assert seeder.validate_database_target(url, {fingerprint}) == fingerprint


def test_routing_query_cannot_bypass_remote_fingerprint():
    url = "postgresql://user:pass@localhost:5432/db?%68ost=remote.example"
    with pytest.raises(PermissionError, match="routing query override"):
        seeder.validate_database_target(url, {seeder.compute_target_fingerprint(url)})


def test_validate_database_target_rejects_empty():
    with pytest.raises(PermissionError, match="empty or not configured"):
        seeder.validate_database_target("")
    with pytest.raises(PermissionError, match="empty or not configured"):
        seeder.validate_database_target(None, allowed_fingerprints=frozenset())


def test_validate_database_target_remote_without_fingerprint_rejected():
    neon_url = "postgresql+psycopg://user:pass@ep-cool-fog-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
    with pytest.raises(PermissionError, match="refused unsafe database target"):
        seeder.validate_database_target(neon_url, allowed_fingerprints=frozenset())


def test_validate_database_target_remote_with_matching_fingerprint_allowed(monkeypatch):
    neon_url = "postgresql+psycopg://user:pass@ep-cool-fog-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
    expected_fp = seeder.compute_target_fingerprint(neon_url)

    # Allowed via explicit parameter
    fp = seeder.validate_database_target(neon_url, allowed_fingerprints={expected_fp})
    assert fp == expected_fp

    # Allowed via environment variable
    monkeypatch.setenv(
        "SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS", f"foo, {expected_fp}, bar"
    )
    fp_env = seeder.validate_database_target(neon_url)
    assert fp_env == expected_fp


def test_generate_verifies_sha256_payload_integrity(
    db_session: Session, seeded_sme_rubric
):
    """Test that prompt_sha256 and response_sha256 match stored UTF-8 payloads."""
    import hashlib

    del seeded_sme_rubric
    run_id = uuid.uuid4()
    _run_id, eval_ids = seeder.generate(db_session, count=1, run_id=run_id)

    ag = (
        db_session.query(AgentGeneration)
        .filter(AgentGeneration.evaluation_id.in_(eval_ids))
        .one()
    )
    expected_prompt_sha = hashlib.sha256(ag.prompt_text.encode("utf-8")).hexdigest()
    expected_response_sha = hashlib.sha256(ag.response_text.encode("utf-8")).hexdigest()

    assert ag.prompt_sha256 == expected_prompt_sha
    assert ag.response_sha256 == expected_response_sha


def test_generate_rejects_count_zero_or_negative(db_session: Session):
    """Test that generate() rejects count <= 0 before mutating anything."""
    # Ensure no users exist yet or check user count
    initial_user_count = db_session.query(User).count()

    with pytest.raises(ValueError, match="positive integer"):
        seeder.generate(db_session, count=0)

    with pytest.raises(ValueError, match="positive integer"):
        seeder.generate(db_session, count=-1)

    assert db_session.query(User).count() == initial_user_count


def test_generate_and_cleanup_run_id_isolated(db_session: Session, seeded_sme_rubric):
    """Test generating with a specific run-id and cleaning up only that run-id."""
    del seeded_sme_rubric
    run_1 = uuid.uuid4()
    run_2 = uuid.uuid4()

    # Generate run 1 with 2 items
    gen_run_1, eval_ids_1 = seeder.generate(db_session, count=2, run_id=run_1)
    assert gen_run_1 == run_1
    assert len(eval_ids_1) == 2

    # Generate run 2 with 2 items
    gen_run_2, eval_ids_2 = seeder.generate(db_session, count=2, run_id=run_2)
    assert gen_run_2 == run_2
    assert len(eval_ids_2) == 2

    # Verify rows exist for both runs
    assert (
        db_session.query(Document)
        .filter(Document.title.like(f"%[run:{run_1}]%"))
        .count()
        == 2
    )
    assert (
        db_session.query(Document)
        .filter(Document.title.like(f"%[run:{run_2}]%"))
        .count()
        == 2
    )
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_1))
        .count()
        == 2
    )
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_2))
        .count()
        == 2
    )

    # Cleanup ONLY run 1
    found, left = seeder.cleanup(db_session, run_id=run_1)
    assert found == 2
    assert left == 2

    # For run 1: PreferenceLog, AgentGeneration, AgentResult are gone
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_1))
        .count()
        == 0
    )
    assert (
        db_session.query(AgentGeneration)
        .filter(AgentGeneration.evaluation_id.in_(eval_ids_1))
        .count()
        == 0
    )
    assert (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id.in_(eval_ids_1))
        .count()
        == 0
    )

    # For run 1: Documents and Jobs remain in place (immutable snapshots preserved)
    assert (
        db_session.query(Document)
        .filter(Document.title.like(f"%[run:{run_1}]%"))
        .count()
        == 2
    )
    assert (
        db_session.query(EvaluationJob)
        .filter(EvaluationJob.evaluation_id.in_(eval_ids_1))
        .count()
        == 2
    )

    # Run 2 remains completely untouched!
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_2))
        .count()
        == 2
    )
    assert (
        db_session.query(AgentGeneration)
        .filter(AgentGeneration.evaluation_id.in_(eval_ids_2))
        .count()
        == 2
    )
    assert (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id.in_(eval_ids_2))
        .count()
        == 2
    )


def test_cleanup_ambiguity_doc_job_mismatch_fails_closed(
    db_session: Session, seeded_sme_rubric
):
    """Cleanup rolls back if candidate document has no matching evaluation job."""
    del seeded_sme_rubric
    run_id = uuid.uuid4()
    seeder.generate(db_session, count=1, run_id=run_id)

    # Create an orphaned synthetic document with the same run-id
    user = db_session.query(User).filter_by(email=seeder.SYNTHETIC_USER_EMAIL).one()
    orphan_doc = Document(
        document_id=uuid.uuid4(),
        title=seeder._format_title(run_id, 99),
        source_type="slm",
        file_path="uploads/orphan.pdf",
        uploaded_by=user.user_id,
        processing_status="PROCESSED",
    )
    db_session.add(orphan_doc)
    db_session.commit()

    with pytest.raises(RuntimeError, match="Ambiguity detected"):
        seeder.cleanup(db_session, run_id=run_id)

    # Verify rollback: original preference log and generation still exist
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_id))
        .count()
        == 1
    )


def test_cleanup_ambiguity_model_mismatch_fails_closed(
    db_session: Session, seeded_sme_rubric
):
    """Cleanup rolls back if AgentResult uses a non-synthetic model."""
    del seeded_sme_rubric
    run_id = uuid.uuid4()
    _run_id, eval_ids = seeder.generate(db_session, count=1, run_id=run_id)

    # Tamper with the model name on AgentResult
    ar = (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id.in_(eval_ids))
        .one()
    )
    ar.model_name = "real-production-model"
    db_session.commit()

    with pytest.raises(RuntimeError, match="Ambiguity detected in AgentResult"):
        seeder.cleanup(db_session, run_id=run_id)

    # Verify rollback: PreferenceLog was not deleted
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_id))
        .count()
        == 1
    )


def test_cleanup_ambiguity_agent_mismatch_fails_closed(
    db_session: Session, seeded_sme_rubric
):
    """Cleanup rolls back if AgentGeneration agent_id does not match AGENT_ID."""
    del seeded_sme_rubric
    run_id = uuid.uuid4()
    _run_id, eval_ids = seeder.generate(db_session, count=1, run_id=run_id)

    # Tamper with agent_id on AgentGeneration
    ag = (
        db_session.query(AgentGeneration)
        .filter(AgentGeneration.evaluation_id.in_(eval_ids))
        .one()
    )
    ag.agent_id = "coord"
    db_session.commit()

    with pytest.raises(RuntimeError, match="Ambiguity detected in AgentGeneration"):
        seeder.cleanup(db_session, run_id=run_id)

    # Verify rollback
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_id))
        .count()
        == 1
    )


def test_cleanup_ambiguity_user_mismatch_fails_closed(
    db_session: Session, seeded_sme_rubric
):
    """Cleanup rolls back if PreferenceLog was edited by a different user."""
    del seeded_sme_rubric
    run_id = uuid.uuid4()
    _run_id, eval_ids = seeder.generate(db_session, count=1, run_id=run_id)

    # Create another user and assign the PreferenceLog to them
    other_user = User(
        user_id=uuid.uuid4(),
        email="faculty@school.edu",
        name="Real Faculty",
        role=UserRole.FACULTY,
        password_hash="hash",
    )
    db_session.add(other_user)
    db_session.flush()

    pl = (
        db_session.query(PreferenceLog)
        .filter(PreferenceLog.evaluation_id.in_(eval_ids))
        .one()
    )
    pl.user_id = other_user.user_id
    db_session.commit()

    with pytest.raises(RuntimeError, match="Ambiguity detected in PreferenceLog"):
        seeder.cleanup(db_session, run_id=run_id)

    # Preference log remains
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_id))
        .count()
        == 1
    )


def test_cleanup_ambiguity_foreign_log_with_same_note_fails_closed(
    db_session: Session, seeded_sme_rubric
):
    """Cleanup rolls back if a foreign preference log uses the same run_id note."""
    del seeded_sme_rubric
    run_id = uuid.uuid4()
    _run_id, eval_ids = seeder.generate(db_session, count=1, run_id=run_id)

    # Create a separate, real evaluation job and attach a log with this
    # synthetic run's note
    real_doc = Document(
        document_id=uuid.uuid4(),
        title="Real Curriculum Syllabus",
        source_type="slm",
        file_path="uploads/real.pdf",
        uploaded_by=db_session.query(User)
        .filter_by(email=seeder.SYNTHETIC_USER_EMAIL)
        .one()
        .user_id,
        processing_status="PROCESSED",
    )
    db_session.add(real_doc)
    real_job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=real_doc.document_id,
        status="COMPLETED",
        target_agent="sme",
    )
    db_session.add(real_job)
    db_session.flush()

    foreign_log = PreferenceLog(
        evaluation_id=real_job.evaluation_id,
        user_id=db_session.query(User)
        .filter_by(email=seeder.SYNTHETIC_USER_EMAIL)
        .one()
        .user_id,
        agent_name="sme",
        criterion_id="SME-01",
        action="EDIT",
        notes=seeder._format_note(run_id),
    )
    db_session.add(foreign_log)
    db_session.commit()

    with pytest.raises(RuntimeError, match="Ambiguity detected"):
        seeder.cleanup(db_session, run_id=run_id)

    # All logs preserved
    assert (
        db_session.query(PreferenceLog)
        .filter_by(notes=seeder._format_note(run_id))
        .count()
        == 2
    )


def test_cli_requires_confirmation_for_seeding(monkeypatch):
    test_settings = Settings(
        environment="development", database_url="sqlite:///test.db"
    )
    with patch(
        "server.scripts.seed_synthetic_dpo_pairs.get_settings",
        return_value=test_settings,
    ):
        monkeypatch.setattr(sys, "argv", ["seed_synthetic_dpo_pairs", "--count", "5"])
        with pytest.raises(
            PermissionError,
            match="Explicit acknowledgement required for seeding writes",
        ):
            seeder.main()


def test_cli_requires_target_confirmation_for_seeding(monkeypatch):
    test_settings = Settings(
        environment="development", database_url="sqlite:///test.db"
    )
    with patch(
        "server.scripts.seed_synthetic_dpo_pairs.get_settings",
        return_value=test_settings,
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            ["seed_synthetic_dpo_pairs", "--count", "5", "--confirm", "SEED"],
        )
        with pytest.raises(
            PermissionError,
            match="Explicit acknowledgement required for database target",
        ):
            seeder.main()


def test_cli_requires_confirmation_for_cleanup(monkeypatch):
    test_settings = Settings(
        environment="development", database_url="sqlite:///test.db"
    )
    run_id = str(uuid.uuid4())
    with patch(
        "server.scripts.seed_synthetic_dpo_pairs.get_settings",
        return_value=test_settings,
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            ["seed_synthetic_dpo_pairs", "--cleanup", "--run-id", run_id],
        )
        with pytest.raises(
            PermissionError, match="Explicit acknowledgement required for cleanup"
        ):
            seeder.main()


def test_cli_requires_run_id_for_cleanup(monkeypatch):
    test_settings = Settings(
        environment="development", database_url="sqlite:///test.db"
    )
    with patch(
        "server.scripts.seed_synthetic_dpo_pairs.get_settings",
        return_value=test_settings,
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            ["seed_synthetic_dpo_pairs", "--cleanup", "--confirm", "CLEANUP"],
        )
        with pytest.raises(ValueError, match="Cleanup requires an exact --run-id"):
            seeder.main()


def test_cli_rejects_count_zero_or_negative(monkeypatch):
    test_settings = Settings(
        environment="development", database_url="sqlite:///test.db"
    )
    with patch(
        "server.scripts.seed_synthetic_dpo_pairs.get_settings",
        return_value=test_settings,
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "seed_synthetic_dpo_pairs",
                "--count",
                "0",
                "--confirm",
                "SEED",
                "--confirm-target",
                "LOCAL",
            ],
        )
        with pytest.raises(ValueError, match="positive integer"):
            seeder.main()

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "seed_synthetic_dpo_pairs",
                "--count",
                "-5",
                "--confirm",
                "SEED",
                "--confirm-target",
                "LOCAL",
            ],
        )
        with pytest.raises(ValueError, match="positive integer"):
            seeder.main()


def test_cli_rejects_production_environment(monkeypatch):
    test_settings = Settings(environment="production")
    with patch(
        "server.scripts.seed_synthetic_dpo_pairs.get_settings",
        return_value=test_settings,
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            ["seed_synthetic_dpo_pairs", "--confirm", "SEED"],
        )
        with pytest.raises(PermissionError, match="restricted"):
            seeder.main()


def test_cli_requires_matching_fingerprint_for_remote_db(monkeypatch):
    neon_url = "postgresql+psycopg://user:pass@ep-cool-fog-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
    expected_fp = seeder.compute_target_fingerprint(neon_url)

    # 1. Without allowlist, fail closed immediately
    test_settings = Settings(environment="development", database_url=neon_url)
    with patch(
        "server.scripts.seed_synthetic_dpo_pairs.get_settings",
        return_value=test_settings,
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "seed_synthetic_dpo_pairs",
                "--count",
                "5",
                "--confirm",
                "SEED",
                "--confirm-target",
                expected_fp,
            ],
        )
        with pytest.raises(PermissionError, match="refused unsafe database target"):
            seeder.main()

    # 2. With allowlist configured, wrong --confirm-target fails
    monkeypatch.setenv("SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS", expected_fp)
    with patch(
        "server.scripts.seed_synthetic_dpo_pairs.get_settings",
        return_value=test_settings,
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "seed_synthetic_dpo_pairs",
                "--count",
                "5",
                "--confirm",
                "SEED",
                "--confirm-target",
                "WRONG_FP",
            ],
        )
        with pytest.raises(
            PermissionError,
            match="Explicit acknowledgement required for database target",
        ):
            seeder.main()
