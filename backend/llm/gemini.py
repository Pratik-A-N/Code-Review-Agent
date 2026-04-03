import os
import google.generativeai as genai
from llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment")
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self._model = genai.GenerativeModel(model_name)

    def generate(self, prompt: str) -> str:
        response = self._model.generate_content(prompt)
        return response.text
