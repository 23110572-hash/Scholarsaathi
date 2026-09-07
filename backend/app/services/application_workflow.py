from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.agents.application_flow import run_application_flow
from app.core.config import get_settings
from app.models import (
    FINAL_APPLICATION_STATUSES,
    Application,
    ApplicationEvent,
    ApplicationIntent,
    ApplicationIntentStatus,
    ApplicationStatus,
    ApplicationTemplate,
    ApplicationTemplateField,
    Organization,
    OwnershipDomain,
    PublicationStatus,
    Scholarship,
    ScholarshipLifecycle,
    ScholarshipVersion,
    StudentDocument,
    StudentDocumentType,
    StudentSetting,
)
from app.services.application_validation import (
    application_target_error,
    attach_document_snapshots,
    field_value_is_valid,
    invalid_required_field_keys,
    load_decrypted_application_answers,
    profile_value_for_field,
    required_document_types,
    resolved_profile_binding,
    upsert_encrypted_answer,
    valid_student_documents,
)

logger = logging.getLogger(__name__)
settings = get_settings()

_PENDING_STATUSES = {
    ApplicationIntentStatus.WAITING_FOR_PROFILE,
    ApplicationIntentStatus.WAITING_FOR_DOCUMENTS,
    ApplicationIntentStatus.READY,
    ApplicationIntentStatus.SUBMITTING,
}
_SUBMITTED_APPLICATION_STATUSES = FINAL_APPLICATION_STATUSES - {
    ApplicationStatus.WITHDRAWN
}


def new_anonymous_intent_token() -> str:
    return secrets.token_urlsafe(48)


def hash_anonymous_intent_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def intent_expiry(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) + timedelta(hours=settings.application_intent_ttl_hours)


def authorize_application_intent(
    db: Session,
    *,
    scholarship: Scholarship,
    student_account_id: uuid.UUID | None,
    anonymous_token_hash: str | None,
    authorization_source: str,
    now: datetime | None = None,
) -> ApplicationIntent:
    authorized_at = now or datetime.now(UTC)
    owner_key = (
        f"student:{student_account_id}"
        if student_account_id is not None
        else f"anonymous:{anonymous_token_hash}"
    )
    lock_material = f"{owner_key}:{scholarship.domain.value}:{scholarship.id}".encode()
    advisory_key = int.from_bytes(
        hashlib.sha256(lock_material).digest()[:8],
        byteorder="big",
        signed=True,
    )
    db.execute(select(func.pg_advisory_xact_lock(advisory_key)))
    ownership_clause = (
        ApplicationIntent.student_account_id == student_account_id
        if student_account_id is not None
        else ApplicationIntent.anonymous_token_hash == anonymous_token_hash
    )
    intent = db.scalar(
        select(ApplicationIntent)
        .where(
            ownership_clause,
            ApplicationIntent.scholarship_domain == scholarship.domain,
            ApplicationIntent.scholarship_id == scholarship.id,
        )
        .with_for_update()
    )
    if intent is None:
        intent = ApplicationIntent(
            student_domain=OwnershipDomain.STUDENT,
            student_account_id=student_account_id,
            anonymous_token_hash=(
                anonymous_token_hash if student_account_id is None else None
            ),
            scholarship_domain=scholarship.domain,
            scholarship_id=scholarship.id,
            status=(
                ApplicationIntentStatus.READY
                if student_account_id is not None
                else ApplicationIntentStatus.WAITING_FOR_AUTH
            ),
            explicit_authorized_at=authorized_at,
            explicit_authorization_source=authorization_source,
            missing_profile_fields=[],
            missing_document_types=[],
            expires_at=intent_expiry(authorized_at),
        )
        db.add(intent)
        db.flush()
        return intent

    intent.explicit_authorized_at = authorized_at
    intent.explicit_authorization_source = authorization_source
    intent.expires_at = intent_expiry(authorized_at)
    intent.safe_last_error = None
    if student_account_id is not None:
        intent.student_account_id = student_account_id
        # Claiming is one-way: a student-owned intent must no longer be addressable
        # through the anonymous browser token after the cookie is removed.
        intent.anonymous_token_hash = None
        if intent.status != ApplicationIntentStatus.SUBMITTED:
            intent.status = ApplicationIntentStatus.READY
    else:
        intent.status = ApplicationIntentStatus.WAITING_FOR_AUTH

    # A fresh explicit command may re-resolve a changed target only before a draft exists.
    if intent.application_id is None and intent.status != ApplicationIntentStatus.SUBMITTED:
        intent.organization_id = None
        intent.scholarship_version_id = None
        intent.application_template_id = None
    db.flush()
    return intent


