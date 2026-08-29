"""Temporary diagnostic: run the real discover_scholarships service and show the true traceback."""

from __future__ import annotations

import json
import traceback

from app.database import SessionLocal
from app.schemas import DiscoveryProfile
from app.services.ai_discovery import discover_scholarships

profile = DiscoveryProfile(
    message="I study BTech in Odisha. Which scholarships could fit me?",
    preferred_language="en",
)

db = SessionLocal()
try:
    # First: how big is the real payload?
    from app.services.ai_discovery import _candidate_query
    from app.models import KnowledgeChunk
    from sqlalchemy import select

    rows = db.execute(_candidate_query(profile)).all()
    print("candidate rows:", len(rows))
    version_ids = [v.id for _, v, _ in rows]
    if version_ids:
        chunks = db.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.scholarship_version_id.in_(version_ids),
                KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
            )
        ).all()
        print("owner-confirmed chunks:", len(chunks))
        total_chars = sum(len(c.provider_text or "") for c in chunks)
        print("total evidence chars:", total_chars, "~tokens:", total_chars // 4)

    print("\n--- calling discover_scholarships ---")
    result = discover_scholarships(db, profile)
    print("ai_available:", result.ai_available)
    print("notice:", result.notice)
    print("candidates:", len(result.candidates))
    print("assessments:", len(result.assessments))
except Exception:
    print("\n!!! RAW TRACEBACK !!!")
    traceback.print_exc()
finally:
    db.close()
