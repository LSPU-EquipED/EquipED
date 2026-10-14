"""Frozen characterization of the SME harness snapshot serialization."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from equiped_harness.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
)
from equiped_harness.snapshot_contracts import (
    build_evaluation_form_snapshot,
    serialize_snapshot_payload,
)

FIXTURE = Path(__file__).parent / "fixtures" / "harness_snapshot_golden.json"


def test_sme_harness_snapshot_matches_frozen_golden() -> None:
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))
    form_input = golden["form"]
    domain_input = form_input["domains"][0]
    criteria = tuple(
        CriterionDefinition(
            rubric_criterion_id=uuid.UUID(item["rubric_criterion_id"]),
            criterion_code=item["criterion_code"],
            title=item["title"],
            description=item["description"],
            scoring_rule=item["scoring_rule"],
            display_order=item["display_order"],
            strategy_config=LlmRubricGuidanceConfig(**item["strategy_config"]),
        )
        for item in domain_input["criteria"]
    )
    form = FormDefinition(
        rubric_set_id=uuid.UUID(form_input["rubric_set_id"]),
        agent_id=form_input["agent_id"],
        name=form_input["name"],
        version_number=form_input["version_number"],
        adapter_key=form_input["adapter_key"],
        adapter_version=form_input["adapter_version"],
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.UUID(domain_input["rubric_domain_id"]),
                code=domain_input["code"],
                title=domain_input["title"],
                display_order=domain_input["display_order"],
                criteria=criteria,
            ),
        ),
    )

    snapshot = build_evaluation_form_snapshot(uuid.UUID(golden["evaluation_id"]), form)
    serialized = serialize_snapshot_payload(snapshot.snapshot_payload)
    serialized_text = serialized.decode("utf-8")

    assert serialized_text == golden["expected_serialized"]
    assert hashlib.sha256(serialized).hexdigest() == golden["expected_sha256"]
    assert snapshot.snapshot_hash == golden["expected_sha256"]
    criterion_codes = [
        criterion.criterion_code for criterion in snapshot.form.domains[0].criteria
    ]
    assert criterion_codes == [
        "A-01",
        "B-02",
    ]
