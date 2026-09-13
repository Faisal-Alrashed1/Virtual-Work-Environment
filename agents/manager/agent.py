from app.services.ai import ai


class ManagerAgent:
    """Independent AgentExecutor persona for Manager."""

    def __init__(self):
        self.name = "manager"

    def execute(self, user_id: str, message: str, context: str = "") -> str:
        return ai.chat(self.name, message, context)


manager_agent = ManagerAgent()
