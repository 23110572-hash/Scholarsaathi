from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    OrganizationContext,
    require_organization,
    require_organization_write,
)
from app.models import (
    AIExtractionDraft,
    AuditEvent,
    KnowledgeChunk,
    MemberRole,
    Organization,
    PublicationStatus,
    Scholarship,
    ScholarshipLifecycle,
    ScholarshipVersion,
    SourceDocument,
)
from app.presenters import organization_summary, scholarship_card
from app.schemas import (
    MessageResponse,
    OrganizationSummary,
    ScholarshipCard,
    ScholarshipDraftCreate,
    ScholarshipListResponse,
)
from app.utils import slugify

router = APIRouter(prefix="/api", tags=["organizations"])

PUBLISHING_ROLES = {MemberRole.OWNER, MemberRole.CONTENT_EDITOR, MemberRole.PUBLISHER}


def _assert_publishing_role(context: OrganizationContext) -> None:
    if context.membership.role not in PUBLISHING_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Publishing role required")


def _unique_scholarship_slug(
    db: Session,
    context: OrganizationContext,
    title: str,
) -> str:
    base = slugify(title, 150)
    candidate = base
    suffix = 1
    while db.scalar(
        select(Scholarship.id).where(
            Scholarship.domain == context.organization.domain,
            Scholarship.organization_id == context.organization.id,
            Scholarship.slug == candidate,
        )
    ):
        suffix += 1
        candidate = f"{base[:145]}-{suffix}"
    return candidate


@router.get("/organizations/me", response_model=OrganizationSummary)
def my_organization(
    context: OrganizationContext = Depends(require_organization),
) -> OrganizationSummary:
    return organization_summary(context.organization, context.membership)


@router.get("/organizations/me/scholarships", response_model=ScholarshipListResponse)
def my_scholarships(
    context: OrganizationContext = Depends(require_organization),
    db: Session = Depends(get_db),
) -> ScholarshipListResponse:
    domain = context.organization.domain
    rows = db.execute(
        select(Scholarship, ScholarshipVersion, Organization)
        .join(
            ScholarshipVersion,
            and_(
                ScholarshipVersion.domain == Scholarship.domain,
                ScholarshipVersion.scholarship_id == Scholarship.id,
            ),
        )
        .join(
            Organization,
            and_(
                Organization.domain == Scholarship.domain,
                Organization.id == Scholarship.organization_id,
            ),
        )
        .where(
            Scholarship.domain == domain,
            Scholarship.organization_id == context.organization.id,
        )
        .order_by(
            Scholarship.created_at.desc(),
            ScholarshipVersion.version_number.desc(),
        )
    ).all()
    latest: dict[uuid.UUID, tuple[Scholarship, ScholarshipVersion, Organization]] = {}
    for row in rows:
        latest.setdefault(row[0].id, row)
    cards = [scholarship_card(*row) for row in latest.values()]
    return ScholarshipListResponse(items=cards, total=len(cards))


