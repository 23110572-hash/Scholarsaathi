"""Run the REAL discover_scholarships (full evidence payload) repeatedly, exposing raw Groq errors."""

from __future__ import annotations

import time
import traceback

from app.agents.scholarship_ai import AIWorkflowError
from app.database import SessionLocal
from app.schemas import DiscoveryProfile
from app.services.ai_discovery import discover_scholarships

profile = DiscoveryProfile(message="I study BTech in Odisha. Which scholarships fit me?")

for attempt in range(1, 5):
    db = SessionLocal()
    started = time.time()
    try:
        result = discover_scholarships(db, profile)
        print(f"call {attempt}: HTTP-200 equivalent in {time.time() - started:.1f}s "
              f"({len(result.assessments)} assessments)")
    except AIWorkflowError as exc:
        cause = exc.__cause__
        print(f"call {attempt}: -> 502 in {time.time() - started:.1f}s")
        print(f"   AIWorkflowError: {exc}")
        print(f"   underlying: {type(cause).__module__}.{type(cause).__name__}")
        print(f"   detail: {str(cause)[:600]}")
    except Exception:
        traceback.print_exc()
    finally:
        db.close()
    time.sleep(2)
