import json
from app.models.domain import CareerProfile

DIAGNOSTIC_QUESTIONS = [
    "هل كتبت كود البرمجة بنفسك وقمت بتشغيله على جهازك من قبل؟",
    "هل تستطيع بناء صفحة HTML تحتوي نموذجًا (Form) وتنسيقها بـ CSS؟",
    "هل استدعيت API باستخدام JavaScript وجلبت بيانات حقيقية من سيرفر؟",
    "هل بنيت سيرفرًا باستخدام Node.js أو Python أو Java يقبل طلبات HTTP؟",
    "هل استخدمت قاعدة بيانات حقيقية وقمت بإنشاء جدول وكتابة استعلام SQL أو ORM؟",
    "هل تجيد التعامل مع Git مثل clone وcommit وpush وإنشاء فروع (branches)؟",
    "هل كتبت اختبارات وحدة (Unit Tests) للتحقق من عمل الدوال الأساسية؟",
    "هل تعرف كيف تحمي الأسرار ومفاتيح الـ API وتتحقق من دخل المستخدم لمنع الثغرات البسيطة؟",
    "هل استخدمت Docker أو قمت برفع مشروع يعمل على بيئة استضافة سحابية؟",
    "هل تناقش مشاكلك البرمجية وتطلب مساعدة مستندة إلى سجل الأخطاء (Logs) والرموز الدقيقة؟",
]


def diagnostic_state(profile: CareerProfile) -> dict:
    if not profile.diagnostic_summary:
        return {"answers": []}
    try:
        return json.loads(profile.diagnostic_summary)
    except json.JSONDecodeError:
        return {"answers": []}


def answer_score(answer: str) -> int:
    text = answer.strip().lower()
    if any(word in text for word in ["نعم", "yes", "أعرف", "عملت", "نعم أستطيع"]):
        return 1
    return 0
