from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents.scholarship_ai import (
    AICapacityError,
    run_chat_agent,
    run_discovery_agent,
    run_question_agent,
)
from app.api.scholarships import published_scholarship_query
from app.core.config import get_settings
from app.models import KnowledgeChunk, Scholarship, ScholarshipVersion
from app.presenters import scholarship_card
from app.schemas import (
    ChatExtractedFacts,
    DiscoveryProfile,
    DiscoveryResponse,
    ScholarshipQuestionRequest,
    ScholarshipQuestionResponse,
    SourceExcerpt,
)

settings = get_settings()

# OpenRouter / AI providers count prompt tokens plus max_tokens against the tokens-per-minute ceiling and
# rejects the request with HTTP 413 when the sum exceeds it. These constants keep the
# estimate deliberately pessimistic so a request is trimmed rather than refused.
_CHARS_PER_TOKEN = 3
_PROMPT_OVERHEAD_TOKENS = 400
_SAFETY_MARGIN_TOKENS = 600
# A four-candidate bundle measured at 546 completion tokens per assessment against
# openai/gpt-oss-20b. Allowing 620 leaves headroom for a wordier reply, because a
# completion truncated by max_tokens produces invalid JSON and fails the whole request.
_OUTPUT_TOKENS_PER_CANDIDATE = 620
_INTRODUCTION_TOKENS = 700
_MAX_OUTPUT_TOKENS = 5000


def _estimate_tokens(payload: object) -> int:
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    return len(serialized) // _CHARS_PER_TOKEN + _PROMPT_OVERHEAD_TOKENS


