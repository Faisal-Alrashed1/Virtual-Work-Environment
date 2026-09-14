from app.services.ai import ai


class CVExtractor:
    """Parses CV text and extracts baseline technical profile."""

    @staticmethod
    def extract_baseline(text: str) -> dict:
        fallback = {
            "skills": [x for x in ["React", "Python", "FastAPI", "Git"] if x.lower() in text.lower()] or ["Web Development"],
            "projects": [],
            "experience_level": "junior",
            "strengths": ["التعلم العملي"],
            "gaps": ["اختبار الأنظمة", "تكاملات AI الآمنة"],
        }
        return ai.structured("استخرج ملف مهني JSON من السيرة التالية: " + text[:12000], fallback)


cv_extractor = CVExtractor()
