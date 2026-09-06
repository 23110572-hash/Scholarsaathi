"""Add structured scholarship rules and nationwide coverage support.

Revision ID: 20260829_0005
Revises: 20260829_0004
Create Date: 2026-08-29 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260829_0005"
down_revision: str | None = "20260829_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "scholarship_versions",
        "applicable_state_codes",
        schema="public",
        existing_type=postgresql.ARRAY(sa.String(length=2)),
        type_=postgresql.ARRAY(sa.String(length=3)),
        existing_nullable=False,
        postgresql_using="applicable_state_codes::varchar(3)[]",
    )
    op.add_column(
        "scholarship_versions",
        sa.Column(
            "eligibility_rules_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="public",
    )
    op.add_column(
        "scholarship_versions",
        sa.Column(
            "document_requirements_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema="public",
    )
    op.add_column(
        "scholarship_versions",
        sa.Column(
            "application_process_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("scholarship_versions", "application_process_json", schema="public")
    op.drop_column("scholarship_versions", "document_requirements_json", schema="public")
    op.drop_column("scholarship_versions", "eligibility_rules_json", schema="public")
    op.alter_column(
        "scholarship_versions",
        "applicable_state_codes",
        schema="public",
        existing_type=postgresql.ARRAY(sa.String(length=3)),
        type_=postgresql.ARRAY(sa.String(length=2)),
        existing_nullable=False,
        postgresql_using=(
            "CASE WHEN 'ALL' = ANY(applicable_state_codes) "
            "THEN ARRAY[]::varchar(2)[] "
            "ELSE applicable_state_codes::varchar(2)[] END"
        ),
    )
