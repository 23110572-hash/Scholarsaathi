"""Add reusable profiles, private documents, and durable application intents.

Revision ID: 20260829_0004
Revises: 20260829_0003
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260829_0004"
down_revision: str | Sequence[str] | None = "20260829_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROFILE_COLUMNS = (
    "date_of_birth",
    "gender",
    "district",
    "institution_name",
    "board_or_university",
    "specialization",
    "current_semester",
    "class_10_percentage",
    "class_10_passing_year",
    "class_12_percentage",
    "class_12_passing_year",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE public.student_document_type AS ENUM (
            'CLASS_10_MARKSHEET',
            'CLASS_12_MARKSHEET',
            'CURRENT_MARKSHEET',
            'INCOME_CERTIFICATE',
            'CATEGORY_CERTIFICATE',
            'DOMICILE_CERTIFICATE',
            'DISABILITY_CERTIFICATE'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE public.student_document_status AS ENUM ('READY', 'DELETED')
        """
    )
    op.execute(
        """
        CREATE TYPE public.application_intent_status AS ENUM (
            'WAITING_FOR_AUTH',
            'WAITING_FOR_PROFILE',
            'WAITING_FOR_DOCUMENTS',
            'READY',
            'SUBMITTING',
            'SUBMITTED',
            'BLOCKED',
            'CANCELLED',
            'EXPIRED'
        )
        """
    )

    op.add_column(
        "student_settings",
        sa.Column("date_of_birth", sa.Date()),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("gender", sa.String(length=40)),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("district", sa.String(length=120)),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("institution_name", sa.String(length=240)),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("board_or_university", sa.String(length=240)),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("specialization", sa.String(length=120)),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("current_semester", sa.Integer()),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("class_10_percentage", sa.Numeric(precision=5, scale=2)),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("class_10_passing_year", sa.Integer()),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("class_12_percentage", sa.Numeric(precision=5, scale=2)),
        schema="student",
    )
    op.add_column(
        "student_settings",
        sa.Column("class_12_passing_year", sa.Integer()),
        schema="student",
    )
    op.create_check_constraint(
        "v4_ck_setting_current_semester",
        "student_settings",
        "current_semester IS NULL OR current_semester BETWEEN 1 AND 20",
        schema="student",
    )
    op.create_check_constraint(
        "v4_ck_setting_class_10_percentage",
        "student_settings",
        "class_10_percentage IS NULL OR class_10_percentage BETWEEN 0 AND 100",
        schema="student",
    )
    op.create_check_constraint(
        "v4_ck_setting_class_12_percentage",
        "student_settings",
        "class_12_percentage IS NULL OR class_12_percentage BETWEEN 0 AND 100",
        schema="student",
    )
    op.create_check_constraint(
        "v4_ck_setting_class_10_passing_year",
        "student_settings",
        "class_10_passing_year IS NULL OR class_10_passing_year BETWEEN 1950 AND 2100",
        schema="student",
    )
    op.create_check_constraint(
        "v4_ck_setting_class_12_passing_year",
        "student_settings",
        "class_12_passing_year IS NULL OR class_12_passing_year BETWEEN 1950 AND 2100",
        schema="student",
    )
    op.create_check_constraint(
        "v4_ck_setting_date_of_birth",
        "student_settings",
        "date_of_birth IS NULL OR date_of_birth >= DATE '1900-01-01'",
        schema="student",
    )

    # Altering the public partitioned parents propagates both columns to provider partitions.
    op.execute(
        """
        ALTER TABLE public.application_templates
        ADD COLUMN required_document_types jsonb NOT NULL
        DEFAULT '["INCOME_CERTIFICATE", "CURRENT_MARKSHEET"]'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE public.application_template_fields
        ADD COLUMN profile_binding varchar(80)
        """
    )
    op.execute(
        """
        UPDATE public.application_template_fields
        SET profile_binding = CASE field_key
            WHEN 'course' THEN 'course'
            WHEN 'course_year' THEN 'course_year'
            WHEN 'domicile_state' THEN 'state_code'
            WHEN 'family_income_band' THEN 'family_income_range'
            WHEN 'academic_score' THEN 'marks_percentage'
            WHEN 'student_declaration' THEN 'explicit_apply_authorization'
            ELSE profile_binding
        END
        WHERE field_key IN (
            'course',
            'course_year',
            'domicile_state',
            'family_income_band',
            'academic_score',
            'student_declaration'
        )
        """
    )

    op.add_column(
        "applications",
        sa.Column("agent_submission_authorized_at", sa.DateTime(timezone=True)),
        schema="student",
    )
    op.execute(
        """
        UPDATE student.applications
        SET agent_submission_authorized_at = submitted_at
        WHERE submitted_at IS NOT NULL
        """
    )
    op.create_unique_constraint(
        "v4_uq_application_student_context",
        "applications",
        ["id", "student_account_id"],
        schema="student",
    )
    op.create_unique_constraint(
        "v4_uq_application_student_version",
        "applications",
        ["student_account_id", "provider_domain", "scholarship_version_id"],
        schema="student",
    )

    op.execute(
        """
        CREATE TABLE student.student_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            student_domain public.ownership_domain NOT NULL DEFAULT 'STUDENT',
            student_account_id uuid NOT NULL,
            document_type public.student_document_type NOT NULL,
            storage_key text NOT NULL,
            original_filename varchar(255) NOT NULL,
            content_type varchar(120) NOT NULL,
            size_bytes bigint NOT NULL,
            checksum_sha256 varchar(64) NOT NULL,
            status public.student_document_status NOT NULL DEFAULT 'READY',
            issue_date date,
            expiry_date date,
            deleted_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT v4_ck_student_document_domain
                CHECK (student_domain = 'STUDENT'),
            CONSTRAINT v4_ck_student_document_size CHECK (size_bytes > 0),
            CONSTRAINT v4_ck_student_document_dates CHECK (
                expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date
            ),
            CONSTRAINT v4_fk_student_document_owner FOREIGN KEY (
                student_domain, student_account_id
            ) REFERENCES public.accounts (domain, id) ON DELETE CASCADE,
            CONSTRAINT v4_uq_student_document_owner_id UNIQUE (
                student_account_id, id
            ),
            CONSTRAINT v4_uq_student_document_storage_key UNIQUE (storage_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX v4_ix_student_documents_owner_status
        ON student.student_documents (student_account_id, status)
        """
    )

    op.execute(
        """
        CREATE TABLE student.application_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            application_id uuid NOT NULL,
            student_account_id uuid NOT NULL,
            student_document_id uuid NOT NULL,
            document_type public.student_document_type NOT NULL,
            storage_key_snapshot text NOT NULL,
            original_filename_snapshot varchar(255) NOT NULL,
            content_type_snapshot varchar(120) NOT NULL,
            size_bytes_snapshot bigint NOT NULL,
            checksum_sha256_snapshot varchar(64) NOT NULL,
            issue_date_snapshot date,
            expiry_date_snapshot date,
            attached_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT v4_fk_application_document_application FOREIGN KEY (
                application_id, student_account_id
            ) REFERENCES student.applications (id, student_account_id)
                ON DELETE CASCADE,
            CONSTRAINT v4_fk_application_document_source FOREIGN KEY (
                student_account_id, student_document_id
            ) REFERENCES student.student_documents (student_account_id, id),
            CONSTRAINT v4_uq_application_document_type UNIQUE (
                application_id, document_type
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX v4_ix_application_documents_document
        ON student.application_documents (student_document_id)
        """
    )

    op.execute(
        """
        CREATE TABLE student.application_intents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            student_domain public.ownership_domain NOT NULL DEFAULT 'STUDENT',
            student_account_id uuid,
            anonymous_token_hash varchar(64),
            scholarship_domain public.ownership_domain NOT NULL,
            scholarship_id uuid NOT NULL,
            organization_id uuid,
            scholarship_version_id uuid,
            application_template_id uuid,
            application_id uuid,
            status public.application_intent_status NOT NULL DEFAULT 'WAITING_FOR_AUTH',
            explicit_authorized_at timestamptz,
            explicit_authorization_source varchar(80),
            missing_profile_fields jsonb NOT NULL DEFAULT '[]'::jsonb,
            missing_document_types jsonb NOT NULL DEFAULT '[]'::jsonb,
            safe_last_error varchar(500),
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT v4_ck_application_intent_student_domain
                CHECK (student_domain = 'STUDENT'),
            CONSTRAINT v4_ck_application_intent_owner CHECK (
                student_account_id IS NOT NULL OR anonymous_token_hash IS NOT NULL
            ),
            CONSTRAINT v4_fk_application_intent_student FOREIGN KEY (
                student_domain, student_account_id
            ) REFERENCES public.accounts (domain, id) ON DELETE CASCADE,
            CONSTRAINT v4_fk_application_intent_scholarship FOREIGN KEY (
                scholarship_domain, scholarship_id
            ) REFERENCES public.scholarships (domain, id),
            CONSTRAINT v4_fk_application_intent_version FOREIGN KEY (
                scholarship_domain,
                organization_id,
                scholarship_id,
                scholarship_version_id
            ) REFERENCES public.scholarship_versions (
                domain,
                organization_id,
                scholarship_id,
                id
            ),
            CONSTRAINT v4_fk_application_intent_template FOREIGN KEY (
                scholarship_domain,
                organization_id,
                scholarship_version_id,
                application_template_id
            ) REFERENCES public.application_templates (
                domain,
                organization_id,
                scholarship_version_id,
                id
            ),
            CONSTRAINT v4_fk_application_intent_application
                FOREIGN KEY (application_id)
                REFERENCES student.applications (id) ON DELETE SET NULL,
            CONSTRAINT v4_uq_application_intent_student_target UNIQUE (
                student_account_id, scholarship_domain, scholarship_id
            ),
            CONSTRAINT v4_uq_application_intent_anonymous_target UNIQUE (
                anonymous_token_hash, scholarship_domain, scholarship_id
            ),
            CONSTRAINT v4_uq_application_intent_application UNIQUE (application_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX v4_ix_application_intents_student_status
        ON student.application_intents (student_account_id, status)
        """
    )
    op.execute(
        """
        CREATE INDEX v4_ix_application_intents_anonymous
        ON student.application_intents (anonymous_token_hash, status)
        """
    )


