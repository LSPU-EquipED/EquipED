"""make (roadmap_id, course_code) unique across roadmap_courses

The former ``idx_roadmap_courses_roadmap_code`` non-unique index is replaced
by a UNIQUE index on the same columns so resolution can never produce a
course_code collision within one roadmap. The model's ``RoadmapCourse`` no
longer declares the plain index.

Upgrade is conditional: it drops the legacy non-unique index only when
present, then creates the unique index only when absent. Downgrade reverses
this (drop the unique index, recreate the plain one if missing).

Revision ID: 20260808_0002
Revises: 479684525d98
Create Date: 2026-08-08
"""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "20260808_0002"
down_revision = "479684525d98"
branch_labels = None
depends_on = None

_TABLE_NAME = "roadmap_courses"
_LEGACY_INDEX = "idx_roadmap_courses_roadmap_code"
_UNIQUE_INDEX = "uq_roadmap_courses_roadmap_code"
_UNIQUE_COLUMNS = ["roadmap_id", "course_code"]


def _has_index(name: str) -> bool:
    bind = op.get_bind()
    table_names = inspect(bind).get_table_names()
    if _TABLE_NAME not in table_names:
        return False
    return name in [
        i["name"] for i in inspect(bind).get_indexes(_TABLE_NAME)
    ]


def upgrade() -> None:
    # Drop the now-redundant non-unique index first so the unique index can
    # take its place without a name collision.
    if _has_index(_LEGACY_INDEX):
        op.drop_index(_LEGACY_INDEX, table_name=_TABLE_NAME)
    if not _has_index(_UNIQUE_INDEX):
        op.create_index(
            _UNIQUE_INDEX,
            _TABLE_NAME,
            _UNIQUE_COLUMNS,
            unique=True,
        )


def downgrade() -> None:
    if _has_index(_UNIQUE_INDEX):
        op.drop_index(_UNIQUE_INDEX, table_name=_TABLE_NAME)
    if not _has_index(_LEGACY_INDEX):
        op.create_index(
            _LEGACY_INDEX,
            _TABLE_NAME,
            _UNIQUE_COLUMNS,
        )
