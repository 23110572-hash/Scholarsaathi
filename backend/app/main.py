from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import applications, auth, discovery, organizations, scholarships, students
from app.core.config import get_settings
from app.database import get_db

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Unified scholarship publishing, AI discovery, and synthetic application API. "
        "This is an independent prototype, not an official government service."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith(
        ("/api/ai", "/api/applications", "/api/auth/me", "/api/student")
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_request: Request, _exception: SQLAlchemyError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "The database is temporarily unavailable."},
    )


@app.get("/api/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "scholarsaathi-api"}


@app.get("/api/health/ready")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(select(1))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Database is not ready",
        ) from exc
    return {"status": "ready", "database": "postgresql"}


app.include_router(auth.router)
app.include_router(scholarships.router)
app.include_router(organizations.router)
app.include_router(discovery.router)
app.include_router(applications.router)
app.include_router(students.router)
