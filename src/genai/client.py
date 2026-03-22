
from abc import abstractmethod

import numpy as np

from src.genai.chat_response import ChatResponse


class AIClient:
    """
    Interface for provider-specific chat and embedding clients.
    """

    def __init__(self, **kwargs):
        """
        Initialize a provider client.

        Parameters
        ----------
        **kwargs
            Provider-specific initialization parameters.

        Returns
        -------
        None
            Subclasses must implement their own initializer.
        """
        raise NotImplementedError("This class should be subclassed and initialized with the appropriate parameters.")

    @abstractmethod
    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """
        Generate a chat completion.

        Parameters
        ----------
        model : str
            Chat model identifier.
        messages : list[dict]
            Conversation messages in role/content format.
        tools : list[dict] | None
            Optional MCP tool definitions (name, description, input_schema).

        Returns
        -------
        ChatResponse
            Structured response with optional tool calls.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def embed(self, model: str, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings for a batch of texts.

        Parameters
        ----------
        model : str
            Embedding model identifier.
        texts : list[str]
            Input strings to embed.

        Returns
        -------
        numpy.ndarray
            Two-dimensional embedding matrix with one row per input text.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
