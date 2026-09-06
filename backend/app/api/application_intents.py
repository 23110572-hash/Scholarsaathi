from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.scholarships import published_scholarship_query
from app.core.config import get_settings
from app.database import get_db
from app.dependencies import (
    AuthContext,
    optional_student_write,
    require_student,
    require_student_write,
)
from app.models import (
    ApplicationIntent,
    ApplicationIntentStatus,
    Scholarship,
    ScholarshipVersion,
)
from app.schemas import (
    ApplicationIntentBatchResponse,
    ApplicationIntentCreateRequest,
    ApplicationIntentResponse,
)
from app.services.application_workflow import (
    authorize_application_intent,
    claim_anonymous_intents,
    hash_anonymous_intent_token,
    new_anonymous_intent_token,
    resume_pending_intents_for_student,
    run_application_intent,
)

router = APIRouter(prefix="/api", tags=["application intents"])
settings = get_settings()

_TERMINAL_INTENT_STATUSES = {
    ApplicationIntentStatus.SUBMITTED,
    ApplicationIntentStatus.CANCELLED,
    ApplicationIntentStatus.EXPIRED,
}


def _title_for_intent(db: Session, intent: ApplicationIntent) -> str:
    if intent.scholarship_version_id:
        title = db.scalar(
            select(ScholarshipVersion.title).where(
                ScholarshipVersion.domain == intent.scholarship_domain,
                ScholarshipVersion.id == intent.scholarship_version_id,
            )
        )
        if title:
            return title
    title = db.scalar(
        select(ScholarshipVersion.title)
        .join(
            Scholarship,
            (Scholarship.domain == ScholarshipVersion.domain)
            & (Scholarship.current_published_version_id == ScholarshipVersion.id),
        )
        .where(
            Scholarship.domain == intent.scholarship_domain,
            Scholarship.id == intent.scholarship_id,
        )
    )
    return title or "Scholarship"


def _intent_response(
    db: Session,
    intent: ApplicationIntent,
    *,
    scholarship_title: str | None = None,
) -> ApplicationIntentResponse:
    title = scholarship_title or _title_for_intent(db, intent)
    messages = {
        ApplicationIntentStatus.WAITING_FOR_AUTH: (
            "Sign in or create a student account to continue this application."
        ),
        ApplicationIntentStatus.WAITING_FOR_PROFILE: (
            "Complete the listed reusable profile fields; the application will resume "
            "automatically after you save."
        ),
        ApplicationIntentStatus.WAITING_FOR_DOCUMENTS: (
            "Upload the listed private documents; the application will resume automatically."
        ),
        ApplicationIntentStatus.READY: (
            intent.safe_last_error
            or "The application is ready to retry in the ScholarSaathi provider queue."
        ),
        ApplicationIntentStatus.SUBMITTING: (
            "The application is being submitted to the ScholarSaathi provider queue."
        ),
        ApplicationIntentStatus.SUBMITTED: (
            "The application was submitted to the provider's ScholarSaathi queue."
        ),
        ApplicationIntentStatus.BLOCKED: (
            intent.safe_last_error or "The application cannot be submitted right now."
        ),
        ApplicationIntentStatus.EXPIRED: (
            intent.safe_last_error or "This apply request expired; send a new request."
        ),
        ApplicationIntentStatus.CANCELLED: "This application request was cancelled.",
    }
    outcomes = {
        ApplicationIntentStatus.WAITING_FOR_AUTH: "AUTH_REQUIRED",
        ApplicationIntentStatus.WAITING_FOR_PROFILE: "PROFILE_REQUIRED",
        ApplicationIntentStatus.WAITING_FOR_DOCUMENTS: "DOCUMENTS_REQUIRED",
        ApplicationIntentStatus.READY: "READY",
        ApplicationIntentStatus.SUBMITTING: "READY",
        ApplicationIntentStatus.SUBMITTED: "SUBMITTED",
        ApplicationIntentStatus.BLOCKED: "BLOCKED",
        ApplicationIntentStatus.EXPIRED: "EXPIRED",
        ApplicationIntentStatus.CANCELLED: "CANCELLED",
    }
    next_paths = {
        ApplicationIntentStatus.WAITING_FOR_AUTH: f"/login?intent={intent.id}",
        ApplicationIntentStatus.WAITING_FOR_PROFILE: "/student/profile",
        ApplicationIntentStatus.WAITING_FOR_DOCUMENTS: "/student/documents",
        ApplicationIntentStatus.READY: f"/scholarships/{intent.scholarship_id}",
        ApplicationIntentStatus.SUBMITTING: f"/scholarships/{intent.scholarship_id}",
        ApplicationIntentStatus.SUBMITTED: (
            f"/applications/{intent.application_id}" if intent.application_id else None
        ),
        ApplicationIntentStatus.BLOCKED: f"/scholarships/{intent.scholarship_id}",
        ApplicationIntentStatus.EXPIRED: f"/scholarships/{intent.scholarship_id}",
        ApplicationIntentStatus.CANCELLED: None,
    }
    return ApplicationIntentResponse(
        scholarship_id=intent.scholarship_id,
        scholarship_title=title,
        intent_id=intent.id,
        status=intent.status,
        outcome=outcomes[intent.status],
        assistant_message=messages[intent.status],
        missing_profile_fields=list(intent.missing_profile_fields or []),
        missing_document_types=list(intent.missing_document_types or []),
        application_id=intent.application_id,
        next_path=next_paths[intent.status],
        updated_at=intent.updated_at,
    )


