from __future__ import annotations

from datetime import date
from logging import getLogger
from typing import TYPE_CHECKING

from src.agents.builtin_tools import ALL_TOOLS, make_document_search
from src.agents.character_loader import CharacterData
from src.genai import AIModelFacade
from src.mcp import init_mcp_manager
from src.constants import (
    AI_CLIENT_MODEL,
    AI_CLIENT_PROVIDER,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
)
from src.rag import FaissDocumentStore

if TYPE_CHECKING:
    from src.persistence.conversation_db import ConversationDB

logger = getLogger(__name__)


class Agent:

    def __init__(
        self,
        character: CharacterData,
        rules: str = "",
        mcp_config_paths: list[object] | None = None,
        session_id: str | None = None,
        db: ConversationDB | None = None,
        rag_namespace: str | None = None,
    ) -> None:
        """Initialize an agent with chat model, document store, and MCP tools."""
        self.name = character.name
        self.emoji = character.emoji
        self.color = character.color
        self.hi_message = character.hi_message
        self.personality = character.personality
        self.bye_message = character.bye_message
        self.thinking = character.thinking
        self.rules = rules
        self._session_id = session_id
        self._db = db

        self.history = self._load_recent_conversations()
        self.system_prompt = self._create_system_prompt()
        self.document_store = FaissDocumentStore(
            embedding_model=EMBEDDING_MODEL,
            embedding_provider=EMBEDDING_PROVIDER,
            namespace=rag_namespace,
        )
        self.response_times: list[float] = []
        self.on_tool_call = self._default_on_tool_call
        self.mcp_manager = init_mcp_manager(config_paths=mcp_config_paths)
        self.ai_model = AIModelFacade(
            provider=AI_CLIENT_PROVIDER,
            model=AI_CLIENT_MODEL,
            system_prompt=self.system_prompt,
            history=self.history,
        )
        self._register_builtin_tools()


    def _register_builtin_tools(self) -> None:
        """Register default virtual tools available to every agent."""
        self.ai_model.register_tool(make_document_search(self.document_store))
        for tool in ALL_TOOLS:
            self.ai_model.register_tool(tool)


    def _create_system_prompt(self) -> str:
        parts = [
            f"Today's date is {date.today().isoformat()}.",
            f"You are the following character: \n{self.personality}",
        ]
        if self.rules:
            parts.append(f"Guidelines: \n{self.rules}")
        return "\n\n".join(parts)


    def get_start_message(self) -> str:
        """Return the greeting message and register it in chat history."""
        self.ai_model.add_to_history("assistant", self.hi_message)
        return self.hi_message

    def get_history(self) -> list[dict[str, str]]:
        return self.ai_model.history

    def get_context(self) -> list[dict[str, str | int]]:
        return self.document_store.get_context_view()

    def index_document(self, path: str, text: str) -> tuple[str, int, dict[str, int]]:
        """Index text into the document store."""
        doc_id, chunks = self.document_store.add_document(path=path, content=text)
        self.ai_model.add_to_history(
            "system",
            f"[context-loaded] source={path} chunks={chunks} Text='\n {text}'",
        )
        return doc_id, chunks, self.document_store.stats()

    def message(self, user_message: str, skill_instructions: str | None = None) -> str:
        """Generate a chat response to the provided user message."""
        return self.ai_model.generate_response(
            user_message,
            mcp_manager=self.mcp_manager,
            on_tool_call=self.on_tool_call,
            skill_instructions=skill_instructions,
        )

    def close(self) -> None:
        """Release resources held by the agent."""
        pass


    _CONFIRM_TOOLS = {"read_file", "create_file", "edit_file", "delete_file"}

    def _default_on_tool_call(self, tool_name: str, arguments: dict) -> bool:
        """Display tool info and ask for confirmation on file operations."""
        from src.display import console
        args_summary = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        console.print(f"  [dim]🔧 {tool_name}({args_summary})[/dim]")
        if tool_name not in self._CONFIRM_TOOLS:
            return True
        try:
            answer = console.input(
                "  [bold yellow]¿Permitir? (s/n): [/bold yellow]"
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in ("s", "si", "sí", "y", "yes")


    def _load_recent_conversations(self) -> list[dict[str, str]]:
        if self._db and self._session_id:
            try:
                return self._db.load_messages(self._session_id)
            except Exception as e:
                logger.warning("Failed to load history for %s: %s", self._session_id, e)
        return []