def downgrade() -> None:
    op.drop_table("application_intents", schema="student")
    op.drop_table("application_documents", schema="student")
    op.drop_table("student_documents", schema="student")

    op.drop_constraint(
        "v4_uq_application_student_version",
        "applications",
        schema="student",
        type_="unique",
    )
    op.drop_constraint(
        "v4_uq_application_student_context",
        "applications",
        schema="student",
        type_="unique",
    )
    op.drop_column(
        "applications",
        "agent_submission_authorized_at",
        schema="student",
    )

    op.execute(
        "ALTER TABLE public.application_template_fields DROP COLUMN profile_binding"
    )
    op.execute(
        "ALTER TABLE public.application_templates DROP COLUMN required_document_types"
    )

    for constraint_name in (
        "v4_ck_setting_date_of_birth",
        "v4_ck_setting_class_12_passing_year",
        "v4_ck_setting_class_10_passing_year",
        "v4_ck_setting_class_12_percentage",
        "v4_ck_setting_class_10_percentage",
        "v4_ck_setting_current_semester",
    ):
        op.drop_constraint(
            constraint_name,
            "student_settings",
            schema="student",
            type_="check",
        )
    for column_name in reversed(_PROFILE_COLUMNS):
        op.drop_column("student_settings", column_name, schema="student")

    op.execute("DROP TYPE public.application_intent_status")
    op.execute("DROP TYPE public.student_document_status")
    op.execute("DROP TYPE public.student_document_type")
