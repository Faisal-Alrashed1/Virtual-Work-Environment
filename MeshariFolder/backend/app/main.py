from anthropic import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.graph.catalog import seed_agent_catalog
from app.agents.llm_client import LLMConfigError
from app.database import Base, SessionLocal, engine
from app.routers import agents, auth, meeting, onboarding, projects, tasks, users

app = FastAPI(title="Venv API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before demo/deploy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Friendly errors for agent/LLM failures ------------------------------
# Any endpoint that calls the LLM (assign-task, reply, review, meeting chat)
# can fail for reasons that aren't bugs: no API key, spent credit, rate
# limits, upstream hiccups. Without these handlers those surface as a raw
# 500 with a stack trace — confusing for a reviewer and useless to the
# frontend. Each handler returns a clean JSON body with a `detail` the UI
# already knows how to display (it reads `detail` off error responses).

@app.exception_handler(LLMConfigError)
async def _llm_config_error(request: Request, exc: LLMConfigError):
    # 503: the service is up, but the agent feature isn't configured.
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(AuthenticationError)
async def _llm_auth_error(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The AI service rejected the API key (invalid or expired). "
            "Check ANTHROPIC_API_KEY in backend/.env and restart the server."
        },
    )


@app.exception_handler(PermissionDeniedError)
async def _llm_permission_error(request: Request, exc: PermissionDeniedError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The AI service denied the request — this usually means the "
            "account is out of credit. Add credit at console.anthropic.com."
        },
    )


@app.exception_handler(RateLimitError)
async def _llm_rate_limit(request: Request, exc: RateLimitError):
    return JSONResponse(
        status_code=429,
        content={"detail": "The AI service is rate-limited right now — wait a moment and try again."},
    )


@app.exception_handler(APIConnectionError)
async def _llm_connection_error(request: Request, exc: APIConnectionError):
    return JSONResponse(
        status_code=502,
        content={"detail": "Couldn't reach the AI service. Check your connection and try again."},
    )


@app.exception_handler(APIStatusError)
async def _llm_status_error(request: Request, exc: APIStatusError):
    # Catch-all for any other non-2xx from the API (5xx upstream, etc). More
    # specific handlers above take precedence; this only catches the rest.
    return JSONResponse(
        status_code=502,
        content={"detail": "The AI service returned an unexpected error. Try again in a moment."},
    )


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(agents.router)
app.include_router(projects.router)
app.include_router(meeting.router)
app.include_router(onboarding.router)


@app.on_event("startup")
def on_startup():
    # Dev convenience: creates tables if they don't exist. Once the schema
    # stabilizes, switch to `alembic upgrade head` in the startup/deploy
    # script instead and drop this.
    Base.metadata.create_all(bind=engine)

    # Stage 2 — the optional-agent catalog (app/agents/graph/catalog.py).
    # Idempotent: safe to run on every restart.
    db = SessionLocal()
    try:
        seed_agent_catalog(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
