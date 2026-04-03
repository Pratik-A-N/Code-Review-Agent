import os
from groq import Groq
from llm.base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in environment")
        self._client = Groq(api_key=api_key)
        self._model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
