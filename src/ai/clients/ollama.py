from doctest import debug

from ollama import Client
from src.ai import AIClient

class OllamaClient(AIClient):
    
    def __init__(self, host: str):
        if not host:
            raise ValueError("Ollama host is required.")
        self.client = Client(host=host)

    def chat(self, model: str, messages: list[dict[str, str]]) -> str:
        if not model:
            raise ValueError("Model is required.")
        if not messages:
            raise ValueError("messages cannot be empty")

        response = self.client.chat(
            model=model,
            messages=messages
        )

        content = response.message.content
        if content is None:
            raise ValueError("Invalid Ollama response: missing content field.")

        return str(content).strip()
