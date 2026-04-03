from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Send a prompt and return the response text."""
        ...
