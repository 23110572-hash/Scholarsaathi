from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.dependencies import AuthContext, require_student, require_student_write
from app.models import (
    ApplicationDocument,
    OwnershipDomain,
    StudentDocument,
    StudentDocumentStatus,
    StudentDocumentType,
)
from app.schemas import (
    MessageResponse,
    StudentDocumentDownloadResponse,
    StudentDocumentListResponse,
    StudentDocumentResponse,
)
from app.services.application_workflow import resume_pending_intents_for_student
from app.services.document_storage import (
    DocumentStorageError,
    InvalidStudentDocument,
    best_effort_delete_private_document,
    create_download_url,
    private_document_key,
    upload_private_document,
    validate_document_upload,
)

router = APIRouter(prefix="/api/student/documents", tags=["student documents"])
settings = get_settings()


def _document_response(document: StudentDocument) -> StudentDocumentResponse:
    return StudentDocumentResponse(
        id=document.id,
        document_type=document.document_type,
        original_filename=document.original_filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        checksum_sha256=document.checksum_sha256,
        status=document.status,
        issue_date=document.issue_date,
        expiry_date=document.expiry_date,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _student_document(
    db: Session,
    document_id: uuid.UUID,
    student_account_id: uuid.UUID,
) -> StudentDocument:
    document = db.scalar(
        select(StudentDocument).where(
            StudentDocument.id == document_id,
            StudentDocument.student_domain == OwnershipDomain.STUDENT,
            StudentDocument.student_account_id == student_account_id,
            StudentDocument.status == StudentDocumentStatus.READY,
            StudentDocument.deleted_at.is_(None),
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document was not found")
    return document


@router.get("", response_model=StudentDocumentListResponse)
def list_student_documents(
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> StudentDocumentListResponse:
    documents = db.scalars(
        select(StudentDocument)
        .where(
            StudentDocument.student_domain == OwnershipDomain.STUDENT,
            StudentDocument.student_account_id == auth.account.id,
            StudentDocument.status == StudentDocumentStatus.READY,
            StudentDocument.deleted_at.is_(None),
        )
        .order_by(StudentDocument.created_at.desc())
    ).all()
    return StudentDocumentListResponse(
        items=[_document_response(document) for document in documents],
        total=len(documents),
    )


@router.post("", response_model=StudentDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_student_document(
    document_type: Annotated[StudentDocumentType, Form()],
    file: Annotated[UploadFile, File()],
    issue_date: Annotated[date | None, Form()] = None,
    expiry_date: Annotated[date | None, Form()] = None,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> StudentDocumentResponse:
    if issue_date and issue_date > date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Issue date cannot be in the future")
    if expiry_date and issue_date and expiry_date < issue_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Expiry date cannot precede issue date")

    try:
        validated = await validate_document_upload(file)
    except InvalidStudentDocument as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    finally:
        await file.close()

    document_id = uuid.uuid4()
    storage_key = private_document_key(auth.account.id, document_id)
    try:
        upload_private_document(storage_key, validated)
    except DocumentStorageError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    document = StudentDocument(
        id=document_id,
        student_domain=OwnershipDomain.STUDENT,
        student_account_id=auth.account.id,
        document_type=document_type,
        storage_key=storage_key,
        original_filename=validated.original_filename,
        content_type=validated.content_type,
        size_bytes=validated.size_bytes,
        checksum_sha256=validated.checksum_sha256,
        status=StudentDocumentStatus.READY,
        issue_date=issue_date,
        expiry_date=expiry_date,
    )
    try:
        db.add(document)
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        best_effort_delete_private_document(storage_key)
        raise

    resume_pending_intents_for_student(db, auth.account.id)
    return _document_response(document)


@router.get("/{document_id}/download", response_model=StudentDocumentDownloadResponse)
def download_student_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> StudentDocumentDownloadResponse:
    document = _student_document(db, document_id, auth.account.id)
    try:
        url = create_download_url(document.storage_key, document.original_filename)
    except DocumentStorageError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    expires_at = datetime.now(UTC) + timedelta(
        seconds=settings.supabase_s3_signed_url_ttl_seconds
    )
    return StudentDocumentDownloadResponse(url=url, expires_at=expires_at)


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_student_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> MessageResponse:
    document = _student_document(db, document_id, auth.account.id)
    is_attached = db.scalar(
        select(ApplicationDocument.id).where(
            ApplicationDocument.student_account_id == auth.account.id,
            ApplicationDocument.student_document_id == document.id,
        )
    )
    if is_attached:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Document is retained because an application references its submitted snapshot",
        )

    document.status = StudentDocumentStatus.DELETED
    document.deleted_at = datetime.now(UTC)
    db.commit()
    best_effort_delete_private_document(document.storage_key)
    return MessageResponse(message="Document deleted")
