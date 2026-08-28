from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.scholarships import published_scholarship_query
from app.core.config import get_settings
from app.database import get_db
from app.dependencies import (
    AuthContext,
    OrganizationContext,
    require_organization,
    require_organization_write,
    require_student,
    require_student_write,
)
from app.models import (
    Application,
    ApplicationAnswer,
    ApplicationEvent,
    ApplicationStatus,
    ApplicationTemplate,
    ApplicationTemplateField,
    MemberRole,
    Organization,
    OwnershipDomain,
    Scholarship,
    ScholarshipVersion,
)
from app.schemas import (
    ApplicationAnswersUpdate,
    ApplicationCreateRequest,
    ApplicationCreateResponse,
    ApplicationDetailResponse,
    ApplicationEventResponse,
    ApplicationFieldResponse,
    ApplicationListItem,
    ApplicationStatusUpdate,
    MessageResponse,
)

router = APIRouter(prefix="/api", tags=["applications"])
settings = get_settings()


def _student_application_row(
    db: Session,
    application_id: uuid.UUID,
    student_id: uuid.UUID,
):
    return db.execute(
        select(Application, Scholarship, ScholarshipVersion, Organization)
        .join(
            ScholarshipVersion,
            and_(
                ScholarshipVersion.domain == Application.provider_domain,
                ScholarshipVersion.id == Application.scholarship_version_id,
            ),
        )
        .join(
            Scholarship,
            and_(
                Scholarship.domain == ScholarshipVersion.domain,
                Scholarship.id == ScholarshipVersion.scholarship_id,
            ),
        )
        .join(
            Organization,
            and_(
                Organization.domain == Application.provider_domain,
                Organization.id == Application.organization_id,
            ),
        )
        .where(
            Application.id == application_id,
            Application.student_domain == OwnershipDomain.STUDENT,
            Application.student_account_id == student_id,
        )
    ).one_or_none()


