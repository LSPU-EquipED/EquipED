"""Dynamic CID evaluation forms, activations, snapshots, and typed strategy backfills.

Revision ID: 20260829_0004
Revises: 20260829_0003
Create Date: 2026-08-29
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "20260829_0004"
down_revision: str | None = "20260829_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Verbatim frozen strategy configurations matching contracts.
# Embedded here because migrations must not import application code.
_SME_STRATEGY_CONFIGS: dict[str, dict[str, Any]] = {
    "OP-01": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
        "short_sample": {
            "min_units": 4,
            "max_issues_4": 0,
            "max_issues_3": 1,
            "max_issues_2": 2,
        },
    },
    "OP-02": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 4,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "OP-03": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "OP-04": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "OP-05": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 3,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-01": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "A-02": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 5,
        "threshold_3": 3,
        "threshold_2": 2,
    },
    "A-03": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 4,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-04": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 3,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-05": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
}

_GAD_STRATEGY_CONFIGS: dict[str, dict[str, Any]] = {
    "GAD-01": {
        "strategy": "count_band",
        "mode": "maximum_count",
        "threshold_4": 0,
        "threshold_3": 1,
        "threshold_2": 3,
    },
    "GAD-02": {
        "strategy": "ratio_band",
        "mode": "absolute_difference",
        "threshold_4": 2.0,
        "threshold_3": 5.0,
        "threshold_2": 10.0,
    },
    "GAD-03": {
        "strategy": "count_band",
        "mode": "maximum_count",
        "threshold_4": 0,
        "threshold_3": 2,
        "threshold_2": 5,
    },
    "GAD-04": {
        "strategy": "count_band",
        "mode": "maximum_count",
        "threshold_4": 0,
        "threshold_3": 2,
        "threshold_2": 5,
    },
    "GAD-05": {
        "strategy": "count_band",
        "mode": "maximum_count",
        "threshold_4": 0,
        "threshold_3": 2,
        "threshold_2": 5,
    },
}

EXPECTED_SME_CODES = frozenset(_SME_STRATEGY_CONFIGS.keys())
EXPECTED_GAD_CODES = frozenset(_GAD_STRATEGY_CONFIGS.keys())
EXPECTED_ITSO_CODES = frozenset({"ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05"})


def _bind_uuid(is_postgres: bool, val: Any) -> tuple[sa.types.TypeEngine, Any]:
    """Dialect adapter: native sa.Uuid + UUID on PG; sa.String + str on SQLite."""
    if is_postgres:
        u = val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))
        return sa.Uuid(as_uuid=True), u
    else:
        return sa.String(), str(val)


def _preflight_validate_active_form(
    conn: Any,
    is_postgres: bool,
    set_id: uuid.UUID | str,
    agent_id: str,
    expected_codes: frozenset[str],
) -> None:
    """Validate structure, bounds, unique orders/codes, and exact criteria."""
    set_id_type, set_id_param = _bind_uuid(is_postgres, set_id)

    # 1. Validate rubric_sets row (name and positive version_number)
    set_row = conn.execute(
        sa.text(
            "SELECT name, version_number FROM rubric_sets WHERE rubric_set_id = :set_id"
        ).bindparams(sa.bindparam("set_id", type_=set_id_type)),
        {"set_id": set_id_param},
    ).fetchone()

    if set_row is None:
        raise RuntimeError(f"Active {agent_id} rubric set {set_id} not found")

    set_name = str(set_row[0]).strip() if set_row[0] else ""
    if not set_name or len(set_name) > 200:
        raise RuntimeError(f"Active {agent_id} candidate has invalid name '{set_name}'")

    set_ver = int(set_row[1]) if set_row[1] is not None else 0
    if set_ver <= 0:
        raise RuntimeError(
            f"Active {agent_id} candidate has non-positive version {set_ver}"
        )

    # 2. Validate domains
    domains = conn.execute(
        sa.text(
            "SELECT rubric_domain_id, code, title, display_order "
            "FROM rubric_domains WHERE rubric_set_id = :set_id"
        ).bindparams(sa.bindparam("set_id", type_=set_id_type)),
        {"set_id": set_id_param},
    ).fetchall()

    if not domains or len(domains) > 20:
        raise RuntimeError(
            f"Active {agent_id} candidate has invalid domain count {len(domains)}"
        )

    domain_codes: list[str] = []
    domain_orders: list[int] = []
    for d in domains:
        code = str(d[1]).strip() if d[1] else ""
        title = str(d[2]).strip() if d[2] else ""
        order = int(d[3]) if d[3] is not None else -1
        if not code or len(code) > 50:
            raise RuntimeError(
                f"Active {agent_id} candidate has invalid domain code '{code}'"
            )
        if not title or len(title) > 200:
            raise RuntimeError(
                f"Active {agent_id} candidate has invalid domain title '{title}'"
            )
        if order < 0:
            raise RuntimeError(
                f"Active {agent_id} candidate has invalid domain order {order}"
            )
        domain_codes.append(code)
        domain_orders.append(order)

    if len(domain_codes) != len(set(domain_codes)):
        raise RuntimeError(
            f"Active {agent_id} candidate has duplicate domain codes: {domain_codes}"
        )
    if len(domain_orders) != len(set(domain_orders)):
        raise RuntimeError(
            f"Active {agent_id} candidate has duplicate domain orders: {domain_orders}"
        )

    # 3. Validate criteria
    criteria = conn.execute(
        sa.text(
            "SELECT rc.rubric_criterion_id, rc.rubric_domain_id, rc.criterion_code, "
            "rc.title, rc.description, rc.scoring_rule, rc.display_order "
            "FROM rubric_criteria rc "
            "JOIN rubric_domains rd ON rd.rubric_domain_id = rc.rubric_domain_id "
            "WHERE rd.rubric_set_id = :set_id"
        ).bindparams(sa.bindparam("set_id", type_=set_id_type)),
        {"set_id": set_id_param},
    ).fetchall()

    if len(criteria) != len(expected_codes):
        raise RuntimeError(
            f"{agent_id.upper()} active criteria count mismatch: "
            f"expected {len(expected_codes)} rows, got {len(criteria)}"
        )

    found_codes = [r[2] for r in criteria]
    if len(found_codes) != len(set(found_codes)):
        raise RuntimeError(
            f"{agent_id.upper()} active criteria duplicate codes: {found_codes}"
        )
    if set(found_codes) != expected_codes:
        raise RuntimeError(
            f"{agent_id.upper()} active criteria mismatch: "
            f"expected {expected_codes}, got {set(found_codes)}"
        )

    criteria_by_dom: dict[Any, list[Any]] = {}
    for c in criteria:
        dom_id, code = c[1], str(c[2]).strip() if c[2] else ""
        title = str(c[3]).strip() if c[3] else ""
        desc = str(c[4]).strip() if c[4] else ""
        raw_rule = c[5]
        order = int(c[6]) if c[6] is not None else -1

        if not code or len(code) > 50:
            raise RuntimeError(f"{agent_id.upper()} criterion code '{code}' is invalid")
        if not title or len(title) > 200:
            raise RuntimeError(
                f"{agent_id.upper()} criterion title '{title}' exceeds 200 chars"
            )
        if not desc or len(desc) > 4000:
            raise RuntimeError(
                f"{agent_id.upper()} criterion description for '{code}' is invalid"
            )

        if raw_rule is not None:
            rule_str = str(raw_rule).strip()
            if not rule_str:
                raise RuntimeError(
                    f"{agent_id.upper()} criterion '{code}' scoring_rule is blank"
                )
            if len(rule_str) > 4000:
                raise RuntimeError(
                    f"{agent_id.upper()} scoring rule for '{code}' exceeds 4000 chars"
                )
            rule = rule_str
        else:
            rule = None

        if order < 0:
            raise RuntimeError(
                f"{agent_id.upper()} criterion display_order for '{code}' is invalid"
            )

        if agent_id == "itso":
            guidance = desc or rule or ""
            if not guidance or len(guidance) > 4000:
                raise RuntimeError(
                    f"ITSO criterion {code} has invalid guidance length {len(guidance)}"
                )

        criteria_by_dom.setdefault(dom_id, []).append(c)

    # Every selected domain must contain >= 1 criterion
    domain_ids = {d[0] for d in domains}
    criteria_dom_ids = set(criteria_by_dom.keys())
    if domain_ids != criteria_dom_ids:
        raise RuntimeError(
            f"Active {agent_id} candidate contains domain without criteria"
        )

    for dom_id, dom_criteria in criteria_by_dom.items():
        orders = [int(c[6]) for c in dom_criteria]
        if len(orders) != len(set(orders)):
            raise RuntimeError(
                f"{agent_id.upper()} domain {dom_id} duplicate orders: {orders}"
            )


def _verify_backfills_before_activation(
    conn: Any,
    is_postgres: bool,
    active_sme_id: Any,
    active_gad_id: Any,
    active_itso_id: Any,
) -> None:
    """Verify criteria have valid JSON objects and matching strategies."""
    for agent_id, set_id, configs in [
        ("sme", active_sme_id, _SME_STRATEGY_CONFIGS),
        ("gad", active_gad_id, _GAD_STRATEGY_CONFIGS),
    ]:
        set_id_type, set_id_param = _bind_uuid(is_postgres, set_id)
        rows = conn.execute(
            sa.text(
                "SELECT rc.criterion_code, rc.scoring_strategy, rc.strategy_config "
                "FROM rubric_criteria rc "
                "JOIN rubric_domains rd ON rd.rubric_domain_id = rc.rubric_domain_id "
                "WHERE rd.rubric_set_id = :set_id"
            ).bindparams(sa.bindparam("set_id", type_=set_id_type)),
            {"set_id": set_id_param},
        ).fetchall()

        if len(rows) != len(configs):
            raise RuntimeError(
                f"Backfill verification failed for {agent_id}: "
                f"expected {len(configs)} criteria, got {len(rows)}"
            )

        for code, strat, cfg_raw in rows:
            if not strat or not isinstance(strat, str):
                raise RuntimeError(
                    f"Criterion {code} missing scoring_strategy after backfill"
                )
            expected_cfg = configs.get(code)
            if not expected_cfg:
                raise RuntimeError(
                    f"Unexpected criterion code {code} in {agent_id} active set"
                )

            cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else cfg_raw
            if not isinstance(cfg, dict):
                raise RuntimeError(
                    f"Criterion {code} strategy_config is not JSON object: {type(cfg)}"
                )
            if strat != expected_cfg["strategy"] or cfg != expected_cfg:
                raise RuntimeError(
                    f"Criterion {code} strategy mismatch: config={cfg}, "
                    f"column={strat}, expected={expected_cfg}"
                )

    # ITSO verification
    set_id_type, set_id_param = _bind_uuid(is_postgres, active_itso_id)
    itso_rows = conn.execute(
        sa.text(
            "SELECT rc.criterion_code, rc.scoring_strategy, rc.strategy_config, "
            "rc.description, rc.scoring_rule "
            "FROM rubric_criteria rc "
            "JOIN rubric_domains rd ON rd.rubric_domain_id = rc.rubric_domain_id "
            "WHERE rd.rubric_set_id = :set_id"
        ).bindparams(sa.bindparam("set_id", type_=set_id_type)),
        {"set_id": set_id_param},
    ).fetchall()

    if len(itso_rows) != 5:
        raise RuntimeError(
            f"ITSO criteria count mismatch: expected 5, got {len(itso_rows)}"
        )

    for code, strat, cfg_raw, desc, rule in itso_rows:
        if strat != "llm_rubric_guidance":
            raise RuntimeError(
                f"ITSO criterion {code} scoring_strategy is '{strat}', "
                "expected 'llm_rubric_guidance'"
            )
        cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else cfg_raw
        expected_guidance = (desc or rule or "").strip()
        expected_itso_cfg = {
            "strategy": "llm_rubric_guidance",
            "guidance": expected_guidance,
        }
        if not isinstance(cfg, dict) or cfg != expected_itso_cfg:
            raise RuntimeError(
                f"ITSO criterion {code} strategy_config mismatch: "
                f"got {cfg}, expected {expected_itso_cfg}"
            )


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(UTC)
    is_postgres = conn.dialect.name == "postgresql"

    # 1. Preflight check & active candidate capture BEFORE any normalization
    has_rubrics = (
        conn.execute(sa.text("SELECT 1 FROM rubric_sets LIMIT 1")).fetchone()
        is not None
    )

    active_sme_id = None
    active_coord_id = None
    active_gad_id = None
    active_itso_id = None

    if has_rubrics:
        sme_active = conn.execute(
            sa.text(
                "SELECT rubric_set_id FROM rubric_sets "
                "WHERE agent_id = 'sme' AND status = 'active'"
            )
        ).fetchall()
        coord_active = conn.execute(
            sa.text(
                "SELECT rubric_set_id FROM rubric_sets "
                "WHERE agent_id = 'coordinator' AND status = 'active'"
            )
        ).fetchall()
        gad_active = conn.execute(
            sa.text(
                "SELECT rubric_set_id FROM rubric_sets "
                "WHERE agent_id = 'gad' AND status = 'active'"
            )
        ).fetchall()
        itso_active = conn.execute(
            sa.text(
                "SELECT rubric_set_id FROM rubric_sets "
                "WHERE agent_id = 'itso' AND status = 'active'"
            )
        ).fetchall()

        if not (
            len(sme_active) == 1
            and len(coord_active) == 1
            and len(gad_active) == 1
            and len(itso_active) == 1
        ):
            raise RuntimeError(
                "Migration preflight failed: rubric_sets must contain exactly one "
                f"active revision per agent (got sme={len(sme_active)}, "
                f"coord={len(coord_active)}, gad={len(gad_active)}, "
                f"itso={len(itso_active)})"
            )

        active_sme_id = sme_active[0][0]
        active_coord_id = coord_active[0][0]
        active_gad_id = gad_active[0][0]
        active_itso_id = itso_active[0][0]

        # Exact structure and criteria preflight validation
        _preflight_validate_active_form(
            conn, is_postgres, active_sme_id, "sme", EXPECTED_SME_CODES
        )
        _preflight_validate_active_form(
            conn, is_postgres, active_gad_id, "gad", EXPECTED_GAD_CODES
        )
        _preflight_validate_active_form(
            conn, is_postgres, active_itso_id, "itso", EXPECTED_ITSO_CODES
        )

    # 2. Normalize status active -> published before CHECK constraint
    if has_rubrics:
        conn.execute(
            sa.text(
                "UPDATE rubric_sets SET status = 'published' WHERE status = 'active'"
            )
        )

    # 3. Alter rubric_sets table (columns, FKs with ON DELETE SET NULL, constraints)
    with op.batch_alter_table("rubric_sets") as batch_op:
        batch_op.add_column(
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "published_by",
                sa.Uuid(),
                sa.ForeignKey(
                    "users.user_id",
                    name="fk_rubric_sets_published_by",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "created_by",
                sa.Uuid(),
                sa.ForeignKey(
                    "users.user_id",
                    name="fk_rubric_sets_created_by",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "retired_by",
                sa.Uuid(),
                sa.ForeignKey(
                    "users.user_id",
                    name="fk_rubric_sets_retired_by",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("adapter_key", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "adapter_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.create_unique_constraint(
            "uq_rubric_sets_agent_id_rubric_set_id",
            ["agent_id", "rubric_set_id"],
        )
        batch_op.create_check_constraint(
            "ck_rubric_sets_status",
            "status IN ('draft', 'published', 'retired')",
        )

    # 4. Retire Coordinator v1 and backfill audit/adapter fields
    if has_rubrics:
        coord_id_type, coord_id_param = _bind_uuid(is_postgres, active_coord_id)
        conn.execute(
            sa.text(
                "UPDATE rubric_sets "
                "SET status = 'retired', retired_at = :now, retired_by = NULL "
                "WHERE rubric_set_id = :coord_id"
            ).bindparams(sa.bindparam("coord_id", type_=coord_id_type)),
            {"coord_id": coord_id_param, "now": now},
        )
        conn.execute(
            sa.text(
                "UPDATE rubric_sets "
                "SET adapter_key = agent_id WHERE adapter_key IS NULL"
            )
        )
        conn.execute(
            sa.text(
                "UPDATE rubric_sets SET published_at = created_at "
                "WHERE status = 'published' AND published_at IS NULL"
            )
        )

    with op.batch_alter_table("rubric_sets") as batch_op:
        batch_op.alter_column(
            "adapter_key",
            existing_type=sa.String(length=50),
            nullable=False,
        )

    # Partial unique index for one draft per agent
    op.create_index(
        "uq_rubric_sets_one_draft_per_agent",
        "rubric_sets",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )

    # 5. Alter rubric_criteria table: add scoring_strategy and strategy_config
    with op.batch_alter_table("rubric_criteria") as batch_op:
        batch_op.add_column(
            sa.Column("scoring_strategy", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(sa.Column("strategy_config", sa.JSON(), nullable=True))

    # 6. Create rubric_agent_activations table with composite FK
    op.create_table(
        "rubric_agent_activations",
        sa.Column("agent_id", sa.String(length=50), primary_key=True, nullable=False),
        sa.Column("rubric_set_id", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_by",
            sa.Uuid(),
            sa.ForeignKey(
                "users.user_id",
                name="fk_rubric_agent_activations_updated_by",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "rubric_set_id"],
            ["rubric_sets.agent_id", "rubric_sets.rubric_set_id"],
            name="fk_rubric_agent_activations_rubric_set",
        ),
    )

    # 7. Create evaluation_form_snapshots table
    op.create_table(
        "evaluation_form_snapshots",
        sa.Column("snapshot_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "evaluation_id",
            sa.Uuid(),
            sa.ForeignKey(
                "evaluation_jobs.evaluation_id",
                name="fk_eval_snapshots_evaluation_id",
            ),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column(
            "rubric_set_id",
            sa.Uuid(),
            sa.ForeignKey(
                "rubric_sets.rubric_set_id",
                name="fk_eval_snapshots_rubric_set_id",
            ),
            nullable=False,
        ),
        sa.Column("snapshot_payload", sa.JSON(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("adapter_key", sa.String(length=50), nullable=False),
        sa.Column("adapter_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "evaluation_id", "agent_id", name="uq_evaluation_form_snapshots_eval_agent"
        ),
    )

    # Add DB-level immutability protection for evaluation_form_snapshots
    if is_postgres:
        op.execute(
            sa.text(
                """
                CREATE OR REPLACE FUNCTION trg_evaluation_form_snapshots_immutable()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'evaluation_form_snapshots rows are immutable';
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER trg_evaluation_form_snapshots_immutable
                BEFORE UPDATE OR DELETE ON evaluation_form_snapshots
                FOR EACH ROW
                EXECUTE FUNCTION trg_evaluation_form_snapshots_immutable();
                """
            )
        )
    else:
        op.execute(
            sa.text(
                """
                CREATE TRIGGER IF NOT EXISTS trg_eval_snapshots_no_update
                BEFORE UPDATE ON evaluation_form_snapshots
                BEGIN
                    SELECT RAISE(FAIL, 'evaluation_form_snapshots immutable');
                END;
                """
            )
        )
        op.execute(
            sa.text(
                """
                CREATE TRIGGER IF NOT EXISTS trg_eval_snapshots_no_delete
                BEFORE DELETE ON evaluation_form_snapshots
                BEGIN
                    SELECT RAISE(FAIL, 'evaluation_form_snapshots immutable');
                END;
                """
            )
        )

    # 8. Add nullable form_snapshot_id to agent_results
    with op.batch_alter_table("agent_results") as batch_op:
        batch_op.add_column(
            sa.Column(
                "form_snapshot_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "evaluation_form_snapshots.snapshot_id",
                    name="fk_agent_results_form_snapshot_id",
                ),
                nullable=True,
            )
        )

    # 9. Backfill criteria scoring strategies & strategy configs
    if has_rubrics:
        sme_id_type, sme_set_param = _bind_uuid(is_postgres, active_sme_id)
        for code, cfg in _SME_STRATEGY_CONFIGS.items():
            conn.execute(
                sa.text(
                    "UPDATE rubric_criteria "
                    "SET scoring_strategy = :strat, strategy_config = :cfg "
                    "WHERE criterion_code = :code AND rubric_domain_id IN ("
                    "  SELECT rd.rubric_domain_id FROM rubric_domains rd "
                    "  WHERE rd.rubric_set_id = :set_id"
                    ")"
                ).bindparams(
                    sa.bindparam("strat", type_=sa.String),
                    sa.bindparam("cfg", type_=sa.JSON),
                    sa.bindparam("code", type_=sa.String),
                    sa.bindparam("set_id", type_=sme_id_type),
                ),
                {
                    "strat": cfg["strategy"],
                    "cfg": cfg,
                    "code": code,
                    "set_id": sme_set_param,
                },
            )

        gad_id_type, gad_set_param = _bind_uuid(is_postgres, active_gad_id)
        for code, cfg in _GAD_STRATEGY_CONFIGS.items():
            conn.execute(
                sa.text(
                    "UPDATE rubric_criteria "
                    "SET scoring_strategy = :strat, strategy_config = :cfg "
                    "WHERE criterion_code = :code AND rubric_domain_id IN ("
                    "  SELECT rd.rubric_domain_id FROM rubric_domains rd "
                    "  WHERE rd.rubric_set_id = :set_id"
                    ")"
                ).bindparams(
                    sa.bindparam("strat", type_=sa.String),
                    sa.bindparam("cfg", type_=sa.JSON),
                    sa.bindparam("code", type_=sa.String),
                    sa.bindparam("set_id", type_=gad_id_type),
                ),
                {
                    "strat": cfg["strategy"],
                    "cfg": cfg,
                    "code": code,
                    "set_id": gad_set_param,
                },
            )

        itso_id_type, itso_set_param = _bind_uuid(is_postgres, active_itso_id)
        itso_crit_rows = conn.execute(
            sa.text(
                "SELECT rc.rubric_criterion_id, rc.criterion_code, "
                "rc.description, rc.scoring_rule "
                "FROM rubric_criteria rc "
                "JOIN rubric_domains rd ON rd.rubric_domain_id = rc.rubric_domain_id "
                "WHERE rd.rubric_set_id = :set_id"
            ).bindparams(sa.bindparam("set_id", type_=itso_id_type)),
            {"set_id": itso_set_param},
        ).fetchall()

        for row in itso_crit_rows:
            crit_id, code, desc, rule = row[0], row[1], row[2], row[3]
            guidance = desc or rule or code
            cfg = {"strategy": "llm_rubric_guidance", "guidance": guidance}
            crit_id_type, crit_id_param = _bind_uuid(is_postgres, crit_id)
            conn.execute(
                sa.text(
                    "UPDATE rubric_criteria "
                    "SET scoring_strategy = :strat, strategy_config = :cfg "
                    "WHERE rubric_criterion_id = :id"
                ).bindparams(
                    sa.bindparam("strat", type_=sa.String),
                    sa.bindparam("cfg", type_=sa.JSON),
                    sa.bindparam("id", type_=crit_id_type),
                ),
                {
                    "strat": "llm_rubric_guidance",
                    "cfg": cfg,
                    "id": crit_id_param,
                },
            )

        # 10. Assert complete backfill mappings before creating activations
        _verify_backfills_before_activation(
            conn, is_postgres, active_sme_id, active_gad_id, active_itso_id
        )

        # 11. Create published Coordinator v2
        v2_set_id = uuid.uuid4()
        v2_domain_id = uuid.uuid4()
        v2_criterion_id = uuid.uuid4()

        rubric_sets_table = sa.table(
            "rubric_sets",
            sa.column("rubric_set_id", sa.Uuid),
            sa.column("agent_id", sa.String),
            sa.column("name", sa.String),
            sa.column("version_number", sa.Integer),
            sa.column("status", sa.String),
            sa.column("adapter_key", sa.String),
            sa.column("adapter_version", sa.Integer),
            sa.column("published_at", sa.DateTime(timezone=True)),
            sa.column("published_by", sa.Uuid),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(
            rubric_sets_table,
            [
                {
                    "rubric_set_id": v2_set_id,
                    "agent_id": "coordinator",
                    "name": "Coordinator Rubric v2",
                    "version_number": 2,
                    "status": "published",
                    "adapter_key": "coordinator",
                    "adapter_version": 1,
                    "published_at": now,
                    "published_by": None,
                    "created_at": now,
                }
            ],
        )
        rubric_domains_table = sa.table(
            "rubric_domains",
            sa.column("rubric_domain_id", sa.Uuid),
            sa.column("rubric_set_id", sa.Uuid),
            sa.column("code", sa.String),
            sa.column("title", sa.String),
            sa.column("display_order", sa.Integer),
        )
        op.bulk_insert(
            rubric_domains_table,
            [
                {
                    "rubric_domain_id": v2_domain_id,
                    "rubric_set_id": v2_set_id,
                    "code": "A",
                    "title": "Assessment",
                    "display_order": 1,
                }
            ],
        )
        rubric_criteria_table = sa.table(
            "rubric_criteria",
            sa.column("rubric_criterion_id", sa.Uuid),
            sa.column("rubric_domain_id", sa.Uuid),
            sa.column("criterion_code", sa.String),
            sa.column("title", sa.String),
            sa.column("description", sa.Text),
            sa.column("scoring_rule", sa.Text),
            sa.column("scoring_strategy", sa.String),
            sa.column("strategy_config", sa.JSON),
            sa.column("display_order", sa.Integer),
        )
        op.bulk_insert(
            rubric_criteria_table,
            [
                {
                    "rubric_criterion_id": v2_criterion_id,
                    "rubric_domain_id": v2_domain_id,
                    "criterion_code": "A-05",
                    "title": "Curriculum Alignment",
                    "description": (
                        "Evaluate alignment between student learning material and "
                        "confirmed course curriculum/syllabus topics."
                    ),
                    "scoring_rule": (
                        "Grounded curriculum alignment scoring for "
                        "course syllabus topics."
                    ),
                    "scoring_strategy": "curriculum_alignment",
                    "strategy_config": {"strategy": "curriculum_alignment"},
                    "display_order": 1,
                }
            ],
        )

        # 12. Activate published SME, GAD, ITSO (from captured IDs) and Coordinator v2
        initial_activations = [
            {"agent_id": "sme", "rubric_set_id": active_sme_id},
            {"agent_id": "gad", "rubric_set_id": active_gad_id},
            {"agent_id": "itso", "rubric_set_id": active_itso_id},
            {"agent_id": "coordinator", "rubric_set_id": v2_set_id},
        ]
        for act in initial_activations:
            act_id_type, act_id_param = _bind_uuid(is_postgres, act["rubric_set_id"])
            conn.execute(
                sa.text(
                    "INSERT INTO rubric_agent_activations "
                    "(agent_id, rubric_set_id, updated_by, updated_at) "
                    "VALUES (:agent, :set_id, NULL, :now)"
                ).bindparams(
                    sa.bindparam("agent", type_=sa.String),
                    sa.bindparam("set_id", type_=act_id_type),
                ),
                {"agent": act["agent_id"], "set_id": act_id_param, "now": now},
            )


def downgrade() -> None:
    raise RuntimeError("Downgrade is not supported for dynamic CID forms migration")
