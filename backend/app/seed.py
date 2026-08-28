from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from argon2 import PasswordHasher
from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    Account,
    AccountRealm,
    AccountStatus,
    AIExtractionDraft,
    Application,
    ApplicationEvent,
    ApplicationFieldType,
    ApplicationStatus,
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
    StudentSetting,
    ownership_domain_for_type,
)

SEED_NAMESPACE = uuid.UUID("52b9b24a-9e5f-4e19-81b1-4da8245b9ae1")
DEMO_PASSWORD = "Demo@ScholarSaathi2026"
DEMO_STUDENT_LOGIN = "student@demo.scholarsaathi.local"


def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


def timestamp(month: int, day: int, hour: int = 9) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=UTC)


ORGANIZATION_SPECS = [
    {
        "key": "central",
        "slug": "national-education-support-directorate-demo",
        "legal_name": "National Education Support Directorate — Synthetic Demo",
        "display_name": "National Education Support Directorate",
        "type": OrganizationType.CENTRAL_GOVERNMENT,
        "state": None,
        "publisher_login": "central.publisher@demo.scholarsaathi.local",
    },
    {
        "key": "odisha",
        "slug": "odisha-student-opportunity-mission-demo",
        "legal_name": "Odisha Student Opportunity Mission — Synthetic Demo",
        "display_name": "Odisha Student Opportunity Mission",
        "type": OrganizationType.STATE_GOVERNMENT,
        "state": "OD",
        "publisher_login": "odisha.publisher@demo.scholarsaathi.local",
    },
    {
        "key": "aarohan",
        "slug": "aarohan-future-skills-demo",
        "legal_name": "Aarohan Future Skills Private Limited — Synthetic Demo",
        "display_name": "Aarohan Future Skills",
        "type": OrganizationType.PRIVATE_COMPANY,
        "state": None,
        "publisher_login": "aarohan.publisher@demo.scholarsaathi.local",
    },
    {
        "key": "udaan",
        "slug": "udaan-learning-trust-demo",
        "legal_name": "Udaan Learning Trust — Synthetic Demo",
        "display_name": "Udaan Learning Trust",
        "type": OrganizationType.NGO,
        "state": None,
        "publisher_login": "udaan.publisher@demo.scholarsaathi.local",
    },
]


