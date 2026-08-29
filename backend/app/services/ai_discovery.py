from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents.scholarship_ai import (
    AICapacityError,
    run_discovery_agent,
    run_question_agent,
)
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

# Groq counts prompt tokens plus max_tokens against the tokens-per-minute ceiling and
# rejects the request with HTTP 413 when the sum exceeds it. These constants keep the
# estimate deliberately pessimistic so a request is trimmed rather than refused.
_CHARS_PER_TOKEN = 3
_PROMPT_OVERHEAD_TOKENS = 400
_SAFETY_MARGIN_TOKENS = 600
_MIN_OUTPUT_TOKENS = 900
_MAX_OUTPUT_TOKENS = 5000
_OUTPUT_TOKENS_PER_CANDIDATE = 320


def _estimate_tokens(payload: object) -> int:
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    return len(serialized) // _CHARS_PER_TOKEN + _PROMPT_OVERHEAD_TOKENS


def _plan_discovery_request(
    student_facts: dict[str, Any],
    candidate_payload: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Trim candidates until prompt + output tokens fit the configured Groq budget.

    Returns the candidates to assess and the max_tokens to request. Dropping the tail is
    safe: candidates are ordered by nearest deadline and every one still reaches the
    student through the unfiltered ``candidates`` list.
    """
    candidates = candidate_payload[: settings.groq_discovery_max_candidates]
    while candidates:
        prompt_tokens = _estimate_tokens(
            {"student_facts": student_facts, "candidate_scholarships": candidates}
        )
        available = settings.groq_token_budget - prompt_tokens - _SAFETY_MARGIN_TOKENS
        wanted = min(
            _MAX_OUTPUT_TOKENS,
            _OUTPUT_TOKENS_PER_CANDIDATE * len(candidates) + _MIN_OUTPUT_TOKENS,
        )
        if available >= _MIN_OUTPUT_TOKENS:
            return candidates, min(wanted, available)
        candidates = candidates[:-1]
    return [], 0


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
    citations_by_version: dict[str, set[str]] = {}
    evidence_limit = settings.groq_discovery_evidence_char_limit
    for scholarship, version, organization in rows:
        version_key = str(version.id)
        evidence = [
            {
                "citation_id": str(chunk.id),
                "section": chunk.section_title,
                "page": chunk.page_number,
                "text": (chunk.provider_text or "")[:evidence_limit],
            }
            for chunk in chunks_by_version[version_key]
        ]
        citations_by_version[version_key] = {item["citation_id"] for item in evidence}
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

    student_facts = profile.model_dump(mode="json", exclude_none=True)
    assessed, max_output_tokens = _plan_discovery_request(student_facts, candidate_payload)
    if not assessed:
        return DiscoveryResponse(
            ai_available=False,
            model=settings.groq_model,
            notice=(
                "The published scholarship catalog is available, but the provider evidence "
                "is too large for the current AI token budget. Narrow the search with a "
                "state, course, or education level."
            ),
            candidates=cards,
            introduction=None,
            assessments=[],
        )

    allowed_citations = {
        candidate["scholarship_version_id"]: citations_by_version[
            candidate["scholarship_version_id"]
        ]
        for candidate in assessed
    }

    try:
        parsed = run_discovery_agent(
            {"student_facts": student_facts, "candidate_scholarships": assessed},
            allowed_citations,
            max_output_tokens,
        )
    except AICapacityError:
        return DiscoveryResponse(
            ai_available=False,
            model=settings.groq_model,
            notice=(
                "AI assessment is at its usage limit for the moment. The published catalog "
                "below is complete, and assessments resume within a minute."
            ),
            candidates=cards,
            introduction=None,
            assessments=[],
        )
    if parsed is None:
        return DiscoveryResponse(
            ai_available=True,
            model=settings.groq_model,
            notice="AI returned no source-confirmed assessment. The catalog candidates are still shown.",
            candidates=cards,
            assessments=[],
        )

    notice = "AI assessments use only provider-confirmed evidence and are not official decisions."
    if len(assessed) < len(candidate_payload):
        notice = (
            f"AI assessed the {len(assessed)} nearest-deadline scholarships using only "
            f"provider-confirmed evidence. All {len(candidate_payload)} catalog candidates "
            "are listed, and assessments are not official decisions."
        )

    return DiscoveryResponse(
        ai_available=True,
        model=settings.groq_model,
        notice=notice,
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

    try:
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
    except AICapacityError:
        return ScholarshipQuestionResponse(
            ai_available=False,
            model=settings.groq_model,
            label="PROVIDER_CONFIRMATION_REQUIRED",
            answer=(
                "AI answering is at its usage limit for the moment. Please try again in a "
                "minute, or review the provider information on this page."
            ),
            citations=[],
            suggested_questions=[],
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
