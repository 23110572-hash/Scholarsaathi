"""Create the initial ScholarSaathi platform schema.

Revision ID: 20260822_0001
Revises: None
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260822_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

account_realm = postgresql.ENUM(
    "STUDENT",
    "ORGANIZATION_MEMBER",
    "PLATFORM_AUTHORITY",
    name="account_realm",
    create_type=False,
)
account_status = postgresql.ENUM(
    "ACTIVE", "LOCKED", "DISABLED", "DELETED", name="account_status", create_type=False
)
organization_type = postgresql.ENUM(
    "CENTRAL_GOVERNMENT",
    "STATE_GOVERNMENT",
    "PRIVATE_COMPANY",
    "NGO",
    name="organization_type",
    create_type=False,
)
verification_status = postgresql.ENUM(
    "PENDING_VERIFICATION",
    "VERIFIED",
    "REJECTED",
    "SUSPENDED",
    "WITHDRAWN",
    name="verification_status",
    create_type=False,
)
member_role = postgresql.ENUM(
    "OWNER",
    "CONTENT_EDITOR",
    "PUBLISHER",
    "APPLICATION_REVIEWER",
    name="member_role",
    create_type=False,
)
member_status = postgresql.ENUM(
    "INVITED", "ACTIVE", "REVOKED", name="member_status", create_type=False
)
scholarship_lifecycle = postgresql.ENUM(
    "ACTIVE", "PAUSED", "ARCHIVED", name="scholarship_lifecycle", create_type=False
)
publication_status = postgresql.ENUM(
    "DRAFT",
    "PROCESSING_SOURCE",
    "EXTRACTION_REVIEW",
    "CHANGES_REQUIRED",
    "READY_FOR_REVIEW",
    "IN_REVIEW",
    "PUBLISHED",
    "PAUSED",
    "EXPIRED",
    "ARCHIVED",
    "SUPERSEDED",
    "REJECTED",
    name="publication_status",
    create_type=False,
)
review_decision = postgresql.ENUM(
    "APPROVED",
    "CHANGES_REQUESTED",
    "REJECTED",
    name="review_decision",
    create_type=False,
)
application_status = postgresql.ENUM(
    "DRAFT",
    "READY_FOR_STUDENT_REVIEW",
    "SUBMITTED",
    "UNDER_ORGANIZATION_REVIEW",
    "CORRECTION_REQUESTED",
    "RESUBMITTED",
    "APPROVED",
    "REJECTED",
    "WITHDRAWN",
    name="application_status",
    create_type=False,
)
application_field_type = postgresql.ENUM(
    "TEXT",
    "NUMBER",
    "DATE",
    "SELECT",
    "MULTISELECT",
    "CHECKBOX",
    "TEXTAREA",
    name="application_field_type",
    create_type=False,
)

enum_types = (
    account_realm,
    account_status,
    organization_type,
    verification_status,
    member_role,
    member_status,
    scholarship_lifecycle,
    publication_status,
    review_decision,
    application_status,
    application_field_type,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    bind = op.get_bind()
    for enum_type in enum_types:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("login_identifier", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("realm", account_realm, nullable=False),
        sa.Column("status", account_status, nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("login_identifier", name="uq_accounts_login_identifier"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_account_id", "auth_sessions", ["account_id"])

    op.create_table(
        "student_settings",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_alias", sa.String(80)),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "organizations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("legal_name", sa.String(240), nullable=False),
        sa.Column("display_name", sa.String(180), nullable=False),
        sa.Column("type", organization_type, nullable=False),
        sa.Column("jurisdiction_state_code", sa.String(2)),
        sa.Column(
            "verification_status",
            verification_status,
            nullable=False,
            server_default="PENDING_VERIFICATION",
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "verified_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "type != 'STATE_GOVERNMENT' OR jurisdiction_state_code IS NOT NULL",
            name="ck_state_government_has_jurisdiction",
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.create_table(
        "organization_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", member_role, nullable=False),
        sa.Column("status", member_status, nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("organization_id", "account_id", name="uq_org_member"),
    )
    op.create_index(
        "ix_organization_members_organization_id",
        "organization_members",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_members_account_id", "organization_members", ["account_id"]
    )

    op.create_table(
        "organization_verification_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", verification_status, nullable=False),
        sa.Column("mock_evidence_reference", sa.String(240)),
        sa.Column(
            "reviewer_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("decision_reason", sa.Text()),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_org_verification_requests_organization_id",
        "organization_verification_requests",
        ["organization_id"],
    )

    op.create_table(
        "scholarships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("current_published_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "lifecycle_status",
            scholarship_lifecycle,
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "slug", name="uq_org_scholarship_slug"),
    )
    op.create_index("ix_scholarships_organization_id", "scholarships", ["organization_id"])

    op.create_table(
        "scholarship_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scholarship_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("knowledge_summary", sa.Text(), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("applicable_state_codes", postgresql.ARRAY(sa.String(2)), nullable=False),
        sa.Column("education_levels", postgresql.ARRAY(sa.String(60)), nullable=False),
        sa.Column("course_families", postgresql.ARRAY(sa.String(80)), nullable=False),
        sa.Column("category_tags", postgresql.ARRAY(sa.String(80)), nullable=False),
        sa.Column("benefit_summary", sa.Text(), nullable=False),
        sa.Column("benefit_amount_min", sa.Numeric(12, 2)),
        sa.Column("benefit_amount_max", sa.Numeric(12, 2)),
        sa.Column("application_opens_at", sa.DateTime(timezone=True)),
        sa.Column("application_deadline_at", sa.DateTime(timezone=True)),
        sa.Column("official_source_url", sa.Text(), nullable=False),
        sa.Column("provider_helpdesk_url", sa.Text(), nullable=False),
        sa.Column(
            "publication_status",
            publication_status,
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("last_provider_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "submitted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "application_deadline_at IS NULL OR application_opens_at IS NULL "
            "OR application_deadline_at >= application_opens_at",
            name="ck_scholarship_application_dates",
        ),
        sa.UniqueConstraint(
            "scholarship_id", "version_number", name="uq_scholarship_version_number"
        ),
    )
    op.create_index(
        "ix_scholarship_versions_scholarship_id",
        "scholarship_versions",
        ["scholarship_id"],
    )
    op.create_index(
        "ix_scholarship_versions_application_deadline_at",
        "scholarship_versions",
        ["application_deadline_at"],
    )
    op.create_index(
        "ix_scholarship_versions_publication_status",
        "scholarship_versions",
        ["publication_status"],
    )
    op.create_foreign_key(
        "fk_scholarships_current_published_version",
        "scholarships",
        "scholarship_versions",
        ["current_published_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "source_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scholarship_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarship_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("usage_rights_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_source_documents_scholarship_version_id",
        "source_documents",
        ["scholarship_version_id"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scholarship_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarship_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("section_title", sa.String(240), nullable=False),
        sa.Column("approved_text", sa.Text(), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english'::regconfig, coalesce(approved_text, ''::text))",
                persisted=True,
            ),
        ),
        sa.Column("embedding_reference", sa.String(240)),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_scholarship_version_id",
        "knowledge_chunks",
        ["scholarship_version_id"],
    )
    op.create_index(
        "ix_knowledge_chunks_search_vector",
        "knowledge_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.create_table(
        "ai_extraction_drafts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scholarship_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarship_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_identifier", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("extracted_content_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_mapping_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_ai_extraction_drafts_scholarship_version_id",
        "ai_extraction_drafts",
        ["scholarship_version_id"],
    )

    op.create_table(
        "publication_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scholarship_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarship_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("decision", review_decision, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_publication_reviews_scholarship_version_id",
        "publication_reviews",
        ["scholarship_version_id"],
    )

    op.create_table(
        "saved_scholarships",
        sa.Column(
            "student_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "scholarship_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarships.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "application_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scholarship_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarship_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "scholarship_version_id",
            "template_version",
            name="uq_application_template_version",
        ),
    )

    op.create_table(
        "application_template_fields",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "application_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(180), nullable=False),
        sa.Column("help_text", sa.Text(), nullable=False),
        sa.Column("field_type", application_field_type, nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("options_json", postgresql.JSONB()),
        sa.Column(
            "source_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_chunks.id", ondelete="SET NULL"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "application_template_id",
            "field_key",
            name="uq_application_template_field_key",
        ),
    )

    op.create_table(
        "applications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "student_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scholarship_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarship_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "application_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", application_status, nullable=False, server_default="DRAFT"),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_recorded_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_applications_student_account_id", "applications", ["student_account_id"]
    )
    op.create_index("ix_applications_organization_id", "applications", ["organization_id"])

    op.create_table(
        "application_answers",
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application_template_fields.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "application_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("safe_message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_application_events_application_id", "application_events", ["application_id"]
    )

    op.create_table(
        "audit_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "actor_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "safe_metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("application_events")
    op.drop_table("application_answers")
    op.drop_table("applications")
    op.drop_table("application_template_fields")
    op.drop_table("application_templates")
    op.drop_table("saved_scholarships")
    op.drop_table("publication_reviews")
    op.drop_table("ai_extraction_drafts")
    op.drop_table("knowledge_chunks")
    op.drop_table("source_documents")
    op.drop_constraint(
        "fk_scholarships_current_published_version", "scholarships", type_="foreignkey"
    )
    op.drop_table("scholarship_versions")
    op.drop_table("scholarships")
    op.drop_table("organization_verification_requests")
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_table("student_settings")
    op.drop_table("auth_sessions")
    op.drop_table("accounts")

    bind = op.get_bind()
    for enum_type in reversed(enum_types):
        enum_type.drop(bind, checkfirst=True)
