class HRBehaviorEvaluator:
    """Evaluates behavioral engagement and communication patterns."""

    @staticmethod
    def evaluate_behavior(user_messages_count: int, completed_tasks_count: int) -> dict:
        score = 4 if user_messages_count >= completed_tasks_count else 3
        return {
            "behavior_score": score,
            "summary": "تقييم سلوكي مبني على الالتزام والتواصل والاستجابة للملاحظات.",
        }


hr_behavior_evaluator = HRBehaviorEvaluator()
