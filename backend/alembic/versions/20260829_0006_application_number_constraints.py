"""Add provider-defined numeric application-field constraints.

Revision ID: 20260829_0006
Revises: 20260829_0005
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0006"
down_revision: str | None = "20260829_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Altering the partitioned parent propagates the columns to every provider partition.
    op.execute(
        """
        ALTER TABLE public.application_template_fields
            ADD COLUMN numeric_min numeric,
            ADD COLUMN numeric_max numeric,
            ADD COLUMN numeric_step numeric
        """
    )
    op.execute(
        """
        ALTER TABLE public.application_template_fields
            ADD CONSTRAINT v6_ck_application_field_numeric_range
                CHECK (numeric_min IS NULL OR numeric_max IS NULL OR numeric_min <= numeric_max),
            ADD CONSTRAINT v6_ck_application_field_numeric_step
                CHECK (numeric_step IS NULL OR numeric_step > 0)
        """
    )
    op.execute(
        """
        UPDATE public.application_template_fields
        SET numeric_min = CASE profile_binding
                WHEN 'course_year' THEN 1
                WHEN 'marks_percentage' THEN 0
                ELSE numeric_min
            END,
            numeric_max = CASE profile_binding
                WHEN 'course_year' THEN 12
                WHEN 'marks_percentage' THEN 100
                ELSE numeric_max
            END,
            numeric_step = CASE profile_binding
                WHEN 'course_year' THEN 1
                WHEN 'marks_percentage' THEN 0.01
                ELSE numeric_step
            END
        WHERE field_type = 'NUMBER'
          AND profile_binding IN ('course_year', 'marks_percentage')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.application_template_fields
            DROP CONSTRAINT v6_ck_application_field_numeric_step,
            DROP CONSTRAINT v6_ck_application_field_numeric_range,
            DROP COLUMN numeric_step,
            DROP COLUMN numeric_max,
            DROP COLUMN numeric_min
        """
    )
