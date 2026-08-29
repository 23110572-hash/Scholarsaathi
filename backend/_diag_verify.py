"""Verify the fix: repeated real discovery calls must never surface a 502."""

from __future__ import annotations

import time

from app.agents.scholarship_ai import AICapacityError, AIWorkflowError
from app.core.config import get_settings
from app.database import SessionLocal
from app.schemas import DiscoveryProfile
from app.services.ai_discovery import _plan_discovery_request, discover_scholarships

settings = get_settings()
print(f"token budget={settings.groq_token_budget} "
      f"max_candidates={settings.groq_discovery_max_candidates} "
      f"evidence_char_limit={settings.groq_discovery_evidence_char_limit}")

profile = DiscoveryProfile(message="I study BTech in Odisha. Which scholarships fit me?")

failures = 0
for attempt in range(1, 7):
    db = SessionLocal()
    started = time.time()
    try:
        result = discover_scholarships(db, profile)
        elapsed = time.time() - started
        print(f"call {attempt}: 200 in {elapsed:5.1f}s | ai={result.ai_available} "
              f"candidates={len(result.candidates)} assessments={len(result.assessments)}")
        if not result.ai_available:
            print(f"           degraded notice -> {result.notice[:90]}")
    except AICapacityError as exc:
        failures += 1
        print(f"call {attempt}: LEAKED AICapacityError -> {exc}")
    except AIWorkflowError as exc:
        failures += 1
        print(f"call {attempt}: -> 502 {exc} | cause={type(exc.__cause__).__name__}")
        print(f"           {str(exc.__cause__)[:300]}")
    finally:
        db.close()

print(f"\n502 responses: {failures} of 6")

# Show the planner's sizing decision against the real catalog payload.
print("\n--- planner sizing on the real payload ---")
db = SessionLocal()
from sqlalchemy import select  # noqa: E402

from app.models import KnowledgeChunk  # noqa: E402
from app.services.ai_discovery import _candidate_query  # noqa: E402

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
payload = [
    {
        "scholarship_version_id": str(v.id),
        "title": v.title,
        "evidence": [
            {"citation_id": str(c.id), "text": (c.provider_text or "")[
                : settings.groq_discovery_evidence_char_limit]}
            for c in by_version.get(str(v.id), [])
        ],
    }
    for _, v, _ in rows
]
assessed, max_out = _plan_discovery_request({"message": profile.message}, payload)
print(f"catalog candidates={len(payload)} -> assessed={len(assessed)} max_tokens={max_out}")
