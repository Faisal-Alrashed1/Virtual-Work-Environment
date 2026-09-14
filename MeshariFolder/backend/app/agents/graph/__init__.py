"""
Stage 2 agent orchestration, built on LangGraph instead of the plain
custom router Stage 1 used (app/agents/orchestrator.py, weekly_cycle.py —
both untouched, still driving the existing endpoints).

This package is additive: nothing here is wired into the app yet except
the onboarding graph. See docs/STAGE2_ONBOARDING_FLOW.md for the design
and what's still open (the router endpoints that drive this from the
frontend, and porting weekly_cycle.py's state machine to a StateGraph
with the ask_agent collaboration tool).
"""
