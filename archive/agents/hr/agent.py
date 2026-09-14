from app.services.ai import ai


class HRAgent:
    """Independent AgentExecutor persona for HR."""

    def __init__(self):
        self.name = "hr"

    def execute(self, user_id: str, message: str, context: str = "") -> str:
        return ai.chat(self.name, message, context)


hr_agent = HRAgent()
