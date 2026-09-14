from agents.shared_infra.robust_tool import robust_tool
from agents.hr.tools import core

@robust_tool(fallback_reply="تعذر جلب سجل الحضور حاليًا.")
def safe_fetch_attendance_log(user_id: str) -> dict:
    return core.fetch_attendance_log(user_id)

@robust_tool(fallback_reply="تعذر تسجيل الدرجة السلوكية حاليًا.")
def safe_record_behavior_score(user_id: str, score: int) -> bool:
    return core.record_behavior_score(user_id, score)
