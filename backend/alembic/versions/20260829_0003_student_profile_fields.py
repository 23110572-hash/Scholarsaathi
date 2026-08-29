"""Add eligibility profile fields to student settings

Revision ID: 20260829_0003
Revises: 20260822_0002
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260829_0003"
down_revision: str | Sequence[str] | None = "20260822_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# student.student_settings is a plain table in the student schema, not one of the
# LIST (domain) partitioned public.* tables, so plain ADD COLUMN is sufficient.
_SCHEMA = "student"
_TABLE = "student_settings"

_NEW_COLUMNS = (
    sa.Column("full_name", sa.String(length=120), nullable=True),
    sa.Column("state_code", sa.String(length=2), nullable=True),
    sa.Column("education_level", sa.String(length=60), nullable=True),
    sa.Column("course", sa.String(length=80), nullable=True),
    sa.Column("course_year", sa.Integer(), nullable=True),
    sa.Column("marks_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column("family_income_range", sa.String(length=80), nullable=True),
    sa.Column(
        "categories",
        postgresql.ARRAY(sa.String(length=80)),
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Column("photo_data_url", sa.Text(), nullable=True),
)


def upgrade() -> None:
    for column in _NEW_COLUMNS:
        op.add_column(_TABLE, column.copy(), schema=_SCHEMA)

    op.create_check_constraint(
        "v2_ck_setting_course_year",
        _TABLE,
        "course_year IS NULL OR (course_year >= 1 AND course_year <= 12)",
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        "v2_ck_setting_marks_percentage",
        _TABLE,
        "marks_percentage IS NULL OR (marks_percentage >= 0 AND marks_percentage <= 100)",
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("v2_ck_setting_marks_percentage", _TABLE, schema=_SCHEMA, type_="check")
    op.drop_constraint("v2_ck_setting_course_year", _TABLE, schema=_SCHEMA, type_="check")
    for column in reversed(_NEW_COLUMNS):
        op.drop_column(_TABLE, column.name, schema=_SCHEMA)
