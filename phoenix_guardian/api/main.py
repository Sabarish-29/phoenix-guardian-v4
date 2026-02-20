"""FastAPI main application.

Central API server for Phoenix Guardian medical AI documentation system.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from phoenix_guardian.agents.navigator_agent import PatientNotFoundError
try:
    from phoenix_guardian.agents.safety_agent import SecurityException
except BaseException:
    SecurityException = Exception
from phoenix_guardian.api.routes import agents, auth, encounters, health, patients, transcription
from phoenix_guardian.api.routes import pqc as pqc_routes
from phoenix_guardian.api.routes import learning as learning_routes
from phoenix_guardian.api.routes import orchestration as orchestration_routes
from phoenix_guardian.api.routes import security_console as security_console_routes
from phoenix_guardian.api.routes import treatment_shadow as treatment_shadow_routes
from phoenix_guardian.api.routes import silent_voice as silent_voice_routes
from phoenix_guardian.api.routes import zebra_hunter as zebra_hunter_routes
from phoenix_guardian.api.routes import v5_dashboard as v5_dashboard_routes
from phoenix_guardian.api.utils.orchestrator import OrchestrationError
from phoenix_guardian.database.connection import db

# Create FastAPI app
app = FastAPI(
    title="Phoenix Guardian API",
    description="Medical AI Documentation System - REST API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database connection and seed demo users on startup."""
    db.connect()
    try:
        db.create_tables()
    except Exception as exc:
        # Safe to ignore if tables/enums already exist (e.g. concurrent workers)
        print(f"Note: create_tables encountered: {exc}")
    print(f"Database connected: {db.config.host}:{db.config.port}/{db.config.name}")

    # Seed demo users if the DB is empty (first deploy)
    _seed_demo_users()


def _seed_demo_users() -> None:
    """Create demo users if none exist in the database."""
    from phoenix_guardian.models.user import User, UserRole
    from phoenix_guardian.api.auth.utils import hash_password

    try:
        with db.session_scope() as session:
            if session.query(User).first() is not None:
                print("Users already exist — skipping seed")
                return

            demo_users = [
                User(
                    email="dr.smith@phoenixguardian.health",
                    password_hash=hash_password("Doctor123!"),
                    first_name="John",
                    last_name="Smith",
                    role=UserRole.PHYSICIAN,
                    is_active=True,
                ),
                User(
                    email="admin@phoenixguardian.health",
                    password_hash=hash_password("Admin123!"),
                    first_name="System",
                    last_name="Administrator",
                    role=UserRole.ADMIN,
                    is_active=True,
                ),
                User(
                    email="nurse.jones@phoenixguardian.health",
                    password_hash=hash_password("Nurse123!"),
                    first_name="Sarah",
                    last_name="Jones",
                    role=UserRole.NURSE,
                    is_active=True,
                ),
            ]
            for u in demo_users:
                session.add(u)
            print(f"Seeded {len(demo_users)} demo users")
    except Exception as exc:
        print(f"Warning: Could not seed demo users: {exc}")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown."""
    db.disconnect()
    print("Database disconnected")


# CORS middleware (configure for production)
import os as _os
_cors_origins = [
    "http://localhost:3000",  # React dev server
    "http://localhost:4000",  # Serve (fallback port)
    "http://localhost:5173",  # Vite dev server
    "https://phoenixguardian.netlify.app",  # Netlify production
]
# Allow custom CORS origin via env var
_extra_origin = _os.getenv("CORS_ORIGIN")
if _extra_origin:
    _cors_origins.append(_extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handlers
@app.exception_handler(PatientNotFoundError)
async def patient_not_found_handler(
    request: Request,  # pylint: disable=unused-argument
    exc: PatientNotFoundError,
) -> JSONResponse:
    """Handle patient not found errors."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "PatientNotFoundError",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(OrchestrationError)
async def orchestration_error_handler(
    request: Request,  # pylint: disable=unused-argument
    exc: OrchestrationError,
) -> JSONResponse:
    """Handle orchestration errors."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "OrchestrationError",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(SecurityException)
async def security_exception_handler(
    request: Request,  # pylint: disable=unused-argument
    exc: SecurityException,
) -> JSONResponse:
    """Handle security validation failures."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "SecurityException",
            "message": str(exc),
            "threat_type": str(exc.threat_type),
            "threat_level": str(exc.threat_level),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(
    request: Request,  # pylint: disable=unused-argument
    exc: ValueError,
) -> JSONResponse:
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "ValidationError",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# Include routers
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["health"],
)

app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["authentication"],
)

app.include_router(
    patients.router,
    prefix="/api/v1/patients",
    tags=["patients"],
)

app.include_router(
    encounters.router,
    prefix="/api/v1/encounters",
    tags=["encounters"],
)

app.include_router(
    agents.router,
    prefix="/api/v1",
    tags=["agents"],
)

app.include_router(
    transcription.router,
    prefix="/api/v1/transcription",
    tags=["transcription"],
)

app.include_router(
    pqc_routes.router,
    prefix="/api/v1",
    tags=["post-quantum-cryptography"],
)

app.include_router(
    learning_routes.router,
    prefix="/api/v1",
    tags=["bidirectional-learning"],
)

app.include_router(
    orchestration_routes.router,
    prefix="/api/v1",
    tags=["agent-orchestration"],
)

app.include_router(
    security_console_routes.router,
    prefix="/api/v1",
    tags=["security-console"],
)

app.include_router(
    treatment_shadow_routes.router,
    prefix="/api/v1/treatment-shadow",
    tags=["treatment-shadow"],
)

app.include_router(
    silent_voice_routes.router,
    prefix="/api/v1/silent-voice",
    tags=["silent-voice"],
)

app.include_router(
    zebra_hunter_routes.router,
    prefix="/api/v1/zebra-hunter",
    tags=["zebra-hunter"],
)

app.include_router(
    v5_dashboard_routes.router,
    prefix="/api/v1/v5",
    tags=["v5-dashboard"],
)


# Root endpoint
@app.get("/")
async def root() -> dict:
    """API root endpoint.

    Returns:
        API information and status
    """
    return {
        "name": "Phoenix Guardian API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
