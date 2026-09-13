import json
from typing import Any

from openai import OpenAI, OpenAIError
from app.core.config import settings


SYSTEMS = {
    "manager": """أنت Manager هندسي خبير في شركة افتراضية. عرّف الـJunior بالمشروع والمتطلبات والبنية والنتيجة المتوقعة، ثم قيّم الأداء التقني أسبوعيًا اعتمادًا على تقرير Senior والأدلة فقط. لا تنفذ عمل Senior ولا تخترع معلومات. اكتب بالعربية الواضحة وباختصار، واسأل سؤالًا واحدًا عند الحاجة.""",
    "senior": """أنت Senior Developer والمشرف المباشر على Junior. قسّم المشروع الكبير إلى مهمة واحدة صغيرة في كل مرة. أثناء التنفيذ قدّم تلميحًا متدرجًا أو شرحًا، ولا تعط الحل الكامل. اقبل الحل غير المكتمل ووضّح الخطوة التالية. بعد التسليم راجع الـcommit أو Pull Request من حيث الصحة والبنية والوضوح والاختبارات والأمان. اربط كل ملاحظة بدليل، وميّز بين المؤكد والاقتراح. اكتب خطوات قصيرة وواضحة.""",
    "hr": """أنت HR في شركة افتراضية. قيّم الالتزام بالمواعيد والاستمرارية والتواصل والانضباط والاستجابة للملاحظات والسلوك المهني. اعتمد على سجل واقعي وتقارير Senior وManager فقط، ولا تصدر حكمًا تقنيًا أو قرار توظيف. إذا لم يوجد دليل كافٍ فقل ذلك بوضوح.""",
    "career": """أنت مستشار مسار مهني عملي ومختصر. استنتج أكبر قدر ممكن من السيرة وسجل الحوار، ولا تكرر سؤالًا سبق أن أجاب عنه المستخدم. اسأل سؤالًا واحدًا فقط في كل رسالة وعند الضرورة فقط. تكفي لبداية المسار معرفة: الدور المستهدف، مستوى الخبرة، وهدف التدريب. متى توفرت هذه المعلومات، توقف عن طرح الأسئلة، لخّص الاستنتاج في نقاط قصيرة، واطلب من المستخدم الضغط على زر «ابدأ مساري الآن». لا تقدم خطة طويلة داخل المحادثة لأن النظام سينشئ المسار بعد التأكيد.""",
}


class AIService:
    def __init__(self):
        self.providers: list[tuple[OpenAI, str]] = []
        if settings.deepseek_api_key:
            self.providers.append((OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, timeout=60), settings.deepseek_model))

    def _completion(self, instructions: str, prompt: str, json_mode: bool = False) -> str:
        """Use the Chat Completions API supported by the pinned OpenAI SDK."""
        for client, model in self.providers:
            kwargs: dict[str, Any] = {"model": model, "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}]}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                response = client.chat.completions.create(**kwargs)
                if response.choices[0].message.content:
                    return response.choices[0].message.content
            except OpenAIError:
                continue
        return ""

    def chat(self, agent: str, message: str, context: str = "") -> str:
        fallback = {
            "manager": "فهمت تحديثك. وضّح القرار الذي اتخذته، سبب اختياره، وكيف ستتحقق من استيفاء معايير المهمة.",
            "senior": "لن أنفذ الحل عنك، لكن ابدأ بتقسيم المشكلة إلى مدخلات ومخرجات وحالات فشل. شاركني الجزء الذي توقفت عنده وسنراجعه معًا.",
            "hr": "سجلت طريقة تواصلك وتعاملك مع الملاحظات. سأضم الأدلة إلى تقرير نهاية الأسبوع.",
            "career": "أخبرني عن المشروع الذي استمتعت ببنائه، الدور الذي تستهدفه، وما المهارات التي ترغب في تطويرها. سأستخدم إجابتك لتخصيص المسار.",
        }.get(agent, "تم تسجيل رسالتك.")
        if not self.providers:
            return fallback
        response = self._completion(
            SYSTEMS[agent]
            + "\nقواعد الإجابة: أجب مباشرة، لا تكرر كلام المستخدم، لا تدّع الاطلاع على ملف غير موجود في السياق، واجعل الإجراء التالي واضحًا."
            + "\nالسياق الموثوق:\n"
            + context,
            message,
        )
        return response or fallback

    def structured(self, prompt: str, fallback: dict) -> dict:
        if not self.providers: return fallback
        output = self._completion("أعد كائن JSON صالحًا فقط دون markdown.", prompt, json_mode=True)
        try: return json.loads(output)
        except (json.JSONDecodeError, TypeError): return fallback


ai = AIService()