def claim_anonymous_intents(
    db: Session,
    *,
    student_account_id: uuid.UUID,
    anonymous_token_hash: str,
) -> list[ApplicationIntent]:
    anonymous_intents = db.scalars(
        select(ApplicationIntent)
        .where(
            ApplicationIntent.anonymous_token_hash == anonymous_token_hash,
            ApplicationIntent.student_account_id.is_(None),
            ApplicationIntent.status.notin_(
                [ApplicationIntentStatus.CANCELLED, ApplicationIntentStatus.EXPIRED]
            ),
        )
        .with_for_update()
    ).all()
    claimed: list[ApplicationIntent] = []
    for anonymous_intent in anonymous_intents:
        existing = db.scalar(
            select(ApplicationIntent)
            .where(
                ApplicationIntent.student_account_id == student_account_id,
                ApplicationIntent.scholarship_domain
                == anonymous_intent.scholarship_domain,
                ApplicationIntent.scholarship_id == anonymous_intent.scholarship_id,
                ApplicationIntent.id != anonymous_intent.id,
            )
            .with_for_update()
        )
        if existing is not None:
            if (
                anonymous_intent.explicit_authorized_at
                and (
                    existing.explicit_authorized_at is None
                    or anonymous_intent.explicit_authorized_at
                    > existing.explicit_authorized_at
                )
            ):
                existing.explicit_authorized_at = anonymous_intent.explicit_authorized_at
                existing.explicit_authorization_source = (
                    anonymous_intent.explicit_authorization_source
                )
                existing.expires_at = anonymous_intent.expires_at
                if existing.status != ApplicationIntentStatus.SUBMITTED:
                    existing.status = ApplicationIntentStatus.READY
            # The cancelled anonymous row needs a non-null owner value, but the real
            # browser-token hash must not remain usable after account ownership is set.
            anonymous_intent.anonymous_token_hash = hashlib.sha256(
                f"claimed:{anonymous_intent.id}:{anonymous_token_hash}".encode()
            ).hexdigest()
            anonymous_intent.status = ApplicationIntentStatus.CANCELLED
            anonymous_intent.safe_last_error = "Claimed into the existing student intent."
            existing.anonymous_token_hash = None
            claimed.append(existing)
            continue

        anonymous_intent.student_account_id = student_account_id
        anonymous_intent.anonymous_token_hash = None
        if anonymous_intent.status != ApplicationIntentStatus.SUBMITTED:
            anonymous_intent.status = ApplicationIntentStatus.READY
        claimed.append(anonymous_intent)
    db.flush()
    return list({intent.id: intent for intent in claimed}.values())


