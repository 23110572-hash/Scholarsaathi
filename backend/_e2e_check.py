"""End-to-end check through the real FastAPI stack: /api/ai/discover must not return 502."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
body = {"message": "I study BTech in Odisha. Which scholarships could fit me?"}

statuses = []
for attempt in range(1, 4):
    started = time.time()
    resp = client.post("/api/ai/discover", json=body, headers={"x-forwarded-for": f"10.0.0.{attempt}"})
    statuses.append(resp.status_code)
    elapsed = time.time() - started
    if resp.status_code == 200:
        data = resp.json()
        print(f"attempt {attempt}: 200 in {elapsed:5.1f}s | ai_available={data['ai_available']} "
              f"candidates={len(data['candidates'])} assessments={len(data['assessments'])}")
        print(f"           notice: {data['notice'][:100]}")
    else:
        print(f"attempt {attempt}: {resp.status_code} in {elapsed:5.1f}s -> {resp.text[:200]}")

print(f"\nstatuses: {statuses}")
print("502 present:", 502 in statuses)
