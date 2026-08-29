from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.schemas import (
    DiscoveryAssessmentBundle,
    ScholarshipAssessment,
    ScholarshipChatParsed,
    ScholarshipQuestionParsed,
)

settings = get_settings()
logger = logging.getLogger(__name__)

FACT_EXTRACTION_RULES = """
Fill 'extracted' with ONLY the eligibility facts the student actually stated in their own message
on this turn. Leave a field null when it was not mentioned. Never guess and never copy a value from
facts that were already known. Use these encodings:
- state: the 2-letter Indian State or UT code, for example OD for Odisha, MH for Maharashtra.
- education_level: one of DIPLOMA, UNDERGRADUATE, POSTGRADUATE, DOCTORAL, CLASS_11_12.
- course: a short uppercase token such as BTECH, BE, BARCH, TECHNICAL_DIPLOMA, BSC, BCOM, BA, MBBS,
  or STEM when they are vague about a science or engineering subject.
- course_year: an integer from 1 to 12. "2nd year" is 2.
- marks_percentage: a number from 0 to 100. Convert a CGPA out of 10 by multiplying by 9.5.
- family_income_range: one of UP_TO_250000, 250001_TO_400000, 400001_TO_600000, 600001_TO_800000,
  ABOVE_800000. "around 3 lakh" is 250001_TO_400000.
- categories: uppercase tokens such as FIRST_GENERATION, WOMEN, SC, ST, OBC, EWS, MINORITY,
  DISABILITY, RURAL, ORPHAN.
""".strip()

DISCOVERY_INSTRUCTIONS = (
    """
You are ScholarSaathi, an evidence-grounded scholarship discovery assistant chatting directly with a student.
You receive temporary, non-identifying student facts and candidate scholarships from the
ScholarSaathi database. Assess every candidate independently using only the supplied,
provider-confirmed evidence. Never use model memory, invent a condition, or mix evidence between
scholarships. Every matching point and possible conflict must cite one or more exact citation IDs
belonging to that scholarship version. If evidence is incomplete or contradictory, use
CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION. LIKELY_ELIGIBLE is advisory guidance, never an
official decision. The scholarship provider always makes the final decision. Report confidence as a
decimal between 0 and 1. Keep every summary under 300 characters and every statement under 200 characters.

Write the 'introduction' as a short, warm, plain-language message to the student that says what you
compared and what stood out. Two or three sentences, no bullet lists, no restating every rule.
If a detail in student_facts is missing and it changed what you could conclude, say which one.
Address the student directly as "you" and vary your phrasing between turns.
""".strip()
    + "\n\n"
    + FACT_EXTRACTION_RULES
)

CHAT_INSTRUCTIONS = (
    """
You are ScholarSaathi, a warm and practical scholarship assistant chatting with an Indian student
inside the ScholarSaathi web app. This turn is a CONVERSATION turn: you are talking, not producing
eligibility verdicts.

Classify the student's message into 'intent':
- GREETING: hello, hi, namaste, good morning, or similar openers.
- SMALL_TALK: thanks, ok, bye, who are you, what can you do.
- GENERAL_QUESTION: how scholarships or this platform work, what documents are usually needed,
  what a deadline or income certificate means, how to apply, how ScholarSaathi decides matches.
- SHARING_DETAILS: the student is telling you their state, course, year, marks, income, or category.
- SCHOLARSHIP_SEARCH: they are asking you to find or suggest scholarships for them.
- OUT_OF_SCOPE: unrelated to education funding.

Write 'reply' as a real chat message: friendly, specific, 2 to 4 short sentences, no markdown, no
bullet symbols, no headings. Address the student directly as "you". Vary your phrasing between turns
so it does not read like a template.

For a GREETING, introduce yourself in one line and then ask for the details you need in a natural
sentence, mentioning what you can do with them. Ask for at most three details in one message so it
does not feel like a form. Prefer state, course, and study year first, then marks, family income,
and any category later.

For a GENERAL_QUESTION you may explain how scholarships, documents, deadlines, and applications
generally work in India, and how to use this app. You must NOT state the eligibility rule, benefit
amount, deadline, or selection criterion of any specific scholarship, because those are only valid
when quoted from provider-confirmed evidence, which you do not have on this turn. If asked about a
specific scholarship's rules, say you can open that scholarship and answer from the provider's own
published text, and invite them to ask there. You may name scholarships from 'catalog_titles' when
listing what is available, but never attach conditions to those names.

For OUT_OF_SCOPE, say briefly that you only help with scholarships and education funding, then
offer to help them find one.

Set 'requested_details' to the detail keys you still need most, at most three, ordered by how much
they would improve matching. Use only: state, education_level, course, course_year,
marks_percentage, family_income_range, categories. Leave it empty when you already have enough or
when the turn was not about matching.

Set 'suggested_replies' to at most three short things the student could tap to answer you, phrased
in the student's own voice, each under 40 characters, for example "I study BTech in Odisha" or
"My marks are 78%". Leave empty for OUT_OF_SCOPE.

Never ask for or accept Aadhaar, PAN, bank details, phone numbers, passwords, or OTPs. If the
student volunteers such a value, tell them not to share it and do not repeat it back.
Answer in the student's preferred language when one is given.
""".strip()
    + "\n\n"
    + FACT_EXTRACTION_RULES
)

