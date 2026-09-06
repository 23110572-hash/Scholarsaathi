from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.catalog_data import (
    CATALOG_ORGANIZATION_SPECS,
    CATALOG_SCHOLARSHIP_SPECS,
)
from app.models import (
    Account,
    AccountRealm,
    AccountStatus,
    AIExtractionDraft,
    Application,
    ApplicationIntent,
    ApplicationTemplate,
    ApplicationTemplateField,
    AuditEvent,
    KnowledgeChunk,
    MemberRole,
    MemberStatus,
    Organization,
    OrganizationMember,
    OwnershipDomain,
    PublicationStatus,
    SavedScholarship,
    Scholarship,
    ScholarshipLifecycle,
    ScholarshipVersion,
    SourceDocument,
    ownership_domain_for_type,
)
from app.services.application_templates import DEFAULT_FIELD_DEFINITIONS

SEED_NAMESPACE = uuid.UUID("52b9b24a-9e5f-4e19-81b1-4da8245b9ae1")
CATALOG_REVISION = "nsp-demo-catalog-v2"
CATALOG_PUBLISHED_AT = datetime(2026, 8, 29, 12, tzinfo=UTC)
CATALOG_MARKER_ID = uuid.uuid5(SEED_NAMESPACE, f"catalog-marker:{CATALOG_REVISION}")
OWNER_CONFIRMED = "OWNER_CONFIRMED"

BROKEN_HELPER_SLUGS = tuple(f"central-demo-scholarship-{number}-2026" for number in range(1, 11))

LEGACY_REFERENCE_SLUGS = (
    "central-sector-scholarship-college-university-students",
    "national-means-cum-merit-scholarship-scheme",
    "aicte-pragati-scholarship-girl-students",
    "aicte-saksham-scholarship-students-with-disabilities",
    "aicte-swanath-scholarship-scheme",
    "ishan-uday-special-scholarship-north-eastern-region",
    "pg-indira-gandhi-scholarship-single-girl-child",
    "pg-scholarship-university-rank-holders",
    "aicte-postgraduate-scholarship-gate-gpat-ceed",
    "prime-ministers-scholarship-capf-assam-rifles",
    "prime-ministers-scholarship-rpf-rpsf",
    "pm-yasasvi-top-class-school-education",
    "pm-yasasvi-top-class-college-education",
    "pm-yasasvi-post-matric-obc-ebc-dnt",
    "post-matric-scholarship-scheduled-caste-students",
    "top-class-education-scheduled-caste-students",
    "national-overseas-scholarship-scheduled-caste-others",
    "national-fellowship-scholarship-higher-education-st",
    "national-overseas-scholarship-st-students",
    "top-class-education-students-with-disabilities",
    "west-bengal-swami-vivekananda-merit-cum-means",
    "odisha-e-medhabruti-scholarship",
    "gujarat-mukhyamantri-yuva-swavalamban-yojana",
    "maharashtra-rajarshi-shahu-maharaj-shikshan-shulkh-shishyavrutti",
    "karnataka-ssp-post-matric-scholarship",
    "kerala-state-merit-scholarship",
    "tamil-nadu-bc-mbc-dnc-post-matric-scholarship",
    "telangana-epass-post-matric-scholarship",
    "andhra-pradesh-jnanabhumi-post-matric-scholarship",
    "madhya-pradesh-mukhyamantri-medhavi-vidyarthi-yojana",
    "rajasthan-chief-minister-higher-education-scholarship",
    "uttar-pradesh-post-matric-scholarship",
    "bihar-post-matric-scholarship",
    "jharkhand-ekalyan-post-matric-scholarship",
    "haryana-har-chhatravratti-post-matric-scholarship",
    "punjab-dr-ambedkar-post-matric-scholarship",
    "himachal-pradesh-kalpana-chawla-chhatravriti",
    "assam-combined-merit-degree-scholarship",
    "uttarakhand-post-matric-scholarship",
    "chhattisgarh-post-matric-scholarship",
    "reliance-foundation-undergraduate-scholarships",
    "reliance-foundation-postgraduate-scholarships",
    "sbi-platinum-jubilee-asha-scholarship",
    "hdfc-bank-parivartan-ecss-programme",
    "kotak-kanya-scholarship",
    "tata-capital-pankh-scholarship-programme",
    "santoor-womens-scholarship",
    "foundation-for-excellence-scholarship",
    "colgate-keep-india-smiling-foundation-scholarship",
    "loreal-india-for-young-women-in-science-scholarship",
)

