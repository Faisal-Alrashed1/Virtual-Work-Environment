"""
Makes onboarding resumable from the database alone.

The onboarding graph (onboarding_graph.py) pauses three times waiting for the
graduate. Its checkpointer is in-memory and per-process, so on its own a
closed tab is fine but a server restart — or a second API worker, or a deploy
— loses the thread, and the graduate is stranded on a wizard step the server
no longer remembers. Rather than trust that fragile copy, the database is the
source of truth: every pause's output is saved on the User row (questions,
suggested track + reasoning, suggested agents — see routers/onboarding.py),
and this module rebuilds a graph thread from those columns whenever it isn't
already sitting at the right pause.

Rebuilding costs **zero LLM calls**: LangGraph's update_state(..., as_node=X)
writes state as though node X had just finished, which leaves the graph
paused right before the next human step. The graduate's next answer then
resumes it normally. (Verified against a fresh graph with an empty
checkpointer — see smoke_test_stage2_onboarding_resume.py.)

Works with any checkpointer, so a future persistent one can be dropped in
without touching this.
"""
from app.models import OnboardingStage, User

# stage -> (node that already ran, node the graph pauses in)
PAUSE_POINTS = {
    OnboardingStage.QA: ("generate_questions", "await_answers"),
    OnboardingStage.TRACK: ("suggest_track", "await_track_approval"),
    OnboardingStage.AGENTS: ("suggest_agents", "await_agent_approval"),
}


class NotResumable(Exception):
    """The database doesn't hold enough to rebuild this stage — a graduate
    who was mid-wizard before resume state existed. They start over."""


def thread_config(user: User) -> dict:
    return {"configurable": {"thread_id": user.id}}


def drop_thread(graph, user: User) -> None:
    """Forget any in-memory state for this graduate (a fresh CV upload or a
    reset must start a clean run, not continue a stale one)."""
    graph.checkpointer.delete_thread(user.id)


def _required_data_present(user: User, stage: OnboardingStage) -> bool:
    if stage == OnboardingStage.QA:
        return bool(user.cv_raw_text) and bool(user.onboarding_qa_json)
    if stage == OnboardingStage.TRACK:
        return user.suggested_track is not None
    if stage == OnboardingStage.AGENTS:
        # A graduate who was mid-wizard before suggestions were saved has
        # none stored — they can still resume and simply pick from the full
        # catalog, so only the confirmed track is required.
        return user.track_confirmed
    return False


def can_resume(user: User, stage: OnboardingStage) -> bool:
    """Whether the database has everything needed to rebuild `stage`."""
    return stage in PAUSE_POINTS and _required_data_present(user, stage)


def graph_values_for(user: User, catalog: list[dict]) -> dict:
    """The graph's state, reconstructed from the User row."""
    values: dict = {
        "user_id": user.id,
        "cv_raw_text": user.cv_raw_text or "",
        "catalog": catalog,
        "intro_text": user.intro_text,
        "questions": list(user.onboarding_qa_json or []),
    }
    if user.suggested_track is not None:
        values["suggested_track"] = user.suggested_track.value
        values["track_reasoning"] = user.suggested_track_reasoning or ""
    if user.track_confirmed:
        values["approved_track"] = user.track.value
    values["suggested_agent_ids"] = list(user.suggested_agent_ids_json or [])
    return values


def ensure_paused_at(graph, user: User, catalog: list[dict], stage: OnboardingStage) -> bool:
    """Guarantee the graduate's graph thread is paused at `stage`'s human
    step, rebuilding it from the database if it isn't (a restart, a different
    worker, a stale thread). Returns True if it had to rebuild.

    Raises NotResumable if a rebuild is needed but the database lacks the
    data — only the Q&A step can hit this, and only for graduates who were
    already mid-wizard before the generated questions were being saved."""
    ran_node, pause_node = PAUSE_POINTS[stage]
    config = thread_config(user)
    if graph.get_state(config).next == (pause_node,):
        return False  # the live thread is already exactly where it should be
    if not _required_data_present(user, stage):
        raise NotResumable(stage.value)
    graph.update_state(config, graph_values_for(user, catalog), as_node=ran_node)
    return True