def _set_anonymous_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        settings.application_intent_cookie_name,
        raw_token,
        max_age=settings.application_intent_ttl_hours * 60 * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )


@router.post("/application-intents", response_model=ApplicationIntentBatchResponse)
def create_application_intents(
    payload: ApplicationIntentCreateRequest,
    request: Request,
    response: Response,
    auth: AuthContext | None = Depends(optional_student_write),
    db: Session = Depends(get_db),
) -> ApplicationIntentBatchResponse:
    rows = db.execute(
        published_scholarship_query().where(
            Scholarship.id.in_(payload.scholarship_ids)
        )
    ).all()
    rows_by_id: dict[uuid.UUID, list[tuple]] = {}
    for row in rows:
        rows_by_id.setdefault(row[0].id, []).append(row)
    if any(
        len(rows_by_id.get(scholarship_id, [])) != 1
        for scholarship_id in payload.scholarship_ids
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Every scholarship target must identify exactly one current published scholarship",
        )

    raw_anonymous_token = request.cookies.get(settings.application_intent_cookie_name)
    if auth is None and not raw_anonymous_token:
        raw_anonymous_token = new_anonymous_intent_token()
    anonymous_hash = (
        hash_anonymous_intent_token(raw_anonymous_token)
        if raw_anonymous_token
        else None
    )

    if auth is not None and anonymous_hash:
        claim_anonymous_intents(
            db,
            student_account_id=auth.account.id,
            anonymous_token_hash=anonymous_hash,
        )

    titles: dict[uuid.UUID, str] = {}
    intents: list[ApplicationIntent] = []
    now = datetime.now(UTC)
    for scholarship_id in payload.scholarship_ids:
        scholarship, version, _organization = rows_by_id[scholarship_id][0]
        titles[scholarship.id] = version.title
        intents.append(
            authorize_application_intent(
                db,
                scholarship=scholarship,
                student_account_id=auth.account.id if auth else None,
                anonymous_token_hash=anonymous_hash,
                authorization_source=payload.authorization_source,
                now=now,
            )
        )
    db.commit()

    if auth is None:
        assert raw_anonymous_token is not None
        _set_anonymous_cookie(response, raw_anonymous_token)
    elif raw_anonymous_token:
        response.delete_cookie(settings.application_intent_cookie_name, path="/")

    if auth is not None:
        intents = [run_application_intent(db, intent.id) for intent in intents]
    return ApplicationIntentBatchResponse(
        items=[
            _intent_response(db, intent, scholarship_title=titles[intent.scholarship_id])
            for intent in intents
        ]
    )


@router.post(
    "/student/application-intents/resume",
    response_model=ApplicationIntentBatchResponse,
)
def resume_application_intents(
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> ApplicationIntentBatchResponse:
    raw_anonymous_token = request.cookies.get(settings.application_intent_cookie_name)
    if raw_anonymous_token:
        claim_anonymous_intents(
            db,
            student_account_id=auth.account.id,
            anonymous_token_hash=hash_anonymous_intent_token(raw_anonymous_token),
        )
        db.commit()
        response.delete_cookie(settings.application_intent_cookie_name, path="/")
    intents = resume_pending_intents_for_student(db, auth.account.id)
    return ApplicationIntentBatchResponse(
        items=[_intent_response(db, intent) for intent in intents]
    )


@router.get(
    "/student/application-intents",
    response_model=ApplicationIntentBatchResponse,
)
def list_application_intents(
    pending_only: bool = Query(default=False),
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> ApplicationIntentBatchResponse:
    query = select(ApplicationIntent).where(
        ApplicationIntent.student_account_id == auth.account.id
    )
    if pending_only:
        query = query.where(
            ApplicationIntent.status.notin_(_TERMINAL_INTENT_STATUSES)
        )
    intents = db.scalars(query.order_by(ApplicationIntent.updated_at.desc())).all()
    return ApplicationIntentBatchResponse(
        items=[_intent_response(db, intent) for intent in intents]
    )


@router.get(
    "/student/application-intents/{intent_id}",
    response_model=ApplicationIntentResponse,
)
def application_intent_detail(
    intent_id: uuid.UUID,
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> ApplicationIntentResponse:
    intent = db.scalar(
        select(ApplicationIntent).where(
            ApplicationIntent.id == intent_id,
            ApplicationIntent.student_account_id == auth.account.id,
        )
    )
    if intent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application intent was not found")
    return _intent_response(db, intent)
