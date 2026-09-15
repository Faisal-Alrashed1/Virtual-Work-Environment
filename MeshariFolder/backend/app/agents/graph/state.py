"""State schema for the Stage 2 onboarding graph (onboarding_graph.py)."""
from typing import Optional, TypedDict


class QAItem(TypedDict):
    question: str
    answer: Optional[str]  # None until answered; stays None if skipped


class OnboardingState(TypedDict, total=False):
    user_id: str
    cv_raw_text: str
    intro_text: Optional[str]  # free text the graduate adds themselves

    questions: list[QAItem]

    suggested_track: str  # TrackEnum value, CV-inferred
    track_reasoning: str  # shown to the graduate alongside the suggestion
    approved_track: str  # set once the graduate confirms or overrides

    # Catalog rows (as plain dicts — id/name/description), supplied by the
    # caller when starting the graph so this module stays DB-session-free.
    catalog: list[dict]
    suggested_agent_ids: list[str]
    approved_agent_ids: list[str]

    stage: str  # mirrors models.OnboardingStage
