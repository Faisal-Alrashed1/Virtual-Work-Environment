"""
Seed data for the Stage 2 agent catalog — the optional agents a graduate
can add to their roster on top of the default three (Manager/Mentor/HR,
always included and not stored here). Call seed_agent_catalog(db) once at
app startup, the same spot Base.metadata.create_all runs (app/main.py).

Agreed with Meshari: this list is expected to grow over time — that's the
whole reason it's a table (AgentCatalog) instead of hardcoded logic.
"""
from sqlalchemy.orm import Session

from app.models import AgentCatalog, AgentType, TrackEnum

CATALOG: list[dict] = [
    {
        "id": "security_reviewer",
        "agent_type": AgentType.SECURITY_REVIEWER,
        "name": "Security reviewer",
        "description": (
            "Reviews submitted work for common vulnerabilities and secure-"
            "coding practices, alongside the Mentor's regular review."
        ),
        "suggested_for_tracks_json": [TrackEnum.CYBERSECURITY.value],
    },
    {
        "id": "data_reviewer",
        "agent_type": AgentType.DATA_REVIEWER,
        "name": "Data reviewer",
        "description": (
            "Reviews notebooks, pipelines, and model code for data "
            "quality, reproducibility, and evaluation methodology."
        ),
        "suggested_for_tracks_json": [TrackEnum.DATA_SCIENCE_AI.value],
    },
    {
        "id": "career_coach",
        "agent_type": AgentType.CAREER_COACH,
        "name": "Career coach",
        "description": (
            "Resume feedback and interview prep on top of the regular "
            "weekly work — useful across every track."
        ),
        "suggested_for_tracks_json": [t.value for t in TrackEnum],
    },
    {
        "id": "devops",
        "agent_type": AgentType.DEVOPS,
        "name": "DevOps",
        "description": (
            "Reviews CI/CD, deployment, and infrastructure-as-code work "
            "alongside the Mentor's regular review."
        ),
        "suggested_for_tracks_json": [
            TrackEnum.CLOUD_DEVOPS.value,
            TrackEnum.NETWORKS_INFRASTRUCTURE.value,
        ],
    },
]


def seed_agent_catalog(db: Session) -> None:
    """Upserts CATALOG into agent_catalog. Safe to call on every startup —
    rows that already exist (by id) are left untouched, so an admin edit
    to a row's description/track suggestions isn't clobbered on restart."""
    existing_ids = {row.id for row in db.query(AgentCatalog.id).all()}
    for entry in CATALOG:
        if entry["id"] in existing_ids:
            continue
        db.add(AgentCatalog(**entry))
    db.commit()


def catalog_as_dicts(db: Session) -> list[dict]:
    """What onboarding_graph.py's suggest_agents node reads — plain dicts
    so the graph module itself never needs a DB session."""
    return [
        {"id": row.id, "name": row.name, "description": row.description}
        for row in db.query(AgentCatalog).all()
    ]
