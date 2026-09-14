"""
LangChain Client Provider & Setup
"""
from typing import Any


class LangChainSetup:

    @staticmethod
    def get_llm(temperature: float = 0.2) -> Any:
        # Returns model instance configured for DeepSeek / OpenAI
        return None


langchain_setup = LangChainSetup()
