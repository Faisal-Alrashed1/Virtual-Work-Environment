from app.services.ai import ai


class CodeReviewerEngine:
    """Analyzes submitted code and formulates detailed review feedback."""

    @staticmethod
    def review_submission(evidence: dict) -> dict:
        fallback = {
            "senior": {
                "outcome": "improve",
                "scores": {"تنفيذ المطلوب": 3, "جودة الكود": 3, "المنطق": 3, "الأمان والاختبارات": 3},
                "analysis": "تعذر الحصول على تحليل موثوق، ناقش Senior وتحقق من المعايير.",
                "improvements": ["شغّل الكود وتحقق من النتيجة"],
                "rationale": "يلزم تحقق إضافي.",
                "confidence": 1,
            }
        }
        return ai.structured(f"أنت Senior المشرف المباشر. حلل المحاولة مقارنة بكل معيار نجاح. الأدلة: {evidence}", fallback)


code_reviewer_engine = CodeReviewerEngine()
