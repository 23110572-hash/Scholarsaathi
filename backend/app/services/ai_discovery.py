from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents.scholarship_ai import run_discovery_agent, run_question_agent
from app.api.scholarships import published_scholarship_query
from app.core.config import get_settings
from app.models import KnowledgeChunk, Scholarship, ScholarshipVersion
from app.presenters import scholarship_card
from app.schemas import (
    DiscoveryProfile,
    DiscoveryResponse,
    ScholarshipQuestionRequest,
    ScholarshipQuestionResponse,
    SourceExcerpt,
)

settings = get_settings()


def _candidate_query(profile: DiscoveryProfile):
    query = published_scholarship_query()
    if profile.state:
        query = query.where(
            or_(
                ScholarshipVersion.applicable_state_codes.any("ALL"),
                ScholarshipVersion.applicable_state_codes.any(profile.state),
            )
        )
    if profile.education_level:
        query = query.where(ScholarshipVersion.education_levels.any(profile.education_level))
    if profile.course:
        query = query.where(
            or_(
                ScholarshipVersion.course_families.any(profile.course),
                ScholarshipVersion.course_families.any("ALL_UNDERGRADUATE"),
                ScholarshipVersion.course_families.any("ALL_RECOGNIZED_COURSES"),
                ScholarshipVersion.course_families.any("STEM"),
            )
        )
    return query.order_by(ScholarshipVersion.application_deadline_at).limit(12)


def discover_scholarships(db: Session, profile: DiscoveryProfile) -> DiscoveryResponse:
    rows = db.execute(_candidate_query(profile)).all()
    cards = [scholarship_card(*row) for row in rows]

    if not rows:
        return DiscoveryResponse(
            ai_available=bool(settings.groq_api_key),
            model=settings.groq_model if settings.groq_api_key else None,
            notice="No active published scholarships matched the initial search scope.",
            candidates=[],
            introduction="Try broadening the state, course, or education-level information.",
            assessments=[],
        )

    version_ids = [version.id for _, version, _ in rows]
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.scholarship_version_id.in_(version_ids),
            KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
        )
        .order_by(KnowledgeChunk.scholarship_version_id, KnowledgeChunk.ordinal)
    ).all()
    chunks_by_version: dict[str, list[KnowledgeChunk]] = defaultdict(list)
    for chunk in chunks:
        chunks_by_version[str(chunk.scholarship_version_id)].append(chunk)

    if not settings.groq_api_key:
        return DiscoveryResponse(
            ai_available=False,
            model=None,
            notice=(
                "The published scholarship catalog is available, but AI assessment requires "
                "GROQ_API_KEY in the backend environment."
            ),
            candidates=cards,
            introduction=None,
            assessments=[],
        )

    candidate_payload: list[dict[str, Any]] = []
    allowed_citations: dict[str, set[str]] = {}
    for scholarship, version, organization in rows:
        version_key = str(version.id)
        evidence = [
            {
                "citation_id": str(chunk.id),
                "section": chunk.section_title,
                "page": chunk.page_number,
                "text": chunk.provider_text,
            }
            for chunk in chunks_by_version[version_key]
        ]
        allowed_citations[version_key] = {item["citation_id"] for item in evidence}
        candidate_payload.append(
            {
                "scholarship_id": str(scholarship.id),
                "scholarship_version_id": version_key,
                "title": version.title,
                "provider": organization.display_name,
                "provider_type": organization.type.value,
                "deadline": (
                    version.application_deadline_at.isoformat()
                    if version.application_deadline_at
                    else None
                ),
                "evidence": evidence,
            }
        )

    parsed = run_discovery_agent(
        {
            "student_facts": profile.model_dump(mode="json", exclude_none=True),
            "candidate_scholarships": candidate_payload,
        },
        allowed_citations,
    )
    if parsed is None:
        return DiscoveryResponse(
            ai_available=True,
            model=settings.groq_model,
            notice="AI returned no source-confirmed assessment. The catalog candidates are still shown.",
            candidates=cards,
            assessments=[],
        )

    return DiscoveryResponse(
        ai_available=True,
        model=settings.groq_model,
        notice="AI assessments use only provider-confirmed evidence and are not official decisions.",
        candidates=cards,
        introduction=parsed.introduction,
        assessments=parsed.assessments,
    )


def answer_scholarship_question(
    db: Session,
    scholarship_id: uuid.UUID,
    request: ScholarshipQuestionRequest,
) -> ScholarshipQuestionResponse:
    row = db.execute(
        published_scholarship_query().where(Scholarship.id == scholarship_id)
    ).one_or_none()
    if not row:
        raise LookupError("Scholarship was not found")

    _scholarship, version, organization = row
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.domain == version.domain,
            KnowledgeChunk.organization_id == version.organization_id,
            KnowledgeChunk.scholarship_version_id == version.id,
            KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
        )
        .order_by(KnowledgeChunk.ordinal)
    ).all()
    excerpts = {
        str(chunk.id): SourceExcerpt(
            citation_id=str(chunk.id),
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            text=chunk.provider_text,
        )
        for chunk in chunks
    }

    if not settings.groq_api_key:
        return ScholarshipQuestionResponse(
            ai_available=False,
            model=None,
            label="PROVIDER_CONFIRMATION_REQUIRED",
            answer=(
                "Question answering is temporarily unavailable. Review the scholarship "
                "information below or contact the provider."
            ),
            citations=[],
            suggested_questions=[],
        )

    parsed = run_question_agent(
        {
            "question": request.question,
            "preferred_language": request.preferred_language,
            "scholarship": {
                "version_id": str(version.id),
                "title": version.title,
                "provider": organization.display_name,
                "last_confirmed_at": version.last_provider_confirmed_at.isoformat(),
                "evidence": [excerpt.model_dump() for excerpt in excerpts.values()],
            },
        },
        set(excerpts),
    )
    if parsed is None:
        return ScholarshipQuestionResponse(
            ai_available=True,
            model=settings.groq_model,
            label="PROVIDER_CONFIRMATION_REQUIRED",
            answer="I could not confirm an answer from the provider-published information.",
            citations=[],
            suggested_questions=[],
        )

    return ScholarshipQuestionResponse(
        ai_available=True,
        model=settings.groq_model,
        label=parsed.label,
        answer=parsed.answer,
        citations=[excerpts[citation_id] for citation_id in parsed.citation_ids],
        suggested_questions=parsed.suggested_questions,
    )