SCHOLARSHIP_SPECS = [
    {
        "slug": "national-technical-learner-grant-2026",
        "organization": "central",
        "title": "National Technical Learner Grant 2026–27",
        "summary": "Annual support for early-year diploma and undergraduate technical learners across India.",
        "scope": "NATIONAL",
        "states": ["ALL"],
        "levels": ["DIPLOMA", "UNDERGRADUATE"],
        "courses": ["BTECH", "BE", "TECHNICAL_DIPLOMA"],
        "tags": ["MERIT", "INCOME", "TECHNICAL_EDUCATION"],
        "benefit": "Up to ₹75,000 for tuition, learning materials, and a digital-access allowance.",
        "amount_min": 50000,
        "amount_max": 75000,
        "opens": timestamp(8, 1),
        "deadline": timestamp(10, 31, 23),
        "chunks": [
            (
                "Eligibility",
                "Applicants must be enrolled in the first or second year of a recognized B.E., B.Tech, or technical diploma programme in India. The published household-income ceiling is ₹8,00,000 per year, and the previous qualifying examination score should be at least 65 percent.",
            ),
            (
                "Benefit",
                "Selected students may receive ₹50,000 to ₹75,000 for tuition, books, approved learning equipment, and digital access during academic year 2026–27.",
            ),
            (
                "Documents",
                "The application asks for an admission letter, current institution certificate, previous marksheet, household-income certificate, and a student declaration. The prototype must use synthetic documents only.",
            ),
            (
                "Application process",
                "Applications open on 1 August 2026 and close at 23:00 IST on 31 October 2026. Students submit through the common ScholarSaathi application and may receive a correction request before provider review.",
            ),
        ],
    },
    {
        "slug": "national-higher-education-access-award-2026",
        "organization": "central",
        "title": "National Higher Education Access Award 2026–27",
        "summary": "Merit-and-means assistance for students beginning a recognized undergraduate programme.",
        "scope": "NATIONAL",
        "states": ["ALL"],
        "levels": ["UNDERGRADUATE"],
        "courses": ["ALL_UNDERGRADUATE"],
        "tags": ["FIRST_YEAR", "MERIT", "INCOME"],
        "benefit": "₹40,000 annual academic support plus a one-time ₹10,000 learning-access grant.",
        "amount_min": 40000,
        "amount_max": 50000,
        "opens": timestamp(8, 10),
        "deadline": timestamp(11, 15, 23),
        "chunks": [
            (
                "Eligibility",
                "The award is intended for students entering the first year of a recognized undergraduate programme. Published guidance asks for at least 75 percent in the qualifying examination and annual household income not exceeding ₹4,50,000.",
            ),
            (
                "Coverage and benefit",
                "The scheme is open across all States and Union Territories. The annual academic award is ₹40,000 with a one-time learning-access grant of ₹10,000 for newly selected students.",
            ),
            (
                "Required evidence",
                "Applicants provide proof of admission, qualifying marks, household-income evidence, institution details, and a declaration that submitted information is correct.",
            ),
            (
                "Timeline",
                "The 2026–27 application window runs from 10 August to 15 November 2026. Provider review begins after the closing date, with correction messages delivered through the platform timeline.",
            ),
        ],
    },
    {
        "slug": "odisha-technical-pathways-scholarship-2026",
        "organization": "odisha",
        "title": "Odisha Technical Pathways Scholarship 2026–27",
        "summary": "State support for Odisha students pursuing technical degrees and diplomas.",
        "scope": "STATE",
        "states": ["OD"],
        "levels": ["DIPLOMA", "UNDERGRADUATE"],
        "courses": ["BTECH", "BE", "BARCH", "TECHNICAL_DIPLOMA"],
        "tags": ["ODISHA", "INCOME", "TECHNICAL_EDUCATION"],
        "benefit": "₹55,000 per academic year for eligible technical learners.",
        "amount_min": 55000,
        "amount_max": 55000,
        "opens": timestamp(7, 20),
        "deadline": timestamp(10, 20, 23),
        "chunks": [
            (
                "Who may apply",
                "The scholarship is for students domiciled in Odisha who are enrolled in years one through four of a recognized B.Tech, B.E., B.Arch, or technical diploma programme. The published annual family-income ceiling is ₹3,00,000 and the minimum previous-year result is 60 percent.",
            ),
            (
                "Award",
                "An approved student receives ₹55,000 for academic year 2026–27. The provider may request continued-enrolment confirmation before release of the second instalment.",
            ),
            (
                "Application checklist",
                "The common application requests a synthetic domicile record for the demo, institution enrolment confirmation, latest marksheet, income evidence, course year, and consent declaration.",
            ),
            (
                "Dates and support",
                "Applications are accepted from 20 July through 20 October 2026. Questions and correction requests are handled in the ScholarSaathi provider inbox for this synthetic demonstration.",
            ),
        ],
    },
    {
        "slug": "odisha-rural-women-stem-fellowship-2026",
        "organization": "odisha",
        "title": "Odisha Rural Women in STEM Fellowship 2026–27",
        "summary": "Academic and mentoring support for women from rural Odisha studying STEM subjects.",
        "scope": "STATE",
        "states": ["OD"],
        "levels": ["UNDERGRADUATE", "POSTGRADUATE"],
        "courses": ["STEM"],
        "tags": ["WOMEN", "RURAL", "ODISHA", "STEM"],
        "benefit": "₹60,000 academic award with remote mentoring and career workshops.",
        "amount_min": 60000,
        "amount_max": 60000,
        "opens": timestamp(8, 15),
        "deadline": timestamp(11, 30, 23),
        "chunks": [
            (
                "Eligibility",
                "Applicants should identify as women, have Odisha domicile, and have completed secondary schooling in a rural Odisha district. They must be enrolled in a recognized undergraduate or postgraduate STEM programme. Published household income should not exceed ₹5,00,000 per year.",
            ),
            (
                "Fellowship support",
                "The fellowship provides ₹60,000 for academic costs and access to monthly remote mentoring, career-readiness workshops, and a peer learning cohort.",
            ),
            (
                "Evidence requested",
                "The application requests course and institution confirmation, most recent academic result, income evidence, domicile and rural-schooling declarations, and a short statement of academic goals.",
            ),
            (
                "Application window",
                "Applications open on 15 August and close on 30 November 2026. Shortlisted students may be invited to a provider-led online conversation after document review.",
            ),
        ],
    },
    {
        "slug": "aarohan-women-engineers-scholarship-2026",
        "organization": "aarohan",
        "title": "Aarohan Women Engineers Scholarship 2026–27",
        "summary": "Private scholarship for women in the first three years of an engineering degree.",
        "scope": "NATIONAL_PRIVATE",
        "states": ["ALL"],
        "levels": ["UNDERGRADUATE"],
        "courses": ["BTECH", "BE"],
        "tags": ["WOMEN", "ENGINEERING", "MERIT", "INCOME"],
        "benefit": "Up to ₹1,00,000 toward tuition and an industry mentoring programme.",
        "amount_min": 75000,
        "amount_max": 100000,
        "opens": timestamp(8, 5),
        "deadline": timestamp(10, 5, 23),
        "chunks": [
            (
                "Applicant profile",
                "The scholarship is open to women studying in years one, two, or three of a recognized B.Tech or B.E. programme in India. Guidance states a minimum previous academic score of 70 percent and household income not exceeding ₹6,00,000.",
            ),
            (
                "Financial and mentoring benefit",
                "Awards range from ₹75,000 to ₹1,00,000 toward tuition. Selected scholars also join a six-month engineering mentoring programme delivered by volunteer professionals.",
            ),
            (
                "Application material",
                "Applicants provide enrolment and marks evidence, an income declaration, a 300-word learning-goal response, and consent for the provider to review the synthetic demo application.",
            ),
            (
                "Selection schedule",
                "Applications close on 5 October 2026. The synthetic provider review includes completeness screening, an academic review, and a mock final decision shown in the platform timeline.",
            ),
        ],
    },
    {
        "slug": "aarohan-green-innovation-grant-2026",
        "organization": "aarohan",
        "title": "Aarohan Green Innovation Student Grant 2026",
        "summary": "Project grant for final-year STEM students developing measurable sustainability solutions.",
        "scope": "NATIONAL_PRIVATE",
        "states": ["ALL"],
        "levels": ["UNDERGRADUATE", "POSTGRADUATE"],
        "courses": ["STEM"],
        "tags": ["FINAL_YEAR", "PROJECT_GRANT", "SUSTAINABILITY"],
        "benefit": "Project funding from ₹50,000 to ₹1,50,000 plus technical mentoring.",
        "amount_min": 50000,
        "amount_max": 150000,
        "opens": timestamp(8, 20),
        "deadline": timestamp(12, 15, 23),
        "chunks": [
            (
                "Who can submit",
                "Final-year undergraduate or postgraduate STEM students at recognized Indian institutions may submit individually or in teams of up to four. The proposed project must address an environmental or sustainability problem and include measurable outcomes.",
            ),
            (
                "Grant size",
                "Selected proposals receive between ₹50,000 and ₹1,50,000 based on the reviewed budget and milestone plan. Technical mentoring is offered for up to eight months.",
            ),
            (
                "Proposal requirements",
                "The application includes a problem statement, proposed solution, implementation milestones, budget, team roles, institution mentor confirmation, and a declaration that the work is original.",
            ),
            (
                "Dates",
                "Proposals are accepted from 20 August until 15 December 2026. The provider may request a clarification or revised budget before the mock review decision.",
            ),
        ],
    },
    {
        "slug": "udaan-first-generation-graduate-fellowship-2026",
        "organization": "udaan",
        "title": "Udaan First-Generation Graduate Fellowship 2026–27",
        "summary": "NGO scholarship and mentoring for first-generation undergraduate students.",
        "scope": "NATIONAL_NGO",
        "states": ["ALL"],
        "levels": ["UNDERGRADUATE"],
        "courses": ["ALL_UNDERGRADUATE"],
        "tags": ["FIRST_GENERATION", "INCOME", "MENTORING"],
        "benefit": "₹40,000 annual support, peer mentoring, and academic planning sessions.",
        "amount_min": 40000,
        "amount_max": 40000,
        "opens": timestamp(7, 25),
        "deadline": timestamp(9, 30, 23),
        "chunks": [
            (
                "Eligibility guidance",
                "Applicants should be the first person in their immediate family to pursue a university degree and be enrolled in a recognized undergraduate programme. The guidance asks for at least 55 percent in the most recent examination and annual household income up to ₹4,00,000.",
            ),
            (
                "Fellowship package",
                "The fellowship provides ₹40,000 for academic costs, a trained peer mentor, quarterly academic-planning sessions, and access to group career workshops.",
            ),
            (
                "What the application asks",
                "Students provide enrolment and academic evidence, an income declaration, a first-generation learner declaration, and a short response describing the support that would help them continue studying.",
            ),
            (
                "Deadline and review",
                "Applications close on 30 September 2026. The NGO reviews completeness and need before recording a synthetic decision in ScholarSaathi.",
            ),
        ],
    },
    {
        "slug": "udaan-accessible-education-scholarship-2026",
        "organization": "udaan",
        "title": "Udaan Accessible Education Scholarship 2026–27",
        "summary": "Flexible study support for diploma and degree students with disabilities.",
        "scope": "NATIONAL_NGO",
        "states": ["ALL"],
        "levels": ["DIPLOMA", "UNDERGRADUATE", "POSTGRADUATE"],
        "courses": ["ALL_RECOGNIZED_COURSES"],
        "tags": ["DISABILITY", "ACCESSIBILITY", "INCOME"],
        "benefit": "Up to ₹80,000 for tuition, assistive technology, transport, or learning support.",
        "amount_min": 40000,
        "amount_max": 80000,
        "opens": timestamp(8, 1),
        "deadline": timestamp(11, 20, 23),
        "chunks": [
            (
                "Eligibility guidance",
                "The scholarship supports students with a disability who are enrolled in a recognized diploma, undergraduate, or postgraduate programme in India. Published household income should not exceed ₹8,00,000. No single course discipline is preferred.",
            ),
            (
                "Flexible award",
                "Awards range from ₹40,000 to ₹80,000 and may support tuition, accessible transport, assistive technology, communication support, or other approved educational access needs.",
            ),
            (
                "Application information",
                "The application requests enrolment evidence, a non-sensitive description of the requested educational support, household-income evidence, and the relevant provider-specified disability documentation category. The public demo uses synthetic information only.",
            ),
            (
                "Dates and accommodations",
                "Applications close on 20 November 2026. Students may request an accessible interview format or communication accommodation through the provider helpdesk.",
            ),
        ],
    },
]


