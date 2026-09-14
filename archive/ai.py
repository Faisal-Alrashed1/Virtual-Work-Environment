import json
from typing import Any

from openai import OpenAI, OpenAIError
from app.core.config import settings
from app.services.agents import FALLBACK_REPLIES, SYSTEMS


class AIService:
    def __init__(self):
        self.providers: list[tuple[OpenAI, str]] = []
        if settings.deepseek_api_key:
            self.providers.append((OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, timeout=60), settings.deepseek_model))

    def _completion(self, instructions: str, prompt: str, json_mode: bool = False) -> str:
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
        fallback = FALLBACK_REPLIES.get(agent, "تم تسجيل رسالتك.")
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
        if not self.providers:
            return fallback
        output = self._completion("أعد كائن JSON صالحًا فقط دون markdown.", prompt, json_mode=True)
        try:
            return json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return fallback


ai = AIService()
