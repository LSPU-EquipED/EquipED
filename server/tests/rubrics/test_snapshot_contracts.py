"""Tests for snapshot contracts, serialization, hashing, and verifier."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from typing import Any

import pytest
from pydantic import ValidationError
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)
from server.modules.rubrics.manifests import get_agent_manifest
from server.modules.rubrics.repository import validate_form_definition
from server.modules.rubrics.snapshot_contracts import (
    EvaluationFormSnapshotPayload,
    SnapshotIntegrityError,
    build_evaluation_form_snapshot,
    compute_snapshot_hash,
    serialize_snapshot_payload,
    verify_evaluation_form_snapshot,
)


def _sample_criterion(
    *,
    criterion_id: uuid.UUID | None = None,
    code: str = "CRIT-01",
    title: str = "Sample Criterion",
    description: str = "Sample description for testing.",
    scoring_rule: str | None = "Standard scoring rule.",
    display_order: int = 0,
    strategy_config: Any = None,
) -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=criterion_id or uuid.uuid4(),
        criterion_code=code,
        title=title,
        description=description,
        scoring_rule=scoring_rule,
        display_order=display_order,
        strategy_config=strategy_config
        or LlmRubricGuidanceConfig(guidance="Evaluate content quality."),
    )


def _sample_domain(
    *,
    domain_id: uuid.UUID | None = None,
    code: str = "DOM-01",
    title: str = "Sample Domain",
    display_order: int = 0,
    criteria: tuple[CriterionDefinition, ...] | list[CriterionDefinition] | None = None,
) -> DomainDefinition:
    return DomainDefinition(
        rubric_domain_id=domain_id or uuid.uuid4(),
        code=code,
        title=title,
        display_order=display_order,
        criteria=criteria or (_sample_criterion(),),
    )


def _sample_form(
    *,
    set_id: uuid.UUID | None = None,
    agent_id: str = "sme",
    name: str = "SME Evaluation Form",
    version_number: int = 1,
    adapter_key: str = "sme",
    adapter_version: int = 1,
    domains: tuple[DomainDefinition, ...] | list[DomainDefinition] | None = None,
) -> FormDefinition:
    return FormDefinition(
        rubric_set_id=set_id or uuid.uuid4(),
        agent_id=agent_id,
        name=name,
        version_number=version_number,
        adapter_key=adapter_key,
        adapter_version=adapter_version,
        domains=domains or (_sample_domain(),),
    )


# ---------------------------------------------------------------------------
# 1. Deterministic Key Order and Unicode Exact UTF-8 Tests
# ---------------------------------------------------------------------------


def test_deterministic_key_order_and_utf8():
    eval_id = uuid.uuid4()
    set_id = uuid.uuid4()
    crit1 = _sample_criterion(
        code="CRIT-01",
        title="Pamantayan — Kalidad ng Nilalaman (日本語 / Tagalog)",
        description="Pagsusuri ng nilalaman na may kakaibang titik: ñ, é, ü, 🚀",
        scoring_rule="Rule with quotes \" and special chars <>&'/",
        display_order=0,
    )
    dom1 = _sample_domain(code="DOM-01", title="Saklaw", criteria=(crit1,))
    form = _sample_form(
        set_id=set_id,
        agent_id="sme",
        name="Pagsusulit ng Rubric Form",
        domains=(dom1,),
    )

    payload = EvaluationFormSnapshotPayload(
        evaluation_id=eval_id,
        rubric_set_id=set_id,
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        form=form,
    )

    serialized = serialize_snapshot_payload(payload)
    assert isinstance(serialized, bytes)

    # Must contain exact UTF-8 bytes without \uXXXX escaping
    decoded_str = serialized.decode("utf-8")
    assert "Pamantayan — Kalidad ng Nilalaman (日本語 / Tagalog)" in decoded_str
    assert "ñ, é, ü, 🚀" in decoded_str
    assert "\\u" not in decoded_str

    # Must have sorted keys and no space separators
    expected_compact = json.dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert serialized == expected_compact

    # SHA-256 computation is deterministic
    computed_hash = compute_snapshot_hash(payload)
    assert computed_hash == hashlib.sha256(serialized).hexdigest()
    assert len(computed_hash) == 64
    assert computed_hash == computed_hash.lower()


# ---------------------------------------------------------------------------
# 2. Builder Stability and Candidate Construction
# ---------------------------------------------------------------------------


def test_builder_output_stable_and_canonicalizes():
    eval_id = uuid.uuid4()
    set_id = uuid.uuid4()

    # Create criteria out of order
    c2 = _sample_criterion(code="B-02", display_order=1)
    c1 = _sample_criterion(code="A-01", display_order=0)

    # Create domains out of order
    d2 = _sample_domain(code="DOM-B", display_order=1, criteria=(c2, c1))
    d1 = _sample_domain(code="DOM-A", display_order=0, criteria=(c1, c2))

    non_canonical_form = _sample_form(
        set_id=set_id,
        agent_id="sme",
        domains=(d2, d1),
    )

    dto1 = build_evaluation_form_snapshot(
        evaluation_id=eval_id,
        form=non_canonical_form,
    )

    # Building again with equivalent form produces identical payload and hash
    dto2 = build_evaluation_form_snapshot(
        evaluation_id=eval_id,
        form=non_canonical_form,
    )

    assert dto1.snapshot_hash == dto2.snapshot_hash
    assert dto1.snapshot_payload == dto2.snapshot_payload
    assert dto1.evaluation_id == eval_id
    assert dto1.agent_id == "sme"
    assert dto1.rubric_set_id == set_id
    assert dto1.adapter_key == "sme"
    assert dto1.adapter_version == 1

    # In canonical form, d1 comes before d2, and c1 before c2
    assert [d.code for d in dto1.form.domains] == ["DOM-A", "DOM-B"]
    assert [c.criterion_code for c in dto1.form.domains[0].criteria] == ["A-01", "B-02"]
    assert [c.criterion_code for c in dto1.form.domains[1].criteria] == ["A-01", "B-02"]


def test_snapshot_id_excluded_from_hash():
    eval_id = uuid.uuid4()
    form = _sample_form(agent_id="sme")

    sid1 = uuid.uuid4()
    sid2 = uuid.uuid4()
    assert sid1 != sid2

    dto1 = build_evaluation_form_snapshot(eval_id, form, snapshot_id=sid1)
    dto2 = build_evaluation_form_snapshot(eval_id, form, snapshot_id=sid2)

    assert dto1.snapshot_id == sid1
    assert dto2.snapshot_id == sid2
    assert dto1.snapshot_hash == dto2.snapshot_hash
    assert dto1.snapshot_payload == dto2.snapshot_payload


# ---------------------------------------------------------------------------
# 3. Canonical Ordering Enforcement on Untrusted Payload
# ---------------------------------------------------------------------------


def test_noncanonical_domain_order_rejected_on_untrusted_payload():
    eval_id = uuid.uuid4()
    set_id = uuid.uuid4()

    d1 = _sample_domain(code="DOM-01", display_order=0)
    d2 = _sample_domain(code="DOM-02", display_order=1)

    # Form with reversed domains
    reversed_form = _sample_form(
        set_id=set_id,
        agent_id="sme",
        domains=(d2, d1),
    )

    raw_payload = {
        "evaluation_id": str(eval_id),
        "rubric_set_id": str(set_id),
        "agent_id": "sme",
        "adapter_key": "sme",
        "adapter_version": 1,
        "form": reversed_form.model_dump(mode="json"),
    }

    with pytest.raises(ValidationError, match="canonical ordering"):
        EvaluationFormSnapshotPayload.model_validate(raw_payload)

    # Verifier must also fail closed
    with pytest.raises(SnapshotIntegrityError):
        verify_evaluation_form_snapshot(
            snapshot_id=uuid.uuid4(),
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash="a" * 64,
            snapshot_payload=raw_payload,
        )


def test_noncanonical_criterion_order_rejected_on_untrusted_payload():
    eval_id = uuid.uuid4()
    set_id = uuid.uuid4()

    c1 = _sample_criterion(code="C-01", display_order=0)
    c2 = _sample_criterion(code="C-02", display_order=1)

    # Domain with reversed criteria
    dom = _sample_domain(code="DOM-01", display_order=0, criteria=(c2, c1))
    form = _sample_form(set_id=set_id, agent_id="sme", domains=(dom,))

    raw_payload = {
        "evaluation_id": str(eval_id),
        "rubric_set_id": str(set_id),
        "agent_id": "sme",
        "adapter_key": "sme",
        "adapter_version": 1,
        "form": form.model_dump(mode="json"),
    }

    with pytest.raises(ValidationError, match="canonical ordering"):
        EvaluationFormSnapshotPayload.model_validate(raw_payload)

    with pytest.raises(SnapshotIntegrityError):
        verify_evaluation_form_snapshot(
            snapshot_id=uuid.uuid4(),
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash="b" * 64,
            snapshot_payload=raw_payload,
        )


# ---------------------------------------------------------------------------
# 4. Recursive Immutability Tests
# ---------------------------------------------------------------------------


def test_recursive_immutability():
    eval_id = uuid.uuid4()
    form = _sample_form(agent_id="sme")
    dto = build_evaluation_form_snapshot(eval_id, form)

    with pytest.raises(ValidationError):
        dto.snapshot_id = uuid.uuid4()  # type: ignore[misc]

    with pytest.raises(ValidationError):
        dto.agent_id = "gad"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        dto.snapshot_payload.agent_id = "gad"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        dto.snapshot_payload.form.name = "Tampered Name"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        dto.snapshot_payload.form.domains[0].criteria[0].title = "Tampered"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 5. Unknown Fields Rejection Tests
# ---------------------------------------------------------------------------


def test_unknown_fields_rejected_at_all_layers():
    eval_id = uuid.uuid4()
    form = _sample_form(agent_id="sme")
    dto = build_evaluation_form_snapshot(eval_id, form)
    raw_payload = dto.snapshot_payload.model_dump(mode="json")

    # Extra field at payload root
    payload_with_extra = copy.deepcopy(raw_payload)
    payload_with_extra["unexpected_field"] = "malicious"
    with pytest.raises(ValidationError):
        EvaluationFormSnapshotPayload.model_validate(payload_with_extra)

    # Extra field at form layer
    payload_form_extra = copy.deepcopy(raw_payload)
    payload_form_extra["form"]["extra_form_prop"] = 123
    with pytest.raises(ValidationError):
        EvaluationFormSnapshotPayload.model_validate(payload_form_extra)

    # Extra field at strategy config layer
    payload_config_extra = copy.deepcopy(raw_payload)
    payload_config_extra["form"]["domains"][0]["criteria"][0]["strategy_config"][
        "extra_config"
    ] = "inject"
    with pytest.raises(ValidationError):
        EvaluationFormSnapshotPayload.model_validate(payload_config_extra)


# ---------------------------------------------------------------------------
# 6. Non-finite Float Configuration Rejection
# ---------------------------------------------------------------------------


def test_non_finite_config_rejected():
    with pytest.raises(ValidationError):
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=float("nan"),
            threshold_3=80.0,
            threshold_2=60.0,
        )

    with pytest.raises(ValidationError):
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=100.0,
            threshold_3=float("inf"),
            threshold_2=60.0,
        )


# ---------------------------------------------------------------------------
# 7. Duplicated Column Mismatch Tests
# ---------------------------------------------------------------------------


def test_duplicated_column_mismatches_rejected():
    eval_id = uuid.uuid4()
    set_id = uuid.uuid4()
    form = _sample_form(set_id=set_id, agent_id="sme")
    dto = build_evaluation_form_snapshot(eval_id, form)
    payload_dict = dto.snapshot_payload.model_dump(mode="json")

    # Mismatched evaluation_id
    with pytest.raises(SnapshotIntegrityError, match="evaluation_id mismatch"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=uuid.uuid4(),  # Different
            agent_id="sme",
            rubric_set_id=set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=dto.snapshot_hash,
            snapshot_payload=payload_dict,
        )

    # Mismatched agent_id
    with pytest.raises(SnapshotIntegrityError, match="agent_id mismatch"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="itso",  # Different
            rubric_set_id=set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=dto.snapshot_hash,
            snapshot_payload=payload_dict,
        )

    # Mismatched rubric_set_id
    with pytest.raises(SnapshotIntegrityError, match="rubric_set_id mismatch"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=uuid.uuid4(),  # Different
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=dto.snapshot_hash,
            snapshot_payload=payload_dict,
        )

    # Mismatched adapter_key
    with pytest.raises(SnapshotIntegrityError, match="adapter_key mismatch"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=set_id,
            adapter_key="other_adapter",  # Different
            adapter_version=1,
            snapshot_hash=dto.snapshot_hash,
            snapshot_payload=payload_dict,
        )

    # Mismatched adapter_version
    with pytest.raises(SnapshotIntegrityError, match="adapter_version mismatch"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=set_id,
            adapter_key="sme",
            adapter_version=2,  # Different
            snapshot_hash=dto.snapshot_hash,
            snapshot_payload=payload_dict,
        )


# ---------------------------------------------------------------------------
# 8. Nested Form Identity Mismatch Tests
# ---------------------------------------------------------------------------


def test_nested_form_identity_mismatch():
    eval_id = uuid.uuid4()
    set_id1 = uuid.uuid4()
    set_id2 = uuid.uuid4()

    form = _sample_form(
        set_id=set_id1,
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
    )

    # Agent mismatch
    with pytest.raises(ValidationError, match="agent_id"):
        EvaluationFormSnapshotPayload(
            evaluation_id=eval_id,
            rubric_set_id=set_id1,
            agent_id="gad",
            adapter_key="sme",
            adapter_version=1,
            form=form,
        )

    # Rubric set ID mismatch
    with pytest.raises(ValidationError, match="rubric_set_id"):
        EvaluationFormSnapshotPayload(
            evaluation_id=eval_id,
            rubric_set_id=set_id2,
            agent_id="sme",
            adapter_key="sme",
            adapter_version=1,
            form=form,
        )

    # Adapter key mismatch
    with pytest.raises(ValidationError, match="adapter_key"):
        EvaluationFormSnapshotPayload(
            evaluation_id=eval_id,
            rubric_set_id=set_id1,
            agent_id="sme",
            adapter_key="custom_sme",
            adapter_version=1,
            form=form,
        )

    # Adapter version mismatch
    with pytest.raises(ValidationError, match="adapter_version"):
        EvaluationFormSnapshotPayload(
            evaluation_id=eval_id,
            rubric_set_id=set_id1,
            agent_id="sme",
            adapter_key="sme",
            adapter_version=2,
            form=form,
        )


# ---------------------------------------------------------------------------
# 9. Malformed, Wrong-length, Uppercase Hash Tests
# ---------------------------------------------------------------------------


def test_malformed_wrong_length_uppercase_hash():
    eval_id = uuid.uuid4()
    form = _sample_form(agent_id="sme")
    dto = build_evaluation_form_snapshot(eval_id, form)
    payload_dict = dto.snapshot_payload.model_dump(mode="json")
    correct_hash = dto.snapshot_hash

    # Uppercase hash rejected
    with pytest.raises(SnapshotIntegrityError, match="snapshot_hash"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=form.rubric_set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=correct_hash.upper(),
            snapshot_payload=payload_dict,
        )

    # 63 characters (too short)
    with pytest.raises(SnapshotIntegrityError, match="snapshot_hash"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=form.rubric_set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=correct_hash[:63],
            snapshot_payload=payload_dict,
        )

    # 65 characters (too long)
    with pytest.raises(SnapshotIntegrityError, match="snapshot_hash"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=form.rubric_set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=correct_hash + "a",
            snapshot_payload=payload_dict,
        )

    # Non-hex characters
    with pytest.raises(SnapshotIntegrityError, match="snapshot_hash"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=form.rubric_set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash="z" * 64,
            snapshot_payload=payload_dict,
        )


# ---------------------------------------------------------------------------
# 10. Hash Tamper Verification Tests
# ---------------------------------------------------------------------------


def test_hash_tamper_rejected():
    eval_id = uuid.uuid4()
    form = _sample_form(agent_id="sme")
    dto = build_evaluation_form_snapshot(eval_id, form)

    # Valid DTO parses successfully through verifier
    verified_dto = verify_evaluation_form_snapshot(
        snapshot_id=dto.snapshot_id,
        evaluation_id=eval_id,
        agent_id="sme",
        rubric_set_id=form.rubric_set_id,
        adapter_key="sme",
        adapter_version=1,
        snapshot_hash=dto.snapshot_hash,
        snapshot_payload=dto.snapshot_payload.model_dump(mode="json"),
    )
    assert verified_dto == dto

    # Modifying payload content without changing hash fails verifier
    tampered_payload = dto.snapshot_payload.model_dump(mode="json")
    tampered_payload["form"]["name"] = "Tampered Form Title"

    with pytest.raises(
        SnapshotIntegrityError, match="snapshot_hash does not match recomputed"
    ):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=form.rubric_set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=dto.snapshot_hash,
            snapshot_payload=tampered_payload,
        )

    # Providing different valid hash fails verifier
    fake_hash = "0" * 64
    with pytest.raises(
        SnapshotIntegrityError, match="snapshot_hash does not match recomputed"
    ):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=form.rubric_set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=fake_hash,
            snapshot_payload=dto.snapshot_payload.model_dump(mode="json"),
        )


def test_historical_coordinator_adapter_v1_snapshot_remains_readable():
    eval_id = uuid.uuid4()
    criterion = _sample_criterion(
        code="A-05",
        strategy_config=CurriculumAlignmentConfig(
            guidance="Evaluate syllabus objective alignment."
        ),
    )
    form = _sample_form(
        agent_id="coordinator",
        name="Historical Coordinator Form",
        adapter_key="coordinator",
        adapter_version=1,
        domains=(_sample_domain(criteria=(criterion,)),),
    )
    dto = build_evaluation_form_snapshot(eval_id, form)

    verified = verify_evaluation_form_snapshot(
        snapshot_id=dto.snapshot_id,
        evaluation_id=eval_id,
        agent_id="coordinator",
        rubric_set_id=form.rubric_set_id,
        adapter_key="coordinator",
        adapter_version=1,
        snapshot_hash=dto.snapshot_hash,
        snapshot_payload=dto.snapshot_payload.model_dump(mode="json"),
    )

    assert verified == dto
    # Central validator resolves the form's own adapter_version (v1 here),
    # so a historical v1 form stays valid even though current is v2.
    assert validate_form_definition(form).is_valid


# ---------------------------------------------------------------------------
# 11. Unknown Agent and Manifest Incompatibility Tests
# ---------------------------------------------------------------------------


def test_unknown_agent_rejected():
    with pytest.raises(ValueError, match="Unknown agent capability manifest"):
        get_agent_manifest("unknown_agent")

    eval_id = uuid.uuid4()
    set_id = uuid.uuid4()
    form = _sample_form(set_id=set_id, agent_id="unknown_agent")

    # Repository validation gate fails on unknown agent
    with pytest.raises(ValueError, match="Unknown agent capability manifest"):
        validate_form_definition(form)

    payload = {
        "evaluation_id": str(eval_id),
        "rubric_set_id": str(set_id),
        "agent_id": "unknown_agent",
        "adapter_key": "sme",
        "adapter_version": 1,
        "form": form.model_dump(mode="json"),
    }
    # Snapshot verifier translates to SnapshotIntegrityError
    with pytest.raises(
        SnapshotIntegrityError, match="Unknown agent capability manifest"
    ):
        verify_evaluation_form_snapshot(
            snapshot_id=uuid.uuid4(),
            evaluation_id=eval_id,
            agent_id="unknown_agent",
            rubric_set_id=set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash="a" * 64,
            snapshot_payload=payload,
        )


def test_manifest_incompatible_strategy_rejected_by_verifier():
    # ITSO manifest only supports llm_rubric_guidance
    eval_id = uuid.uuid4()
    set_id = uuid.uuid4()
    crit = _sample_criterion(
        code="IT-01",
        strategy_config=CountBandConfig(
            mode="minimum_count",
            threshold_4=10,
            threshold_3=5,
            threshold_2=2,
        ),
    )
    dom = _sample_domain(code="DOM-IT", criteria=(crit,))
    form = _sample_form(
        set_id=set_id,
        agent_id="itso",
        adapter_key="itso",
        adapter_version=1,
        domains=(dom,),
    )

    dto = build_evaluation_form_snapshot(eval_id, form)
    payload_dict = dto.snapshot_payload.model_dump(mode="json")

    with pytest.raises(
        SnapshotIntegrityError, match="failed manifest validation.*UNSUPPORTED_STRATEGY"
    ):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="itso",
            rubric_set_id=set_id,
            adapter_key="itso",
            adapter_version=1,
            snapshot_hash=dto.snapshot_hash,
            snapshot_payload=payload_dict,
        )


# ---------------------------------------------------------------------------
# 12. Criterion Code Extraction Tests
# ---------------------------------------------------------------------------


def test_criterion_code_extraction_exact():
    eval_id = uuid.uuid4()
    c1 = _sample_criterion(code="CRIT-01", display_order=0)
    c2 = _sample_criterion(code="CRIT-02", display_order=1)
    c3 = _sample_criterion(code="CRIT-03", display_order=0)
    d1 = _sample_domain(code="DOM-01", display_order=0, criteria=(c1, c2))
    d2 = _sample_domain(code="DOM-02", display_order=1, criteria=(c3,))
    form = _sample_form(agent_id="sme", domains=(d1, d2))

    dto = build_evaluation_form_snapshot(eval_id, form)

    expected_codes = ("CRIT-01", "CRIT-02", "CRIT-03")
    expected_set = frozenset({"CRIT-01", "CRIT-02", "CRIT-03"})

    assert dto.criterion_codes == expected_codes
    assert dto.criterion_codes_set == expected_set
    assert dto.payload.criterion_codes == expected_codes
    assert dto.payload.criterion_codes_set == expected_set


# ---------------------------------------------------------------------------
# 13. Privacy & Non-leakage in Exception Messages
# ---------------------------------------------------------------------------


def test_verifier_does_not_leak_untrusted_payload_content():
    sensitive_text = "SUPER_SECRET_INTERNAL_PROMPT_TEXT_DO_NOT_LEAK"
    raw_payload = {
        "evaluation_id": "not-a-uuid",
        "secret": sensitive_text,
    }
    with pytest.raises(SnapshotIntegrityError) as exc_info:
        verify_evaluation_form_snapshot(
            snapshot_id=uuid.uuid4(),
            evaluation_id=uuid.uuid4(),
            agent_id="sme",
            rubric_set_id=uuid.uuid4(),
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash="a" * 64,
            snapshot_payload=raw_payload,
        )

    assert sensitive_text not in str(exc_info.value)


def test_verifier_does_not_swallow_programming_defects(monkeypatch):
    """Ensure internal errors are not reclassified as snapshot corruptions."""
    eval_id = uuid.uuid4()
    form = _sample_form(agent_id="sme")
    dto = build_evaluation_form_snapshot(eval_id, form)

    def _buggy_validate(*args, **kwargs):
        raise RuntimeError("Unexpected internal crash / defect")

    monkeypatch.setattr(
        "server.modules.rubrics.snapshot_contracts.validate_form",
        _buggy_validate,
    )

    with pytest.raises(RuntimeError, match="Unexpected internal crash / defect"):
        verify_evaluation_form_snapshot(
            snapshot_id=dto.snapshot_id,
            evaluation_id=eval_id,
            agent_id="sme",
            rubric_set_id=form.rubric_set_id,
            adapter_key="sme",
            adapter_version=1,
            snapshot_hash=dto.snapshot_hash,
            snapshot_payload=dto.snapshot_payload.model_dump(mode="json"),
        )