def seed_database() -> None:
    hasher = PasswordHasher()
    session = SessionLocal()

    try:
        already_seeded = session.scalar(
            select(Account.id).where(Account.login_identifier == DEMO_STUDENT_LOGIN)
        )
        if already_seeded:
            print("ScholarSaathi synthetic seed data already exists; no changes made.")
            return

        student_id = stable_id("account:student")
        password_hashes = {
            "student": hasher.hash(DEMO_PASSWORD),
            **{
                spec["key"]: hasher.hash(DEMO_PASSWORD)
                for spec in ORGANIZATION_SPECS
            },
        }

        accounts = [
            Account(
                domain=OwnershipDomain.STUDENT,
                id=student_id,
                login_identifier=DEMO_STUDENT_LOGIN,
                password_hash=password_hashes["student"],
                realm=AccountRealm.STUDENT,
                status=AccountStatus.ACTIVE,
            ),
        ]

        publisher_account_ids: dict[str, uuid.UUID] = {}
        for spec in ORGANIZATION_SPECS:
            account_id = stable_id(f"account:publisher:{spec['key']}")
            publisher_account_ids[spec["key"]] = account_id
            accounts.append(
                Account(
                    domain=ownership_domain_for_type(spec["type"]),
                    id=account_id,
                    login_identifier=spec["publisher_login"],
                    password_hash=password_hashes[spec["key"]],
                    realm=AccountRealm.ORGANIZATION_MEMBER,
                    status=AccountStatus.ACTIVE,
                )
            )

        session.add_all(accounts)
        session.add(
            StudentSetting(
                account_id=student_id,
                account_domain=OwnershipDomain.STUDENT,
                display_alias="Aarav (Synthetic)",
                preferred_language="en",
            )
        )
        session.flush()

        organization_ids: dict[str, uuid.UUID] = {}
        organization_by_key: dict[str, Organization] = {}
        for spec in ORGANIZATION_SPECS:
            organization_id = stable_id(f"organization:{spec['key']}")
            organization_ids[spec["key"]] = organization_id
            domain = ownership_domain_for_type(spec["type"])
            organization = Organization(
                domain=domain,
                id=organization_id,
                slug=spec["slug"],
                legal_name=spec["legal_name"],
                display_name=spec["display_name"],
                type=spec["type"],
                jurisdiction_state_code=spec["state"],
                is_synthetic=True,
            )
            organization_by_key[spec["key"]] = organization
            session.add(organization)
            session.add(
                OrganizationMember(
                    domain=domain,
                    id=stable_id(f"organization-member:{spec['key']}:owner"),
                    organization_id=organization_id,
                    account_id=publisher_account_ids[spec["key"]],
                    role=MemberRole.OWNER,
                    status=MemberStatus.ACTIVE,
                )
            )

        session.flush()

        scholarship_ids: dict[str, uuid.UUID] = {}
        scholarship_objects: dict[str, Scholarship] = {}
        for spec in SCHOLARSHIP_SPECS:
            scholarship_id = stable_id(f"scholarship:{spec['slug']}")
            scholarship_ids[spec["slug"]] = scholarship_id
            scholarship = Scholarship(
                domain=organization_by_key[spec["organization"]].domain,
                id=scholarship_id,
                organization_id=organization_ids[spec["organization"]],
                slug=spec["slug"],
                lifecycle_status=ScholarshipLifecycle.ACTIVE,
                is_synthetic=True,
            )
            scholarship_objects[spec["slug"]] = scholarship
            session.add(scholarship)

        session.flush()

        version_ids: dict[str, uuid.UUID] = {}
        template_ids: dict[str, uuid.UUID] = {}
        first_chunk_ids: dict[str, uuid.UUID] = {}

        for spec in SCHOLARSHIP_SPECS:
            slug = spec["slug"]
            version_id = stable_id(f"scholarship-version:{slug}:1")
            version_ids[slug] = version_id
            publisher_id = publisher_account_ids[spec["organization"]]
            domain = organization_by_key[spec["organization"]].domain
            organization_id = organization_ids[spec["organization"]]
            source_url = f"https://example.org/synthetic-scholarships/{slug}/guidelines-2026-27"
            helpdesk_url = f"https://example.org/synthetic-scholarships/{slug}/help"

            version = ScholarshipVersion(
                domain=domain,
                id=version_id,
                organization_id=organization_id,
                scholarship_id=scholarship_ids[slug],
                version_number=1,
                title=spec["title"],
                summary=spec["summary"],
                knowledge_summary=" ".join(chunk[1] for chunk in spec["chunks"]),
                academic_year="2026-27",
                scope=spec["scope"],
                applicable_state_codes=spec["states"],
                education_levels=spec["levels"],
                course_families=spec["courses"],
                category_tags=spec["tags"],
                benefit_summary=spec["benefit"],
                benefit_amount_min=spec["amount_min"],
                benefit_amount_max=spec["amount_max"],
                application_opens_at=spec["opens"],
                application_deadline_at=spec["deadline"],
                official_source_url=source_url,
                provider_helpdesk_url=helpdesk_url,
                publication_status=PublicationStatus.PUBLISHED,
                last_provider_confirmed_at=timestamp(8, 20),
                created_by=publisher_id,
                published_by=publisher_id,
                published_at=timestamp(8, 20),
            )
            session.add(version)

        session.flush()

        for slug, scholarship in scholarship_objects.items():
            scholarship.current_published_version_id = version_ids[slug]

        for spec in SCHOLARSHIP_SPECS:
            slug = spec["slug"]
            version_id = version_ids[slug]
            publisher_id = publisher_account_ids[spec["organization"]]
            domain = organization_by_key[spec["organization"]].domain
            organization_id = organization_ids[spec["organization"]]
            source_id = stable_id(f"source-document:{slug}:guidelines")
            source_text = "\n\n".join(
                f"{section}\n{text}" for section, text in spec["chunks"]
            )
            checksum = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
            source_url = f"https://example.org/synthetic-scholarships/{slug}/guidelines-2026-27"

            session.add(
                SourceDocument(
                    domain=domain,
                    id=source_id,
                    organization_id=organization_id,
                    scholarship_version_id=version_id,
                    display_name=f"{spec['title']} — Synthetic Provider Guidelines",
                    source_kind="PROVIDER_GUIDELINE",
                    content_type="text/plain",
                    size_bytes=len(source_text.encode("utf-8")),
                    storage_key=f"synthetic/{slug}/guidelines-2026-27.txt",
                    source_url=source_url,
                    checksum_sha256=checksum,
                    extracted_text=source_text,
                    usage_rights_confirmed_at=timestamp(8, 19),
                    confirmation_status="OWNER_CONFIRMED",
                    uploaded_by=publisher_id,
                )
            )
            session.flush()

            chunk_ids: list[uuid.UUID] = []
            for ordinal, (section, provider_text) in enumerate(spec["chunks"], start=1):
                chunk_id = stable_id(f"knowledge-chunk:{slug}:{ordinal}")
                chunk_ids.append(chunk_id)
                session.add(
                    KnowledgeChunk(
                        domain=domain,
                        id=chunk_id,
                        organization_id=organization_id,
                        scholarship_version_id=version_id,
                        source_document_id=source_id,
                        ordinal=ordinal,
                        page_number=ordinal,
                        section_title=section,
                        provider_text=provider_text,
                        embedding_reference=None,
                        confirmation_status="OWNER_CONFIRMED",
                    )
                )

            session.flush()
            first_chunk_ids[slug] = chunk_ids[0]
            session.add(
                AIExtractionDraft(
                    domain=domain,
                    id=stable_id(f"ai-extraction:{slug}:1"),
                    organization_id=organization_id,
                    scholarship_version_id=version_id,
                    model_identifier="synthetic-seed-no-model-call",
                    prompt_version="publisher-intake-v1",
                    extracted_content_json={
                        "title": spec["title"],
                        "summary": spec["summary"],
                        "scope": spec["scope"],
                        "states": spec["states"],
                        "education_levels": spec["levels"],
                        "course_families": spec["courses"],
                        "category_tags": spec["tags"],
                        "benefit_summary": spec["benefit"],
                    },
                    source_mapping_json={
                        "confirmed_chunk_ids": [str(chunk_id) for chunk_id in chunk_ids]
                    },
                    status="OWNER_CONFIRMED",
                    confirmed_by=publisher_id,
                    confirmed_at=timestamp(8, 19),
                )
            )

            template_id = stable_id(f"application-template:{slug}:1")
            template_ids[slug] = template_id
            session.add(
                ApplicationTemplate(
                    domain=domain,
                    id=template_id,
                    organization_id=organization_id,
                    scholarship_version_id=version_id,
                    template_version=1,
                    status="OWNER_CONFIRMED",
                    created_by=publisher_id,
                    confirmed_by=publisher_id,
                    confirmed_at=timestamp(8, 19),
                )
            )
            session.flush()

            field_specs = [
                (
                    "course",
                    "Current course",
                    "Choose the course in which the synthetic applicant is currently enrolled.",
                    ApplicationFieldType.SELECT,
                    True,
                    spec["courses"],
                ),
                (
                    "course_year",
                    "Current course year",
                    "Enter the current year of study shown in the synthetic enrolment record.",
                    ApplicationFieldType.NUMBER,
                    True,
                    None,
                ),
                (
                    "domicile_state",
                    "Domicile State or Union Territory",
                    "Use a synthetic state value for this prototype application.",
                    ApplicationFieldType.SELECT,
                    True,
                    spec["states"] if spec["states"] != ["ALL"] else ["OD", "MH", "KA", "WB", "DL"],
                ),
                (
                    "family_income_band",
                    "Annual household-income range",
                    "Select a range; do not enter bank, Aadhaar, or tax identifiers.",
                    ApplicationFieldType.SELECT,
                    True,
                    ["UP_TO_250000", "250001_TO_400000", "400001_TO_600000", "600001_TO_800000", "ABOVE_800000"],
                ),
                (
                    "academic_score",
                    "Most recent academic percentage",
                    "Enter the percentage from the supplied synthetic marksheet.",
                    ApplicationFieldType.NUMBER,
                    True,
                    None,
                ),
                (
                    "student_declaration",
                    "Synthetic-data declaration",
                    "Confirm that this public prototype contains no real personal or government identity data.",
                    ApplicationFieldType.CHECKBOX,
                    True,
                    None,
                ),
            ]

            for order, field in enumerate(field_specs, start=1):
                key, label, help_text, field_type, required, options = field
                session.add(
                    ApplicationTemplateField(
                        domain=domain,
                        id=stable_id(f"application-template-field:{slug}:{key}"),
                        organization_id=organization_id,
                        scholarship_version_id=version_id,
                        application_template_id=template_id,
                        field_key=key,
                        label=label,
                        help_text=help_text,
                        field_type=field_type,
                        required=required,
                        options_json=options,
                        source_chunk_id=first_chunk_ids[slug],
                        sort_order=order,
                    )
                )

            session.add(
                AuditEvent(
                    domain=domain,
                    id=stable_id(f"audit:publish:{slug}:1"),
                    actor_account_id=publisher_id,
                    organization_id=organization_ids[spec["organization"]],
                    action="SCHOLARSHIP_VERSION_PUBLISHED_BY_OWNER",
                    resource_type="scholarship_version",
                    resource_id=version_id,
                    safe_metadata_json={
                        "synthetic": True,
                        "version_number": 1,
                        "academic_year": "2026-27",
                        "publication_authority": "OWNER",
                    },
                )
            )

        # Flush all parent records before inserting rows that reference them. SQLAlchemy
        # cannot infer ordering here because the seed uses deterministic foreign-key IDs
        # without ORM relationship assignments.
        session.flush()

        session.add_all(
            [
                SavedScholarship(
                    student_account_id=student_id,
                    student_domain=OwnershipDomain.STUDENT,
                    scholarship_domain=OwnershipDomain.STATE_GOVERNMENT,
                    scholarship_id=scholarship_ids[
                        "odisha-technical-pathways-scholarship-2026"
                    ],
                ),
                SavedScholarship(
                    student_account_id=student_id,
                    student_domain=OwnershipDomain.STUDENT,
                    scholarship_domain=OwnershipDomain.NGO_PRIVATE,
                    scholarship_id=scholarship_ids[
                        "aarohan-women-engineers-scholarship-2026"
                    ],
                ),
            ]
        )

        application_slug = "odisha-technical-pathways-scholarship-2026"
        application_id = stable_id("application:student:odisha-technical:draft")
        session.add(
            Application(
                id=application_id,
                student_domain=OwnershipDomain.STUDENT,
                student_account_id=student_id,
                provider_domain=OwnershipDomain.STATE_GOVERNMENT,
                organization_id=organization_ids["odisha"],
                scholarship_version_id=version_ids[application_slug],
                application_template_id=template_ids[application_slug],
                status=ApplicationStatus.DRAFT,
                is_synthetic=True,
                consent_recorded_at=timestamp(8, 21),
            )
        )
        session.flush()
        session.add(
            ApplicationEvent(
                id=stable_id("application-event:student:odisha-technical:created"),
                application_id=application_id,
                actor_domain=OwnershipDomain.STUDENT,
                actor_account_id=student_id,
                event_type="DRAFT_CREATED",
                safe_message=(
                    "Synthetic draft created. No real student information has been added."
                ),
            )
        )

        session.commit()
        print("ScholarSaathi synthetic PostgreSQL dataset created.")
        print("All organizations, scholarships, sources, and applications are synthetic.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