QUESTION_INSTRUCTIONS = """
You are ScholarSaathi, a friendly and conversational scholarship assistant chatting directly with a student.
Answer only from the supplied provider-confirmed evidence for this scholarship version. Do not use
model memory or infer an unstated rule. Use exact citation IDs from the supplied evidence. If the
evidence is missing or ambiguous, use PROVIDER_CONFIRMATION_REQUIRED. Never claim an official
eligibility or selection decision. Be warm and supportive, and answer in the requested language when possible.
""".strip()


class AIWorkflowError(RuntimeError):
    """Raised when a LangGraph AI workflow cannot produce a safe typed result."""


class AICapacityError(AIWorkflowError):
    """Raised when the AI provider refused the request for quota or size reasons."""


def _capacity_refusal(exc: Exception) -> bool:
    """Return True when the AI provider refused the call for token quota or request-size reasons."""
    status_code = getattr(exc, "status_code", None)
    if status_code in {413, 429}:
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("code") == "rate_limit_exceeded":
            return True
    return False


class DiscoveryAgentState(TypedDict, total=False):
    payload: dict[str, Any]
    allowed_citations: dict[str, set[str]]
    max_output_tokens: int
    parsed: DiscoveryAssessmentBundle
    result: DiscoveryAssessmentBundle


class QuestionAgentState(TypedDict, total=False):
    payload: dict[str, Any]
    allowed_citations: set[str]
    parsed: ScholarshipQuestionParsed
    result: ScholarshipQuestionParsed


class ChatAgentState(TypedDict, total=False):
    payload: dict[str, Any]
    result: ScholarshipChatParsed


def _chat_model(max_tokens: int) -> ChatOpenAI:
    if not settings.openrouter_api_key:
        raise AIWorkflowError("OPENROUTER_API_KEY is not configured")
    return ChatOpenAI(
        model=settings.ai_model,
        api_key=settings.openrouter_api_key.get_secret_value(),
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        max_tokens=max_tokens,
        timeout=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )


def _generate_discovery(state: DiscoveryAgentState) -> dict[str, DiscoveryAssessmentBundle]:
    structured_model = _chat_model(state["max_output_tokens"]).with_structured_output(
        DiscoveryAssessmentBundle,
        method="json_schema",
        strict=True,
    )
    parsed = structured_model.invoke(
        [
            SystemMessage(content=DISCOVERY_INSTRUCTIONS),
            HumanMessage(content=json.dumps(state["payload"], ensure_ascii=False)),
        ]
    )
    if not isinstance(parsed, DiscoveryAssessmentBundle):
        raise AIWorkflowError("Discovery agent returned an unexpected response type")
    return {"parsed": parsed}


