from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from app.catalog_data import (
    CONTENT_REPHRASED_NOTICE,
    REFERENCE_ORGANIZATION_SPECS,
    REFERENCE_SCHOLARSHIP_SPECS,
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
    OrganizationType,
    OwnershipDomain,
    PublicationStatus,
    SavedScholarship,
    Scholarship,
    ScholarshipLifecycle,
    ScholarshipVersion,
    SourceDocument,
    ownership_domain_for_type,
)
from app.services.application_templates import (
    DEFAULT_FIELD_DEFINITIONS,
    DEFAULT_REQUIRED_DOCUMENT_TYPES,
)

SEED_NAMESPACE = uuid.UUID("52b9b24a-9e5f-4e19-81b1-4da8245b9ae1")
REFERENCE_CATALOG_AT = datetime(2026, 8, 29, 12, tzinfo=UTC)
REFERENCE_STATUS = "PUBLIC_SOURCE_REFERENCE"

# Exact records created by the removed add_10_scholarships.py helper. Both the ID and
# slug must match before cleanup, so similarly named user/provider records are untouched.
BROKEN_HELPER_TARGETS = {
    uuid.UUID("6e226c05-cae7-589b-b146-e13bf7b54956"): "central-demo-scholarship-1-2026",
    uuid.UUID("ba0e7625-05ab-577c-a4e7-19f96133a816"): "central-demo-scholarship-2-2026",
    uuid.UUID("318a16f7-09f7-5f7d-b603-c1f0b4ce4422"): "central-demo-scholarship-3-2026",
    uuid.UUID("ef6da622-571a-52b7-bdf2-1ae9e7afc6ab"): "central-demo-scholarship-4-2026",
    uuid.UUID("59a905c3-9ce6-5ebe-b8ed-f4598a1c7524"): "central-demo-scholarship-5-2026",
    uuid.UUID("fd2e68c8-27fd-54b6-91af-12a134a982d4"): "central-demo-scholarship-6-2026",
    uuid.UUID("b6e86160-b25e-5ba5-983c-8f67cd851e53"): "central-demo-scholarship-7-2026",
    uuid.UUID("70053608-d7f9-5177-8af5-bd1583b91b43"): "central-demo-scholarship-8-2026",
    uuid.UUID("b5d75df2-8dcc-5714-aaad-e501e428f0c5"): "central-demo-scholarship-9-2026",
    uuid.UUID("7329a64a-e4ba-5996-843c-3de028506170"): "central-demo-scholarship-10-2026",
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


def _remove_broken_helper_records(session: Session) -> int:
    exact_conditions = [
        and_(Scholarship.id == scholarship_id, Scholarship.slug == slug)
        for scholarship_id, slug in BROKEN_HELPER_TARGETS.items()
    ]
    target_ids = list(
        session.scalars(
            select(Scholarship.id).where(
                Scholarship.domain == OwnershipDomain.CENTRAL_GOVERNMENT,
                or_(*exact_conditions),
            )
        )
    )
    if not target_ids:
        return 0

    version_ids = list(
        session.scalars(
            select(ScholarshipVersion.id).where(
                ScholarshipVersion.domain == OwnershipDomain.CENTRAL_GOVERNMENT,
                ScholarshipVersion.scholarship_id.in_(target_ids),
            )
        )
    )

    # Remove only dependencies that prevent deleting these exact scholarship roots.
    session.execute(
        delete(ApplicationIntent).where(
            ApplicationIntent.scholarship_domain == OwnershipDomain.CENTRAL_GOVERNMENT,
            ApplicationIntent.scholarship_id.in_(target_ids),
        )
    )
    if version_ids:
        session.execute(
            delete(Application).where(
                Application.provider_domain == OwnershipDomain.CENTRAL_GOVERNMENT,
                Application.scholarship_version_id.in_(version_ids),
            )
        )
    session.execute(
        delete(SavedScholarship).where(
            SavedScholarship.scholarship_domain == OwnershipDomain.CENTRAL_GOVERNMENT,
            SavedScholarship.scholarship_id.in_(target_ids),
        )
    )
    session.execute(
        update(Scholarship)
        .where(
            Scholarship.domain == OwnershipDomain.CENTRAL_GOVERNMENT,
            Scholarship.id.in_(target_ids),
        )
        .values(current_published_version_id=None)
    )
    session.flush()
    session.execute(
        delete(Scholarship).where(
            Scholarship.domain == OwnershipDomain.CENTRAL_GOVERNMENT,
            Scholarship.id.in_(target_ids),
        )
    )
    session.flush()
    return len(target_ids)


def _scope_for_type(organization_type: OrganizationType) -> str:
    if organization_type == OrganizationType.CENTRAL_GOVERNMENT:
        return "NATIONAL"
    if organization_type == OrganizationType.STATE_GOVERNMENT:
        return "STATE"
    if organization_type == OrganizationType.PRIVATE_COMPANY:
        return "NATIONAL_PRIVATE"
    return "NATIONAL_NGO"


def _reference_chunks(spec: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("Overview", spec["summary"]),
        ("Eligibility", spec["eligibility"]),
        ("Benefit", spec["benefit"]),
        (
            "Official source and application guidance",
            (
                f"{CONTENT_REPHRASED_NOTICE} This is a public-source reference entry; "
                "the provider has not onboarded or confirmed it in ScholarSaathi. "
                "Application dates and procedures can change, so use the official source: "
                f"{spec['official_source_url']}"
            ),
        ),
    ]


def _course_options(spec: dict[str, Any]) -> list[str] | None:
    courses = list(spec["courses"])
    if any(course in _GENERIC_COURSE_MARKERS for course in courses):
        return None
    return courses


def reconcile_reference_catalog(
    session: Session,
    password_hash: str,
) -> dict[str, int]:
    """Remove the exact broken helper rows and idempotently reconcile 50 references.

    The caller owns the transaction. Reference entries remain synthetic internally because
    their real providers have not onboarded; public text always points to the official source.
    """

    removed_count = _remove_broken_helper_records(session)
    organization_specs = {str(spec["key"]): spec for spec in REFERENCE_ORGANIZATION_SPECS}

    account_expected_ids = {
        key: stable_id(f"reference:account:publisher:{key}") for key in organization_specs
    }
    publisher_logins = [str(spec["publisher_login"]) for spec in REFERENCE_ORGANIZATION_SPECS]
    existing_accounts = list(
        session.scalars(
            select(Account).where(
                or_(
                    Account.id.in_(list(account_expected_ids.values())),
                    Account.login_identifier.in_(publisher_logins),
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
        login = str(spec["publisher_login"])
        expected_id = account_expected_ids[key]
        account = accounts_by_id.get((domain, expected_id)) or accounts_by_login.get(
            (domain, login.lower())
        )
        if account is None:
            account = Account(
                domain=domain,
                id=expected_id,
                login_identifier=login,
                password_hash=password_hash,
                realm=AccountRealm.ORGANIZATION_MEMBER,
                status=AccountStatus.ACTIVE,
            )
            session.add(account)
        else:
            _set_values(
                account,
                login_identifier=login,
                realm=AccountRealm.ORGANIZATION_MEMBER,
                status=AccountStatus.ACTIVE,
            )
        accounts_by_key[key] = account
    session.flush()

    organization_expected_ids = {
        key: stable_id(f"reference:organization:{key}") for key in organization_specs
    }
    organization_slugs = [str(spec["slug"]) for spec in REFERENCE_ORGANIZATION_SPECS]
    existing_organizations = list(
        session.scalars(
            select(Organization).where(
                or_(
                    Organization.id.in_(list(organization_expected_ids.values())),
                    Organization.slug.in_(organization_slugs),
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
        expected_id = organization_expected_ids[key]
        slug = str(spec["slug"])
        organization = organizations_by_id.get((domain, expected_id)) or organizations_by_slug.get(
            (domain, slug)
        )
        if organization is None:
            organization = Organization(domain=domain, id=expected_id, slug=slug)
            session.add(organization)
        _set_values(
            organization,
            slug=slug,
            legal_name=spec["legal_name"],
            display_name=spec["display_name"],
            type=spec["type"],
            jurisdiction_state_code=spec["state"],
            is_synthetic=True,
        )
        organizations_by_key[key] = organization
    session.flush()

    member_expected_ids = {
        key: stable_id(f"reference:organization-member:{key}:owner") for key in organization_specs
    }
    account_ids = [account.id for account in accounts_by_key.values()]
    existing_members = list(
        session.scalars(
            select(OrganizationMember).where(
                or_(
                    OrganizationMember.id.in_(list(member_expected_ids.values())),
                    OrganizationMember.account_id.in_(account_ids),
                )
            )
        )
    )
    members_by_id = {(member.domain, member.id): member for member in existing_members}
    members_by_account = {(member.domain, member.account_id): member for member in existing_members}
    for key, organization in organizations_by_key.items():
        account = accounts_by_key[key]
        expected_id = member_expected_ids[key]
        member = members_by_id.get((organization.domain, expected_id)) or members_by_account.get(
            (organization.domain, account.id)
        )
        if member is None:
            member = OrganizationMember(domain=organization.domain, id=expected_id)
            session.add(member)
        _set_values(
            member,
            organization_id=organization.id,
            account_id=account.id,
            role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE,
        )
    session.flush()

    scholarship_expected_ids = {
        str(spec["slug"]): stable_id(f"reference:scholarship:{spec['slug']}")
        for spec in REFERENCE_SCHOLARSHIP_SPECS
    }
    reference_slugs = [str(spec["slug"]) for spec in REFERENCE_SCHOLARSHIP_SPECS]
    existing_scholarships = list(
        session.scalars(
            select(Scholarship).where(
                or_(
                    Scholarship.id.in_(list(scholarship_expected_ids.values())),
                    Scholarship.slug.in_(reference_slugs),
                )
            )
        )
    )
    scholarships_by_id = {
        (scholarship.domain, scholarship.id): scholarship for scholarship in existing_scholarships
    }
    scholarships_by_owner_slug = {
        (scholarship.domain, scholarship.organization_id, scholarship.slug): scholarship
        for scholarship in existing_scholarships
    }
    scholarships_by_slug: dict[str, Scholarship] = {}

    for spec in REFERENCE_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        organization = organizations_by_key[str(spec["organization"])]
        expected_id = scholarship_expected_ids[slug]
        scholarship = scholarships_by_id.get(
            (organization.domain, expected_id)
        ) or scholarships_by_owner_slug.get((organization.domain, organization.id, slug))
        if scholarship is None:
            scholarship = Scholarship(
                domain=organization.domain,
                id=expected_id,
                organization_id=organization.id,
                slug=slug,
            )
            session.add(scholarship)
        _set_values(
            scholarship,
            organization_id=organization.id,
            slug=slug,
            lifecycle_status=ScholarshipLifecycle.ACTIVE,
            is_synthetic=True,
            archived_at=None,
        )
        scholarships_by_slug[slug] = scholarship
    session.flush()

    version_expected_ids = {
        slug: stable_id(f"reference:scholarship-version:{slug}:1") for slug in scholarships_by_slug
    }
    scholarship_ids = [item.id for item in scholarships_by_slug.values()]
    existing_versions = list(
        session.scalars(
            select(ScholarshipVersion).where(
                or_(
                    ScholarshipVersion.id.in_(list(version_expected_ids.values())),
                    ScholarshipVersion.scholarship_id.in_(scholarship_ids),
                )
            )
        )
    )
    versions_by_id = {(version.domain, version.id): version for version in existing_versions}
    versions_by_number = {
        (version.domain, version.scholarship_id, version.version_number): version
        for version in existing_versions
    }
    versions_by_slug: dict[str, ScholarshipVersion] = {}

    for spec in REFERENCE_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        scholarship = scholarships_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        publisher = accounts_by_key[str(spec["organization"])]
        expected_id = version_expected_ids[slug]
        chunks = _reference_chunks(spec)
        version = versions_by_id.get((scholarship.domain, expected_id)) or versions_by_number.get(
            (scholarship.domain, scholarship.id, 1)
        )
        if version is None:
            version = ScholarshipVersion(
                domain=scholarship.domain,
                id=expected_id,
                organization_id=organization.id,
                scholarship_id=scholarship.id,
                version_number=1,
            )
            session.add(version)
        _set_values(
            version,
            organization_id=organization.id,
            scholarship_id=scholarship.id,
            version_number=1,
            title=spec["title"],
            summary=spec["summary"],
            knowledge_summary=" ".join(text for _, text in chunks),
            academic_year="See official source",
            scope=_scope_for_type(organization.type),
            applicable_state_codes=list(spec["states"]),
            education_levels=list(spec["levels"]),
            course_families=list(spec["courses"]),
            category_tags=list(spec["tags"]),
            benefit_summary=spec["benefit"],
            benefit_amount_min=None,
            benefit_amount_max=None,
            application_opens_at=None,
            application_deadline_at=None,
            official_source_url=spec["official_source_url"],
            provider_helpdesk_url=spec["official_source_url"],
            publication_status=PublicationStatus.PUBLISHED,
            last_provider_confirmed_at=REFERENCE_CATALOG_AT,
            created_by=publisher.id,
            published_by=publisher.id,
            published_at=REFERENCE_CATALOG_AT,
        )
        versions_by_slug[slug] = version
    session.flush()

    for slug, scholarship in scholarships_by_slug.items():
        scholarship.current_published_version_id = versions_by_slug[slug].id
    session.flush()

    source_expected_ids = {
        slug: stable_id(f"reference:source-document:{slug}:official-summary")
        for slug in scholarships_by_slug
    }
    existing_sources = list(
        session.scalars(
            select(SourceDocument).where(SourceDocument.id.in_(list(source_expected_ids.values())))
        )
    )
    sources_by_id = {(source.domain, source.id): source for source in existing_sources}
    sources_by_slug: dict[str, SourceDocument] = {}

    for spec in REFERENCE_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        version = versions_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        publisher = accounts_by_key[str(spec["organization"])]
        source_id = source_expected_ids[slug]
        chunks = _reference_chunks(spec)
        source_text = "\n\n".join(f"{title}\n{text}" for title, text in chunks)
        encoded_source = source_text.encode("utf-8")
        source = sources_by_id.get((version.domain, source_id))
        if source is None:
            source = SourceDocument(domain=version.domain, id=source_id)
            session.add(source)
        _set_values(
            source,
            organization_id=organization.id,
            scholarship_version_id=version.id,
            display_name=f"{spec['title']} — Official-source reference summary",
            source_kind="PUBLIC_SOURCE_REFERENCE",
            content_type="text/plain; charset=utf-8",
            size_bytes=len(encoded_source),
            storage_key=None,
            source_url=spec["official_source_url"],
            checksum_sha256=hashlib.sha256(encoded_source).hexdigest(),
            extracted_text=source_text,
            usage_rights_confirmed_at=REFERENCE_CATALOG_AT,
            confirmation_status=REFERENCE_STATUS,
            uploaded_by=publisher.id,
        )
        sources_by_slug[slug] = source
    session.flush()

    chunk_expected_ids = {
        (str(spec["slug"]), ordinal): stable_id(
            f"reference:knowledge-chunk:{spec['slug']}:{ordinal}"
        )
        for spec in REFERENCE_SCHOLARSHIP_SPECS
        for ordinal in range(1, 5)
    }
    existing_chunks = list(
        session.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.id.in_(list(chunk_expected_ids.values())))
        )
    )
    chunks_by_id = {(chunk.domain, chunk.id): chunk for chunk in existing_chunks}
    chunk_ids_by_slug: dict[str, list[uuid.UUID]] = {}

    for spec in REFERENCE_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        version = versions_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        source = sources_by_slug[slug]
        chunk_ids: list[uuid.UUID] = []
        for ordinal, (section_title, provider_text) in enumerate(_reference_chunks(spec), start=1):
            chunk_id = chunk_expected_ids[(slug, ordinal)]
            chunk = chunks_by_id.get((version.domain, chunk_id))
            if chunk is None:
                chunk = KnowledgeChunk(domain=version.domain, id=chunk_id)
                session.add(chunk)
            _set_values(
                chunk,
                organization_id=organization.id,
                scholarship_version_id=version.id,
                source_document_id=source.id,
                ordinal=ordinal,
                page_number=None,
                section_title=section_title,
                provider_text=provider_text,
                embedding_reference=None,
                confirmation_status=REFERENCE_STATUS,
            )
            chunk_ids.append(chunk.id)
        chunk_ids_by_slug[slug] = chunk_ids
    session.flush()

    extraction_expected_ids = {
        slug: stable_id(f"reference:ai-extraction:{slug}:1") for slug in scholarships_by_slug
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
        slug: stable_id(f"reference:application-template:{slug}:1") for slug in scholarships_by_slug
    }
    version_ids = [version.id for version in versions_by_slug.values()]
    existing_templates = list(
        session.scalars(
            select(ApplicationTemplate).where(
                or_(
                    ApplicationTemplate.id.in_(list(template_expected_ids.values())),
                    ApplicationTemplate.scholarship_version_id.in_(version_ids),
                )
            )
        )
    )
    templates_by_id = {(template.domain, template.id): template for template in existing_templates}
    templates_by_version = {
        (template.domain, template.scholarship_version_id, template.template_version): template
        for template in existing_templates
    }
    templates_by_slug: dict[str, ApplicationTemplate] = {}

    for spec in REFERENCE_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        version = versions_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        publisher = accounts_by_key[str(spec["organization"])]
        chunk_ids = chunk_ids_by_slug[slug]

        extraction_id = extraction_expected_ids[slug]
        extraction = extractions_by_id.get((version.domain, extraction_id))
        if extraction is None:
            extraction = AIExtractionDraft(domain=version.domain, id=extraction_id)
            session.add(extraction)
        _set_values(
            extraction,
            organization_id=organization.id,
            scholarship_version_id=version.id,
            model_identifier="catalog-seed-no-model-call",
            prompt_version="public-source-reference-v1",
            extracted_content_json={
                "title": spec["title"],
                "summary": spec["summary"],
                "scope": version.scope,
                "states": list(spec["states"]),
                "education_levels": list(spec["levels"]),
                "course_families": list(spec["courses"]),
                "category_tags": list(spec["tags"]),
                "benefit_summary": spec["benefit"],
                "official_source_url": spec["official_source_url"],
                "reference_notice": CONTENT_REPHRASED_NOTICE,
            },
            source_mapping_json={
                "reference_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids],
                "official_source_url": spec["official_source_url"],
            },
            status=REFERENCE_STATUS,
            confirmed_by=None,
            confirmed_at=None,
        )

        template_id = template_expected_ids[slug]
        template = templates_by_id.get((version.domain, template_id)) or templates_by_version.get(
            (version.domain, version.id, 1)
        )
        if template is None:
            template = ApplicationTemplate(domain=version.domain, id=template_id)
            session.add(template)
        _set_values(
            template,
            organization_id=organization.id,
            scholarship_version_id=version.id,
            template_version=1,
            status=REFERENCE_STATUS,
            required_document_types=list(DEFAULT_REQUIRED_DOCUMENT_TYPES),
            created_by=publisher.id,
            confirmed_by=None,
            confirmed_at=None,
        )
        templates_by_slug[slug] = template
    session.flush()

    field_expected_ids = {
        (str(spec["slug"]), definition.key): stable_id(
            f"reference:application-template-field:{spec['slug']}:{definition.key}"
        )
        for spec in REFERENCE_SCHOLARSHIP_SPECS
        for definition in DEFAULT_FIELD_DEFINITIONS
    }
    template_ids = [template.id for template in templates_by_slug.values()]
    existing_fields = list(
        session.scalars(
            select(ApplicationTemplateField).where(
                or_(
                    ApplicationTemplateField.id.in_(list(field_expected_ids.values())),
                    ApplicationTemplateField.application_template_id.in_(template_ids),
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
        slug: stable_id(f"reference:audit:publish:{slug}:1") for slug in scholarships_by_slug
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
    for spec in REFERENCE_SCHOLARSHIP_SPECS:
        slug = str(spec["slug"])
        version = versions_by_slug[slug]
        organization = organizations_by_key[str(spec["organization"])]
        publisher = accounts_by_key[str(spec["organization"])]
        template = templates_by_slug[slug]
        option_sets = {
            "course": _course_options(spec),
            "domicile_state": list(spec["states"]),
            "family_income_band": income_options,
        }
        for sort_order, definition in enumerate(DEFAULT_FIELD_DEFINITIONS, start=1):
            field_id = field_expected_ids[(slug, definition.key)]
            field = fields_by_id.get((version.domain, field_id)) or fields_by_key.get(
                (version.domain, template.id, definition.key)
            )
            if field is None:
                field = ApplicationTemplateField(domain=version.domain, id=field_id)
                session.add(field)
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
                source_chunk_id=chunk_ids_by_slug[slug][1],
                sort_order=sort_order,
            )

        audit_id = audit_expected_ids[slug]
        audit = audits_by_id.get((version.domain, audit_id))
        if audit is None:
            audit = AuditEvent(domain=version.domain, id=audit_id)
            session.add(audit)
        _set_values(
            audit,
            actor_account_id=publisher.id,
            organization_id=organization.id,
            action="PUBLIC_SOURCE_REFERENCE_PUBLISHED",
            resource_type="scholarship_version",
            resource_id=version.id,
            safe_metadata_json={
                "synthetic": True,
                "reference_entry": True,
                "provider_onboarded": False,
                "version_number": 1,
                "official_source_url": spec["official_source_url"],
                "content_notice": CONTENT_REPHRASED_NOTICE,
            },
        )

    session.flush()
    return {
        "removed_broken_scholarships": removed_count,
        "reference_organizations": len(REFERENCE_ORGANIZATION_SPECS),
        "reference_scholarships": len(REFERENCE_SCHOLARSHIP_SPECS),
    }