LEGACY_ORGANIZATION_SLUGS = {
    "central": "national-education-support-directorate-demo",
    "odisha": "odisha-student-opportunity-mission-demo",
    "aarohan": "aarohan-future-skills-demo",
    "udaan": "udaan-learning-trust-demo",
    **{
        str(spec["key"]): f"{spec['key']}-scholarship-reference"
        for spec in CATALOG_ORGANIZATION_SPECS
        if spec["key"] not in {"central", "odisha", "aarohan", "udaan"}
    },
}

LEGACY_PUBLISHER_LOGINS = {
    "central": "central.publisher@demo.scholarsaathi.local",
    "odisha": "odisha.publisher@demo.scholarsaathi.local",
    "aarohan": "aarohan.publisher@demo.scholarsaathi.local",
    "udaan": "udaan.publisher@demo.scholarsaathi.local",
    **{
        str(spec["key"]): f"{spec['key']}.catalog@demo.scholarsaathi.local"
        for spec in CATALOG_ORGANIZATION_SPECS
        if spec["key"] not in {"central", "odisha", "aarohan", "udaan"}
    },
}

_GENERIC_COURSE_MARKERS = {
    "ALL_RECOGNIZED_COURSES",
    "ALL_UNDERGRADUATE",
    "PROFESSIONAL_COURSES",
    "SCHOOL_EDUCATION",
    "STEM",
}


def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


def _set_values(instance: Any, **values: Any) -> None:
    for key, value in values.items():
        setattr(instance, key, value)


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _clean_legacy_catalog_once(session: Session) -> int:
    marker = session.get(
        AuditEvent,
        (OwnershipDomain.CENTRAL_GOVERNMENT, CATALOG_MARKER_ID),
    )
    if marker is not None:
        return 0

    target_slugs = {
        *(str(spec["slug"]) for spec in CATALOG_SCHOLARSHIP_SPECS),
        *LEGACY_REFERENCE_SLUGS,
        *BROKEN_HELPER_SLUGS,
    }
    scholarships = list(
        session.scalars(select(Scholarship).where(Scholarship.slug.in_(target_slugs)))
    )
    if not scholarships:
        return 0

    scholarship_ids = [scholarship.id for scholarship in scholarships]
    version_ids = list(
        session.scalars(
            select(ScholarshipVersion.id).where(
                ScholarshipVersion.scholarship_id.in_(scholarship_ids)
            )
        )
    )

    session.execute(
        delete(ApplicationIntent).where(ApplicationIntent.scholarship_id.in_(scholarship_ids))
    )
    if version_ids:
        session.execute(
            delete(Application).where(Application.scholarship_version_id.in_(version_ids))
        )
        # Template fields also point to evidence chunks without ON DELETE CASCADE.
        # Remove them explicitly before deleting scholarship versions/chunks.
        session.execute(
            delete(ApplicationTemplateField).where(
                ApplicationTemplateField.scholarship_version_id.in_(version_ids)
            )
        )
    session.execute(
        delete(SavedScholarship).where(SavedScholarship.scholarship_id.in_(scholarship_ids))
    )
    resource_ids = [*scholarship_ids, *version_ids]
    if resource_ids:
        session.execute(delete(AuditEvent).where(AuditEvent.resource_id.in_(resource_ids)))
    session.execute(
        update(Scholarship)
        .where(Scholarship.id.in_(scholarship_ids))
        .values(current_published_version_id=None)
    )
    session.flush()
    session.execute(delete(Scholarship).where(Scholarship.id.in_(scholarship_ids)))
    session.flush()
    return len(scholarships)


def _scheme_chunks(spec: dict[str, Any]) -> list[tuple[str, str]]:
    opens_at = _as_datetime(spec["opens_at"])
    deadline_at = _as_datetime(spec["deadline_at"])
    document_names = ", ".join(
        document.replace("_", " ").title() for document in spec["required_documents"]
    )
    return [
        ("Eligibility", spec["eligibility"]),
        ("Scholarship benefit", spec["benefit"]),
        (
            "Required documents",
            f"The application requires: {document_names}. All documents must be clear, "
            "current and linked to the applying student's profile.",
        ),
        (
            "Registration schedule",
            f"Registration opens on {opens_at:%d %B %Y} and the last date to submit is "
            f"{deadline_at:%d %B %Y} at {deadline_at:%H:%M} UTC.",
        ),
        ("Application process", " ".join(spec["application_steps"])),
        ("Selection and renewal", " ".join(spec["selection_steps"])),
    ]


