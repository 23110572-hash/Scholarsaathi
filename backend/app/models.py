from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OwnershipDomain(enum.StrEnum):
    STUDENT = "STUDENT"
    CENTRAL_GOVERNMENT = "CENTRAL_GOVERNMENT"
    STATE_GOVERNMENT = "STATE_GOVERNMENT"
    NGO_PRIVATE = "NGO_PRIVATE"


class AccountRealm(enum.StrEnum):
    STUDENT = "STUDENT"
    ORGANIZATION_MEMBER = "ORGANIZATION_MEMBER"


class AccountStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    DISABLED = "DISABLED"
    DELETED = "DELETED"


class OrganizationType(enum.StrEnum):
    CENTRAL_GOVERNMENT = "CENTRAL_GOVERNMENT"
    STATE_GOVERNMENT = "STATE_GOVERNMENT"
    PRIVATE_COMPANY = "PRIVATE_COMPANY"
    NGO = "NGO"


class MemberRole(enum.StrEnum):
    OWNER = "OWNER"
    CONTENT_EDITOR = "CONTENT_EDITOR"
    PUBLISHER = "PUBLISHER"
    APPLICATION_REVIEWER = "APPLICATION_REVIEWER"


class MemberStatus(enum.StrEnum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class ScholarshipLifecycle(enum.StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class PublicationStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"
    SUPERSEDED = "SUPERSEDED"


class ApplicationStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_STUDENT_REVIEW = "READY_FOR_STUDENT_REVIEW"
    SUBMITTED = "SUBMITTED"
    UNDER_ORGANIZATION_REVIEW = "UNDER_ORGANIZATION_REVIEW"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"
    RESUBMITTED = "RESUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class ApplicationFieldType(enum.StrEnum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    DATE = "DATE"
    SELECT = "SELECT"
    MULTISELECT = "MULTISELECT"
    CHECKBOX = "CHECKBOX"
    TEXTAREA = "TEXTAREA"


def _enum(enum_class: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_class, name=name, schema="public")


def ownership_domain_for_type(organization_type: OrganizationType) -> OwnershipDomain:
    if organization_type == OrganizationType.CENTRAL_GOVERNMENT:
        return OwnershipDomain.CENTRAL_GOVERNMENT
    if organization_type == OrganizationType.STATE_GOVERNMENT:
        return OwnershipDomain.STATE_GOVERNMENT
    return OwnershipDomain.NGO_PRIVATE


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("domain", "login_identifier", name="v2_uq_account_login_domain"),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    login_identifier: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    realm: Mapped[AccountRealm] = mapped_column(
        _enum(AccountRealm, "account_realm"), nullable=False
    )
    status: Mapped[AccountStatus] = mapped_column(
        _enum(AccountStatus, "account_status"),
        nullable=False,
        default=AccountStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "account_id"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_session_account",
            ondelete="CASCADE",
        ),
        UniqueConstraint("domain", "token_hash", name="v2_uq_session_token_domain"),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class State(Base):
    __tablename__ = "states"
    __table_args__ = {"schema": "state_government"}

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_union_territory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StudentSetting(Base):
    __tablename__ = "student_settings"
    __table_args__ = (
        CheckConstraint("account_domain = 'STUDENT'", name="v2_ck_setting_student_domain"),
        ForeignKeyConstraint(
            ["account_domain", "account_id"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_setting_account",
            ondelete="CASCADE",
        ),
        {"schema": "student"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    account_domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"),
        nullable=False,
        default=OwnershipDomain.STUDENT,
    )
    display_alias: Mapped[str | None] = mapped_column(String(80))
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "(domain = 'CENTRAL_GOVERNMENT' AND type = 'CENTRAL_GOVERNMENT') OR "
            "(domain = 'STATE_GOVERNMENT' AND type = 'STATE_GOVERNMENT' "
            "AND jurisdiction_state_code IS NOT NULL) OR "
            "(domain = 'NGO_PRIVATE' AND type IN ('NGO', 'PRIVATE_COMPANY'))",
            name="v2_ck_organization_domain_type",
        ),
        UniqueConstraint("domain", "slug", name="v2_uq_organization_slug_domain"),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    type: Mapped[OrganizationType] = mapped_column(
        _enum(OrganizationType, "organization_type"), nullable=False
    )
    jurisdiction_state_code: Mapped[str | None] = mapped_column(String(2))
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "organization_id"],
            ["public.organizations.domain", "public.organizations.id"],
            name="v2_fk_member_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["domain", "account_id"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_member_account",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "domain", "organization_id", "account_id", name="v2_uq_organization_member"
        ),
        UniqueConstraint("domain", "account_id", name="v2_uq_account_one_organization"),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[MemberRole] = mapped_column(
        _enum(MemberRole, "member_role"), nullable=False
    )
    status: Mapped[MemberStatus] = mapped_column(
        _enum(MemberStatus, "member_status"),
        nullable=False,
        default=MemberStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Scholarship(Base):
    __tablename__ = "scholarships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "organization_id"],
            ["public.organizations.domain", "public.organizations.id"],
            name="v2_fk_scholarship_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["domain", "organization_id", "id", "current_published_version_id"],
            [
                "public.scholarship_versions.domain",
                "public.scholarship_versions.organization_id",
                "public.scholarship_versions.scholarship_id",
                "public.scholarship_versions.id",
            ],
            name="v2_fk_scholarship_current_version",
            use_alter=True,
        ),
        UniqueConstraint(
            "domain", "organization_id", "slug", name="v2_uq_organization_scholarship_slug"
        ),
        UniqueConstraint(
            "domain", "organization_id", "id", name="v2_uq_scholarship_owner"
        ),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    current_published_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lifecycle_status: Mapped[ScholarshipLifecycle] = mapped_column(
        _enum(ScholarshipLifecycle, "scholarship_lifecycle"),
        nullable=False,
        default=ScholarshipLifecycle.ACTIVE,
    )
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScholarshipVersion(Base):
    __tablename__ = "scholarship_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "organization_id", "scholarship_id"],
            [
                "public.scholarships.domain",
                "public.scholarships.organization_id",
                "public.scholarships.id",
            ],
            name="v2_fk_version_scholarship_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["domain", "created_by"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_version_creator",
        ),
        ForeignKeyConstraint(
            ["domain", "published_by"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_version_publisher",
        ),
        UniqueConstraint(
            "domain",
            "scholarship_id",
            "version_number",
            name="v2_uq_scholarship_version_number",
        ),
        UniqueConstraint(
            "domain",
            "organization_id",
            "scholarship_id",
            "id",
            name="v2_uq_version_scholarship_owner",
        ),
        UniqueConstraint(
            "domain", "organization_id", "id", name="v2_uq_version_owner"
        ),
        CheckConstraint(
            "application_deadline_at IS NULL OR application_opens_at IS NULL "
            "OR application_deadline_at >= application_opens_at",
            name="v2_ck_scholarship_application_dates",
        ),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scholarship_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_summary: Mapped[str] = mapped_column(Text, nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    applicable_state_codes: Mapped[list[str]] = mapped_column(ARRAY(String(2)))
    education_levels: Mapped[list[str]] = mapped_column(ARRAY(String(60)))
    course_families: Mapped[list[str]] = mapped_column(ARRAY(String(80)))
    category_tags: Mapped[list[str]] = mapped_column(ARRAY(String(80)))
    benefit_summary: Mapped[str] = mapped_column(Text, nullable=False)
    benefit_amount_min: Mapped[float | None] = mapped_column(Numeric(12, 2))
    benefit_amount_max: Mapped[float | None] = mapped_column(Numeric(12, 2))
    application_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    official_source_url: Mapped[str] = mapped_column(Text, nullable=False)
    provider_helpdesk_url: Mapped[str] = mapped_column(Text, nullable=False)
    publication_status: Mapped[PublicationStatus] = mapped_column(
        _enum(PublicationStatus, "publication_status"),
        nullable=False,
        default=PublicationStatus.DRAFT,
    )
    last_provider_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "organization_id", "scholarship_version_id"],
            [
                "public.scholarship_versions.domain",
                "public.scholarship_versions.organization_id",
                "public.scholarship_versions.id",
            ],
            name="v2_fk_source_version_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["domain", "uploaded_by"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_source_uploader",
        ),
        UniqueConstraint(
            "domain", "organization_id", "scholarship_version_id", "id",
            name="v2_uq_source_version_owner",
        ),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scholarship_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    usage_rights_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confirmation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "organization_id", "scholarship_version_id"],
            [
                "public.scholarship_versions.domain",
                "public.scholarship_versions.organization_id",
                "public.scholarship_versions.id",
            ],
            name="v2_fk_chunk_version_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["domain", "organization_id", "scholarship_version_id", "source_document_id"],
            [
                "public.source_documents.domain",
                "public.source_documents.organization_id",
                "public.source_documents.scholarship_version_id",
                "public.source_documents.id",
            ],
            name="v2_fk_chunk_source_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "domain", "organization_id", "scholarship_version_id", "id",
            name="v2_uq_chunk_version_owner",
        ),
        Index("v2_ix_knowledge_chunks_search_vector", "search_vector", postgresql_using="gin"),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scholarship_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str] = mapped_column(String(240), nullable=False)
    provider_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english'::regconfig, coalesce(provider_text, ''::text))",
            persisted=True,
        ),
    )
    embedding_reference: Mapped[str | None] = mapped_column(String(240))
    confirmation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AIExtractionDraft(Base):
    __tablename__ = "ai_extraction_drafts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "organization_id", "scholarship_version_id"],
            [
                "public.scholarship_versions.domain",
                "public.scholarship_versions.organization_id",
                "public.scholarship_versions.id",
            ],
            name="v2_fk_extraction_version_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["domain", "confirmed_by"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_extraction_confirmer",
        ),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scholarship_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    extracted_content_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_mapping_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApplicationTemplate(Base):
    __tablename__ = "application_templates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "organization_id", "scholarship_version_id"],
            [
                "public.scholarship_versions.domain",
                "public.scholarship_versions.organization_id",
                "public.scholarship_versions.id",
            ],
            name="v2_fk_template_version_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["domain", "created_by"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_template_creator",
        ),
        ForeignKeyConstraint(
            ["domain", "confirmed_by"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_template_confirmer",
        ),
        UniqueConstraint(
            "domain", "scholarship_version_id", "template_version",
            name="v2_uq_application_template_version",
        ),
        UniqueConstraint(
            "domain", "organization_id", "scholarship_version_id", "id",
            name="v2_uq_template_version_owner",
        ),
        UniqueConstraint(
            "domain", "id", name="v2_uq_template_domain_id"
        ),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scholarship_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApplicationTemplateField(Base):
    __tablename__ = "application_template_fields"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "organization_id", "scholarship_version_id", "application_template_id"],
            [
                "public.application_templates.domain",
                "public.application_templates.organization_id",
                "public.application_templates.scholarship_version_id",
                "public.application_templates.id",
            ],
            name="v2_fk_field_template_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["domain", "organization_id", "scholarship_version_id", "source_chunk_id"],
            [
                "public.knowledge_chunks.domain",
                "public.knowledge_chunks.organization_id",
                "public.knowledge_chunks.scholarship_version_id",
                "public.knowledge_chunks.id",
            ],
            name="v2_fk_field_source_chunk",
        ),
        UniqueConstraint(
            "domain", "application_template_id", "field_key",
            name="v2_uq_application_template_field_key",
        ),
        UniqueConstraint(
            "domain", "application_template_id", "id",
            name="v2_uq_field_template_id",
        ),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scholarship_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    application_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    help_text: Mapped[str] = mapped_column(Text, nullable=False)
    field_type: Mapped[ApplicationFieldType] = mapped_column(
        _enum(ApplicationFieldType, "application_field_type"), nullable=False
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    options_json: Mapped[list[str] | None] = mapped_column(JSONB)
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class SavedScholarship(Base):
    __tablename__ = "saved_scholarships"
    __table_args__ = (
        CheckConstraint("student_domain = 'STUDENT'", name="v2_ck_saved_student_domain"),
        ForeignKeyConstraint(
            ["student_domain", "student_account_id"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_saved_student",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["scholarship_domain", "scholarship_id"],
            ["public.scholarships.domain", "public.scholarships.id"],
            name="v2_fk_saved_scholarship",
            ondelete="CASCADE",
        ),
        {"schema": "student"},
    )

    student_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    scholarship_domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    scholarship_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    student_domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"),
        nullable=False,
        default=OwnershipDomain.STUDENT,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("student_domain = 'STUDENT'", name="v2_ck_application_student_domain"),
        ForeignKeyConstraint(
            ["student_domain", "student_account_id"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_application_student",
        ),
        ForeignKeyConstraint(
            ["provider_domain", "organization_id"],
            ["public.organizations.domain", "public.organizations.id"],
            name="v2_fk_application_organization",
        ),
        ForeignKeyConstraint(
            ["provider_domain", "organization_id", "scholarship_version_id"],
            [
                "public.scholarship_versions.domain",
                "public.scholarship_versions.organization_id",
                "public.scholarship_versions.id",
            ],
            name="v2_fk_application_version_owner",
        ),
        ForeignKeyConstraint(
            [
                "provider_domain",
                "organization_id",
                "scholarship_version_id",
                "application_template_id",
            ],
            [
                "public.application_templates.domain",
                "public.application_templates.organization_id",
                "public.application_templates.scholarship_version_id",
                "public.application_templates.id",
            ],
            name="v2_fk_application_template_owner",
        ),
        UniqueConstraint(
            "id", "provider_domain", "application_template_id",
            name="v2_uq_application_template_context",
        ),
        {"schema": "student"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"),
        nullable=False,
        default=OwnershipDomain.STUDENT,
    )
    student_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scholarship_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    application_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        _enum(ApplicationStatus, "application_status"),
        nullable=False,
        default=ApplicationStatus.DRAFT,
    )
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["application_id", "provider_domain", "application_template_id"],
            [
                "student.applications.id",
                "student.applications.provider_domain",
                "student.applications.application_template_id",
            ],
            name="v2_fk_answer_application_context",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["provider_domain", "application_template_id", "field_id"],
            [
                "public.application_template_fields.domain",
                "public.application_template_fields.application_template_id",
                "public.application_template_fields.id",
            ],
            name="v2_fk_answer_template_field",
        ),
        {"schema": "student"},
    )

    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    provider_domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), nullable=False
    )
    application_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["application_id"],
            ["student.applications.id"],
            name="v2_fk_event_application",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["actor_domain", "actor_account_id"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_event_actor",
        ),
        {"schema": "student"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_domain: Mapped[OwnershipDomain | None] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain")
    )
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    safe_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["domain", "actor_account_id"],
            ["public.accounts.domain", "public.accounts.id"],
            name="v2_fk_audit_actor",
        ),
        ForeignKeyConstraint(
            ["domain", "organization_id"],
            ["public.organizations.domain", "public.organizations.id"],
            name="v2_fk_audit_organization",
        ),
        {"schema": "public", "postgresql_partition_by": "LIST (domain)"},
    )

    domain: Mapped[OwnershipDomain] = mapped_column(
        _enum(OwnershipDomain, "ownership_domain"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    safe_metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
