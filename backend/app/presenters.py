from decimal import Decimal

from app.models import Organization, OrganizationMember, Scholarship, ScholarshipVersion
from app.schemas import OrganizationSummary, ScholarshipCard


def organization_summary(
    organization: Organization,
    membership: OrganizationMember | None = None,
) -> OrganizationSummary:
    return OrganizationSummary(
        id=organization.id,
        display_name=organization.display_name,
        organization_type=organization.type,
        jurisdiction_state_code=organization.jurisdiction_state_code,
        ownership_domain=organization.domain,
        is_synthetic=organization.is_synthetic,
        member_role=membership.role.value if membership else None,
    )


def _money(value: Decimal | float | None) -> float | None:
    return float(value) if value is not None else None


def scholarship_card(
    scholarship: Scholarship,
    version: ScholarshipVersion,
    organization: Organization,
) -> ScholarshipCard:
    return ScholarshipCard(
        id=scholarship.id,
        version_id=version.id,
        slug=scholarship.slug,
        title=version.title,
        summary=version.summary,
        academic_year=version.academic_year,
        scope=version.scope,
        applicable_state_codes=version.applicable_state_codes,
        education_levels=version.education_levels,
        course_families=version.course_families,
        category_tags=version.category_tags,
        benefit_summary=version.benefit_summary,
        benefit_amount_min=_money(version.benefit_amount_min),
        benefit_amount_max=_money(version.benefit_amount_max),
        application_deadline_at=version.application_deadline_at,
        official_source_url=version.official_source_url,
        last_provider_confirmed_at=version.last_provider_confirmed_at,
        publication_status=version.publication_status,
        is_synthetic=scholarship.is_synthetic or organization.is_synthetic,
        organization=organization_summary(organization),
    )
