"""
Saudi workweek (Sunday-Thursday) date math for the weekly-cycle flow. Used
to turn "5 workdays starting now" into concrete deadlines for a Week and
its subtasks — see docs/STAGE1_PRODUCT_FLOW.md and Week/Task in models.py.

Friday and Saturday are the weekend here, not the Western Saturday/Sunday —
this matters because Venv is for Saudi graduates (Project-Summary.md).
"""
from datetime import datetime, timedelta

# Python's date.weekday(): Monday=0 ... Sunday=6. Saudi weekend is Fri/Sat.
_WEEKEND = {4, 5}


def is_workday(d: datetime) -> bool:
    return d.weekday() not in _WEEKEND


def next_workday(d: datetime) -> datetime:
    """d itself if it's already a workday, otherwise the soonest one after."""
    while not is_workday(d):
        d += timedelta(days=1)
    return d


def n_workdays_from(start: datetime, n: int) -> list[datetime]:
    """The next n workdays at or after start, each at end of day
    (23:59:59) — used as per-subtask deadlines across a Week, with the
    last one doubling as the Week's target_end_at."""
    days: list[datetime] = []
    d = next_workday(start)
    while len(days) < n:
        days.append(d.replace(hour=23, minute=59, second=59, microsecond=0))
        d = next_workday(d + timedelta(days=1))
    return days
