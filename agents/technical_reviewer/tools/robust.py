from agents.shared_infra.robust_tool import robust_tool
from agents.technical_reviewer.tools import core

@robust_tool(fallback_reply="تعذر سحب كود GitHub حاليًا.")
def safe_fetch_github_submission(github_url: str, sha: str) -> dict:
    return core.fetch_github_submission(github_url, sha)

@robust_tool(fallback_reply="تعذر توليد المهمة اليومية حاليًا.")
def safe_generate_daily_task(day: int, difficulty: int) -> dict:
    return core.generate_daily_task(day, difficulty)
