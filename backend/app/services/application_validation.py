from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationAnswer,
    ApplicationDocument,
    ApplicationFieldType,
    ApplicationTemplateField,
    PublicationStatus,
    Scholarship,
    ScholarshipLifecycle,
    ScholarshipVersion,
    StudentDocument,
    StudentDocumentStatus,
    StudentDocumentType,
    StudentSetting,
)
from app.services.application_templates import PROFILE_BINDINGS_BY_FIELD_KEY

_WILDCARD_OPTIONS = {"ALL", "ALL_UNDERGRADUATE", "ALL_RECOGNIZED_COURSES", "STEM"}


def is_nonblank(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def resolved_profile_binding(field: ApplicationTemplateField) -> str | None:
    """Profile attribute this field reads, falling back to the field key mapping.

    Templates stored before a binding was recorded keep ``profile_binding`` empty. Without
    this fallback such a field can never be filled from the student profile, so a complete
    profile is still reported as missing.
    """
    return field.profile_binding or PROFILE_BINDINGS_BY_FIELD_KEY.get(field.field_key)


def profile_value_for_field(
    setting: StudentSetting | None,
    field: ApplicationTemplateField,
    *,
    explicitly_authorized: bool,
) -> Any:
    binding = resolved_profile_binding(field)
    if binding == "explicit_apply_authorization" or field.field_key == "student_declaration":
        return explicitly_authorized
    if setting is None or not binding:
        return None
    return getattr(setting, binding, None)


def field_value_is_valid(field: ApplicationTemplateField, value: Any) -> bool:
    if not is_nonblank(value):
        return not field.required

    if field.field_type in {ApplicationFieldType.TEXT, ApplicationFieldType.TEXTAREA}:
        return isinstance(value, str) and bool(value.strip())
    if field.field_type == ApplicationFieldType.NUMBER:
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    if field.field_type == ApplicationFieldType.DATE:
        if isinstance(value, (date, datetime)):
            return True
        if not isinstance(value, str):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if field.field_type == ApplicationFieldType.CHECKBOX:
        return value is True if field.required else isinstance(value, bool)
    if field.field_type == ApplicationFieldType.SELECT:
        if not isinstance(value, str) or not value.strip():
            return False
        options = {str(option).upper() for option in (field.options_json or [])}
        return not options or bool(options & _WILDCARD_OPTIONS) or value.upper() in options
    if field.field_type == ApplicationFieldType.MULTISELECT:
        if not isinstance(value, list) or not value:
            return False
        options = {str(option).upper() for option in (field.options_json or [])}
        normalized = {str(item).upper() for item in value if is_nonblank(item)}
        return bool(normalized) and (
            not options or bool(options & _WILDCARD_OPTIONS) or normalized <= options
        )
    return False


def invalid_required_field_keys(
    fields: Iterable[ApplicationTemplateField],
    values: Mapping[uuid.UUID, Any],
) -> list[str]:
    return [
        field.field_key
        for field in fields
        if field.required and not field_value_is_valid(field, values.get(field.id))
    ]


def required_document_types(raw_values: Iterable[str]) -> list[StudentDocumentType]:
    result: list[StudentDocumentType] = []
    for value in raw_values:
        document_type = StudentDocumentType(value)
        if document_type not in result:
            result.append(document_type)
    return result


def valid_student_documents(
    db: Session,
    student_account_id: uuid.UUID,
    required_types: Iterable[StudentDocumentType],
) -> dict[StudentDocumentType, StudentDocument]:
    required = list(required_types)
    if not required:
        return {}
    today = date.today()
    documents = db.scalars(
        select(StudentDocument)
        .where(
            StudentDocument.student_account_id == student_account_id,
            StudentDocument.status == StudentDocumentStatus.READY,
            StudentDocument.deleted_at.is_(None),
            StudentDocument.document_type.in_(required),
            (
                StudentDocument.expiry_date.is_(None)
                | (StudentDocument.expiry_date >= today)
            ),
        )
        .order_by(StudentDocument.created_at.desc())
    ).all()
    selected: dict[StudentDocumentType, StudentDocument] = {}
    for document in documents:
        selected.setdefault(document.document_type, document)
    return selected


def application_target_error(
    db: Session,
    application: Application,
    *,
    now: datetime | None = None,
) -> str | None:
    current_time = now or datetime.now(UTC)
    row = db.execute(
        select(Scholarship, ScholarshipVersion)
        .join(
            ScholarshipVersion,
            and_(
                ScholarshipVersion.domain == Scholarship.domain,
                ScholarshipVersion.scholarship_id == Scholarship.id,
                ScholarshipVersion.id == Scholarship.current_published_version_id,
            ),
        )
        .where(
            Scholarship.domain == application.provider_domain,
            Scholarship.organization_id == application.organization_id,
            ScholarshipVersion.id == application.scholarship_version_id,
        )
    ).one_or_none()
    if not row:
        return "The application is not tied to the current published scholarship version."
    scholarship, version = row
    if scholarship.lifecycle_status != ScholarshipLifecycle.ACTIVE:
        return "The scholarship is not currently accepting applications."
    if version.publication_status != PublicationStatus.PUBLISHED:
        return "The scholarship version is not currently published."
    if version.application_opens_at and current_time < version.application_opens_at:
        return "The scholarship application window has not opened."
    if version.application_deadline_at and current_time > version.application_deadline_at:
        return "The scholarship application deadline has passed."
    return None


def load_decrypted_application_answers(
    db: Session,
    application_id: uuid.UUID,
    encryption_key: str,
) -> dict[uuid.UUID, Any]:
    rows = db.execute(
        select(
            ApplicationAnswer.field_id,
            func.pgp_sym_decrypt(ApplicationAnswer.encrypted_value, encryption_key),
        ).where(ApplicationAnswer.application_id == application_id)
    ).all()
    values: dict[uuid.UUID, Any] = {}
    for field_id, serialized in rows:
        try:
            values[field_id] = json.loads(serialized)
        except (TypeError, json.JSONDecodeError):
            values[field_id] = None
    return values


def upsert_encrypted_answer(
    db: Session,
    application: Application,
    field_id: uuid.UUID,
    value: Any,
    encryption_key: str,
) -> None:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    encrypted = func.pgp_sym_encrypt(serialized, encryption_key)
    db.execute(
        insert(ApplicationAnswer)
        .values(
            application_id=application.id,
            field_id=field_id,
            provider_domain=application.provider_domain,
            application_template_id=application.application_template_id,
            encrypted_value=encrypted,
        )
        .on_conflict_do_update(
            index_elements=[ApplicationAnswer.application_id, ApplicationAnswer.field_id],
            set_={"encrypted_value": encrypted, "updated_at": func.now()},
        )
    )


def attach_document_snapshots(
    db: Session,
    application: Application,
    documents: Mapping[StudentDocumentType, StudentDocument],
) -> None:
    for document_type, document in documents.items():
        db.execute(
            insert(ApplicationDocument)
            .values(
                application_id=application.id,
                student_account_id=application.student_account_id,
                student_document_id=document.id,
                document_type=document_type,
                storage_key_snapshot=document.storage_key,
                original_filename_snapshot=document.original_filename,
                content_type_snapshot=document.content_type,
                size_bytes_snapshot=document.size_bytes,
                checksum_sha256_snapshot=document.checksum_sha256,
                issue_date_snapshot=document.issue_date,
                expiry_date_snapshot=document.expiry_date,
            )
            .on_conflict_do_update(
                constraint="v4_uq_application_document_type",
                set_={
                    "student_document_id": document.id,
                    "storage_key_snapshot": document.storage_key,
                    "original_filename_snapshot": document.original_filename,
                    "content_type_snapshot": document.content_type,
                    "size_bytes_snapshot": document.size_bytes,
                    "checksum_sha256_snapshot": document.checksum_sha256,
                    "issue_date_snapshot": document.issue_date,
                    "expiry_date_snapshot": document.expiry_date,
                    "attached_at": func.now(),
                },
            )
        )
