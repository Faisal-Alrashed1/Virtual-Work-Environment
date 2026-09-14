class DifficultyEngine:
    """Calculates adaptive difficulty scaling for upcoming sprint cycles."""

    @staticmethod
    def adjust_difficulty(current_difficulty: int, average_performance: float) -> int:
        if average_performance >= 4.0:
            return min(5, current_difficulty + 1)
        if average_performance < 2.5:
            return max(1, current_difficulty - 1)
        return current_difficulty


difficulty_engine = DifficultyEngine()