def _cannot_determine(version_id: str, reason: str) -> ScholarshipAssessment:
    return ScholarshipAssessment(
        scholarship_version_id=version_id,
        assessment="CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION",
        confidence=0,
        summary=reason,
        matching_points=[],
        possible_conflicts=[],
        missing_information=["More of your details, or a check against the provider's own page."],
        next_steps=["Open this scholarship to ask about its published rules."],
        warning="The scholarship provider makes the final decision.",
    )


def _validate_discovery(state: DiscoveryAgentState) -> dict[str, DiscoveryAssessmentBundle]:
    parsed = state.get("parsed")
    if parsed is None:
        raise AIWorkflowError("Discovery agent returned no structured assessment")

    allowed_citations = state["allowed_citations"]
    parsed_by_version: dict[str, ScholarshipAssessment] = {}
    for assessment in parsed.assessments:
        version_id = assessment.scholarship_version_id
        if version_id in allowed_citations and version_id not in parsed_by_version:
            parsed_by_version[version_id] = assessment

    validated: list[ScholarshipAssessment] = []
    for version_id, citation_ids in allowed_citations.items():
        assessment = parsed_by_version.get(version_id)
        if assessment is None:
            validated.append(
                _cannot_determine(
                    version_id,
                    "I could not match your details against this provider's published "
                    "information yet.",
                )
            )
            continue

        claims = [*assessment.matching_points, *assessment.possible_conflicts]
        claims_have_evidence = all(
            claim.citation_ids
            and all(citation_id in citation_ids for citation_id in claim.citation_ids)
            for claim in claims
        )
        conclusion_has_evidence = bool(claims) or (
            assessment.assessment == "CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION"
        )
        if claims_have_evidence and conclusion_has_evidence:
            validated.append(assessment)
        else:
            validated.append(
                _cannot_determine(
                    version_id,
                    "I could not confirm this against the provider's published information, "
                    "so I am not drawing a conclusion.",
                )
            )

    return {
        "result": DiscoveryAssessmentBundle(
            introduction=parsed.introduction,
            assessments=validated,
            extracted=parsed.extracted,
        )
    }


def _generate_question(state: QuestionAgentState) -> dict[str, ScholarshipQuestionParsed]:
    structured_model = _chat_model(1800).with_structured_output(
        ScholarshipQuestionParsed,
        method="json_schema",
        strict=True,
    )
    parsed = structured_model.invoke(
        [
            SystemMessage(content=QUESTION_INSTRUCTIONS),
            HumanMessage(content=json.dumps(state["payload"], ensure_ascii=False)),
        ]
    )
    if not isinstance(parsed, ScholarshipQuestionParsed):
        raise AIWorkflowError("Question agent returned an unexpected response type")
    return {"parsed": parsed}


def _question_fallback(
    answer: str,
    suggested_questions: list[str] | None = None,
) -> ScholarshipQuestionParsed:
    return ScholarshipQuestionParsed(
        label="PROVIDER_CONFIRMATION_REQUIRED",
        answer=answer,
        citation_ids=[],
        suggested_questions=suggested_questions or [],
    )


def _validate_question(state: QuestionAgentState) -> dict[str, ScholarshipQuestionParsed]:
    parsed = state.get("parsed")
    if parsed is None:
        raise AIWorkflowError("Question agent returned no structured answer")

    citation_ids = list(dict.fromkeys(parsed.citation_ids))
    if any(citation_id not in state["allowed_citations"] for citation_id in citation_ids):
        result = _question_fallback(
            "I could not confirm the generated answer against the provider source.",
            parsed.suggested_questions,
        )
    elif parsed.label == "SUPPORTED_BY_PROVIDER_SOURCE" and not citation_ids:
        result = _question_fallback(
            "The provider source did not contain enough evidence for an answer.",
            parsed.suggested_questions,
        )
    else:
        result = parsed.model_copy(update={"citation_ids": citation_ids})
    return {"result": result}


def _generate_chat(state: ChatAgentState) -> dict[str, ScholarshipChatParsed]:
    structured_model = _chat_model(900).with_structured_output(
        ScholarshipChatParsed,
        method="json_schema",
        strict=True,
    )
    parsed = structured_model.invoke(
        [
            SystemMessage(content=CHAT_INSTRUCTIONS),
            HumanMessage(content=json.dumps(state["payload"], ensure_ascii=False)),
        ]
    )
    if not isinstance(parsed, ScholarshipChatParsed):
        raise AIWorkflowError("Chat agent returned an unexpected response type")
    return {"result": parsed}


