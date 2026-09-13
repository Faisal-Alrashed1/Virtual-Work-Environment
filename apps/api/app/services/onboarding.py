import json

from app.models.domain import CareerProfile


DIAGNOSTIC_QUESTIONS = [
    "هل تعرف أساسيات البرمجة مثل المتغيرات والشروط والدوال؟",
    "هل سبق أن كتبت برنامجًا بسيطًا بلغة Python بنفسك؟",
    "هل تعرف أساسيات الواجهة الأمامية مثل HTML وCSS وJavaScript؟",
    "هل تعرف ما هو الـBackend أو سبق أن بنيت API؟",
    "هل تعاملت مع قاعدة بيانات أو كتبت أوامر SQL؟",
    "هل استخدمت Git وGitHub لحفظ مشروع ورفع التعديلات؟",
    "هل تستطيع تتبع خطأ في الكود وكتابة اختبار بسيط؟",
    "هل سبق أن ربطت Frontend مع Backend عبر API بسيطة؟",
    "هل تستطيع تنظيم مشروع Web إلى ملفات ودوال صغيرة واضحة؟",
    "هل تعرف أساسيات حماية المفاتيح والبيانات والتحقق من المدخلات؟",
]


def diagnostic_state(profile: CareerProfile) -> dict:
    try:
        state = json.loads(profile.diagnostic_summary or "{}")
    except (json.JSONDecodeError, TypeError):
        state = {}
    answers = state.get("answers", [])
    state["answers"] = answers if isinstance(answers, list) else []
    return state


def answer_score(answer: str) -> int:
    normalized = answer.strip().lower()
    negative = ("لا", "ما أعرف", "ماعندي", "لم أجرب", "من الصفر", "0")
    positive = ("نعم", "اعرف", "أعرف", "جربت", "سبق", "عندي", "1")
    if normalized == "0" or any(token in normalized for token in negative):
        return 0
    if normalized == "1" or any(token in normalized for token in positive):
        return 1
    return 0
