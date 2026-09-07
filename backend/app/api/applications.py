from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, select
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
    ApplicationDocument,
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
    ApplicationDocumentResponse,
    ApplicationEventResponse,
    ApplicationFieldResponse,
    ApplicationListItem,
    ApplicationStatusUpdate,
    MessageResponse,
)
from app.services.application_validation import (
    application_target_error,
    attach_document_snapshots,
    field_value_is_valid,
    invalid_required_field_keys,
    load_decrypted_application_answers,
    required_document_types,
    resolved_profile_binding,
    upsert_encrypted_answer,
    valid_student_documents,
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


def _student_application_detail(
    db: Session,
    application: Application,
    scholarship: Scholarship,
    version: ScholarshipVersion,
    organization: Organization,
    *,
    answers: dict[uuid.UUID, object],
) -> ApplicationDetailResponse:
    template = db.scalar(
        select(ApplicationTemplate).where(
            ApplicationTemplate.domain == application.provider_domain,
            ApplicationTemplate.id == application.application_template_id,
        )
    )
    fields = db.scalars(
        select(ApplicationTemplateField)
        .where(
            ApplicationTemplateField.domain == application.provider_domain,
            ApplicationTemplateField.application_template_id
            == application.application_template_id,
        )
        .order_by(ApplicationTemplateField.sort_order)
    ).all()
    documents = db.scalars(
        select(ApplicationDocument)
        .where(ApplicationDocument.application_id == application.id)
        .order_by(ApplicationDocument.attached_at)
    ).all()
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
        agent_submission_authorized_at=application.agent_submission_authorized_at,
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
                profile_binding=resolved_profile_binding(field),
                numeric_min=(float(field.numeric_min) if field.numeric_min is not None else None),
                numeric_max=(float(field.numeric_max) if field.numeric_max is not None else None),
                numeric_step=(float(field.numeric_step) if field.numeric_step is not None else None),
                sort_order=field.sort_order,
            )
            for field in fields
        ],
        required_document_types=(template.required_document_types if template else []),
        documents=[
            ApplicationDocumentResponse(
                id=document.id,
                student_document_id=document.student_document_id,
                document_type=document.document_type,
                original_filename=document.original_filename_snapshot,
                content_type=document.content_type_snapshot,
                size_bytes=document.size_bytes_snapshot,
                checksum_sha256=document.checksum_sha256_snapshot,
                issue_date=document.issue_date_snapshot,
                expiry_date=document.expiry_date_snapshot,
                attached_at=document.attached_at,
            )
            for document in documents
        ],
        answers=answers,
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
        select(Application)
        .where(
            Application.student_domain == OwnershipDomain.STUDENT,
            Application.student_account_id == auth.account.id,
            Application.provider_domain == scholarship.domain,
            Application.scholarship_version_id == version.id,
        )
        .order_by(Application.created_at.desc())
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
    response: Response,
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> ApplicationDetailResponse:
    row = _student_application_row(db, application_id, auth.account.id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application was not found")
    application = row[0]
    answers = load_decrypted_application_answers(
        db,
        application.id,
        settings.app_secret_key.get_secret_value(),
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    return _student_application_detail(db, *row, answers=answers)


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
    fields_by_id = {field.id: field for field in fields}
    unknown_ids = set(payload.answers) - set(fields_by_id)
    if unknown_ids:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "One or more fields are invalid",
        )

    invalid_keys = [
        fields_by_id[field_id].field_key
        for field_id, value in payload.answers.items()
        if not field_value_is_valid(fields_by_id[field_id], value)
    ]
    if invalid_keys:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid value for application field(s): " + ", ".join(invalid_keys),
        )

    encryption_key = settings.app_secret_key.get_secret_value()
    for field_id, value in payload.answers.items():
        upsert_encrypted_answer(
            db,
            application,
            fields_by_id[field_id],
            value,
            encryption_key,
        )

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
    if application.status in {
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.RESUBMITTED,
        ApplicationStatus.UNDER_ORGANIZATION_REVIEW,
        ApplicationStatus.APPROVED,
        ApplicationStatus.REJECTED,
    }:
        return MessageResponse(message="Application is already in the provider queue")
    if application.status not in {
        ApplicationStatus.DRAFT,
        ApplicationStatus.READY_FOR_STUDENT_REVIEW,
        ApplicationStatus.CORRECTION_REQUESTED,
    }:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Application cannot be submitted now",
        )

    if target_error := application_target_error(db, application):
        raise HTTPException(status.HTTP_409_CONFLICT, target_error)

    template = db.scalar(
        select(ApplicationTemplate).where(
            ApplicationTemplate.domain == application.provider_domain,
            ApplicationTemplate.id == application.application_template_id,
        )
    )
    if template is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The application template is no longer available",
        )
    fields = list(
        db.scalars(
            select(ApplicationTemplateField)
            .where(
                ApplicationTemplateField.domain == application.provider_domain,
                ApplicationTemplateField.application_template_id
                == application.application_template_id,
            )
            .order_by(ApplicationTemplateField.sort_order)
        ).all()
    )
    answers = load_decrypted_application_answers(
        db,
        application.id,
        settings.app_secret_key.get_secret_value(),
    )
    missing_fields = invalid_required_field_keys(fields, answers)
    if missing_fields:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Required application field(s) are incomplete or invalid: "
            + ", ".join(missing_fields),
        )

    try:
        document_types = required_document_types(template.required_document_types or [])
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The provider template contains an invalid document requirement",
        ) from exc
    documents = valid_student_documents(db, auth.account.id, document_types)
    missing_documents = [
        document_type.value
        for document_type in document_types
        if document_type not in documents
    ]
    if missing_documents:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Required document(s) are missing or expired: "
            + ", ".join(missing_documents),
        )
    attach_document_snapshots(db, application, documents)

    now = datetime.now(UTC)
    is_resubmission = application.status == ApplicationStatus.CORRECTION_REQUESTED
    application.status = (
        ApplicationStatus.RESUBMITTED
        if is_resubmission
        else ApplicationStatus.SUBMITTED
    )
    application.submitted_at = now
    application.agent_submission_authorized_at = now
    db.add(
        ApplicationEvent(
            application_id=application.id,
            actor_domain=OwnershipDomain.STUDENT,
            actor_account_id=auth.account.id,
            event_type="RESUBMITTED" if is_resubmission else "SUBMITTED",
            safe_message=(
                "Application resubmitted to the provider's ScholarSaathi queue."
                if is_resubmission
                else "Application submitted to the provider's ScholarSaathi queue."
            ),
        )
    )
    db.commit()
    return MessageResponse(message="Application submitted to the provider queue")


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