def _plan_discovery_request(
    student_facts: dict[str, Any],
    candidate_payload: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Trim candidates until prompt + output tokens fit the configured AI token budget.

    Returns the candidates to assess and the max_tokens to request. Dropping the tail is
    safe: candidates are ordered by nearest deadline and every one still reaches the
    student through the unfiltered ``candidates`` list.
    """
    candidates = candidate_payload[: settings.ai_discovery_max_candidates]
    while candidates:
        prompt_tokens = _estimate_tokens(
            {"student_facts": student_facts, "candidate_scholarships": candidates}
        )
        available = settings.ai_token_budget - prompt_tokens - _SAFETY_MARGIN_TOKENS
        wanted = min(
            _MAX_OUTPUT_TOKENS,
            _OUTPUT_TOKENS_PER_CANDIDATE * len(candidates) + _INTRODUCTION_TOKENS,
        )
        # Only accept a plan whose full output allowance fits, so the model is never
        # cut off mid-JSON by a max_tokens value the budget could not cover.
        if available >= wanted:
            return candidates, wanted
        candidates = candidates[:-1]
    return [], 0


# Facts that make an eligibility assessment meaningful. Without at least one of these the
# assistant has nothing to compare against provider evidence, so assessing every catalog
# candidate would only produce "cannot determine" noise.
_ELIGIBILITY_FIELDS = (
    "state",
    "education_level",
    "course",
    "course_year",
    "marks_percentage",
    "family_income_range",
)


def _has_eligibility_facts(profile: DiscoveryProfile) -> bool:
    if any(getattr(profile, name) is not None for name in _ELIGIBILITY_FIELDS):
        return True
    return bool(profile.categories)


def _scripted_chat_reply() -> DiscoveryResponse:
    """Deterministic conversational reply used when the AI provider is unavailable."""
    return DiscoveryResponse(
        ai_available=False,
        model=None,
        notice="AI chat is not configured, so this is a standard reply.",
        candidates=[],
        introduction=(
            "Hello, I am ScholarSaathi. Tell me your State or UT, your course, and your "
            "current study year, and I will look for scholarships that fit you."
        ),
        assessments=[],
        mode="CONVERSATION",
        intent="GREETING",
        requested_details=["state", "course", "course_year"],
        suggested_replies=[
            "I study BTech in Odisha",
            "I am in my 2nd year",
            "What details do you need?",
        ],
        extracted=ChatExtractedFacts(),
    )


def _conversation_response(
    db: Session,
    profile: DiscoveryProfile,
) -> DiscoveryResponse:
    """Handle a turn that carries no eligibility facts as pure conversation.

    No candidates and no assessments are returned, so a greeting or a general question
    never renders a wall of indeterminate scholarship cards.
    """
    if not settings.openrouter_api_key:
        return _scripted_chat_reply()

    # Titles only. The chat agent is explicitly barred from attaching conditions to them,
    # so it needs no evidence and stays cheap.
    titles = db.execute(
        published_scholarship_query().order_by(ScholarshipVersion.application_deadline_at).limit(12)
    ).all()
    catalog_titles = [
        f"{version.title} — {organization.display_name}" for _, version, organization in titles
    ]

    try:
        parsed = run_chat_agent(
            {
                "message": profile.message,
                "preferred_language": profile.preferred_language,
                "known_student_facts": profile.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude={"message", "preferred_language"},
                ),
                "catalog_titles": catalog_titles,
                "catalog_count": len(catalog_titles),
            }
        )
    except AICapacityError:
        return _scripted_chat_reply()

    if parsed is None:
        return _scripted_chat_reply()

    return DiscoveryResponse(
        ai_available=True,
        model=settings.ai_model,
        notice=(
            "Share a few details and I will compare them against provider-confirmed "
            "scholarship information."
        ),
        candidates=[],
        introduction=parsed.reply,
        assessments=[],
        mode="CONVERSATION",
        intent=parsed.intent,
        requested_details=parsed.requested_details,
        suggested_replies=parsed.suggested_replies,
        extracted=parsed.extracted,
    )


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
    # A greeting or a general question carries no eligibility facts. Answer it as chat
    # rather than assessing the whole catalog against nothing.
    if not _has_eligibility_facts(profile):
        return _conversation_response(db, profile)

    rows = db.execute(_candidate_query(profile)).all()
    cards = [scholarship_card(*row) for row in rows]

    if not rows:
        return DiscoveryResponse(
            ai_available=bool(settings.openrouter_api_key),
            model=settings.ai_model if settings.openrouter_api_key else None,
            notice="No active published scholarships matched the initial search scope.",
            candidates=[],
            introduction=(
                "I could not find a published scholarship matching those details yet. Try a "
                "wider course or education level, or leave the State blank to see all-India "
                "programmes."
            ),
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

    if not settings.openrouter_api_key:
        return DiscoveryResponse(
            ai_available=False,
            model=None,
            notice=(
                "The published scholarship catalog is available, but AI assessment requires "
                "OPENROUTER_API_KEY in the backend environment."
            ),
            candidates=cards,
            introduction=None,
            assessments=[],
        )

    candidate_payload: list[dict[str, Any]] = []
    citations_by_version: dict[str, set[str]] = {}
    evidence_limit = settings.ai_discovery_evidence_char_limit
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
            model=settings.ai_model,
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
            model=settings.ai_model,
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
            model=settings.ai_model,
            notice="AI returned no source-confirmed assessment. The catalog candidates are still shown.",
            candidates=cards,
            assessments=[],
        )

    notice = "Assessments use only provider-confirmed information and are not official decisions."
    if len(assessed) < len(candidate_payload):
        notice = (
            f"I looked closely at the {len(assessed)} nearest deadlines out of "
            f"{len(candidate_payload)} matching scholarships, using only provider-confirmed "
            "information. These are not official decisions."
        )

    # Keep the conversation moving: name the details that would sharpen the next pass.
    missing = [name for name in _ELIGIBILITY_FIELDS if getattr(profile, name) is None]
    if not profile.categories:
        missing.append("categories")

    return DiscoveryResponse(
        ai_available=True,
        model=settings.ai_model,
        notice=notice,
        candidates=cards,
        introduction=parsed.introduction,
        assessments=parsed.assessments,
        mode="ASSESSMENT",
        intent="SCHOLARSHIP_SEARCH",
        requested_details=missing[:3],
        suggested_replies=[],
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

    if not settings.openrouter_api_key:
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
            model=settings.ai_model,
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
            model=settings.ai_model,
            label="PROVIDER_CONFIRMATION_REQUIRED",
            answer="I could not confirm an answer from the provider-published information.",
            citations=[],
            suggested_questions=[],
        )

    return ScholarshipQuestionResponse(
        ai_available=True,
        model=settings.ai_model,
        label=parsed.label,
        answer=parsed.answer,
        citations=[excerpts[citation_id] for citation_id in parsed.citation_ids],
        suggested_questions=parsed.suggested_questions,
    )
