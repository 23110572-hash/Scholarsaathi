"""Measure ACTUAL prompt/completion tokens for a 4-candidate discovery call."""

from __future__ import annotations

import json

import httpx
from langchain_core.utils.function_calling import convert_to_json_schema
from sqlalchemy import select

from app.agents.scholarship_ai import DISCOVERY_INSTRUCTIONS
from app.core.config import get_settings
from app.database import SessionLocal
from app.models import KnowledgeChunk
from app.schemas import DiscoveryAssessmentBundle, DiscoveryProfile
from app.services.ai_discovery import _candidate_query

settings = get_settings()
profile = DiscoveryProfile(message="I study BTech in Odisha. Which scholarships fit me?")

db = SessionLocal()
rows = db.execute(_candidate_query(profile)).all()
chunks = db.scalars(
    select(KnowledgeChunk).where(
        KnowledgeChunk.scholarship_version_id.in_([v.id for _, v, _ in rows]),
        KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
    )
).all()
db.close()

by_version: dict[str, list] = {}
for c in chunks:
    by_version.setdefault(str(c.scholarship_version_id), []).append(c)

candidates = [
    {
        "scholarship_id": str(s.id),
        "scholarship_version_id": str(v.id),
        "title": v.title,
        "provider": o.display_name,
        "provider_type": o.type.value,
        "deadline": v.application_deadline_at.isoformat() if v.application_deadline_at else None,
        "evidence": [
            {
                "citation_id": str(c.id),
                "section": c.section_title,
                "page": c.page_number,
                "text": (c.provider_text or "")[: settings.groq_discovery_evidence_char_limit],
            }
            for c in by_version.get(str(v.id), [])
        ],
    }
    for s, v, o in rows
][: settings.groq_discovery_max_candidates]

payload = {
    "student_facts": profile.model_dump(mode="json", exclude_none=True),
    "candidate_scholarships": candidates,
}

resp = httpx.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {settings.groq_api_key.get_secret_value()}"},
    json={
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": DISCOVERY_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0,
        "max_tokens": 5000,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "DiscoveryAssessmentBundle",
                "schema": convert_to_json_schema(DiscoveryAssessmentBundle, strict=True),
                "strict": True,
            },
        },
    },
    timeout=120,
)
print("HTTP", resp.status_code)
data = resp.json()
if resp.status_code == 200:
    usage = data["usage"]
    print(f"candidates sent      : {len(candidates)}")
    print(f"prompt_tokens        : {usage['prompt_tokens']}")
    print(f"completion_tokens    : {usage['completion_tokens']}  <-- actual output needed")
    print(f"total_tokens         : {usage['total_tokens']}")
    print(f"per-candidate output : {usage['completion_tokens'] / len(candidates):.0f}")
    print(f"finish_reason        : {data['choices'][0]['finish_reason']}")
else:
    print(json.dumps(data, indent=2)[:800])
