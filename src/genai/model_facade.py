from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from logging import getLogger
from typing import TYPE_CHECKING, Callable

from src.genai.providers import Provider

if TYPE_CHECKING:
    from src.mcp.manager import MCPManager

logger = getLogger(__name__)

MAX_TOOL_ROUNDS = 5


class AIModelFacade:
    """Facade around provider-specific AI clients for chat interactions."""

    def __init__(
        self,
        provider: Provider,
        model: str,
        system_prompt: str,
        history: list[dict[str, str]]
    ):
        """
        Initializes the AIModelFacade with the specified model and sets up
        the AI client.

        Parameters
        ----------
        provider : Provider
            The provider of the AI model to use for generating responses.
        model : str
            The name of the AI model to use for generating responses.
        system_prompt : str
            The system prompt that defines context and behavior instructions.
        history : list[dict[str, str]]
            Existing conversation history to prepend after the system message.

        Returns
        -------
        None
            Initializes internal client and conversation history state.
        """

        self.model = model
        self.provider = provider
        self.system_prompt = system_prompt
        self.history = [
            {"role": "system", "content": self.system_prompt},
            *history
        ]

        if provider == Provider.OLLAMA:
            from src.genai.clients.ollama import get_ollama_client
            self.client = get_ollama_client()
        elif provider == Provider.GEMINI:
            from src.genai.clients.gemini import get_gemini_client
            self.client = get_gemini_client()
        elif provider == Provider.OPEN_ROUTER:
            from src.genai.clients.openrouter import get_openrouter_client
            self.client = get_openrouter_client()
        else:
            raise ValueError(f"Unsupported provider: {provider}")


    def add_to_history(self, role: str, content: str) -> None:
        """
        Adds a message to the conversation history.

        Parameters
        ----------
        role : str
            Chat role of message (for example, ``user`` or ``assistant``).
        content : str
            Message content to append.

        Returns
        -------
        None
            The message is appended to in-memory history.
        """

        self.history.append({"role": role, "content": content})

    def generate_response(
        self,
        user_message: str,
        retrieval_context: str | None = None,
        mcp_manager: MCPManager | None = None,
        on_tool_call: Callable[[str, dict], bool] | None = None,
        skill_instructions: str | None = None,
    ) -> str:
        """Generate a response using the AI model with optional tool use.

        Parameters
        ----------
        user_message : str
            The message from the user to respond to.
        retrieval_context : str or None
            RAG context injected as a temporary system message.
        mcp_manager : MCPManager or None
            MCP manager providing tool definitions and execution.
        on_tool_call : callable or None
            Callback ``(tool_name, arguments) -> bool`` for tool approval.
        skill_instructions : str or None
            Skill-specific instructions injected into the prompt.

        Returns
        -------
        str
            The AI model's response text.
        """
        messages, tool_messages = self._build_turn_messages(
            user_message, retrieval_context, skill_instructions,
        )
        tools = mcp_manager.get_tools() if mcp_manager else None

        try:
            content = self._run_tool_loop(
                messages, tool_messages, tools, mcp_manager, on_tool_call,
            )
        except Exception as e:
            logger.error("AI provider error (%s): %s", self.provider, e)
            content = "Sorry, I'm not feeling very well."

        self.history.append({"role": "user", "content": user_message})
        self.history.extend(tool_messages)
        self.history.append({"role": "assistant", "content": content})
        return content

    def _build_turn_messages(
        self,
        user_message: str,
        retrieval_context: str | None,
        skill_instructions: str | None,
    ) -> tuple[list[dict], list[dict]]:
        """Build the message list for a single turn.

        Parameters
        ----------
        user_message : str
            The user's input text.
        retrieval_context : str or None
            Optional RAG context to prepend.
        skill_instructions : str or None
            Optional skill instructions to prepend.

        Returns
        -------
        tuple of (list[dict], list[dict])
            The full message list and an empty tool-messages accumulator.
        """
        messages: list[dict] = list(self.history)
        if retrieval_context:
            messages.append({"role": "system", "content": f"[context-used]\n{retrieval_context}"})
        if skill_instructions:
            messages.append({"role": "system", "content": f"[skill]\n{skill_instructions}"})
        messages.append({"role": "user", "content": user_message})
        return messages, []

    def _run_tool_loop(
        self,
        messages: list[dict],
        tool_messages: list[dict],
        tools: list[dict] | None,
        mcp_manager: MCPManager | None,
        on_tool_call: Callable[[str, dict], bool] | None,
    ) -> str:
        """Chat with the model, executing tool calls up to MAX_TOOL_ROUNDS.

        Parameters
        ----------
        messages : list of dict
            Conversation messages (mutated in place).
        tool_messages : list of dict
            Accumulator for tool-related messages to persist later.
        tools : list of dict or None
            Tool definitions from MCP, or None to disable tools.
        mcp_manager : MCPManager or None
            Manager used to execute tool calls.
        on_tool_call : callable or None
            Approval callback for each tool invocation.

        Returns
        -------
        str
            The final text content from the model.
        """
        response = None
        tool_cache: dict[tuple[str, str], str] = {}

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.chat(
                model=self.model, messages=messages, tools=tools,
            )
            if not response.has_tool_calls:
                break
            self._process_tool_round(
                response, messages, tool_messages, tool_cache,
                mcp_manager, on_tool_call,
            )

        content = response.content if response else None
        if not content:
            raise ValueError("Received empty response from the AI model.")
        return content

    def _process_tool_round(
        self,
        response: object,
        messages: list[dict],
        tool_messages: list[dict],
        tool_cache: dict[tuple[str, str], str],
        mcp_manager: MCPManager | None,
        on_tool_call: Callable[[str, dict], bool] | None,
    ) -> None:
        """Execute one round of tool calls and append results to messages.

        Parameters
        ----------
        response : object
            The model response containing tool calls.
        messages : list of dict
            Conversation messages (mutated in place).
        tool_messages : list of dict
            Accumulator for tool messages.
        tool_cache : dict
            Cache of ``(name, args_json) -> result`` to avoid duplicates.
        mcp_manager : MCPManager or None
            Manager used to execute tool calls.
        on_tool_call : callable or None
            Approval callback for each tool invocation.
        """
        tool_call_msg = {
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ],
        }
        messages.append(tool_call_msg)
        tool_messages.append(tool_call_msg)

        def _exec(tc: object) -> tuple[object, str]:
            if on_tool_call and not on_tool_call(tc.name, tc.arguments):
                return tc, "Tool call denied by user."
            cache_key = (tc.name, json.dumps(tc.arguments, sort_keys=True))
            if cache_key in tool_cache:
                return tc, tool_cache[cache_key]
            result = mcp_manager.call_tool(tc.name, tc.arguments)
            tool_cache[cache_key] = result
            return tc, result

        if on_tool_call and len(response.tool_calls) > 1:
            results = [_exec(tc) for tc in response.tool_calls]
        else:
            with ThreadPoolExecutor(max_workers=len(response.tool_calls)) as pool:
                results = list(pool.map(_exec, response.tool_calls))

        for tc, result in results:
            tool_result_msg = {
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.name,
                "content": result,
            }
            messages.append(tool_result_msg)
            tool_messages.append(tool_result_msg)
