"""Built-in virtual tools registered on every agent."""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime
from typing import TYPE_CHECKING

from src.genai.chat_response import VirtualTool

if TYPE_CHECKING:
    from src.rag.faiss_store import FaissDocumentStore


def make_document_search(store: FaissDocumentStore) -> VirtualTool:
    """RAG search over indexed documents."""

    def handler(arguments: dict) -> str:
        query = arguments.get("query", "")
        k = arguments.get("num_results", 3)
        retrieved = store.search(query=query, k=k, min_score=-1.0)
        if not retrieved:
            return "No relevant documents found."
        sections = [
            f"[source: {r.path}#chunk-{r.chunk_id} | score: {r.score:.3f}]\n{r.text}"
            for r in retrieved
        ]
        return "\n\n".join(sections)

    return VirtualTool(
        name="document_search",
        description=(
            "Search indexed documents for information relevant to a query. "
            "Use when the user asks about content from uploaded or indexed files."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant document chunks.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Max results to return (default: 3).",
                },
            },
            "required": ["query"],
        },
        handler=handler,
    )


def make_get_current_datetime() -> VirtualTool:
    """Current date and time."""

    def handler(arguments: dict) -> str:
        fmt = arguments.get("format", "%Y-%m-%dT%H:%M:%S")
        return datetime.now().strftime(fmt)

    return VirtualTool(
        name="get_current_datetime",
        description="Get the current date and time.",
        input_schema={
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "description": "strftime format string (default: ISO 8601).",
                },
            },
            "required": [],
        },
        handler=handler,
    )


def make_python_eval() -> VirtualTool:
    """Evaluate a Python expression and return the result."""

    safe_builtins = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "len": len, "sorted": sorted, "reversed": reversed,
        "range": range, "enumerate": enumerate, "zip": zip, "map": map,
        "filter": filter, "list": list, "dict": dict, "set": set,
        "tuple": tuple, "str": str, "int": int, "float": float, "bool": bool,
        "True": True, "False": False, "None": None,
        "hex": hex, "bin": bin, "oct": oct, "ord": ord, "chr": chr,
        "pow": pow, "divmod": divmod, "isinstance": isinstance, "type": type,
        "any": any, "all": all,
    }

    def handler(arguments: dict) -> str:
        expression = arguments.get("expression", "")
        if not expression.strip():
            return "Error: empty expression."
        try:
            result = eval(expression, {"__builtins__": safe_builtins})  # noqa: S307
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    return VirtualTool(
        name="python_eval",
        description=(
            "Evaluate a Python expression (math, string ops, list comprehensions). "
            "No imports or side effects allowed. Use for calculations."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Python expression to evaluate, e.g. '2**10' or '[x*2 for x in range(5)]'.",
                },
            },
            "required": ["expression"],
        },
        handler=handler,
    )


def make_set_reminder() -> VirtualTool:
    """Store a reminder the agent can check later."""
    reminders: list[dict[str, str]] = []

    def handler(arguments: dict) -> str:
        action = arguments.get("action", "add")
        if action == "list":
            if not reminders:
                return "No reminders set."
            lines = [f"- [{r['time']}] {r['text']}" for r in reminders]
            return "\n".join(lines)
        if action == "clear":
            reminders.clear()
            return "All reminders cleared."
        text = arguments.get("text", "")
        time = arguments.get("time", datetime.now().strftime("%Y-%m-%d %H:%M"))
        if not text:
            return "Error: reminder text is required."
        reminders.append({"text": text, "time": time})
        return f"Reminder set: [{time}] {text}"

    return VirtualTool(
        name="reminder",
        description="Manage reminders: add, list, or clear them.",
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "clear"],
                    "description": "Action to perform (default: add).",
                },
                "text": {
                    "type": "string",
                    "description": "Reminder text (required for 'add').",
                },
                "time": {
                    "type": "string",
                    "description": "When to remind (free-form, e.g. '2025-04-01 09:00' or 'tomorrow morning').",
                },
            },
            "required": [],
        },
        handler=handler,
    )


def make_system_info() -> VirtualTool:
    """Return basic system information."""

    def handler(arguments: dict) -> str:
        info = {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "hostname": platform.node(),
        }
        return json.dumps(info, indent=2)

    return VirtualTool(
        name="system_info",
        description="Get basic system information (OS, hostname, Python version).",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=handler,
    )


def make_clipboard() -> VirtualTool:
    """Read from or write to the system clipboard."""

    def handler(arguments: dict) -> str:
        action = arguments.get("action", "read")
        if action == "write":
            text = arguments.get("text", "")
            if not text:
                return "Error: text is required to write to clipboard."
            try:
                proc = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text, text=True, timeout=5,
                )
                return "Copied to clipboard." if proc.returncode == 0 else "Error: xclip failed."
            except FileNotFoundError:
                return "Error: xclip not installed."
            except Exception as e:
                return f"Error: {e}"
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout if result.returncode == 0 else "Clipboard is empty."
        except FileNotFoundError:
            return "Error: xclip not installed."
        except Exception as e:
            return f"Error: {e}"

    return VirtualTool(
        name="clipboard",
        description="Read from or write to the system clipboard.",
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write"],
                    "description": "Read from or write to clipboard (default: read).",
                },
                "text": {
                    "type": "string",
                    "description": "Text to copy (required for 'write').",
                },
            },
            "required": [],
        },
        handler=handler,
    )


def make_json_formatter() -> VirtualTool:
    """Pretty-print or minify JSON."""

    def handler(arguments: dict) -> str:
        raw = arguments.get("text", "")
        minify = arguments.get("minify", False)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"
        if minify:
            return json.dumps(parsed, separators=(",", ":"))
        return json.dumps(parsed, indent=2, ensure_ascii=False)

    return VirtualTool(
        name="json_format",
        description="Pretty-print or minify a JSON string.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "JSON string to format.",
                },
                "minify": {
                    "type": "boolean",
                    "description": "If true, minify instead of pretty-printing.",
                },
            },
            "required": ["text"],
        },
        handler=handler,
    )


ALL_TOOLS: list[VirtualTool] = [
    make_get_current_datetime(),
    make_python_eval(),
    make_set_reminder(),
    make_system_info(),
    make_clipboard(),
    make_json_formatter(),
]