class _ApplicationRuntime:
    def __init__(
        self,
        db: Session,
        intent: ApplicationIntent,
        supplied_values: dict[str, Any] | None = None,
    ):
        self.db = db
        self.intent = intent
        # Values the student stated in chat for this submission only. They fill provider
        # form fields when the reusable profile has no usable value, and are never
        # written back to the profile.
        self.supplied_values: dict[str, Any] = dict(supplied_values or {})
        self.now = datetime.now(UTC)
        self.scholarship: Scholarship | None = None
        self.version: ScholarshipVersion | None = None
        self.organization: Organization | None = None
        self.template: ApplicationTemplate | None = None
        self.fields: list[ApplicationTemplateField] = []
        self.field_values: dict[uuid.UUID, Any] = {}
        self.documents: dict[StudentDocumentType, StudentDocument] = {}
        self.application: Application | None = None
        self.is_resubmission = False

    def _state(self, *, halted: bool = False) -> dict[str, Any]:
        return {
            "halted": halted,
            "status": self.intent.status.value,
            "application_id": (
                str(self.intent.application_id) if self.intent.application_id else None
            ),
        }

    def _block(self, message: str) -> dict[str, Any]:
        self.intent.status = ApplicationIntentStatus.BLOCKED
        self.intent.safe_last_error = message[:500]
        self.db.flush()
        return self._state(halted=True)

    def resolve_target(self) -> dict[str, Any]:
        if self.intent.status == ApplicationIntentStatus.SUBMITTED:
            return self._state(halted=True)
        if self.intent.expires_at <= self.now:
            self.intent.status = ApplicationIntentStatus.EXPIRED
            self.intent.safe_last_error = "This application request expired. Send a new apply request."
            self.db.flush()
            return self._state(halted=True)

        row = self.db.execute(
            select(Scholarship, ScholarshipVersion, Organization)
            .join(
                ScholarshipVersion,
                and_(
                    ScholarshipVersion.domain == Scholarship.domain,
                    ScholarshipVersion.scholarship_id == Scholarship.id,
                    ScholarshipVersion.id == Scholarship.current_published_version_id,
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
                Scholarship.domain == self.intent.scholarship_domain,
                Scholarship.id == self.intent.scholarship_id,
                Scholarship.lifecycle_status == ScholarshipLifecycle.ACTIVE,
                ScholarshipVersion.publication_status == PublicationStatus.PUBLISHED,
            )
        ).one_or_none()
        if row is None:
            return self._block("The scholarship is not currently published or active.")
        self.scholarship, self.version, self.organization = row
        self.template = self.db.scalar(
            select(ApplicationTemplate)
            .where(
                ApplicationTemplate.domain == self.scholarship.domain,
                ApplicationTemplate.organization_id == self.scholarship.organization_id,
                ApplicationTemplate.scholarship_version_id == self.version.id,
                ApplicationTemplate.status == "OWNER_CONFIRMED",
            )
            .order_by(ApplicationTemplate.template_version.desc())
        )
        if self.template is None:
            return self._block("The provider has not published an application template.")

        if (
            self.intent.scholarship_version_id
            and self.intent.scholarship_version_id != self.version.id
        ):
            return self._block(
                "The published scholarship version changed after authorization. "
                "Send a fresh apply request."
            )
        if (
            self.intent.application_template_id
            and self.intent.application_template_id != self.template.id
        ):
            return self._block(
                "The provider application template changed after authorization. "
                "Send a fresh apply request."
            )
        self.intent.organization_id = self.scholarship.organization_id
        self.intent.scholarship_version_id = self.version.id
        self.intent.application_template_id = self.template.id
        self.intent.safe_last_error = None
        self.db.flush()
        return self._state()

    def authentication_gate(self) -> dict[str, Any]:
        if self.intent.student_account_id is None:
            self.intent.status = ApplicationIntentStatus.WAITING_FOR_AUTH
            self.intent.safe_last_error = None
            self.db.flush()
            return self._state(halted=True)
        return self._state()

    def validate_window(self) -> dict[str, Any]:
        if self.intent.explicit_authorized_at is None:
            return self._block("Explicit student authorization is required.")
        assert self.version is not None
        if self.version.application_opens_at and self.now < self.version.application_opens_at:
            return self._block("The scholarship application window has not opened.")
        if (
            self.version.application_deadline_at
            and self.now > self.version.application_deadline_at
        ):
            return self._block("The scholarship application deadline has passed.")
        return self._state()

    def load_readiness(self) -> dict[str, Any]:
        assert self.template is not None
        assert self.intent.student_account_id is not None
        self.fields = list(
            self.db.scalars(
                select(ApplicationTemplateField)
                .where(
                    ApplicationTemplateField.domain == self.template.domain,
                    ApplicationTemplateField.application_template_id == self.template.id,
                )
                .order_by(ApplicationTemplateField.sort_order)
            ).all()
        )
        setting = self.db.get(StudentSetting, self.intent.student_account_id)
        missing_profile: list[str] = []
        for field in self.fields:
            binding = resolved_profile_binding(field)
            if binding and binding in self.supplied_values:
                # Presence is authoritative for this attempt. An invalid current answer
                # must stay missing rather than silently reviving an older profile value.
                value = self.supplied_values[binding]
            else:
                value = profile_value_for_field(
                    setting,
                    field,
                    explicitly_authorized=True,
                )
            if field.required and not field_value_is_valid(field, value):
                missing_profile.append(binding or field.field_key)
            elif field_value_is_valid(field, value):
                self.field_values[field.id] = value

        try:
            required_types = required_document_types(
                self.template.required_document_types or []
            )
        except ValueError:
            return self._block("The provider template contains an invalid document requirement.")
        self.documents = valid_student_documents(
            self.db,
            self.intent.student_account_id,
            required_types,
        )
        missing_documents = [
            document_type.value
            for document_type in required_types
            if document_type not in self.documents
        ]
        self.intent.missing_profile_fields = list(dict.fromkeys(missing_profile))
        self.intent.missing_document_types = missing_documents
        self.db.flush()
        return self._state()

    def persist_readiness(self) -> dict[str, Any]:
        if self.intent.missing_profile_fields:
            self.intent.status = ApplicationIntentStatus.WAITING_FOR_PROFILE
            self.intent.safe_last_error = None
            self.db.flush()
            return self._state(halted=True)
        if self.intent.missing_document_types:
            self.intent.status = ApplicationIntentStatus.WAITING_FOR_DOCUMENTS
            self.intent.safe_last_error = None
            self.db.flush()
            return self._state(halted=True)
        self.intent.status = ApplicationIntentStatus.READY
        self.intent.safe_last_error = None
        self.db.flush()
        return self._state()

    def _existing_application(self) -> Application | None:
        assert self.intent.student_account_id is not None
        applications = list(
            self.db.scalars(
                select(Application)
                .join(
                    ScholarshipVersion,
                    and_(
                        ScholarshipVersion.domain == Application.provider_domain,
                        ScholarshipVersion.id == Application.scholarship_version_id,
                    ),
                )
                .where(
                    Application.student_account_id == self.intent.student_account_id,
                    ScholarshipVersion.scholarship_id == self.intent.scholarship_id,
                )
                .order_by(Application.created_at.desc())
                .with_for_update()
            ).all()
        )
        return next(
            (
                application
                for application in applications
                if application.status in _SUBMITTED_APPLICATION_STATUSES
            ),
            applications[0] if applications else None,
        )

    def create_or_reuse_application(self) -> dict[str, Any]:
        assert self.intent.student_account_id is not None
        assert self.scholarship is not None
        assert self.version is not None
        assert self.template is not None
        application = self._existing_application()
        if application and application.status in _SUBMITTED_APPLICATION_STATUSES:
            self.intent.application_id = application.id
            self.intent.status = ApplicationIntentStatus.SUBMITTED
            self.intent.missing_profile_fields = []
            self.intent.missing_document_types = []
            self.intent.safe_last_error = None
            self.db.flush()
            return self._state(halted=True)
        if application and application.status == ApplicationStatus.WITHDRAWN:
            return self._block("A withdrawn application cannot be submitted automatically.")
        if application and application.status == ApplicationStatus.CORRECTION_REQUESTED:
            correction_at = self.db.scalar(
                select(ApplicationEvent.created_at)
                .where(
                    ApplicationEvent.application_id == application.id,
                    ApplicationEvent.event_type == ApplicationStatus.CORRECTION_REQUESTED.value,
                )
                .order_by(ApplicationEvent.created_at.desc())
            )
            if (
                correction_at is None
                or self.intent.explicit_authorized_at is None
                or self.intent.explicit_authorized_at <= correction_at
            ):
                return self._block(
                    "The provider requested corrections. Send a fresh apply request after "
                    "updating the requested information."
                )
            self.is_resubmission = True
        if application and (
            application.scholarship_version_id != self.version.id
            or application.application_template_id != self.template.id
        ):
            return self._block("An existing draft belongs to an older provider version.")

        created = application is None
        if application is None:
            application = Application(
                student_domain=OwnershipDomain.STUDENT,
                student_account_id=self.intent.student_account_id,
                provider_domain=self.scholarship.domain,
                organization_id=self.scholarship.organization_id,
                scholarship_version_id=self.version.id,
                application_template_id=self.template.id,
                status=ApplicationStatus.DRAFT,
                is_synthetic=self.scholarship.is_synthetic,
                consent_recorded_at=self.intent.explicit_authorized_at,
                agent_submission_authorized_at=self.intent.explicit_authorized_at,
            )
            self.db.add(application)
            self.db.flush()
        else:
            application.agent_submission_authorized_at = self.intent.explicit_authorized_at
            application.consent_recorded_at = (
                application.consent_recorded_at or self.intent.explicit_authorized_at
            )

        self.application = application
        self.intent.application_id = application.id
        self.intent.status = ApplicationIntentStatus.SUBMITTING
        encryption_key = settings.app_secret_key.get_secret_value()
        for field in self.fields:
            if field.id in self.field_values:
                upsert_encrypted_answer(
                    self.db,
                    application,
                    field,
                    self.field_values[field.id],
                    encryption_key,
                )
        attach_document_snapshots(self.db, application, self.documents)
        if created:
            self.db.add(
                ApplicationEvent(
                    application_id=application.id,
                    actor_domain=OwnershipDomain.STUDENT,
                    actor_account_id=self.intent.student_account_id,
                    event_type="DRAFT_CREATED",
                    safe_message=(
                        "Application created in the ScholarSaathi provider queue after "
                        "explicit student authorization."
                    ),
                )
            )
        self.db.flush()
        return self._state()

    def submit_application(self) -> dict[str, Any]:
        assert self.application is not None
        assert self.template is not None
        target_error = application_target_error(self.db, self.application, now=self.now)
        if target_error:
            return self._block(target_error)

        values = load_decrypted_application_answers(
            self.db,
            self.application.id,
            settings.app_secret_key.get_secret_value(),
        )
        missing_fields = invalid_required_field_keys(self.fields, values)
        if missing_fields:
            self.intent.missing_profile_fields = missing_fields
            self.intent.status = ApplicationIntentStatus.WAITING_FOR_PROFILE
            self.db.flush()
            return self._state(halted=True)

        required_types = required_document_types(
            self.template.required_document_types or []
        )
        selected_types = set(self.documents)
        missing_documents = [
            document_type.value
            for document_type in required_types
            if document_type not in selected_types
        ]
        expired_documents = [
            document.document_type.value
            for document in self.documents.values()
            if document.expiry_date and document.expiry_date < date.today()
        ]
        if missing_documents or expired_documents:
            self.intent.missing_document_types = list(
                dict.fromkeys([*missing_documents, *expired_documents])
            )
            self.intent.status = ApplicationIntentStatus.WAITING_FOR_DOCUMENTS
            self.db.flush()
            return self._state(halted=True)

        submitted_at = datetime.now(UTC)
        self.application.status = (
            ApplicationStatus.RESUBMITTED
            if self.is_resubmission
            else ApplicationStatus.SUBMITTED
        )
        self.application.submitted_at = submitted_at
        self.application.agent_submission_authorized_at = (
            self.intent.explicit_authorized_at
        )
        event_type = "RESUBMITTED" if self.is_resubmission else "SUBMITTED"
        self.db.add(
            ApplicationEvent(
                application_id=self.application.id,
                actor_domain=OwnershipDomain.STUDENT,
                actor_account_id=self.intent.student_account_id,
                event_type=event_type,
                safe_message=(
                    "Application resubmitted to the provider's ScholarSaathi queue after "
                    "a fresh explicit student request."
                    if self.is_resubmission
                    else "Application submitted to the provider's ScholarSaathi queue after "
                    "explicit student authorization."
                ),
            )
        )
        self.intent.status = ApplicationIntentStatus.SUBMITTED
        self.intent.missing_profile_fields = []
        self.intent.missing_document_types = []
        self.intent.safe_last_error = None
        self.db.flush()
        return self._state()

    def finalize(self) -> dict[str, Any]:
        self.db.flush()
        return self._state(halted=True)


def run_application_intent(
    db: Session,
    intent_id: uuid.UUID,
    supplied_values: dict[str, Any] | None = None,
) -> ApplicationIntent:
    intent = db.scalar(
        select(ApplicationIntent)
        .where(ApplicationIntent.id == intent_id)
        .with_for_update()
    )
    if intent is None:
        raise LookupError("Application intent was not found")
    try:
        run_application_flow(_ApplicationRuntime(db, intent, supplied_values), intent.id)
        db.commit()
    except Exception:
        logger.error("Application intent execution failed (intent_id=%s)", intent_id)
        db.rollback()
        recoverable = db.get(ApplicationIntent, intent_id)
        if recoverable is None:
            raise
        if recoverable.status not in {
            ApplicationIntentStatus.SUBMITTED,
            ApplicationIntentStatus.CANCELLED,
            ApplicationIntentStatus.EXPIRED,
            ApplicationIntentStatus.BLOCKED,
        }:
            recoverable.status = (
                ApplicationIntentStatus.READY
                if recoverable.student_account_id
                else ApplicationIntentStatus.WAITING_FOR_AUTH
            )
            recoverable.safe_last_error = (
                "The application workflow is temporarily unavailable and can be retried."
            )
            db.commit()
        return recoverable
    return db.get(ApplicationIntent, intent_id) or intent


def resume_pending_intents_for_student(
    db: Session,
    student_account_id: uuid.UUID,
) -> list[ApplicationIntent]:
    intent_ids = list(
        db.scalars(
            select(ApplicationIntent.id)
            .where(
                ApplicationIntent.student_account_id == student_account_id,
                ApplicationIntent.status.in_(_PENDING_STATUSES),
            )
            .order_by(ApplicationIntent.created_at)
        ).all()
    )
    return [run_application_intent(db, intent_id) for intent_id in intent_ids]
