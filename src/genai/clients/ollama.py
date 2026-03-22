import json
from functools import lru_cache

import numpy as np
from ollama import Client

from src.constants import OLLAMA_HOST
from src.genai import AIClient
from src.genai.chat_response import ChatResponse, ToolCall


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

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """
        Send a chat request to Ollama.

        Parameters
        ----------
        model : str
            Ollama model name used for generation.
        messages : list[dict]
            Message list in role/content format.
        tools : list[dict] | None
            Optional MCP tool definitions.

        Returns
        -------
        ChatResponse
            Structured response with optional tool calls.
        """
        if not model:
            raise ValueError("Model is required.")
        if not messages:
            raise ValueError("messages cannot be empty")

        ollama_tools = None
        if tools:
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ]

        try:
            response = self.client.chat(
                model=model,
                messages=messages,
                tools=ollama_tools,
            )

            content = response.message.content or None

            tool_calls: list[ToolCall] = []
            if response.message.tool_calls:
                for tc in response.message.tool_calls:
                    args = tc.function.arguments
                    tool_calls.append(
                        ToolCall(
                            id=getattr(tc, "id", f"call_{id(tc)}"),
                            name=tc.function.name,
                            arguments=args if isinstance(args, dict) else json.loads(args),
                        )
                    )

            return ChatResponse(content=content, tool_calls=tool_calls)

        except Exception as e:
            print(type(e), e)
            return ChatResponse(content=None)

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
