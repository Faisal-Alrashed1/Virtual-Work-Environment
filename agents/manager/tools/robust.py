from agents.shared_infra.robust_tool import robust_tool
from agents.manager.tools import core

@robust_tool(fallback_reply="تعذر جلب التقرير الأسبوعي حاليًا.")
def safe_fetch_weekly_report(cycle_id: str) -> dict:
    return core.fetch_weekly_report(cycle_id)

@robust_tool(fallback_reply="تعذر تحديث أهداف المشروع حاليًا.")
def safe_update_project_goals(user_id: str, new_goals: list[str]) -> bool:
    return core.update_project_goals(user_id, new_goals)
