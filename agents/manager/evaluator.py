class ManagerTechnicalEvaluator:
    """Evaluates weekly technical progress based on Senior reports."""

    @staticmethod
    def evaluate_weekly_performance(technical_avg: float | None) -> dict:
        score = max(1, min(5, round(technical_avg or 3)))
        return {
            "technical_score": score,
            "summary": "تقييم تقني مبني على تقرير Senior ومراجعات المهام.",
        }


manager_evaluator = ManagerTechnicalEvaluator()