@router.post(
    "/organizations/me/scholarships",
    response_model=ScholarshipCard,
    status_code=status.HTTP_201_CREATED,
)
def create_scholarship_draft(
    payload: ScholarshipDraftCreate,
    context: OrganizationContext = Depends(require_organization_write),
    db: Session = Depends(get_db),
) -> ScholarshipCard:
    _assert_publishing_role(context)
    now = datetime.now(UTC)
    domain = context.organization.domain
    scholarship = Scholarship(
        domain=domain,
        organization_id=context.organization.id,
        slug=_unique_scholarship_slug(db, context, payload.title),
        lifecycle_status=ScholarshipLifecycle.ACTIVE,
        is_synthetic=context.organization.is_synthetic,
    )
    db.add(scholarship)
    db.flush()

    source_text = "\n\n".join(
        f"{section.section_title}\n{section.text}" for section in payload.source_sections
    )
    version = ScholarshipVersion(
        domain=domain,
        organization_id=context.organization.id,
        scholarship_id=scholarship.id,
        version_number=1,
        title=payload.title,
        summary=payload.summary,
        knowledge_summary=source_text,
        academic_year=payload.academic_year,
        scope=payload.scope.upper(),
        applicable_state_codes=payload.applicable_state_codes,
        education_levels=payload.education_levels,
        course_families=payload.course_families,
        category_tags=payload.category_tags,
        benefit_summary=payload.benefit_summary,
        benefit_amount_min=payload.benefit_amount_min,
        benefit_amount_max=payload.benefit_amount_max,
        application_opens_at=payload.application_opens_at,
        application_deadline_at=payload.application_deadline_at,
        official_source_url=str(payload.official_source_url),
        provider_helpdesk_url=str(payload.provider_helpdesk_url),
        publication_status=PublicationStatus.DRAFT,
        last_provider_confirmed_at=now,
        created_by=context.auth.account.id,
    )
    db.add(version)
    db.flush()

    source = SourceDocument(
        domain=domain,
        organization_id=context.organization.id,
        scholarship_version_id=version.id,
        display_name=f"{payload.title} — Provider-entered source",
        source_kind="PROVIDER_ENTERED_TEXT",
        content_type="text/plain",
        size_bytes=len(source_text.encode("utf-8")),
        storage_key=None,
        source_url=str(payload.official_source_url),
        checksum_sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        extracted_text=source_text,
        usage_rights_confirmed_at=now,
        confirmation_status="OWNER_CONFIRMED",
        uploaded_by=context.auth.account.id,
    )
    db.add(source)
    db.flush()

    chunk_ids: list[str] = []
    for ordinal, section in enumerate(payload.source_sections, start=1):
        chunk = KnowledgeChunk(
            domain=domain,
            organization_id=context.organization.id,
            scholarship_version_id=version.id,
            source_document_id=source.id,
            ordinal=ordinal,
            page_number=ordinal,
            section_title=section.section_title,
            provider_text=section.text,
            confirmation_status="OWNER_CONFIRMED",
        )
        db.add(chunk)
        db.flush()
        chunk_ids.append(str(chunk.id))

    db.add_all(
        [
            AIExtractionDraft(
                domain=domain,
                organization_id=context.organization.id,
                scholarship_version_id=version.id,
                model_identifier="provider-structured-entry",
                prompt_version="owner-intake-v2",
                extracted_content_json=payload.model_dump(mode="json"),
                source_mapping_json={"confirmed_chunk_ids": chunk_ids},
                status="OWNER_CONFIRMED",
                confirmed_by=context.auth.account.id,
                confirmed_at=now,
            ),
            AuditEvent(
                domain=domain,
                actor_account_id=context.auth.account.id,
                organization_id=context.organization.id,
                action="SCHOLARSHIP_DRAFT_CREATED_BY_OWNER",
                resource_type="scholarship_version",
                resource_id=version.id,
                safe_metadata_json={"version_number": 1},
            ),
        ]
    )
    db.commit()
    return scholarship_card(scholarship, version, context.organization)


@router.post(
    "/organizations/me/scholarship-versions/{version_id}/publish",
    response_model=MessageResponse,
)
def publish_scholarship_version(
    version_id: uuid.UUID,
    context: OrganizationContext = Depends(require_organization_write),
    db: Session = Depends(get_db),
) -> MessageResponse:
    _assert_publishing_role(context)
    domain = context.organization.domain
    row = db.execute(
        select(ScholarshipVersion, Scholarship)
        .join(
            Scholarship,
            and_(
                Scholarship.domain == ScholarshipVersion.domain,
                Scholarship.id == ScholarshipVersion.scholarship_id,
            ),
        )
        .where(
            ScholarshipVersion.domain == domain,
            ScholarshipVersion.id == version_id,
            Scholarship.organization_id == context.organization.id,
        )
    ).one_or_none()
    if not row:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Scholarship version was not found in your organization",
        )
    version, scholarship = row
    if version.publication_status != PublicationStatus.DRAFT:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only an owner draft can be published directly",
        )

    chunk_count = db.scalar(
        select(KnowledgeChunk.id)
        .where(
            KnowledgeChunk.domain == domain,
            KnowledgeChunk.organization_id == context.organization.id,
            KnowledgeChunk.scholarship_version_id == version.id,
            KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
        )
        .limit(1)
    )
    if not chunk_count:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "At least one provider-confirmed source section is required",
        )

    now = datetime.now(UTC)
    previous_version_id = scholarship.current_published_version_id
    if previous_version_id:
        previous = db.scalar(
            select(ScholarshipVersion).where(
                ScholarshipVersion.domain == domain,
                ScholarshipVersion.id == previous_version_id,
                ScholarshipVersion.organization_id == context.organization.id,
            )
        )
        if previous:
            previous.publication_status = PublicationStatus.SUPERSEDED

    version.publication_status = PublicationStatus.PUBLISHED
    version.published_by = context.auth.account.id
    version.published_at = now
    version.last_provider_confirmed_at = now
    scholarship.current_published_version_id = version.id
    db.add(
        AuditEvent(
            domain=domain,
            actor_account_id=context.auth.account.id,
            organization_id=context.organization.id,
            action="SCHOLARSHIP_VERSION_PUBLISHED_BY_OWNER",
            resource_type="scholarship_version",
            resource_id=version.id,
            safe_metadata_json={
                "previous_version_id": (
                    str(previous_version_id) if previous_version_id else None
                ),
                "publication_authority": "OWNER",
                "source_sections": 1,
            },
        )
    )
    db.commit()
    return MessageResponse(
        message="Published directly by your organization; no platform approval is required"
    )
