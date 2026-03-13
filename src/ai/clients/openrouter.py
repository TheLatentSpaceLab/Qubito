import requests
import json
from functools import lru_cache

from src.constants import OPENROUTER_API_KEY
from src.ai.client import AIClient


class OpenRouterClient(AIClient):
    """OpenRouter implementation of chat API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def chat(self, model: str, messages: list[dict[str, str]]) -> str:
        """
        Send a chat request to OpenRouter.

        Parameters
        ----------
        model : str
            OpenRouter model name used for generation.
        messages : list[dict[str, str]]
            Message list in role/content format.

        Returns
        -------
        str
            Assistant text response.
        """
        if not model:
            raise ValueError("Model is required.")
        if not messages:
            raise ValueError("messages cannot be empty")

        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "model": model,
                    "messages": messages,
                })
            )

            response = response.json()
            return response['choices'][0]['message']['content']

        except Exception as e:
            print(type(e), e)


@lru_cache(maxsize=1)
def get_openrouter_client() -> OpenRouterClient:
    """
    Return a cached OpenRouter client instance.

    Returns
    -------
    OpenRouterClient
        Singleton-like cached client configured from app constants.
    """
    return OpenRouterClient(api_key=OPENROUTER_API_KEY)
