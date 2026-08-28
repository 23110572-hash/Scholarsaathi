import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_student, require_student_write
from app.models import (
    ApplicationTemplate,
    ApplicationTemplateField,
    KnowledgeChunk,
    Organization,
    OrganizationType,
    OwnershipDomain,
    PublicationStatus,
    SavedScholarship,
    Scholarship,
    ScholarshipLifecycle,
    ScholarshipVersion,
)
from app.presenters import scholarship_card
from app.schemas import (
    ApplicationFieldResponse,
    SavedScholarshipResponse,
    ScholarshipDetailResponse,
    ScholarshipListResponse,
    SourceExcerpt,
)

router = APIRouter(prefix="/api", tags=["scholarships"])


def published_scholarship_query():
    return (
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
            Scholarship.lifecycle_status == ScholarshipLifecycle.ACTIVE,
            ScholarshipVersion.publication_status == PublicationStatus.PUBLISHED,
        )
    )


@router.get("/scholarships", response_model=ScholarshipListResponse)
def list_scholarships(
    q: str | None = Query(default=None, max_length=120),
    state_code: str | None = Query(default=None, min_length=2, max_length=2),
    organization_type: OrganizationType | None = None,
    education_level: str | None = Query(default=None, max_length=60),
    course: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=24, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ScholarshipListResponse:
    query = published_scholarship_query()
    if q:
        term = f"%{q.strip()}%"
        query = query.where(
            or_(
                ScholarshipVersion.title.ilike(term),
                ScholarshipVersion.summary.ilike(term),
                ScholarshipVersion.knowledge_summary.ilike(term),
            )
        )
    if state_code:
        state = state_code.upper()
        query = query.where(
            or_(
                ScholarshipVersion.applicable_state_codes.any("ALL"),
                ScholarshipVersion.applicable_state_codes.any(state),
            )
        )
    if organization_type:
        query = query.where(Organization.type == organization_type)
    if education_level:
        query = query.where(
            ScholarshipVersion.education_levels.any(education_level.upper())
        )
    if course:
        normalized_course = course.upper()
        query = query.where(
            or_(
                ScholarshipVersion.course_families.any(normalized_course),
                ScholarshipVersion.course_families.any("ALL_UNDERGRADUATE"),
                ScholarshipVersion.course_families.any("ALL_RECOGNIZED_COURSES"),
                ScholarshipVersion.course_families.any("STEM"),
            )
        )

    all_rows = db.execute(
        query.order_by(ScholarshipVersion.application_deadline_at)
    ).all()
    rows = all_rows[offset : offset + limit]
    return ScholarshipListResponse(
        items=[scholarship_card(*row) for row in rows],
        total=len(all_rows),
    )


@router.get("/scholarships/{scholarship_id}", response_model=ScholarshipDetailResponse)
def scholarship_detail(
    scholarship_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ScholarshipDetailResponse:
    row = db.execute(
        published_scholarship_query().where(Scholarship.id == scholarship_id)
    ).one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scholarship was not found")
    scholarship, version, organization = row
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.domain == scholarship.domain,
            KnowledgeChunk.organization_id == scholarship.organization_id,
            KnowledgeChunk.scholarship_version_id == version.id,
            KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
        )
        .order_by(KnowledgeChunk.ordinal)
    ).all()
    template = db.scalar(
        select(ApplicationTemplate)
        .where(
            ApplicationTemplate.domain == scholarship.domain,
            ApplicationTemplate.organization_id == scholarship.organization_id,
            ApplicationTemplate.scholarship_version_id == version.id,
            ApplicationTemplate.status == "OWNER_CONFIRMED",
        )
        .order_by(ApplicationTemplate.template_version.desc())
    )
    fields = []
    if template:
        fields = db.scalars(
            select(ApplicationTemplateField)
            .where(
                ApplicationTemplateField.domain == scholarship.domain,
                ApplicationTemplateField.application_template_id == template.id,
            )
            .order_by(ApplicationTemplateField.sort_order)
        ).all()

    card = scholarship_card(scholarship, version, organization)
    return ScholarshipDetailResponse(
        **card.model_dump(),
        knowledge_summary=version.knowledge_summary,
        provider_helpdesk_url=version.provider_helpdesk_url,
        evidence=[
            SourceExcerpt(
                citation_id=str(chunk.id),
                section_title=chunk.section_title,
                page_number=chunk.page_number,
                text=chunk.provider_text,
            )
            for chunk in chunks
        ],
        application_template_id=template.id if template else None,
        application_fields=[
            ApplicationFieldResponse(
                id=field.id,
                field_key=field.field_key,
                label=field.label,
                help_text=field.help_text,
                field_type=field.field_type,
                required=field.required,
                options=field.options_json,
                sort_order=field.sort_order,
            )
            for field in fields
        ],
    )


@router.get("/student/saved-scholarships", response_model=ScholarshipListResponse)
def list_saved_scholarships(
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> ScholarshipListResponse:
    rows = db.execute(
        published_scholarship_query()
        .join(
            SavedScholarship,
            and_(
                SavedScholarship.scholarship_domain == Scholarship.domain,
                SavedScholarship.scholarship_id == Scholarship.id,
            ),
        )
        .where(
            SavedScholarship.student_domain == OwnershipDomain.STUDENT,
            SavedScholarship.student_account_id == auth.account.id,
        )
        .order_by(SavedScholarship.created_at.desc())
    ).all()
    return ScholarshipListResponse(
        items=[scholarship_card(*row) for row in rows],
        total=len(rows),
    )


@router.post(
    "/student/saved-scholarships/{scholarship_id}",
    response_model=SavedScholarshipResponse,
)
def save_scholarship(
    scholarship_id: uuid.UUID,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> SavedScholarshipResponse:
    published = db.execute(
        published_scholarship_query()
        .where(Scholarship.id == scholarship_id)
        .with_only_columns(Scholarship.domain, Scholarship.id)
    ).one_or_none()
    if not published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scholarship was not found")
    scholarship_domain, published_id = published
    statement = (
        insert(SavedScholarship)
        .values(
            student_domain=OwnershipDomain.STUDENT,
            student_account_id=auth.account.id,
            scholarship_domain=scholarship_domain,
            scholarship_id=published_id,
        )
        .on_conflict_do_nothing(
            index_elements=[
                SavedScholarship.student_account_id,
                SavedScholarship.scholarship_domain,
                SavedScholarship.scholarship_id,
            ]
        )
    )
    db.execute(statement)
    db.commit()
    return SavedScholarshipResponse(scholarship_id=scholarship_id, saved=True)


@router.delete(
    "/student/saved-scholarships/{scholarship_id}",
    response_model=SavedScholarshipResponse,
)
def unsave_scholarship(
    scholarship_id: uuid.UUID,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> SavedScholarshipResponse:
    db.execute(
        delete(SavedScholarship).where(
            SavedScholarship.student_domain == OwnershipDomain.STUDENT,
            SavedScholarship.student_account_id == auth.account.id,
            SavedScholarship.scholarship_id == scholarship_id,
        )
    )
    db.commit()
    return SavedScholarshipResponse(scholarship_id=scholarship_id, saved=False)
