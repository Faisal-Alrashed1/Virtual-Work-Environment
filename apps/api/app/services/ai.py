import json
from typing import Any

from openai import OpenAI
from app.core.config import settings


SYSTEMS = {
    "manager": "أنت مدير هندسي خبير. ناقش المتطلبات والقرارات والتسليم. لا تراجع تفاصيل جودة الكود بدل المرشد.",
    "mentor": "أنت مرشد تقني. ساعد المتعلم بتلميحات وشرح دون تنفيذ المهمة عنه، وبعد التسليم راجع الكود والمنطق والأمان.",
    "hr": "أنت مسؤول موارد بشرية. راقب التواصل والمهنية والاستقلالية وقدّم ملاحظات مدعومة بأدلة.",
    "career": """أنت مستشار مسار مهني عملي ومختصر. استنتج أكبر قدر ممكن من السيرة وسجل الحوار، ولا تكرر سؤالًا سبق أن أجاب عنه المستخدم. اسأل سؤالًا واحدًا فقط في كل رسالة وعند الضرورة فقط. تكفي لبداية المسار معرفة: الدور المستهدف، مستوى الخبرة، وهدف التدريب. متى توفرت هذه المعلومات، توقف عن طرح الأسئلة، لخّص الاستنتاج في نقاط قصيرة، واطلب من المستخدم الضغط على زر «ابدأ مساري الآن». لا تقدم خطة طويلة داخل المحادثة لأن النظام سينشئ المسار بعد التأكيد.""",
}


class AIService:
    def __init__(self): self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def _completion(self, instructions: str, prompt: str, json_mode: bool = False) -> str:
        """Use the Chat Completions API supported by the pinned OpenAI SDK."""
        if not self.client:
            return ""
        kwargs: dict[str, Any] = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def chat(self, agent: str, message: str, context: str = "") -> str:
        if not self.client:
            fallback = {
                "manager": "فهمت تحديثك. وضّح القرار الذي اتخذته، سبب اختياره، وكيف ستتحقق من استيفاء معايير المهمة.",
                "mentor": "لن أنفذ الحل عنك، لكن ابدأ بتقسيم المشكلة إلى مدخلات ومخرجات وحالات فشل. شاركني الجزء الذي توقفت عنده وسنراجعه معًا.",
                "hr": "سجلت طريقة تواصلك وتعاملك مع الملاحظات. سأضم الأدلة إلى تقرير نهاية الأسبوع.",
                "career": "أخبرني عن المشروع الذي استمتعت ببنائه، الدور الذي تستهدفه، وما المهارات التي ترغب في تطويرها. سأستخدم إجابتك لتخصيص المسار.",
            }
            return fallback.get(agent, "تم تسجيل رسالتك.")
        return self._completion(SYSTEMS[agent] + "\nالسياق:\n" + context, message)

    def structured(self, prompt: str, fallback: dict) -> dict:
        if not self.client: return fallback
        output = self._completion("أعد كائن JSON صالحًا فقط دون markdown.", prompt, json_mode=True)
        try: return json.loads(output)
        except (json.JSONDecodeError, TypeError): return fallback


ai = AIService()