def _course_options(spec: dict[str, Any]) -> list[str] | None:
    courses = list(spec["courses"])
    if any(course in _GENERIC_COURSE_MARKERS for course in courses):
        return None
    return courses


def _state_options(spec: dict[str, Any]) -> list[str] | None:
    states = list(spec["states"])
    return None if states == ["ALL"] else states


def reconcile_reference_catalog(
    session: Session,
    password_hash: str,
) -> dict[str, int]:
    """Rebuild and then idempotently reconcile the complete NSP demonstration catalog."""

    removed_count = _clean_legacy_catalog_once(session)
    organization_specs = {str(spec["key"]): spec for spec in CATALOG_ORGANIZATION_SPECS}

    account_expected_ids = {
        key: stable_id(f"{CATALOG_REVISION}:account:publisher:{key}") for key in organization_specs
    }
    desired_logins = [str(spec["publisher_login"]) for spec in CATALOG_ORGANIZATION_SPECS]
    existing_accounts = list(
        session.scalars(
            select(Account).where(
                or_(
                    Account.id.in_(list(account_expected_ids.values())),
                    Account.login_identifier.in_(
                        [*desired_logins, *LEGACY_PUBLISHER_LOGINS.values()]
                    ),
                )
            )
        )
    )
    accounts_by_id = {(account.domain, account.id): account for account in existing_accounts}
    accounts_by_login = {
        (account.domain, account.login_identifier.lower()): account for account in existing_accounts
    }
    accounts_by_key: dict[str, Account] = {}

    for key, spec in organization_specs.items():
        domain = ownership_domain_for_type(spec["type"])
        desired_login = str(spec["publisher_login"])
        account = (
            accounts_by_id.get((domain, account_expected_ids[key]))
            or accounts_by_login.get((domain, desired_login.lower()))
            or accounts_by_login.get((domain, LEGACY_PUBLISHER_LOGINS[key].lower()))
        )
        if account is None:
            account = Account(
                domain=domain,
                id=account_expected_ids[key],
                login_identifier=desired_login,
                password_hash=password_hash,
                realm=AccountRealm.ORGANIZATION_MEMBER,
                status=AccountStatus.ACTIVE,
            )
            session.add(account)
        else:
            _set_values(
                account,
                login_identifier=desired_login,
                realm=AccountRealm.ORGANIZATION_MEMBER,
                status=AccountStatus.ACTIVE,
            )
        accounts_by_key[key] = account
    session.flush()

    organization_expected_ids = {
        key: stable_id(f"{CATALOG_REVISION}:organization:{key}") for key in organization_specs
    }
    desired_slugs = [str(spec["slug"]) for spec in CATALOG_ORGANIZATION_SPECS]
    existing_organizations = list(
        session.scalars(
            select(Organization).where(
                or_(
                    Organization.id.in_(list(organization_expected_ids.values())),
                    Organization.slug.in_([*desired_slugs, *LEGACY_ORGANIZATION_SLUGS.values()]),
                )
            )
        )
    )
    organizations_by_id = {
        (organization.domain, organization.id): organization
        for organization in existing_organizations
    }
    organizations_by_slug = {
        (organization.domain, organization.slug): organization
        for organization in existing_organizations
    }
    organizations_by_key: dict[str, Organization] = {}

    for key, spec in organization_specs.items():
        domain = ownership_domain_for_type(spec["type"])
        desired_slug = str(spec["slug"])
        organization = (
            organizations_by_id.get((domain, organization_expected_ids[key]))
            or organizations_by_slug.get((domain, desired_slug))
            or organizations_by_slug.get((domain, LEGACY_ORGANIZATION_SLUGS[key]))
        )
        if organization is None:
            organization = Organization(
                domain=domain,
                id=organization_expected_ids[key],
                slug=desired_slug,
                legal_name=spec["legal_name"],
                display_name=spec["display_name"],
                type=spec["type"],
                jurisdiction_state_code=spec["state"],
                is_synthetic=True,
            )
            session.add(organization)
        else:
            _set_values(
                organization,
                slug=desired_slug,
                legal_name=spec["legal_name"],
                display_name=spec["display_name"],
                type=spec["type"],
                jurisdiction_state_code=spec["state"],
                is_synthetic=True,
            )
        organizations_by_key[key] = organization
    session.flush()

    member_expected_ids = {
        key: stable_id(f"{CATALOG_REVISION}:organization-member:{key}:owner")
        for key in organization_specs
    }
    existing_members = list(
        session.scalars(
            select(OrganizationMember).where(
                or_(
                    OrganizationMember.id.in_(list(member_expected_ids.values())),
                    OrganizationMember.account_id.in_(
                        [account.id for account in accounts_by_key.values()]
                    ),
                )
            )
        )
    )
    members_by_id = {(member.domain, member.id): member for member in existing_members}
    members_by_account = {(member.domain, member.account_id): member for member in existing_members}
    for key, organization in organizations_by_key.items():
        account = accounts_by_key[key]
        member = members_by_id.get(
            (organization.domain, member_expected_ids[key])
        ) or members_by_account.get((organization.domain, account.id))
        if member is None:
            member = OrganizationMember(
                domain=organization.domain,
                id=member_expected_ids[key],
                organization_id=organization.id,
                account_id=account.id,
                role=MemberRole.OWNER,
                status=MemberStatus.ACTIVE,
            )
            session.add(member)
        else:
            _set_values(
                member,
                organization_id=organization.id,
                account_id=account.id,
                role=MemberRole.OWNER,
                status=MemberStatus.ACTIVE,
            )
    session.flush()

    scholarship_expected_ids = {
        str(spec["slug"]): stable_id(f"{CATALOG_REVISION}:scholarship:{spec['slug']}")
        for spec in CATALOG_SCHOLARSHIP_SPECS
    }
    existing_scholarships = list(
        session.scalars(
            select(Scholarship).where(
                or_(
                    Scholarship.id.in_(list(scholarship_expected_ids.values())),
                    Scholarship.slug.in_([str(spec["slug"]) for spec in CATALOG_SCHOLARSHIP_SPECS]),
                )
            )
        )
    )
    scholarships_by_id = {
        (scholarship.domain, scholarship.id): scholarship for scholarship in existing_scholarships
    }
    scholarships_by_slug = {
        (scholarship.domain, scholarship.organization_id, scholarship.slug): scholarship
        for scholarship in existing_scholarships
    }
    scholarship_by_slug: dict[str, Scholarship] = {}

    for spec in CATALOG_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        organization = organizations_by_key[str(spec["organization"])]
        scholarship = scholarships_by_id.get(
            (organization.domain, scholarship_expected_ids[slug])
        ) or scholarships_by_slug.get((organization.domain, organization.id, slug))
        if scholarship is None:
            scholarship = Scholarship(
                domain=organization.domain,
                id=scholarship_expected_ids[slug],
                organization_id=organization.id,
                slug=slug,
                lifecycle_status=ScholarshipLifecycle.ACTIVE,
                is_synthetic=True,
            )
            session.add(scholarship)
        else:
            _set_values(
                scholarship,
                organization_id=organization.id,
                slug=slug,
                lifecycle_status=ScholarshipLifecycle.ACTIVE,
                is_synthetic=True,
                archived_at=None,
            )
        scholarship_by_slug[slug] = scholarship
    session.flush()

    version_expected_ids = {
        slug: stable_id(f"{CATALOG_REVISION}:scholarship-version:{slug}:1")
        for slug in scholarship_by_slug
    }
    existing_versions = list(
        session.scalars(
            select(ScholarshipVersion).where(
                or_(
                    ScholarshipVersion.id.in_(list(version_expected_ids.values())),
                    ScholarshipVersion.scholarship_id.in_(
                        [item.id for item in scholarship_by_slug.values()]
                    ),
                )
            )
        )
    )
    versions_by_id = {(version.domain, version.id): version for version in existing_versions}
    versions_by_number = {
        (version.domain, version.scholarship_id, version.version_number): version
        for version in existing_versions
    }
    version_by_slug: dict[str, ScholarshipVersion] = {}

    for spec in CATALOG_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        scholarship = scholarship_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        publisher = accounts_by_key[str(spec["organization"])]
        version = versions_by_id.get(
            (scholarship.domain, version_expected_ids[slug])
        ) or versions_by_number.get((scholarship.domain, scholarship.id, 1))
        chunks = _scheme_chunks(spec)
        if version is None:
            version = ScholarshipVersion(
                domain=scholarship.domain,
                id=version_expected_ids[slug],
                organization_id=organization.id,
                scholarship_id=scholarship.id,
                version_number=1,
                title=spec["title"],
                summary=spec["summary"],
                knowledge_summary=" ".join(text for _, text in chunks),
                academic_year=spec["academic_year"],
                scope=spec["scope"],
                applicable_state_codes=list(spec["states"]),
                education_levels=list(spec["levels"]),
                course_families=list(spec["courses"]),
                category_tags=list(spec["tags"]),
                eligibility_rules_json=dict(spec["eligibility_rules"]),
                document_requirements_json=list(spec["document_rules"]),
                application_process_json=dict(spec["application_process"]),
                benefit_summary=spec["benefit"],
                benefit_amount_min=spec["amount_min"],
                benefit_amount_max=spec["amount_max"],
                application_opens_at=_as_datetime(spec["opens_at"]),
                application_deadline_at=_as_datetime(spec["deadline_at"]),
                official_source_url=spec["official_source_url"],
                provider_helpdesk_url=spec["provider_helpdesk_url"],
                publication_status=PublicationStatus.PUBLISHED,
                last_provider_confirmed_at=CATALOG_PUBLISHED_AT,
                created_by=publisher.id,
                published_by=publisher.id,
                published_at=CATALOG_PUBLISHED_AT,
            )
            session.add(version)
        else:
            _set_values(
                version,
                organization_id=organization.id,
                scholarship_id=scholarship.id,
                version_number=1,
                title=spec["title"],
                summary=spec["summary"],
                knowledge_summary=" ".join(text for _, text in chunks),
                academic_year=spec["academic_year"],
                scope=spec["scope"],
                applicable_state_codes=list(spec["states"]),
                education_levels=list(spec["levels"]),
                course_families=list(spec["courses"]),
                category_tags=list(spec["tags"]),
                eligibility_rules_json=dict(spec["eligibility_rules"]),
                document_requirements_json=list(spec["document_rules"]),
                application_process_json=dict(spec["application_process"]),
                benefit_summary=spec["benefit"],
                benefit_amount_min=spec["amount_min"],
                benefit_amount_max=spec["amount_max"],
                application_opens_at=_as_datetime(spec["opens_at"]),
                application_deadline_at=_as_datetime(spec["deadline_at"]),
                official_source_url=spec["official_source_url"],
                provider_helpdesk_url=spec["provider_helpdesk_url"],
                publication_status=PublicationStatus.PUBLISHED,
                last_provider_confirmed_at=CATALOG_PUBLISHED_AT,
                created_by=publisher.id,
                published_by=publisher.id,
                published_at=CATALOG_PUBLISHED_AT,
            )
        version_by_slug[slug] = version
    session.flush()

    for slug, scholarship in scholarship_by_slug.items():
        scholarship.current_published_version_id = version_by_slug[slug].id
    session.flush()

    source_expected_ids = {
        slug: stable_id(f"{CATALOG_REVISION}:source-document:{slug}:guidelines")
        for slug in scholarship_by_slug
    }
    existing_sources = list(
        session.scalars(
            select(SourceDocument).where(SourceDocument.id.in_(list(source_expected_ids.values())))
        )
    )
    sources_by_id = {(source.domain, source.id): source for source in existing_sources}
    source_by_slug: dict[str, SourceDocument] = {}

    for spec in CATALOG_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        version = version_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        publisher = accounts_by_key[str(spec["organization"])]
        chunks = _scheme_chunks(spec)
        source_text = "\n\n".join(f"{title}\n{text}" for title, text in chunks)
        encoded_source = source_text.encode("utf-8")
        source = sources_by_id.get((version.domain, source_expected_ids[slug]))
        if source is None:
            source = SourceDocument(
                domain=version.domain,
                id=source_expected_ids[slug],
                organization_id=organization.id,
                scholarship_version_id=version.id,
                display_name=f"{spec['title']} — Scheme Guidelines",
                source_kind="SCHEME_GUIDELINE",
                content_type="text/plain; charset=utf-8",
                size_bytes=len(encoded_source),
                storage_key=f"catalog/{slug}/guidelines.txt",
                source_url=spec["official_source_url"],
                checksum_sha256=hashlib.sha256(encoded_source).hexdigest(),
                extracted_text=source_text,
                usage_rights_confirmed_at=CATALOG_PUBLISHED_AT,
                confirmation_status=OWNER_CONFIRMED,
                uploaded_by=publisher.id,
            )
            session.add(source)
        else:
            _set_values(
                source,
                organization_id=organization.id,
                scholarship_version_id=version.id,
                display_name=f"{spec['title']} — Scheme Guidelines",
                source_kind="SCHEME_GUIDELINE",
                content_type="text/plain; charset=utf-8",
                size_bytes=len(encoded_source),
                storage_key=f"catalog/{slug}/guidelines.txt",
                source_url=spec["official_source_url"],
                checksum_sha256=hashlib.sha256(encoded_source).hexdigest(),
                extracted_text=source_text,
                usage_rights_confirmed_at=CATALOG_PUBLISHED_AT,
                confirmation_status=OWNER_CONFIRMED,
                uploaded_by=publisher.id,
            )
        source_by_slug[slug] = source
    session.flush()

    chunk_expected_ids = {
        (str(spec["slug"]), ordinal): stable_id(
            f"{CATALOG_REVISION}:knowledge-chunk:{spec['slug']}:{ordinal}"
        )
        for spec in CATALOG_SCHOLARSHIP_SPECS
        for ordinal in range(1, 7)
    }
    existing_chunks = list(
        session.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.id.in_(list(chunk_expected_ids.values())))
        )
    )
    chunks_by_id = {(chunk.domain, chunk.id): chunk for chunk in existing_chunks}
    chunk_ids_by_slug: dict[str, list[uuid.UUID]] = {}

    for spec in CATALOG_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        version = version_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        source = source_by_slug[slug]
        chunk_ids: list[uuid.UUID] = []
        for ordinal, (section_title, provider_text) in enumerate(_scheme_chunks(spec), start=1):
            chunk_id = chunk_expected_ids[(slug, ordinal)]
            chunk = chunks_by_id.get((version.domain, chunk_id))
            if chunk is None:
                chunk = KnowledgeChunk(
                    domain=version.domain,
                    id=chunk_id,
                    organization_id=organization.id,
                    scholarship_version_id=version.id,
                    source_document_id=source.id,
                    ordinal=ordinal,
                    page_number=ordinal,
                    section_title=section_title,
                    provider_text=provider_text,
                    embedding_reference=None,
                    confirmation_status=OWNER_CONFIRMED,
                )
                session.add(chunk)
            else:
                _set_values(
                    chunk,
                    organization_id=organization.id,
                    scholarship_version_id=version.id,
                    source_document_id=source.id,
                    ordinal=ordinal,
                    page_number=ordinal,
                    section_title=section_title,
                    provider_text=provider_text,
                    embedding_reference=None,
                    confirmation_status=OWNER_CONFIRMED,
                )
            chunk_ids.append(chunk.id)
        chunk_ids_by_slug[slug] = chunk_ids
    session.flush()

    extraction_expected_ids = {
        slug: stable_id(f"{CATALOG_REVISION}:ai-extraction:{slug}:1")
        for slug in scholarship_by_slug
    }
    existing_extractions = list(
        session.scalars(
            select(AIExtractionDraft).where(
                AIExtractionDraft.id.in_(list(extraction_expected_ids.values()))
            )
        )
    )
    extractions_by_id = {(draft.domain, draft.id): draft for draft in existing_extractions}

    template_expected_ids = {
        slug: stable_id(f"{CATALOG_REVISION}:application-template:{slug}:1")
        for slug in scholarship_by_slug
    }
    existing_templates = list(
        session.scalars(
            select(ApplicationTemplate).where(
                or_(
                    ApplicationTemplate.id.in_(list(template_expected_ids.values())),
                    ApplicationTemplate.scholarship_version_id.in_(
                        [version.id for version in version_by_slug.values()]
                    ),
                )
            )
        )
    )
    templates_by_id = {(template.domain, template.id): template for template in existing_templates}
    templates_by_version = {
        (template.domain, template.scholarship_version_id, template.template_version): template
        for template in existing_templates
    }
    template_by_slug: dict[str, ApplicationTemplate] = {}

    for spec in CATALOG_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        version = version_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        publisher = accounts_by_key[str(spec["organization"])]
        extraction = extractions_by_id.get((version.domain, extraction_expected_ids[slug]))
        extracted_content = {
            "title": spec["title"],
            "summary": spec["summary"],
            "academic_year": spec["academic_year"],
            "scope": spec["scope"],
            "states": list(spec["states"]),
            "education_levels": list(spec["levels"]),
            "course_families": list(spec["courses"]),
            "category_tags": list(spec["tags"]),
            "benefit_summary": spec["benefit"],
            "benefit_amount_min": spec["amount_min"],
            "benefit_amount_max": spec["amount_max"],
            "eligibility_rules": dict(spec["eligibility_rules"]),
            "document_requirements": list(spec["document_rules"]),
            "application_process": dict(spec["application_process"]),
        }
        if extraction is None:
            extraction = AIExtractionDraft(
                domain=version.domain,
                id=extraction_expected_ids[slug],
                organization_id=organization.id,
                scholarship_version_id=version.id,
                model_identifier="nsp-catalog-rule-builder-v2",
                prompt_version="structured-scholarship-v2",
                extracted_content_json=extracted_content,
                source_mapping_json={
                    "confirmed_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids_by_slug[slug]]
                },
                status=OWNER_CONFIRMED,
                confirmed_by=publisher.id,
                confirmed_at=CATALOG_PUBLISHED_AT,
            )
            session.add(extraction)
        else:
            _set_values(
                extraction,
                organization_id=organization.id,
                scholarship_version_id=version.id,
                model_identifier="nsp-catalog-rule-builder-v2",
                prompt_version="structured-scholarship-v2",
                extracted_content_json=extracted_content,
                source_mapping_json={
                    "confirmed_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids_by_slug[slug]]
                },
                status=OWNER_CONFIRMED,
                confirmed_by=publisher.id,
                confirmed_at=CATALOG_PUBLISHED_AT,
            )

        template = templates_by_id.get(
            (version.domain, template_expected_ids[slug])
        ) or templates_by_version.get((version.domain, version.id, 1))
        if template is None:
            template = ApplicationTemplate(
                domain=version.domain,
                id=template_expected_ids[slug],
                organization_id=organization.id,
                scholarship_version_id=version.id,
                template_version=1,
                status=OWNER_CONFIRMED,
                required_document_types=list(spec["required_documents"]),
                created_by=publisher.id,
                confirmed_by=publisher.id,
                confirmed_at=CATALOG_PUBLISHED_AT,
            )
            session.add(template)
        else:
            _set_values(
                template,
                organization_id=organization.id,
                scholarship_version_id=version.id,
                template_version=1,
                status=OWNER_CONFIRMED,
                required_document_types=list(spec["required_documents"]),
                created_by=publisher.id,
                confirmed_by=publisher.id,
                confirmed_at=CATALOG_PUBLISHED_AT,
            )
        template_by_slug[slug] = template
    session.flush()

    field_expected_ids = {
        (str(spec["slug"]), definition.key): stable_id(
            f"{CATALOG_REVISION}:application-template-field:{spec['slug']}:{definition.key}"
        )
        for spec in CATALOG_SCHOLARSHIP_SPECS
        for definition in DEFAULT_FIELD_DEFINITIONS
    }
    existing_fields = list(
        session.scalars(
            select(ApplicationTemplateField).where(
                or_(
                    ApplicationTemplateField.id.in_(list(field_expected_ids.values())),
                    ApplicationTemplateField.application_template_id.in_(
                        [template.id for template in template_by_slug.values()]
                    ),
                )
            )
        )
    )
    fields_by_id = {(field.domain, field.id): field for field in existing_fields}
    fields_by_key = {
        (field.domain, field.application_template_id, field.field_key): field
        for field in existing_fields
    }

    audit_expected_ids = {
        slug: stable_id(f"{CATALOG_REVISION}:audit:publish:{slug}:1")
        for slug in scholarship_by_slug
    }
    existing_audits = list(
        session.scalars(
            select(AuditEvent).where(AuditEvent.id.in_(list(audit_expected_ids.values())))
        )
    )
    audits_by_id = {(audit.domain, audit.id): audit for audit in existing_audits}
    income_options = [
        "UP_TO_250000",
        "250001_TO_400000",
        "400001_TO_600000",
        "600001_TO_800000",
        "ABOVE_800000",
    ]

    for spec in CATALOG_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        version = version_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        publisher = accounts_by_key[str(spec["organization"])]
        template = template_by_slug[slug]
        option_sets = {
            "course": _course_options(spec),
            "domicile_state": _state_options(spec),
            "family_income_band": income_options,
        }
        for sort_order, definition in enumerate(DEFAULT_FIELD_DEFINITIONS, start=1):
            field_id = field_expected_ids[(slug, definition.key)]
            field = fields_by_id.get((version.domain, field_id)) or fields_by_key.get(
                (version.domain, template.id, definition.key)
            )
            if field is None:
                field = ApplicationTemplateField(
                    domain=version.domain,
                    id=field_id,
                    organization_id=organization.id,
                    scholarship_version_id=version.id,
                    application_template_id=template.id,
                    field_key=definition.key,
                    label=definition.label,
                    help_text=definition.help_text,
                    field_type=definition.field_type,
                    required=True,
                    options_json=option_sets.get(definition.key),
                    profile_binding=definition.profile_binding,
                    source_chunk_id=chunk_ids_by_slug[slug][0],
                    sort_order=sort_order,
                )
                session.add(field)
            else:
                _set_values(
                    field,
                    organization_id=organization.id,
                    scholarship_version_id=version.id,
                    application_template_id=template.id,
                    field_key=definition.key,
                    label=definition.label,
                    help_text=definition.help_text,
                    field_type=definition.field_type,
                    required=True,
                    options_json=option_sets.get(definition.key),
                    profile_binding=definition.profile_binding,
                    source_chunk_id=chunk_ids_by_slug[slug][0],
                    sort_order=sort_order,
                )

        audit = audits_by_id.get((version.domain, audit_expected_ids[slug]))
        if audit is None:
            audit = AuditEvent(
                domain=version.domain,
                id=audit_expected_ids[slug],
                actor_account_id=publisher.id,
                organization_id=organization.id,
                action="SCHOLARSHIP_VERSION_PUBLISHED_BY_OWNER",
                resource_type="scholarship_version",
                resource_id=version.id,
                safe_metadata_json={
                    "catalog_revision": CATALOG_REVISION,
                    "demonstration_data": True,
                    "version_number": 1,
                    "academic_year": spec["academic_year"],
                },
            )
            session.add(audit)
        else:
            _set_values(
                audit,
                actor_account_id=publisher.id,
                organization_id=organization.id,
                action="SCHOLARSHIP_VERSION_PUBLISHED_BY_OWNER",
                resource_type="scholarship_version",
                resource_id=version.id,
                safe_metadata_json={
                    "catalog_revision": CATALOG_REVISION,
                    "demonstration_data": True,
                    "version_number": 1,
                    "academic_year": spec["academic_year"],
                },
            )

    marker = session.get(
        AuditEvent,
        (OwnershipDomain.CENTRAL_GOVERNMENT, CATALOG_MARKER_ID),
    )
    if marker is None:
        central_organization = organizations_by_key["central"]
        central_publisher = accounts_by_key["central"]
        session.add(
            AuditEvent(
                domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                id=CATALOG_MARKER_ID,
                actor_account_id=central_publisher.id,
                organization_id=central_organization.id,
                action="CATALOG_REBUILD_COMPLETED",
                resource_type="scholarship_catalog",
                resource_id=None,
                safe_metadata_json={
                    "catalog_revision": CATALOG_REVISION,
                    "scholarship_count": len(CATALOG_SCHOLARSHIP_SPECS),
                },
            )
        )

    session.flush()
    return {
        "removed_legacy_scholarships": removed_count,
        "catalog_organizations": len(CATALOG_ORGANIZATION_SPECS),
        "catalog_scholarships": len(CATALOG_SCHOLARSHIP_SPECS),
    }
