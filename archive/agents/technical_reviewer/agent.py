from app.services.ai import ai


class TechnicalReviewerAgent:
    """Independent AgentExecutor persona for Senior Technical Reviewer."""

    def __init__(self):
        self.name = "senior"

    def execute(self, user_id: str, message: str, context: str = "") -> str:
        return ai.chat(self.name, message, context)


technical_reviewer_agent = TechnicalReviewerAgent()
