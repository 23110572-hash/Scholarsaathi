from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import UTC, datetime

from app.database import SessionLocal
from app.models import (
    Account,
    ApplicationTemplate,
    ApplicationTemplateField,
    KnowledgeChunk,
    Organization,
    OwnershipDomain,
    PublicationStatus,
    Scholarship,
    ScholarshipLifecycle,
    ScholarshipVersion,
    SourceDocument,
)
from app.services.application_templates import (
    DEFAULT_FIELD_DEFINITIONS,
    DEFAULT_REQUIRED_DOCUMENT_TYPES,
)

SEED_NAMESPACE = uuid.UUID("52b9b24a-9e5f-4e19-81b1-4da8245b9ae1")


def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


def timestamp(month: int, day: int, hour: int = 9) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=UTC)


def main() -> None:
    session = SessionLocal()
    try:
        organization = (
            session.query(Organization)
            .filter_by(slug="national-education-support-directorate-demo")
            .first()
        )
        publisher = (
            session.query(Account)
            .filter_by(login_identifier="central.publisher@demo.scholarsaathi.local")
            .first()
        )
        if organization is None or publisher is None:
            raise RuntimeError("Central demo organization and publisher must be seeded first")

        for number in range(1, 11):
            slug = f"central-demo-scholarship-{number}-2026"
            title = f"Central Demo Scholarship Programme {number}"
            scholarship_id = stable_id(f"scholarship:{slug}")
            version_id = stable_id(f"version:{slug}:1")

            scholarship = session.get(
                Scholarship,
                (OwnershipDomain.CENTRAL_GOVERNMENT, scholarship_id),
            )
            if scholarship is None:
                scholarship = Scholarship(
                    domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                    id=scholarship_id,
                    organization_id=organization.id,
                    slug=slug,
                    lifecycle_status=ScholarshipLifecycle.ACTIVE,
                    is_synthetic=True,
                )
                session.add(scholarship)
                session.flush()

            version = session.get(
                ScholarshipVersion,
                (OwnershipDomain.CENTRAL_GOVERNMENT, version_id),
            )
            if version is None:
                version = ScholarshipVersion(
                    domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                    id=version_id,
                    scholarship_id=scholarship_id,
                    organization_id=organization.id,
                    version_number=1,
                    publication_status=PublicationStatus.PUBLISHED,
                    knowledge_summary="Synthetic eligibility requirements.",
                    title=title,
                    summary=f"Synthetic demo scholarship {number} for central government.",
                    academic_year="2026-27",
                    scope="NATIONAL",
                    applicable_state_codes=["ALL"],
                    education_levels=["UNDERGRADUATE"],
                    course_families=["BTECH", "BE", "BCA", "BSC"],
                    category_tags=["MERIT", "INCOME"],
                    benefit_amount_min=10000 * number,
                    benefit_amount_max=15000 * number,
                    benefit_summary=f"Up to ₹{15000 * number} annual academic support.",
                    application_opens_at=timestamp(8, 1),
                    application_deadline_at=timestamp(11, 30, 23),
                    official_source_url=f"https://provider.gov.in/demo/{slug}",
                    provider_helpdesk_url="https://provider.gov.in/help",
                    last_provider_confirmed_at=timestamp(8, 20),
                    created_by=publisher.id,
                    published_by=publisher.id,
                    published_at=timestamp(8, 20),
                )
                session.add(version)
                session.flush()
            scholarship.current_published_version_id = version.id

            template_id = stable_id(f"application-template:{slug}")
            template = session.get(
                ApplicationTemplate,
                (OwnershipDomain.CENTRAL_GOVERNMENT, template_id),
            )
            if template is None:
                template = ApplicationTemplate(
                    domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                    id=template_id,
                    organization_id=organization.id,
                    scholarship_version_id=version_id,
                    template_version=1,
                    status="OWNER_CONFIRMED",
                    required_document_types=list(DEFAULT_REQUIRED_DOCUMENT_TYPES),
                    created_by=publisher.id,
                    confirmed_by=publisher.id,
                    confirmed_at=timestamp(8, 19),
                )
                session.add(template)
                session.flush()
            else:
                template.required_document_types = list(DEFAULT_REQUIRED_DOCUMENT_TYPES)

            source_id = stable_id(f"source-document:{slug}:guidelines")
            source = session.get(
                SourceDocument,
                (OwnershipDomain.CENTRAL_GOVERNMENT, source_id),
            )
            source_text = (
                "Applicants must be enrolled in an undergraduate programme. "
                "The income ceiling is ₹8,00,000."
            )
            if source is None:
                source = SourceDocument(
                    domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                    id=source_id,
                    organization_id=organization.id,
                    scholarship_version_id=version_id,
                    display_name=f"{title} — Synthetic Guidelines",
                    source_kind="PROVIDER_GUIDELINE",
                    content_type="text/plain",
                    size_bytes=len(source_text.encode("utf-8")),
                    storage_key=f"synthetic/{slug}/guidelines.txt",
                    source_url=f"https://provider.gov.in/demo/{slug}/guidelines",
                    checksum_sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                    extracted_text=source_text,
                    usage_rights_confirmed_at=timestamp(8, 19),
                    confirmation_status="OWNER_CONFIRMED",
                    uploaded_by=publisher.id,
                )
                session.add(source)
                session.flush()

            chunk_id = stable_id(f"chunk:{slug}:eligibility")
            chunk = session.get(
                KnowledgeChunk,
                (OwnershipDomain.CENTRAL_GOVERNMENT, chunk_id),
            )
            if chunk is None:
                chunk = KnowledgeChunk(
                    domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                    id=chunk_id,
                    scholarship_version_id=version_id,
                    organization_id=organization.id,
                    source_document_id=source_id,
                    ordinal=1,
                    page_number=1,
                    section_title="Eligibility",
                    provider_text=source_text,
                    confirmation_status="OWNER_CONFIRMED",
                )
                session.add(chunk)
                session.flush()

            option_sets = {
                "course": version.course_families,
                "domicile_state": version.applicable_state_codes,
                "family_income_band": [
                    "UP_TO_250000",
                    "250001_TO_400000",
                    "400001_TO_600000",
                    "600001_TO_800000",
                    "ABOVE_800000",
                ],
            }
            for sort_order, definition in enumerate(DEFAULT_FIELD_DEFINITIONS, start=1):
                field_id = stable_id(
                    f"application-template-field:{slug}:{definition.key}"
                )
                field = session.get(
                    ApplicationTemplateField,
                    (OwnershipDomain.CENTRAL_GOVERNMENT, field_id),
                )
                if field is None:
                    field = ApplicationTemplateField(
                        domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                        id=field_id,
                        organization_id=organization.id,
                        scholarship_version_id=version_id,
                        application_template_id=template_id,
                        field_key=definition.key,
                        label=definition.label,
                        help_text=definition.help_text,
                        field_type=definition.field_type,
                        required=True,
                        options_json=option_sets.get(definition.key),
                        profile_binding=definition.profile_binding,
                        source_chunk_id=chunk_id,
                        sort_order=sort_order,
                    )
                    session.add(field)
                else:
                    field.profile_binding = definition.profile_binding
                    field.options_json = option_sets.get(definition.key)

        session.commit()
        print("Successfully added 10 scholarships with canonical application templates.")
    except Exception as exc:
        session.rollback()
        print(f"Error adding scholarships: {exc}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
