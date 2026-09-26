from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.graph.catalog import seed_agent_catalog
from app.agents.llm_client import ALL_PROVIDERS_FAILED, LLMConfigError
from app.database import SessionLocal, engine
from app.language import LanguageMiddleware
from app.migrations import upgrade_database
from app.routers import agents, auth, company, invitations, meeting, onboarding, projects, tasks, users

app = FastAPI(title="Venv API", version="0.1.0")

# Reads X-Venv-Language so every agent call answers in the graduate's language
# (app/language.py, docs/AGENT_LANGUAGE.md).
app.add_middleware(LanguageMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMConfigError)
async def _llm_config_error(request: Request, exc: LLMConfigError):
    # No provider in LLM_PROVIDER_PRIORITY has any API key set at all.
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def _all_providers_failed(request: Request, exc: RuntimeError):
    # Every provider in the priority chain was tried and failed — the
    # message is built in llm_client.py / onboarding_graph.py and always
    # starts with ALL_PROVIDERS_FAILED. Any other RuntimeError is a real
    # bug, not a provider outage, so it falls through to FastAPI's default
    # 500 handling instead of being reported as a clean 503.
    if str(exc).startswith(ALL_PROVIDERS_FAILED):
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    raise exc


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(agents.router)
app.include_router(projects.router)
app.include_router(meeting.router)
app.include_router(onboarding.router)
app.include_router(company.router)
app.include_router(invitations.router)


@app.on_event("startup")
def on_startup():
    # Alembic, not create_all: create_all never adds a column to a table that
    # already exists. See app/migrations.py and docs/MIGRATIONS.md.
    upgrade_database(engine)
    db = SessionLocal()
    try:
        seed_agent_catalog(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
