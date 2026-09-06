from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_ALLOWED_CONTENT_TYPES = {
    "application/pdf": (".pdf",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
}
_FORBIDDEN_FILENAME_TERMS = re.compile(
    r"(?:aadhaar|aadhar|\bpan(?:[\s_-]*card)?\b|bank|passbook|\botp\b)",
    re.IGNORECASE,
)


class DocumentStorageError(RuntimeError):
    """Raised when private object storage is unavailable or misconfigured."""


class InvalidStudentDocument(ValueError):
    """Raised when an uploaded object does not meet the controlled document policy."""


@dataclass(frozen=True, slots=True)
class ValidatedDocumentUpload:
    content: bytes
    original_filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str


def _storage_configuration() -> tuple[str, str, str, str, str]:
    values = (
        settings.supabase_s3_endpoint,
        settings.supabase_s3_region,
        settings.supabase_s3_bucket,
        (
            settings.supabase_s3_access_key_id.get_secret_value()
            if settings.supabase_s3_access_key_id
            else None
        ),
        (
            settings.supabase_s3_secret_access_key.get_secret_value()
            if settings.supabase_s3_secret_access_key
            else None
        ),
    )
    if not all(value and value.strip() for value in values):
        raise DocumentStorageError("Private document storage is not configured")
    return tuple(value.strip() for value in values)  # type: ignore[return-value]


@lru_cache
def _s3_client() -> Any:
    endpoint, region, _bucket, access_key, secret_key = _storage_configuration()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _bucket() -> str:
    return _storage_configuration()[2]


def private_document_key(
    student_account_id: uuid.UUID,
    document_id: uuid.UUID,
) -> str:
    return f"students/{student_account_id}/{document_id}/{uuid.uuid4().hex}"


def _safe_filename(filename: str | None) -> str:
    candidate = (filename or "document").replace("\\", "/").split("/")[-1]
    candidate = "".join(character for character in candidate if character.isprintable()).strip()
    candidate = candidate[:255] or "document"
    if _FORBIDDEN_FILENAME_TERMS.search(candidate):
        raise InvalidStudentDocument(
            "Aadhaar, PAN, bank, passbook, and OTP documents are not accepted"
        )
    return candidate


def _detected_content_type(content: bytes) -> str | None:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


async def validate_document_upload(upload: UploadFile) -> ValidatedDocumentUpload:
    filename = _safe_filename(upload.filename)
    declared_content_type = (upload.content_type or "").lower().split(";", 1)[0].strip()
    if declared_content_type == "image/jpg":
        declared_content_type = "image/jpeg"
    if declared_content_type not in _ALLOWED_CONTENT_TYPES:
        raise InvalidStudentDocument("Only PDF, JPEG, and PNG documents are accepted")

    maximum = settings.supabase_s3_upload_max_bytes
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await upload.read(min(1024 * 1024, maximum + 1 - size))
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        if size > maximum:
            raise InvalidStudentDocument(
                f"Document exceeds the {maximum}-byte upload limit"
            )
    if size == 0:
        raise InvalidStudentDocument("Document file is empty")

    content = b"".join(chunks)
    detected_content_type = _detected_content_type(content)
    if detected_content_type is None or detected_content_type != declared_content_type:
        raise InvalidStudentDocument("Document content does not match its MIME type")

    suffix = PurePosixPath(filename.lower()).suffix
    if suffix not in _ALLOWED_CONTENT_TYPES[detected_content_type]:
        raise InvalidStudentDocument("Document filename extension does not match its content")

    return ValidatedDocumentUpload(
        content=content,
        original_filename=filename,
        content_type=detected_content_type,
        size_bytes=size,
        checksum_sha256=hashlib.sha256(content).hexdigest(),
    )


def upload_private_document(storage_key: str, upload: ValidatedDocumentUpload) -> None:
    try:
        _s3_client().put_object(
            Bucket=_bucket(),
            Key=storage_key,
            Body=upload.content,
            ContentType=upload.content_type,
            Metadata={"sha256": upload.checksum_sha256},
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("Private document upload failed")
        raise DocumentStorageError("Private document storage is temporarily unavailable") from exc


def create_download_url(storage_key: str, original_filename: str) -> str:
    disposition = f"attachment; filename*=UTF-8''{quote(original_filename)}"
    try:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": _bucket(),
                "Key": storage_key,
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=settings.supabase_s3_signed_url_ttl_seconds,
            HttpMethod="GET",
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("Private document signing failed")
        raise DocumentStorageError("A private download link could not be created") from exc


def delete_private_document(storage_key: str) -> None:
    try:
        _s3_client().delete_object(Bucket=_bucket(), Key=storage_key)
    except (BotoCoreError, ClientError) as exc:
        logger.error("Private document deletion failed")
        raise DocumentStorageError("Private document storage is temporarily unavailable") from exc


def best_effort_delete_private_document(storage_key: str) -> None:
    try:
        delete_private_document(storage_key)
    except DocumentStorageError:
        # The database row remains inaccessible. Operational cleanup can retry this key.
        logger.warning("Private document object remains queued for cleanup")