def _application_detail(
    db: Session,
    application: Application,
    scholarship: Scholarship,
    version: ScholarshipVersion,
    organization: Organization,
) -> ApplicationDetailResponse:
    fields = db.scalars(
        select(ApplicationTemplateField)
        .where(
            ApplicationTemplateField.domain == application.provider_domain,
            ApplicationTemplateField.application_template_id
            == application.application_template_id,
        )
        .order_by(ApplicationTemplateField.sort_order)
    ).all()
    answered_field_ids = list(
        db.scalars(
            select(ApplicationAnswer.field_id).where(
                ApplicationAnswer.application_id == application.id
            )
        ).all()
    )
    events = db.scalars(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application.id)
        .order_by(ApplicationEvent.created_at)
    ).all()
    return ApplicationDetailResponse(
        id=application.id,
        status=application.status,
        scholarship_id=scholarship.id,
        scholarship_title=version.title,
        organization_name=organization.display_name,
        is_synthetic=application.is_synthetic,
        consent_recorded_at=application.consent_recorded_at,
        submitted_at=application.submitted_at,
        fields=[
            ApplicationFieldResponse(
                id=field.id,
                field_key=field.field_key,
                label=field.label,
                help_text=field.help_text,
                field_type=field.field_type,
                required=field.required,
                options=field.options_json,
                sort_order=field.sort_order,
            )
            for field in fields
        ],
        answered_field_ids=answered_field_ids,
        events=[
            ApplicationEventResponse(
                event_type=event.event_type,
                safe_message=event.safe_message,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


@router.post(
    "/scholarships/{scholarship_id}/applications",
    response_model=ApplicationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    scholarship_id: uuid.UUID,
    payload: ApplicationCreateRequest,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> ApplicationCreateResponse:
    if not payload.consent_to_store_application:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Explicit consent is required before creating a stored application",
        )

    row = db.execute(
        published_scholarship_query().where(Scholarship.id == scholarship_id)
    ).one_or_none()
    if not row:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Published scholarship was not found",
        )
    scholarship, version, _organization = row
    template = db.scalar(
        select(ApplicationTemplate)
        .where(
            ApplicationTemplate.domain == scholarship.domain,
            ApplicationTemplate.organization_id == scholarship.organization_id,
            ApplicationTemplate.scholarship_version_id == version.id,
            ApplicationTemplate.status == "OWNER_CONFIRMED",
        )
        .order_by(ApplicationTemplate.template_version.desc())
    )
    if not template:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This scholarship does not have a common application template",
        )

    existing = db.scalar(
        select(Application).where(
            Application.student_domain == OwnershipDomain.STUDENT,
            Application.student_account_id == auth.account.id,
            Application.provider_domain == scholarship.domain,
            Application.scholarship_version_id == version.id,
            Application.status.in_(
                [
                    ApplicationStatus.DRAFT,
                    ApplicationStatus.READY_FOR_STUDENT_REVIEW,
                    ApplicationStatus.CORRECTION_REQUESTED,
                ]
            ),
        )
    )
    if existing:
        return ApplicationCreateResponse(
            id=existing.id,
            status=existing.status,
            scholarship_version_id=existing.scholarship_version_id,
            application_template_id=existing.application_template_id,
            is_synthetic=existing.is_synthetic,
        )

    now = datetime.now(UTC)
    application = Application(
        student_domain=OwnershipDomain.STUDENT,
        student_account_id=auth.account.id,
        provider_domain=scholarship.domain,
        organization_id=scholarship.organization_id,
        scholarship_version_id=version.id,
        application_template_id=template.id,
        status=ApplicationStatus.DRAFT,
        is_synthetic=scholarship.is_synthetic,
        consent_recorded_at=now,
    )
    db.add(application)
    db.flush()
    db.add(
        ApplicationEvent(
            application_id=application.id,
            actor_domain=OwnershipDomain.STUDENT,
            actor_account_id=auth.account.id,
            event_type="DRAFT_CREATED",
            safe_message="Application draft created after student consent.",
        )
    )
    db.commit()
    return ApplicationCreateResponse(
        id=application.id,
        status=application.status,
        scholarship_version_id=application.scholarship_version_id,
        application_template_id=application.application_template_id,
        is_synthetic=application.is_synthetic,
    )


@router.get("/student/applications", response_model=list[ApplicationListItem])
def list_student_applications(
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[ApplicationListItem]:
    rows = db.execute(
        select(Application, ScholarshipVersion, Organization)
        .join(
            ScholarshipVersion,
            and_(
                ScholarshipVersion.domain == Application.provider_domain,
                ScholarshipVersion.id == Application.scholarship_version_id,
            ),
        )
        .join(
            Organization,
            and_(
                Organization.domain == Application.provider_domain,
                Organization.id == Application.organization_id,
            ),
        )
        .where(
            Application.student_domain == OwnershipDomain.STUDENT,
            Application.student_account_id == auth.account.id,
        )
        .order_by(Application.updated_at.desc())
    ).all()
    return [
        ApplicationListItem(
            id=application.id,
            status=application.status,
            scholarship_title=version.title,
            organization_name=organization.display_name,
            is_synthetic=application.is_synthetic,
            updated_at=application.updated_at,
        )
        for application, version, organization in rows
    ]


@router.get("/applications/{application_id}", response_model=ApplicationDetailResponse)
def application_detail(
    application_id: uuid.UUID,
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> ApplicationDetailResponse:
    row = _student_application_row(db, application_id, auth.account.id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application was not found")
    return _application_detail(db, *row)


@router.put("/applications/{application_id}/answers", response_model=MessageResponse)
def update_application_answers(
    application_id: uuid.UUID,
    payload: ApplicationAnswersUpdate,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> MessageResponse:
    row = _student_application_row(db, application_id, auth.account.id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application was not found")
    application = row[0]
    if application.status not in {
        ApplicationStatus.DRAFT,
        ApplicationStatus.READY_FOR_STUDENT_REVIEW,
        ApplicationStatus.CORRECTION_REQUESTED,
    }:
        raise HTTPException(status.HTTP_409_CONFLICT, "Application answers are locked")

    fields = db.scalars(
        select(ApplicationTemplateField).where(
            ApplicationTemplateField.domain == application.provider_domain,
            ApplicationTemplateField.application_template_id
            == application.application_template_id,
        )
    ).all()
    allowed_ids = {field.id for field in fields}
    unknown_ids = set(payload.answers) - allowed_ids
    if unknown_ids:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "One or more fields are invalid",
        )

    encryption_key = settings.app_secret_key.get_secret_value()
    for field_id, value in payload.answers.items():
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        encrypted = func.pgp_sym_encrypt(serialized, encryption_key)
        statement = (
            insert(ApplicationAnswer)
            .values(
                application_id=application.id,
                field_id=field_id,
                provider_domain=application.provider_domain,
                application_template_id=application.application_template_id,
                encrypted_value=encrypted,
            )
            .on_conflict_do_update(
                index_elements=[
                    ApplicationAnswer.application_id,
                    ApplicationAnswer.field_id,
                ],
                set_={
                    "encrypted_value": encrypted,
                    "updated_at": func.now(),
                },
            )
        )
        db.execute(statement)

    application.status = ApplicationStatus.READY_FOR_STUDENT_REVIEW
    db.commit()
    return MessageResponse(message="Application answers encrypted and saved")


@router.post("/applications/{application_id}/submit", response_model=MessageResponse)
def submit_application(
    application_id: uuid.UUID,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> MessageResponse:
    row = _student_application_row(db, application_id, auth.account.id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application was not found")
    application = row[0]
    if application.status not in {
        ApplicationStatus.DRAFT,
        ApplicationStatus.READY_FOR_STUDENT_REVIEW,
        ApplicationStatus.CORRECTION_REQUESTED,
    }:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Application cannot be submitted now",
        )

    required_fields = set(
        db.scalars(
            select(ApplicationTemplateField.id).where(
                ApplicationTemplateField.domain == application.provider_domain,
                ApplicationTemplateField.application_template_id
                == application.application_template_id,
                ApplicationTemplateField.required.is_(True),
            )
        ).all()
    )
    answered_fields = set(
        db.scalars(
            select(ApplicationAnswer.field_id).where(
                ApplicationAnswer.application_id == application.id
            )
        ).all()
    )
    if missing := required_fields - answered_fields:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{len(missing)} required application field(s) are incomplete",
        )

    now = datetime.now(UTC)
    is_resubmission = application.status == ApplicationStatus.CORRECTION_REQUESTED
    application.status = (
        ApplicationStatus.RESUBMITTED
        if is_resubmission
        else ApplicationStatus.SUBMITTED
    )
    application.submitted_at = now
    db.add(
        ApplicationEvent(
            application_id=application.id,
            actor_domain=OwnershipDomain.STUDENT,
            actor_account_id=auth.account.id,
            event_type="RESUBMITTED" if is_resubmission else "SUBMITTED",
            safe_message=(
                "Synthetic application resubmitted to the provider."
                if is_resubmission
                else "Synthetic application submitted to the provider."
            ),
        )
    )
    db.commit()
    return MessageResponse(message="Synthetic application submitted to the provider")


@router.get("/organizations/me/applications", response_model=list[ApplicationListItem])
def list_organization_applications(
    context: OrganizationContext = Depends(require_organization),
    db: Session = Depends(get_db),
) -> list[ApplicationListItem]:
    rows = db.execute(
        select(Application, ScholarshipVersion, Organization)
        .join(
            ScholarshipVersion,
            and_(
                ScholarshipVersion.domain == Application.provider_domain,
                ScholarshipVersion.id == Application.scholarship_version_id,
            ),
        )
        .join(
            Organization,
            and_(
                Organization.domain == Application.provider_domain,
                Organization.id == Application.organization_id,
            ),
        )
        .where(
            Application.provider_domain == context.organization.domain,
            Application.organization_id == context.organization.id,
        )
        .order_by(Application.updated_at.desc())
    ).all()
    return [
        ApplicationListItem(
            id=application.id,
            status=application.status,
            scholarship_title=version.title,
            organization_name=organization.display_name,
            is_synthetic=application.is_synthetic,
            updated_at=application.updated_at,
        )
        for application, version, organization in rows
    ]


@router.post(
    "/organizations/me/applications/{application_id}/status",
    response_model=MessageResponse,
)
def update_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusUpdate,
    context: OrganizationContext = Depends(require_organization_write),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if context.membership.role not in {
        MemberRole.OWNER,
        MemberRole.APPLICATION_REVIEWER,
    }:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Application reviewer role required",
        )
    application = db.scalar(
        select(Application).where(
            Application.id == application_id,
            Application.provider_domain == context.organization.domain,
            Application.organization_id == context.organization.id,
        )
    )
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application was not found")

    target = ApplicationStatus(payload.status)
    allowed_transitions = {
        ApplicationStatus.SUBMITTED: {ApplicationStatus.UNDER_ORGANIZATION_REVIEW},
        ApplicationStatus.RESUBMITTED: {ApplicationStatus.UNDER_ORGANIZATION_REVIEW},
        ApplicationStatus.UNDER_ORGANIZATION_REVIEW: {
            ApplicationStatus.CORRECTION_REQUESTED,
            ApplicationStatus.APPROVED,
            ApplicationStatus.REJECTED,
        },
    }
    if target not in allowed_transitions.get(application.status, set()):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Application status transition is not allowed",
        )

    application.status = target
    db.add(
        ApplicationEvent(
            application_id=application.id,
            actor_domain=context.organization.domain,
            actor_account_id=context.auth.account.id,
            event_type=target.value,
            safe_message=payload.message,
        )
    )
    db.commit()
    return MessageResponse(message=f"Application moved to {target.value}")
