from __future__ import annotations

from datetime import date
from logging import getLogger

from src.agents.character_loader import CharacterData
from src.genai import AIModelFacade
from src.mcp import get_mcp_manager
from src.constants import (
    AI_CLIENT_MODEL,
    AI_CLIENT_PROVIDER,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER
)
from src.rag import FaissDocumentStore

logger = getLogger(__name__)


class Agent:

    def __init__(self, character: CharacterData, rules: str = "") -> None:
        """
        Initialize an agent with chat model, document store, and MCP tools.
        """

        self.name = character.name
        self.emoji = character.emoji
        self.color = character.color
        self.hi_message = character.hi_message
        self.personality = character.personality
        self.rules = rules

        self.history = self._load_recent_conversations()
        self.system_prompt = self._create_system_prompt()
        self.document_store = FaissDocumentStore(
            embedding_model=EMBEDDING_MODEL,
            embedding_provider=EMBEDDING_PROVIDER
        )
        self.response_times: list[float] = []
        self.mcp_manager = get_mcp_manager()
        self.ai_model = AIModelFacade(
            provider=AI_CLIENT_PROVIDER,
            model=AI_CLIENT_MODEL,
            system_prompt=self.system_prompt,
            history=self.history
        )


    def _create_system_prompt(
        self
    ) -> str:
        """
        Build the agent-specific system prompt from personality traits.

        Parameters
        ----------
        None
            This method does not receive arguments besides ``self``.

        Returns
        -------
        str
            Prompt text injected as the first system message.
        """

        parts = [
            f"Today's date is {date.today().isoformat()}.",
            f"You are the following character: \n{self.personality}",
        ]
        if self.rules:
            parts.append(f"Guidelines: \n{self.rules}")
        return "\n\n".join(parts)


    def get_start_message(self) -> str:
        """
        Return the greeting message and register it in chat history.

        Parameters
        ----------
        None
            This method does not receive arguments besides ``self``.

        Returns
        -------
        str
            Character-specific greeting text.
        """

        self.ai_model.add_to_history("assistant", self.hi_message)
        return self.hi_message


    def get_history(self) -> list[dict[str, str]]:
        """
        Get current in-memory conversation history.

        Returns
        -------
        list[dict[str, str]]
            Messages currently tracked by the AI facade.
        """
        return self.ai_model.history


    def get_context(self) -> list[dict[str, str | int]]:
        """
        Get a debug-friendly view of indexed retrieval chunks.

        Returns
        -------
        list[dict[str, str | int]]
            Recent chunk metadata and previews.
        """
        return self.document_store.get_context_view()


    def index_document(self, path: str, text: str) -> tuple[str, int, dict[str, int]]:
        """
        Index already-extracted text into the document store and register the
        operation in conversation history.

        Parameters
        ----------
        path : str
            Original file path (used as metadata, not read here).
        text : str
            Pre-extracted textual content to index.

        Returns
        -------
        tuple[str, int, dict[str, int]]
            Tuple ``(doc_id, chunks, stats)``.
        """

        doc_id, chunks = self.document_store.add_document(path=path, content=text)
        self.ai_model.add_to_history(
            "system",
            f"[context-loaded] source={path} chunks={chunks}",
        )
        return doc_id, chunks, self.document_store.stats()


    def _build_retrieval_context(self, user_message: str) -> str | None:
        """
        Get content from document store related to user_message

        Parameters
        ----------
        user_message : str
            User query used for retrieval.

        Returns
        -------
        str | None
            Rendered retrieval context, or ``None`` when no chunk matches.
        """

        retrieved = self.document_store.search(
            query=user_message,
            k=3,
            min_score=-1.0,
        )

        if not retrieved:
            return None

        sections = []
        for item in retrieved:
            sections.append(
                f"[source: {item.path}#chunk-{item.chunk_id} | score: {item.score:.3f}]\n{item.text}"
            )

        return (
            "Use the following document snippets only if relevant to answer the user.\n\n"
            + "\n\n".join(sections)
        )


    def _on_tool_call(self, tool_name: str, arguments: dict) -> None:
        """Display a brief indicator when the model invokes a tool."""
        from src.display import console
        args_summary = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        console.print(f"  [dim]🔧 {tool_name}({args_summary})[/dim]")


    def message(self, user_message: str, skill_instructions: str | None = None) -> str:
        """
        Generate a chat response to the provided user message.

        Parameters
        ----------
        user_message : str
            The message from the user to which the agent should respond.
        skill_instructions : str | None
            Optional instructions from an LLM skill, injected for this turn only.

        Returns
        -------
        str
            The response generated by the AI model.
        """

        retrieval_context = self._build_retrieval_context(user_message)
        return self.ai_model.generate_response(
            user_message,
            retrieval_context,
            mcp_manager=self.mcp_manager,
            on_tool_call=self._on_tool_call,
            skill_instructions=skill_instructions,
        )


    def close(self) -> None:
        """Release resources held by the agent."""
        pass


    def _load_recent_conversations(self) -> list[dict[str, str]]:
        """
        Load previous conversations from persistence.

        Returns
        -------
        list[dict[str, str]]
            Previously stored messages. Current implementation returns an
            empty list.
        """

        return []
