"""Split business data into four owner-controlled PostgreSQL schemas.

Revision ID: 20260822_0002
Revises: 20260822_0001
Create Date: 2026-08-22
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa

from alembic import op

revision: str = "20260822_0002"
down_revision: str | Sequence[str] | None = "20260822_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_TABLES = (
    "application_answers",
    "application_events",
    "applications",
    "saved_scholarships",
    "application_template_fields",
    "application_templates",
    "publication_reviews",
    "ai_extraction_drafts",
    "knowledge_chunks",
    "source_documents",
    "scholarship_versions",
    "scholarships",
    "organization_verification_requests",
    "organization_members",
    "organizations",
    "student_settings",
    "auth_sessions",
    "audit_events",
    "accounts",
)

PROVIDER_PARTITIONED_TABLES = (
    "organizations",
    "organization_members",
    "scholarships",
    "scholarship_versions",
    "source_documents",
    "knowledge_chunks",
    "ai_extraction_drafts",
    "application_templates",
    "application_template_fields",
)

DOMAIN_PARTITIONS = (
    ("student", "STUDENT"),
    ("central_government", "CENTRAL_GOVERNMENT"),
    ("state_government", "STATE_GOVERNMENT"),
    ("ngo_private", "NGO_PRIVATE"),
)

PROVIDER_PARTITIONS = DOMAIN_PARTITIONS[1:]


def _execute_all(statements: Iterable[str]) -> None:
    for statement in statements:
        op.execute(sa.text(statement))


def _initial_revision_module() -> ModuleType:
    path = Path(__file__).with_name("20260822_0001_initial_platform.py")
    spec = importlib.util.spec_from_file_location("scholarsaathi_initial_revision", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the initial ScholarSaathi migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upgrade() -> None:
    _execute_all(
        (
            "CREATE SCHEMA student",
            "CREATE SCHEMA central_government",
            "CREATE SCHEMA state_government",
            "CREATE SCHEMA ngo_private",
            "CREATE SCHEMA scholarsaathi_v1_legacy",
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM public.applications a
                    JOIN public.scholarship_versions v ON v.id = a.scholarship_version_id
                    JOIN public.scholarships s ON s.id = v.scholarship_id
                    WHERE a.organization_id <> s.organization_id
                ) THEN
                    RAISE EXCEPTION 'Cannot migrate applications with mismatched scholarship ownership';
                END IF;
                IF EXISTS (
                    SELECT 1
                    FROM public.applications a
                    JOIN public.application_templates t ON t.id = a.application_template_id
                    WHERE t.scholarship_version_id <> a.scholarship_version_id
                ) THEN
                    RAISE EXCEPTION 'Cannot migrate applications with mismatched templates';
                END IF;
                IF EXISTS (
                    SELECT 1
                    FROM public.knowledge_chunks c
                    JOIN public.source_documents d ON d.id = c.source_document_id
                    WHERE c.scholarship_version_id <> d.scholarship_version_id
                ) THEN
                    RAISE EXCEPTION 'Cannot migrate evidence with mismatched source ownership';
                END IF;
            END
            $$
            """,
        )
    )

    for table_name in LEGACY_TABLES:
        op.execute(
            sa.text(
                f'ALTER TABLE public."{table_name}" '
                f'SET SCHEMA scholarsaathi_v1_legacy'
            )
        )

    _execute_all(
        (
            "ALTER TYPE public.account_realm RENAME TO account_realm_v1_legacy",
            "ALTER TYPE public.publication_status RENAME TO publication_status_v1_legacy",
            """
            CREATE TYPE public.ownership_domain AS ENUM (
                'STUDENT', 'CENTRAL_GOVERNMENT', 'STATE_GOVERNMENT', 'NGO_PRIVATE'
            )
            """,
            "CREATE TYPE public.account_realm AS ENUM ('STUDENT', 'ORGANIZATION_MEMBER')",
            """
            CREATE TYPE public.publication_status AS ENUM (
                'DRAFT', 'PUBLISHED', 'PAUSED', 'EXPIRED', 'ARCHIVED', 'SUPERSEDED'
            )
            """,
            """
            CREATE TABLE state_government.states (
                code varchar(2) PRIMARY KEY,
                name varchar(120) NOT NULL UNIQUE,
                is_union_territory boolean NOT NULL DEFAULT false,
                is_active boolean NOT NULL DEFAULT true,
                created_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            """
            INSERT INTO state_government.states (code, name, is_union_territory) VALUES
                ('AP', 'Andhra Pradesh', false),
                ('AR', 'Arunachal Pradesh', false),
                ('AS', 'Assam', false),
                ('BR', 'Bihar', false),
                ('CG', 'Chhattisgarh', false),
                ('GA', 'Goa', false),
                ('GJ', 'Gujarat', false),
                ('HR', 'Haryana', false),
                ('HP', 'Himachal Pradesh', false),
                ('JH', 'Jharkhand', false),
                ('KA', 'Karnataka', false),
                ('KL', 'Kerala', false),
                ('MP', 'Madhya Pradesh', false),
                ('MH', 'Maharashtra', false),
                ('MN', 'Manipur', false),
                ('ML', 'Meghalaya', false),
                ('MZ', 'Mizoram', false),
                ('NL', 'Nagaland', false),
                ('OD', 'Odisha', false),
                ('PB', 'Punjab', false),
                ('RJ', 'Rajasthan', false),
                ('SK', 'Sikkim', false),
                ('TN', 'Tamil Nadu', false),
                ('TS', 'Telangana', false),
                ('TR', 'Tripura', false),
                ('UP', 'Uttar Pradesh', false),
                ('UK', 'Uttarakhand', false),
                ('WB', 'West Bengal', false),
                ('AN', 'Andaman and Nicobar Islands', true),
                ('CH', 'Chandigarh', true),
                ('DH', 'Dadra and Nagar Haveli and Daman and Diu', true),
                ('DL', 'Delhi', true),
                ('JK', 'Jammu and Kashmir', true),
                ('LA', 'Ladakh', true),
                ('LD', 'Lakshadweep', true),
                ('PY', 'Puducherry', true)
            """,
            """
            CREATE TABLE public.accounts (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                login_identifier citext NOT NULL,
                password_hash text NOT NULL,
                realm public.account_realm NOT NULL,
                status public.account_status NOT NULL DEFAULT 'ACTIVE',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                last_login_at timestamptz,
                CONSTRAINT v2_pk_accounts PRIMARY KEY (domain, id),
                CONSTRAINT v2_uq_account_login_domain UNIQUE (domain, login_identifier)
            ) PARTITION BY LIST (domain)
            """,
        )
    )

    for schema_name, domain in DOMAIN_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.accounts PARTITION OF public.accounts "
                f"FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            "CREATE INDEX v2_ix_accounts_login_identifier ON public.accounts (login_identifier)",
            """
            CREATE TABLE public.auth_sessions (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                account_id uuid NOT NULL,
                token_hash varchar(64) NOT NULL,
                expires_at timestamptz NOT NULL,
                last_seen_at timestamptz NOT NULL DEFAULT now(),
                revoked_at timestamptz,
                user_agent varchar(512),
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_auth_sessions PRIMARY KEY (domain, id),
                CONSTRAINT v2_uq_session_token_domain UNIQUE (domain, token_hash),
                CONSTRAINT v2_fk_session_account FOREIGN KEY (domain, account_id)
                    REFERENCES public.accounts (domain, id) ON DELETE CASCADE
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in DOMAIN_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.auth_sessions PARTITION OF public.auth_sessions "
                f"FOR VALUES IN ('{domain}')"
            )
        )
    op.execute(sa.text("CREATE INDEX v2_ix_auth_sessions_token_hash ON public.auth_sessions (token_hash)"))

    _execute_all(
        (
            """
            CREATE TABLE public.organizations (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                slug varchar(120) NOT NULL,
                legal_name varchar(240) NOT NULL,
                display_name varchar(180) NOT NULL,
                type public.organization_type NOT NULL,
                jurisdiction_state_code varchar(2),
                is_synthetic boolean NOT NULL DEFAULT false,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_organizations PRIMARY KEY (domain, id),
                CONSTRAINT v2_uq_organization_slug_domain UNIQUE (domain, slug),
                CONSTRAINT v2_ck_organization_domain_type CHECK (
                    (domain = 'CENTRAL_GOVERNMENT' AND type = 'CENTRAL_GOVERNMENT') OR
                    (domain = 'STATE_GOVERNMENT' AND type = 'STATE_GOVERNMENT'
                        AND jurisdiction_state_code IS NOT NULL) OR
                    (domain = 'NGO_PRIVATE' AND type IN ('NGO', 'PRIVATE_COMPANY'))
                )
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.organizations PARTITION OF public.organizations "
                f"FOR VALUES IN ('{domain}')"
            )
        )
    _execute_all(
        (
            """
            ALTER TABLE state_government.organizations
            ADD CONSTRAINT v2_fk_state_organization_registry
            FOREIGN KEY (jurisdiction_state_code)
            REFERENCES state_government.states (code)
            """,
            """
            CREATE TABLE public.organization_members (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                organization_id uuid NOT NULL,
                account_id uuid NOT NULL,
                role public.member_role NOT NULL,
                status public.member_status NOT NULL DEFAULT 'ACTIVE',
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_organization_members PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_member_organization FOREIGN KEY (domain, organization_id)
                    REFERENCES public.organizations (domain, id) ON DELETE CASCADE,
                CONSTRAINT v2_fk_member_account FOREIGN KEY (domain, account_id)
                    REFERENCES public.accounts (domain, id) ON DELETE CASCADE,
                CONSTRAINT v2_uq_organization_member UNIQUE (domain, organization_id, account_id),
                CONSTRAINT v2_uq_account_one_organization UNIQUE (domain, account_id)
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.organization_members "
                f"PARTITION OF public.organization_members FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            "CREATE INDEX v2_ix_organization_members_account ON public.organization_members (account_id)",
            """
            CREATE TABLE public.scholarships (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                organization_id uuid NOT NULL,
                slug varchar(160) NOT NULL,
                current_published_version_id uuid,
                lifecycle_status public.scholarship_lifecycle NOT NULL DEFAULT 'ACTIVE',
                is_synthetic boolean NOT NULL DEFAULT false,
                created_at timestamptz NOT NULL DEFAULT now(),
                archived_at timestamptz,
                CONSTRAINT v2_pk_scholarships PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_scholarship_organization
                    FOREIGN KEY (domain, organization_id)
                    REFERENCES public.organizations (domain, id) ON DELETE CASCADE,
                CONSTRAINT v2_uq_organization_scholarship_slug
                    UNIQUE (domain, organization_id, slug),
                CONSTRAINT v2_uq_scholarship_owner
                    UNIQUE (domain, organization_id, id)
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.scholarships PARTITION OF public.scholarships "
                f"FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            "CREATE INDEX v2_ix_scholarships_organization ON public.scholarships (organization_id)",
            """
            CREATE TABLE public.scholarship_versions (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                organization_id uuid NOT NULL,
                scholarship_id uuid NOT NULL,
                version_number integer NOT NULL,
                title varchar(240) NOT NULL,
                summary text NOT NULL,
                knowledge_summary text NOT NULL,
                academic_year varchar(20) NOT NULL,
                scope varchar(40) NOT NULL,
                applicable_state_codes varchar(2)[] NOT NULL,
                education_levels varchar(60)[] NOT NULL,
                course_families varchar(80)[] NOT NULL,
                category_tags varchar(80)[] NOT NULL,
                benefit_summary text NOT NULL,
                benefit_amount_min numeric(12,2),
                benefit_amount_max numeric(12,2),
                application_opens_at timestamptz,
                application_deadline_at timestamptz,
                official_source_url text NOT NULL,
                provider_helpdesk_url text NOT NULL,
                publication_status public.publication_status NOT NULL DEFAULT 'DRAFT',
                last_provider_confirmed_at timestamptz NOT NULL,
                created_by uuid NOT NULL,
                published_by uuid,
                created_at timestamptz NOT NULL DEFAULT now(),
                published_at timestamptz,
                CONSTRAINT v2_pk_scholarship_versions PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_version_scholarship_owner
                    FOREIGN KEY (domain, organization_id, scholarship_id)
                    REFERENCES public.scholarships (domain, organization_id, id)
                    ON DELETE CASCADE,
                CONSTRAINT v2_fk_version_creator FOREIGN KEY (domain, created_by)
                    REFERENCES public.accounts (domain, id),
                CONSTRAINT v2_fk_version_publisher FOREIGN KEY (domain, published_by)
                    REFERENCES public.accounts (domain, id),
                CONSTRAINT v2_uq_scholarship_version_number
                    UNIQUE (domain, scholarship_id, version_number),
                CONSTRAINT v2_uq_version_scholarship_owner
                    UNIQUE (domain, organization_id, scholarship_id, id),
                CONSTRAINT v2_uq_version_owner
                    UNIQUE (domain, organization_id, id),
                CONSTRAINT v2_ck_scholarship_application_dates CHECK (
                    application_deadline_at IS NULL OR application_opens_at IS NULL OR
                    application_deadline_at >= application_opens_at
                )
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.scholarship_versions "
                f"PARTITION OF public.scholarship_versions FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            "CREATE INDEX v2_ix_versions_deadline ON public.scholarship_versions (application_deadline_at)",
            "CREATE INDEX v2_ix_versions_status ON public.scholarship_versions (publication_status)",
            """
            ALTER TABLE public.scholarships
            ADD CONSTRAINT v2_fk_scholarship_current_version
            FOREIGN KEY (domain, organization_id, id, current_published_version_id)
            REFERENCES public.scholarship_versions
                (domain, organization_id, scholarship_id, id)
            """,
            """
            CREATE TABLE public.source_documents (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                organization_id uuid NOT NULL,
                scholarship_version_id uuid NOT NULL,
                display_name varchar(240) NOT NULL,
                source_kind varchar(40) NOT NULL,
                content_type varchar(120) NOT NULL,
                size_bytes bigint NOT NULL,
                storage_key text,
                source_url text,
                checksum_sha256 varchar(64) NOT NULL,
                extracted_text text NOT NULL,
                usage_rights_confirmed_at timestamptz NOT NULL,
                confirmation_status varchar(40) NOT NULL,
                uploaded_by uuid NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_source_documents PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_source_version_owner
                    FOREIGN KEY (domain, organization_id, scholarship_version_id)
                    REFERENCES public.scholarship_versions (domain, organization_id, id)
                    ON DELETE CASCADE,
                CONSTRAINT v2_fk_source_uploader FOREIGN KEY (domain, uploaded_by)
                    REFERENCES public.accounts (domain, id),
                CONSTRAINT v2_uq_source_version_owner
                    UNIQUE (domain, organization_id, scholarship_version_id, id)
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.source_documents "
                f"PARTITION OF public.source_documents FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            """
            CREATE TABLE public.knowledge_chunks (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                organization_id uuid NOT NULL,
                scholarship_version_id uuid NOT NULL,
                source_document_id uuid NOT NULL,
                ordinal integer NOT NULL,
                page_number integer,
                section_title varchar(240) NOT NULL,
                provider_text text NOT NULL,
                search_vector tsvector GENERATED ALWAYS AS (
                    to_tsvector('english'::regconfig, coalesce(provider_text, ''::text))
                ) STORED,
                embedding_reference varchar(240),
                confirmation_status varchar(40) NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_knowledge_chunks PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_chunk_version_owner
                    FOREIGN KEY (domain, organization_id, scholarship_version_id)
                    REFERENCES public.scholarship_versions (domain, organization_id, id)
                    ON DELETE CASCADE,
                CONSTRAINT v2_fk_chunk_source_owner
                    FOREIGN KEY (
                        domain, organization_id, scholarship_version_id, source_document_id
                    ) REFERENCES public.source_documents (
                        domain, organization_id, scholarship_version_id, id
                    ) ON DELETE CASCADE,
                CONSTRAINT v2_uq_chunk_version_owner
                    UNIQUE (domain, organization_id, scholarship_version_id, id)
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.knowledge_chunks "
                f"PARTITION OF public.knowledge_chunks FOR VALUES IN ('{domain}')"
            )
        )
    op.execute(
        sa.text(
            "CREATE INDEX v2_ix_knowledge_chunks_search_vector "
            "ON public.knowledge_chunks USING gin (search_vector)"
        )
    )

    _execute_all(
        (
            """
            CREATE TABLE public.ai_extraction_drafts (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                organization_id uuid NOT NULL,
                scholarship_version_id uuid NOT NULL,
                model_identifier varchar(120) NOT NULL,
                prompt_version varchar(80) NOT NULL,
                extracted_content_json jsonb NOT NULL,
                source_mapping_json jsonb NOT NULL,
                status varchar(40) NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                confirmed_by uuid,
                confirmed_at timestamptz,
                CONSTRAINT v2_pk_ai_extraction_drafts PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_extraction_version_owner
                    FOREIGN KEY (domain, organization_id, scholarship_version_id)
                    REFERENCES public.scholarship_versions (domain, organization_id, id)
                    ON DELETE CASCADE,
                CONSTRAINT v2_fk_extraction_confirmer FOREIGN KEY (domain, confirmed_by)
                    REFERENCES public.accounts (domain, id)
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.ai_extraction_drafts "
                f"PARTITION OF public.ai_extraction_drafts FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            """
            CREATE TABLE public.application_templates (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                organization_id uuid NOT NULL,
                scholarship_version_id uuid NOT NULL,
                template_version integer NOT NULL,
                status varchar(40) NOT NULL,
                created_by uuid NOT NULL,
                confirmed_by uuid,
                confirmed_at timestamptz,
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_application_templates PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_template_version_owner
                    FOREIGN KEY (domain, organization_id, scholarship_version_id)
                    REFERENCES public.scholarship_versions (domain, organization_id, id)
                    ON DELETE CASCADE,
                CONSTRAINT v2_fk_template_creator FOREIGN KEY (domain, created_by)
                    REFERENCES public.accounts (domain, id),
                CONSTRAINT v2_fk_template_confirmer FOREIGN KEY (domain, confirmed_by)
                    REFERENCES public.accounts (domain, id),
                CONSTRAINT v2_uq_application_template_version
                    UNIQUE (domain, scholarship_version_id, template_version),
                CONSTRAINT v2_uq_template_version_owner
                    UNIQUE (domain, organization_id, scholarship_version_id, id),
                CONSTRAINT v2_uq_template_domain_id UNIQUE (domain, id)
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.application_templates "
                f"PARTITION OF public.application_templates FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            """
            CREATE TABLE public.application_template_fields (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                organization_id uuid NOT NULL,
                scholarship_version_id uuid NOT NULL,
                application_template_id uuid NOT NULL,
                field_key varchar(100) NOT NULL,
                label varchar(180) NOT NULL,
                help_text text NOT NULL,
                field_type public.application_field_type NOT NULL,
                required boolean NOT NULL,
                options_json jsonb,
                source_chunk_id uuid,
                sort_order integer NOT NULL,
                CONSTRAINT v2_pk_application_template_fields PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_field_template_owner FOREIGN KEY (
                    domain, organization_id, scholarship_version_id, application_template_id
                ) REFERENCES public.application_templates (
                    domain, organization_id, scholarship_version_id, id
                ) ON DELETE CASCADE,
                CONSTRAINT v2_fk_field_source_chunk FOREIGN KEY (
                    domain, organization_id, scholarship_version_id, source_chunk_id
                ) REFERENCES public.knowledge_chunks (
                    domain, organization_id, scholarship_version_id, id
                ),
                CONSTRAINT v2_uq_application_template_field_key
                    UNIQUE (domain, application_template_id, field_key),
                CONSTRAINT v2_uq_field_template_id
                    UNIQUE (domain, application_template_id, id)
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in PROVIDER_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.application_template_fields "
                f"PARTITION OF public.application_template_fields FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            """
            CREATE TABLE public.audit_events (
                domain public.ownership_domain NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                actor_account_id uuid,
                organization_id uuid,
                action varchar(120) NOT NULL,
                resource_type varchar(80) NOT NULL,
                resource_id uuid,
                safe_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_audit_events PRIMARY KEY (domain, id),
                CONSTRAINT v2_fk_audit_actor FOREIGN KEY (domain, actor_account_id)
                    REFERENCES public.accounts (domain, id),
                CONSTRAINT v2_fk_audit_organization FOREIGN KEY (domain, organization_id)
                    REFERENCES public.organizations (domain, id)
            ) PARTITION BY LIST (domain)
            """,
        )
    )
    for schema_name, domain in DOMAIN_PARTITIONS:
        op.execute(
            sa.text(
                f"CREATE TABLE {schema_name}.audit_events PARTITION OF public.audit_events "
                f"FOR VALUES IN ('{domain}')"
            )
        )

    _execute_all(
        (
            """
            CREATE TABLE student.student_settings (
                account_id uuid PRIMARY KEY,
                account_domain public.ownership_domain NOT NULL DEFAULT 'STUDENT',
                display_alias varchar(80),
                preferred_language varchar(10) NOT NULL DEFAULT 'en',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_ck_setting_student_domain CHECK (account_domain = 'STUDENT'),
                CONSTRAINT v2_fk_setting_account FOREIGN KEY (account_domain, account_id)
                    REFERENCES public.accounts (domain, id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE student.saved_scholarships (
                student_account_id uuid NOT NULL,
                scholarship_domain public.ownership_domain NOT NULL,
                scholarship_id uuid NOT NULL,
                student_domain public.ownership_domain NOT NULL DEFAULT 'STUDENT',
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_saved_scholarships PRIMARY KEY (
                    student_account_id, scholarship_domain, scholarship_id
                ),
                CONSTRAINT v2_ck_saved_student_domain CHECK (student_domain = 'STUDENT'),
                CONSTRAINT v2_fk_saved_student FOREIGN KEY (student_domain, student_account_id)
                    REFERENCES public.accounts (domain, id) ON DELETE CASCADE,
                CONSTRAINT v2_fk_saved_scholarship FOREIGN KEY (
                    scholarship_domain, scholarship_id
                ) REFERENCES public.scholarships (domain, id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE student.applications (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                student_domain public.ownership_domain NOT NULL DEFAULT 'STUDENT',
                student_account_id uuid NOT NULL,
                provider_domain public.ownership_domain NOT NULL,
                organization_id uuid NOT NULL,
                scholarship_version_id uuid NOT NULL,
                application_template_id uuid NOT NULL,
                status public.application_status NOT NULL DEFAULT 'DRAFT',
                is_synthetic boolean NOT NULL DEFAULT false,
                consent_recorded_at timestamptz,
                submitted_at timestamptz,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_ck_application_student_domain CHECK (student_domain = 'STUDENT'),
                CONSTRAINT v2_fk_application_student FOREIGN KEY (
                    student_domain, student_account_id
                ) REFERENCES public.accounts (domain, id),
                CONSTRAINT v2_fk_application_organization FOREIGN KEY (
                    provider_domain, organization_id
                ) REFERENCES public.organizations (domain, id),
                CONSTRAINT v2_fk_application_version_owner FOREIGN KEY (
                    provider_domain, organization_id, scholarship_version_id
                ) REFERENCES public.scholarship_versions (domain, organization_id, id),
                CONSTRAINT v2_fk_application_template_owner FOREIGN KEY (
                    provider_domain, organization_id, scholarship_version_id,
                    application_template_id
                ) REFERENCES public.application_templates (
                    domain, organization_id, scholarship_version_id, id
                ),
                CONSTRAINT v2_uq_application_template_context UNIQUE (
                    id, provider_domain, application_template_id
                )
            )
            """,
            "CREATE INDEX v2_ix_applications_student ON student.applications (student_account_id)",
            "CREATE INDEX v2_ix_applications_organization ON student.applications (provider_domain, organization_id)",
            """
            CREATE TABLE student.application_answers (
                application_id uuid NOT NULL,
                field_id uuid NOT NULL,
                provider_domain public.ownership_domain NOT NULL,
                application_template_id uuid NOT NULL,
                encrypted_value bytea NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_pk_application_answers PRIMARY KEY (application_id, field_id),
                CONSTRAINT v2_fk_answer_application_context FOREIGN KEY (
                    application_id, provider_domain, application_template_id
                ) REFERENCES student.applications (
                    id, provider_domain, application_template_id
                ) ON DELETE CASCADE,
                CONSTRAINT v2_fk_answer_template_field FOREIGN KEY (
                    provider_domain, application_template_id, field_id
                ) REFERENCES public.application_template_fields (
                    domain, application_template_id, id
                )
            )
            """,
            """
            CREATE TABLE student.application_events (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                application_id uuid NOT NULL,
                actor_domain public.ownership_domain,
                actor_account_id uuid,
                event_type varchar(80) NOT NULL,
                safe_message text NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT v2_fk_event_application FOREIGN KEY (application_id)
                    REFERENCES student.applications (id) ON DELETE CASCADE,
                CONSTRAINT v2_fk_event_actor FOREIGN KEY (actor_domain, actor_account_id)
                    REFERENCES public.accounts (domain, id)
            )
            """,
            "CREATE INDEX v2_ix_application_events_application ON student.application_events (application_id)",
        )
    )

    # Move identity and domain data. PLATFORM_AUTHORITY is intentionally not migrated.
    _execute_all(
        (
            """
            INSERT INTO public.accounts (
                domain, id, login_identifier, password_hash, realm, status,
                created_at, updated_at, last_login_at
            )
            SELECT DISTINCT
                CASE
                    WHEN a.realm::text = 'STUDENT' THEN 'STUDENT'
                    WHEN o.type::text = 'CENTRAL_GOVERNMENT' THEN 'CENTRAL_GOVERNMENT'
                    WHEN o.type::text = 'STATE_GOVERNMENT' THEN 'STATE_GOVERNMENT'
                    ELSE 'NGO_PRIVATE'
                END::public.ownership_domain,
                a.id, a.login_identifier, a.password_hash,
                a.realm::text::public.account_realm, a.status,
                a.created_at, a.updated_at, a.last_login_at
            FROM scholarsaathi_v1_legacy.accounts a
            LEFT JOIN scholarsaathi_v1_legacy.organization_members m
                ON m.account_id = a.id
            LEFT JOIN scholarsaathi_v1_legacy.organizations o
                ON o.id = m.organization_id
            WHERE a.realm::text <> 'PLATFORM_AUTHORITY'
            """,
            """
            INSERT INTO public.auth_sessions (
                domain, id, account_id, token_hash, expires_at, last_seen_at,
                revoked_at, user_agent, created_at
            )
            SELECT a.domain, s.id, s.account_id, s.token_hash, s.expires_at,
                   s.last_seen_at, s.revoked_at, s.user_agent, s.created_at
            FROM scholarsaathi_v1_legacy.auth_sessions s
            JOIN public.accounts a ON a.id = s.account_id
            """,
            """
            INSERT INTO student.student_settings (
                account_id, account_domain, display_alias, preferred_language,
                created_at, updated_at
            )
            SELECT s.account_id, 'STUDENT', s.display_alias, s.preferred_language,
                   s.created_at, s.updated_at
            FROM scholarsaathi_v1_legacy.student_settings s
            JOIN public.accounts a ON a.id = s.account_id AND a.domain = 'STUDENT'
            """,
            """
            INSERT INTO public.organizations (
                domain, id, slug, legal_name, display_name, type,
                jurisdiction_state_code, is_synthetic, created_at, updated_at
            )
            SELECT
                CASE
                    WHEN type::text = 'CENTRAL_GOVERNMENT' THEN 'CENTRAL_GOVERNMENT'
                    WHEN type::text = 'STATE_GOVERNMENT' THEN 'STATE_GOVERNMENT'
                    ELSE 'NGO_PRIVATE'
                END::public.ownership_domain,
                id, slug, legal_name, display_name, type,
                jurisdiction_state_code, is_synthetic, created_at, updated_at
            FROM scholarsaathi_v1_legacy.organizations
            """,
            """
            INSERT INTO public.organization_members (
                domain, id, organization_id, account_id, role, status, created_at
            )
            SELECT o.domain, m.id, m.organization_id, m.account_id,
                   m.role, m.status, m.created_at
            FROM scholarsaathi_v1_legacy.organization_members m
            JOIN public.organizations o ON o.id = m.organization_id
            JOIN public.accounts a ON a.id = m.account_id AND a.domain = o.domain
            """,
            """
            INSERT INTO public.scholarships (
                domain, id, organization_id, slug, current_published_version_id,
                lifecycle_status, is_synthetic, created_at, archived_at
            )
            SELECT o.domain, s.id, s.organization_id, s.slug, NULL,
                   s.lifecycle_status, s.is_synthetic, s.created_at, s.archived_at
            FROM scholarsaathi_v1_legacy.scholarships s
            JOIN public.organizations o ON o.id = s.organization_id
            """,
            """
            INSERT INTO public.scholarship_versions (
                domain, id, organization_id, scholarship_id, version_number,
                title, summary, knowledge_summary, academic_year, scope,
                applicable_state_codes, education_levels, course_families,
                category_tags, benefit_summary, benefit_amount_min,
                benefit_amount_max, application_opens_at, application_deadline_at,
                official_source_url, provider_helpdesk_url, publication_status,
                last_provider_confirmed_at, created_by, published_by,
                created_at, published_at
            )
            SELECT o.domain, v.id, s.organization_id, v.scholarship_id, v.version_number,
                   v.title, v.summary, v.knowledge_summary, v.academic_year, v.scope,
                   v.applicable_state_codes, v.education_levels, v.course_families,
                   v.category_tags, v.benefit_summary, v.benefit_amount_min,
                   v.benefit_amount_max, v.application_opens_at,
                   v.application_deadline_at, v.official_source_url,
                   v.provider_helpdesk_url,
                   CASE
                       WHEN v.publication_status::text IN (
                           'PUBLISHED', 'PAUSED', 'EXPIRED', 'ARCHIVED', 'SUPERSEDED'
                       ) THEN v.publication_status::text
                       ELSE 'DRAFT'
                   END::public.publication_status,
                   v.last_provider_verified_at, v.created_by,
                   CASE WHEN v.publication_status::text = 'PUBLISHED'
                        THEN v.created_by ELSE NULL END,
                   v.created_at, v.published_at
            FROM scholarsaathi_v1_legacy.scholarship_versions v
            JOIN scholarsaathi_v1_legacy.scholarships s ON s.id = v.scholarship_id
            JOIN public.organizations o ON o.id = s.organization_id
            """,
            """
            UPDATE public.scholarships target
            SET current_published_version_id = source.current_published_version_id
            FROM scholarsaathi_v1_legacy.scholarships source
            WHERE target.id = source.id
            """,
            """
            INSERT INTO public.source_documents (
                domain, id, organization_id, scholarship_version_id, display_name,
                source_kind, content_type, size_bytes, storage_key, source_url,
                checksum_sha256, extracted_text, usage_rights_confirmed_at,
                confirmation_status, uploaded_by, created_at
            )
            SELECT v.domain, d.id, v.organization_id, d.scholarship_version_id,
                   d.display_name, d.source_kind, d.content_type, d.size_bytes,
                   d.storage_key, d.source_url, d.checksum_sha256, d.extracted_text,
                   d.usage_rights_confirmed_at, 'OWNER_CONFIRMED', d.uploaded_by,
                   d.created_at
            FROM scholarsaathi_v1_legacy.source_documents d
            JOIN public.scholarship_versions v ON v.id = d.scholarship_version_id
            """,
            """
            INSERT INTO public.knowledge_chunks (
                domain, id, organization_id, scholarship_version_id,
                source_document_id, ordinal, page_number, section_title,
                provider_text, embedding_reference, confirmation_status, created_at
            )
            SELECT v.domain, c.id, v.organization_id, c.scholarship_version_id,
                   c.source_document_id, c.ordinal, c.page_number, c.section_title,
                   c.approved_text, c.embedding_reference, 'OWNER_CONFIRMED', c.created_at
            FROM scholarsaathi_v1_legacy.knowledge_chunks c
            JOIN public.scholarship_versions v ON v.id = c.scholarship_version_id
            """,
            """
            INSERT INTO public.ai_extraction_drafts (
                domain, id, organization_id, scholarship_version_id,
                model_identifier, prompt_version, extracted_content_json,
                source_mapping_json, status, created_at, confirmed_by, confirmed_at
            )
            SELECT v.domain, d.id, v.organization_id, d.scholarship_version_id,
                   d.model_identifier, d.prompt_version, d.extracted_content_json,
                   (d.source_mapping_json - 'approved_chunk_ids') ||
                       jsonb_build_object(
                           'confirmed_chunk_ids', d.source_mapping_json->'approved_chunk_ids'
                       ),
                   'OWNER_CONFIRMED', d.created_at,
                   CASE WHEN a.id IS NOT NULL THEN d.reviewed_by ELSE v.created_by END,
                   d.reviewed_at
            FROM scholarsaathi_v1_legacy.ai_extraction_drafts d
            JOIN public.scholarship_versions v ON v.id = d.scholarship_version_id
            LEFT JOIN public.accounts a ON a.domain = v.domain AND a.id = d.reviewed_by
            """,
            """
            INSERT INTO public.application_templates (
                domain, id, organization_id, scholarship_version_id,
                template_version, status, created_by, confirmed_by,
                confirmed_at, created_at
            )
            SELECT v.domain, t.id, v.organization_id, t.scholarship_version_id,
                   t.template_version, 'OWNER_CONFIRMED', t.created_by,
                   t.created_by, t.created_at, t.created_at
            FROM scholarsaathi_v1_legacy.application_templates t
            JOIN public.scholarship_versions v ON v.id = t.scholarship_version_id
            """,
            """
            INSERT INTO public.application_template_fields (
                domain, id, organization_id, scholarship_version_id,
                application_template_id, field_key, label, help_text,
                field_type, required, options_json, source_chunk_id, sort_order
            )
            SELECT t.domain, f.id, t.organization_id, t.scholarship_version_id,
                   f.application_template_id, f.field_key, f.label, f.help_text,
                   f.field_type, f.required, f.options_json, f.source_chunk_id,
                   f.sort_order
            FROM scholarsaathi_v1_legacy.application_template_fields f
            JOIN public.application_templates t ON t.id = f.application_template_id
            """,
            """
            INSERT INTO student.saved_scholarships (
                student_account_id, scholarship_domain, scholarship_id,
                student_domain, created_at
            )
            SELECT ss.student_account_id, s.domain, ss.scholarship_id,
                   'STUDENT', ss.created_at
            FROM scholarsaathi_v1_legacy.saved_scholarships ss
            JOIN public.scholarships s ON s.id = ss.scholarship_id
            """,
            """
            INSERT INTO student.applications (
                id, student_domain, student_account_id, provider_domain,
                organization_id, scholarship_version_id, application_template_id,
                status, is_synthetic, consent_recorded_at, submitted_at,
                created_at, updated_at
            )
            SELECT a.id, 'STUDENT', a.student_account_id, v.domain,
                   a.organization_id, a.scholarship_version_id,
                   a.application_template_id, a.status, a.is_synthetic,
                   a.consent_recorded_at, a.submitted_at, a.created_at, a.updated_at
            FROM scholarsaathi_v1_legacy.applications a
            JOIN public.scholarship_versions v ON v.id = a.scholarship_version_id
            """,
            """
            INSERT INTO student.application_answers (
                application_id, field_id, provider_domain,
                application_template_id, encrypted_value, updated_at
            )
            SELECT a.application_id, a.field_id, app.provider_domain,
                   app.application_template_id, a.encrypted_value, a.updated_at
            FROM scholarsaathi_v1_legacy.application_answers a
            JOIN student.applications app ON app.id = a.application_id
            """,
            """
            INSERT INTO student.application_events (
                id, application_id, actor_domain, actor_account_id,
                event_type, safe_message, created_at
            )
            SELECT e.id, e.application_id, a.domain,
                   CASE WHEN a.id IS NULL THEN NULL ELSE e.actor_account_id END,
                   e.event_type, e.safe_message, e.created_at
            FROM scholarsaathi_v1_legacy.application_events e
            LEFT JOIN public.accounts a ON a.id = e.actor_account_id
            """,
            """
            INSERT INTO public.audit_events (
                domain, id, actor_account_id, organization_id, action,
                resource_type, resource_id, safe_metadata_json, created_at
            )
            SELECT o.domain, e.id,
                   COALESCE(v.created_by, owner.account_id),
                   e.organization_id,
                   CASE WHEN e.action = 'SCHOLARSHIP_VERSION_PUBLISHED'
                        THEN 'SCHOLARSHIP_VERSION_PUBLISHED_BY_OWNER'
                        ELSE e.action END,
                   e.resource_type, e.resource_id,
                   e.safe_metadata_json || '{"publication_authority":"OWNER"}'::jsonb,
                   e.created_at
            FROM scholarsaathi_v1_legacy.audit_events e
            JOIN public.organizations o ON o.id = e.organization_id
            LEFT JOIN public.scholarship_versions v ON v.id = e.resource_id
            LEFT JOIN LATERAL (
                SELECT m.account_id
                FROM public.organization_members m
                WHERE m.domain = o.domain AND m.organization_id = o.id
                ORDER BY m.created_at
                LIMIT 1
            ) owner ON true
            """,
            """
            DO $$
            BEGIN
                IF (SELECT count(*) FROM public.organizations) <>
                   (SELECT count(*) FROM scholarsaathi_v1_legacy.organizations) THEN
                    RAISE EXCEPTION 'Organization count changed during schema migration';
                END IF;
                IF (SELECT count(*) FROM public.scholarships) <>
                   (SELECT count(*) FROM scholarsaathi_v1_legacy.scholarships) THEN
                    RAISE EXCEPTION 'Scholarship count changed during schema migration';
                END IF;
                IF (SELECT count(*) FROM student.applications) <>
                   (SELECT count(*) FROM scholarsaathi_v1_legacy.applications) THEN
                    RAISE EXCEPTION 'Application count changed during schema migration';
                END IF;
            END
            $$
            """,
            "DROP SCHEMA scholarsaathi_v1_legacy CASCADE",
            "DROP TYPE public.account_realm_v1_legacy",
            "DROP TYPE public.publication_status_v1_legacy",
            "DROP TYPE public.verification_status",
            "DROP TYPE public.review_decision",
        )
    )


def downgrade() -> None:
    # Build transaction-local snapshots using only types that survive the cutover.
    _execute_all(
        (
            "CREATE TEMP TABLE rb_accounts AS SELECT id, login_identifier, password_hash, realm::text AS realm, status, created_at, updated_at, last_login_at FROM public.accounts",
            "CREATE TEMP TABLE rb_sessions AS SELECT id, account_id, token_hash, expires_at, last_seen_at, revoked_at, user_agent, created_at FROM public.auth_sessions",
            "CREATE TEMP TABLE rb_settings AS SELECT account_id, display_alias, preferred_language, created_at, updated_at FROM student.student_settings",
            "CREATE TEMP TABLE rb_organizations AS SELECT id, slug, legal_name, display_name, type, jurisdiction_state_code, is_synthetic, created_at, updated_at FROM public.organizations",
            "CREATE TEMP TABLE rb_members AS SELECT id, organization_id, account_id, role, status, created_at FROM public.organization_members",
            "CREATE TEMP TABLE rb_scholarships AS SELECT id, organization_id, slug, current_published_version_id, lifecycle_status, is_synthetic, created_at, archived_at FROM public.scholarships",
            "CREATE TEMP TABLE rb_versions AS SELECT id, scholarship_id, version_number, title, summary, knowledge_summary, academic_year, scope, applicable_state_codes, education_levels, course_families, category_tags, benefit_summary, benefit_amount_min, benefit_amount_max, application_opens_at, application_deadline_at, official_source_url, provider_helpdesk_url, publication_status::text AS publication_status, last_provider_confirmed_at, created_by, published_by, created_at, published_at FROM public.scholarship_versions",
            "CREATE TEMP TABLE rb_sources AS SELECT id, scholarship_version_id, display_name, source_kind, content_type, size_bytes, storage_key, source_url, checksum_sha256, extracted_text, usage_rights_confirmed_at, confirmation_status, uploaded_by, created_at FROM public.source_documents",
            "CREATE TEMP TABLE rb_chunks AS SELECT id, scholarship_version_id, source_document_id, ordinal, page_number, section_title, provider_text, embedding_reference, confirmation_status, created_at FROM public.knowledge_chunks",
            "CREATE TEMP TABLE rb_extractions AS SELECT id, scholarship_version_id, model_identifier, prompt_version, extracted_content_json, source_mapping_json, status, created_at, confirmed_by, confirmed_at FROM public.ai_extraction_drafts",
            "CREATE TEMP TABLE rb_templates AS SELECT id, scholarship_version_id, template_version, status, created_by, confirmed_by, created_at FROM public.application_templates",
            "CREATE TEMP TABLE rb_fields AS SELECT id, application_template_id, field_key, label, help_text, field_type, required, options_json, source_chunk_id, sort_order FROM public.application_template_fields",
            "CREATE TEMP TABLE rb_saved AS SELECT student_account_id, scholarship_id, created_at FROM student.saved_scholarships",
            "CREATE TEMP TABLE rb_applications AS SELECT id, student_account_id, organization_id, scholarship_version_id, application_template_id, status, is_synthetic, consent_recorded_at, submitted_at, created_at, updated_at FROM student.applications",
            "CREATE TEMP TABLE rb_answers AS SELECT application_id, field_id, encrypted_value, updated_at FROM student.application_answers",
            "CREATE TEMP TABLE rb_events AS SELECT id, application_id, actor_account_id, event_type, safe_message, created_at FROM student.application_events",
            "CREATE TEMP TABLE rb_audits AS SELECT id, actor_account_id, organization_id, action, resource_type, resource_id, safe_metadata_json, created_at FROM public.audit_events",
            "DROP SCHEMA student CASCADE",
            "DROP SCHEMA central_government CASCADE",
            "DROP SCHEMA state_government CASCADE",
            "DROP SCHEMA ngo_private CASCADE",
        )
    )

    for table_name in reversed(
        (
            "accounts",
            "auth_sessions",
            "organizations",
            "organization_members",
            "scholarships",
            "scholarship_versions",
            "source_documents",
            "knowledge_chunks",
            "ai_extraction_drafts",
            "application_templates",
            "application_template_fields",
            "audit_events",
        )
    ):
        op.execute(sa.text(f"DROP TABLE IF EXISTS public.{table_name} CASCADE"))

    _execute_all(
        (
            "DROP TYPE public.ownership_domain",
            "DROP TYPE public.account_realm",
            "DROP TYPE public.publication_status",
        )
    )

    # Recreate the exact v1 structures, then map owner-controlled rows back into them.
    _initial_revision_module().upgrade()

    _execute_all(
        (
            """
            INSERT INTO public.accounts
            SELECT id, login_identifier, password_hash, realm::public.account_realm,
                   status, created_at, updated_at, last_login_at
            FROM rb_accounts
            """,
            "INSERT INTO public.auth_sessions SELECT * FROM rb_sessions",
            "INSERT INTO public.student_settings SELECT * FROM rb_settings",
            """
            INSERT INTO public.organizations (
                id, slug, legal_name, display_name, type, jurisdiction_state_code,
                verification_status, is_synthetic, verified_at, verified_by,
                suspended_at, created_at, updated_at
            )
            SELECT id, slug, legal_name, display_name, type, jurisdiction_state_code,
                   'VERIFIED', is_synthetic, created_at, NULL, NULL,
                   created_at, updated_at
            FROM rb_organizations
            """,
            "INSERT INTO public.organization_members SELECT * FROM rb_members",
            """
            INSERT INTO public.organization_verification_requests (
                id, organization_id, status, mock_evidence_reference,
                reviewer_account_id, decision_reason, submitted_at, reviewed_at
            )
            SELECT gen_random_uuid(), id, 'VERIFIED', NULL, NULL,
                   'Restored by downgrade from owner-controlled publication.',
                   created_at, created_at
            FROM rb_organizations
            """,
            """
            INSERT INTO public.scholarships (
                id, organization_id, slug, current_published_version_id,
                lifecycle_status, is_synthetic, created_at, archived_at
            )
            SELECT id, organization_id, slug, NULL, lifecycle_status,
                   is_synthetic, created_at, archived_at
            FROM rb_scholarships
            """,
            """
            INSERT INTO public.scholarship_versions (
                id, scholarship_id, version_number, title, summary,
                knowledge_summary, academic_year, scope, applicable_state_codes,
                education_levels, course_families, category_tags, benefit_summary,
                benefit_amount_min, benefit_amount_max, application_opens_at,
                application_deadline_at, official_source_url, provider_helpdesk_url,
                publication_status, last_provider_verified_at, created_by,
                submitted_by, approved_by, created_at, submitted_at, published_at
            )
            SELECT id, scholarship_id, version_number, title, summary,
                   knowledge_summary, academic_year, scope, applicable_state_codes,
                   education_levels, course_families, category_tags, benefit_summary,
                   benefit_amount_min, benefit_amount_max, application_opens_at,
                   application_deadline_at, official_source_url, provider_helpdesk_url,
                   publication_status::public.publication_status,
                   last_provider_confirmed_at, created_by,
                   CASE WHEN publication_status = 'PUBLISHED' THEN created_by ELSE NULL END,
                   published_by, created_at, published_at, published_at
            FROM rb_versions
            """,
            """
            UPDATE public.scholarships s
            SET current_published_version_id = rb.current_published_version_id
            FROM rb_scholarships rb
            WHERE s.id = rb.id
            """,
            """
            INSERT INTO public.source_documents (
                id, scholarship_version_id, display_name, source_kind,
                content_type, size_bytes, storage_key, source_url, checksum_sha256,
                extracted_text, usage_rights_confirmed_at, review_status,
                uploaded_by, created_at
            )
            SELECT id, scholarship_version_id, display_name, source_kind,
                   content_type, size_bytes, storage_key, source_url, checksum_sha256,
                   extracted_text, usage_rights_confirmed_at, confirmation_status,
                   uploaded_by, created_at
            FROM rb_sources
            """,
            """
            INSERT INTO public.knowledge_chunks (
                id, scholarship_version_id, source_document_id, ordinal,
                page_number, section_title, approved_text, embedding_reference,
                review_status, created_at
            )
            SELECT id, scholarship_version_id, source_document_id, ordinal,
                   page_number, section_title, provider_text, embedding_reference,
                   confirmation_status, created_at
            FROM rb_chunks
            """,
            """
            INSERT INTO public.ai_extraction_drafts (
                id, scholarship_version_id, model_identifier, prompt_version,
                extracted_content_json, source_mapping_json, status, created_at,
                reviewed_by, reviewed_at
            )
            SELECT id, scholarship_version_id, model_identifier, prompt_version,
                   extracted_content_json, source_mapping_json, status, created_at,
                   confirmed_by, confirmed_at
            FROM rb_extractions
            """,
            """
            INSERT INTO public.application_templates (
                id, scholarship_version_id, template_version, status,
                created_by, approved_by, created_at
            )
            SELECT id, scholarship_version_id, template_version, status,
                   created_by, confirmed_by, created_at
            FROM rb_templates
            """,
            "INSERT INTO public.application_template_fields SELECT * FROM rb_fields",
            """
            INSERT INTO public.publication_reviews (
                id, scholarship_version_id, reviewer_account_id,
                decision, reason, created_at
            )
            SELECT gen_random_uuid(), id, created_by, 'APPROVED',
                   'Restored by downgrade from direct owner publication.', created_at
            FROM rb_versions
            WHERE publication_status = 'PUBLISHED'
            """,
            "INSERT INTO public.saved_scholarships SELECT * FROM rb_saved",
            "INSERT INTO public.applications SELECT * FROM rb_applications",
            "INSERT INTO public.application_answers SELECT * FROM rb_answers",
            "INSERT INTO public.application_events SELECT * FROM rb_events",
            """
            INSERT INTO public.audit_events
            SELECT id, actor_account_id, organization_id,
                   CASE WHEN action = 'SCHOLARSHIP_VERSION_PUBLISHED_BY_OWNER'
                        THEN 'SCHOLARSHIP_VERSION_PUBLISHED' ELSE action END,
                   resource_type, resource_id,
                   safe_metadata_json - 'publication_authority', created_at
            FROM rb_audits
            """,
        )
    )