@lru_cache
def _chat_graph():
    graph = StateGraph(ChatAgentState)
    graph.add_node("generate_reply", _generate_chat)
    graph.add_edge(START, "generate_reply")
    graph.add_edge("generate_reply", END)
    return graph.compile()


@lru_cache
def _discovery_graph():
    graph = StateGraph(DiscoveryAgentState)
    graph.add_node("generate_assessments", _generate_discovery)
    graph.add_node("validate_provider_evidence", _validate_discovery)
    graph.add_edge(START, "generate_assessments")
    graph.add_edge("generate_assessments", "validate_provider_evidence")
    graph.add_edge("validate_provider_evidence", END)
    return graph.compile()


@lru_cache
def _question_graph():
    graph = StateGraph(QuestionAgentState)
    graph.add_node("generate_answer", _generate_question)
    graph.add_node("validate_provider_evidence", _validate_question)
    graph.add_edge(START, "generate_answer")
    graph.add_edge("generate_answer", "validate_provider_evidence")
    graph.add_edge("validate_provider_evidence", END)
    return graph.compile()


def run_chat_agent(payload: dict[str, Any]) -> ScholarshipChatParsed | None:
    """Answer a conversational turn without producing eligibility verdicts.

    Returns None when no AI provider is configured so the caller can fall back to a
    deterministic scripted reply.
    """
    if not settings.openrouter_api_key:
        return None
    try:
        final_state = _chat_graph().invoke({"payload": payload})
    except AIWorkflowError:
        raise
    except Exception as exc:
        logger.exception("Chat agent failed (model=%s)", settings.ai_model)
        if _capacity_refusal(exc):
            raise AICapacityError("The AI provider refused the chat request") from exc
        raise AIWorkflowError("The scholarship chat workflow failed") from exc

    result = final_state.get("result")
    if not isinstance(result, ScholarshipChatParsed):
        raise AIWorkflowError("The chat agent produced no validated result")
    return result


def run_discovery_agent(
    payload: dict[str, Any],
    allowed_citations: dict[str, set[str]],
    max_output_tokens: int,
) -> DiscoveryAssessmentBundle | None:
    if not settings.openrouter_api_key:
        return None
    try:
        final_state = _discovery_graph().invoke(
            {
                "payload": payload,
                "allowed_citations": allowed_citations,
                "max_output_tokens": max_output_tokens,
            }
        )
    except AIWorkflowError:
        raise
    except Exception as exc:
        logger.exception(
            "Discovery agent failed (model=%s, candidates=%d, max_output_tokens=%d)",
            settings.ai_model,
            len(payload.get("candidate_scholarships", [])),
            max_output_tokens,
        )
        if _capacity_refusal(exc):
            raise AICapacityError("The AI provider refused the discovery request") from exc
        raise AIWorkflowError("The discovery agent workflow failed") from exc

    result = final_state.get("result")
    if not isinstance(result, DiscoveryAssessmentBundle):
        raise AIWorkflowError("The discovery agent produced no validated result")
    return result


def run_question_agent(
    payload: dict[str, Any],
    allowed_citations: set[str],
) -> ScholarshipQuestionParsed | None:
    if not settings.openrouter_api_key:
        return None
    try:
        final_state = _question_graph().invoke(
            {"payload": payload, "allowed_citations": allowed_citations}
        )
    except AIWorkflowError:
        raise
    except Exception as exc:
        logger.exception("Question agent failed (model=%s)", settings.ai_model)
        if _capacity_refusal(exc):
            raise AICapacityError("The AI provider refused the question request") from exc
        raise AIWorkflowError("The scholarship question workflow failed") from exc

    result = final_state.get("result")
    if not isinstance(result, ScholarshipQuestionParsed):
        raise AIWorkflowError("The question agent produced no validated result")
    return result
