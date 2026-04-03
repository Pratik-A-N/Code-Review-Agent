import os
from llm.base import BaseLLMProvider


def get_provider() -> BaseLLMProvider:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        from llm.gemini import GeminiProvider
        return GeminiProvider()
    if provider == "groq":
        from llm.groq import GroqProvider
        return GroqProvider()
    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Supported: gemini, groq"
    )


# Singleton — initialized once at import time
llm = get_provider()
