from datetime import datetime, timedelta, timezone
from enum import Enum


class CycleStage(str, Enum):
    IDLE = "idle"
    KICKOFF = "kickoff"
    ACTIVE = "active"
    WEEK_COMPLETE = "week_complete"


class WeeklyCycleEngine:
    """State machine managing weekly 5-task sprint cycles."""

    @staticmethod
    def calculate_cycle_bounds(days: int = 7) -> tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        ends_at = now + timedelta(days=days)
        return now, ends_at

    @staticmethod
    def is_cycle_completed(completed_tasks_count: int, ends_at: datetime) -> bool:
        now = datetime.now(ends_at.tzinfo) if ends_at.tzinfo else datetime.now()
        return completed_tasks_count >= 5 or ends_at <= now


weekly_cycle_engine = WeeklyCycleEngine()
