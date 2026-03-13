from functools import lru_cache

import numpy as np
from ollama import Client

from src.constants import OLLAMA_HOST
from src.ai import AIClient


class OllamaClient(AIClient):
    """Ollama implementation of chat and embedding APIs."""

    def __init__(self, host: str):
        """
        Create an Ollama client wrapper.

        Parameters
        ----------
        host : str
            Base URL of the running Ollama server.

        Returns
        -------
        None
            Initializes the underlying Ollama SDK client.
        """
        if not host:
            raise ValueError("Ollama host is required.")
        self.client = Client(host=host)

    def chat(self, model: str, messages: list[dict[str, str]]) -> str:
        """
        Send a chat request to Ollama.

        Parameters
        ----------
        model : str
            Ollama model name used for generation.
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
            response = self.client.chat(
                model=model,
                messages=messages
            )
            content = response.message.content
            if content is None:
                raise ValueError("Invalid Ollama response: missing content field.")

            return str(content).strip()

        except Exception as e:
            print(type(e), e)

    def embed(self, model: str, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings through Ollama.

        Parameters
        ----------
        model : str
            Ollama embedding model name.
        texts : list[str]
            Input texts to embed.

        Returns
        -------
        numpy.ndarray
            Embedding matrix with shape ``(len(texts), embedding_dim)``.
        """
        if not model:
            raise ValueError("Embedding model is required.")
        if not texts:
            raise ValueError("texts cannot be empty")

        response = self.client.embed(model=model, input=texts)
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings")
        if not embeddings:
            raise ValueError("Invalid Ollama embedding response: missing embeddings field.")

        return np.asarray(embeddings, dtype=np.float32)

@lru_cache(maxsize=1)
def get_ollama_client() -> OllamaClient:
    """
    Return a cached Ollama client instance.

    Returns
    -------
    OllamaClient
        Singleton-like cached client configured from app constants.
    """
    return OllamaClient(host=OLLAMA_HOST)
