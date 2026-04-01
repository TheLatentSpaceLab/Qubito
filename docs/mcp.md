# MCP Tool Integration

Qubito uses the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) to give agents access to external tools. The agent's AI model can call these tools during conversation to search the web, manage files, run shell commands, control hardware, or interact with any service that implements MCP.

## How it works

```
User message
    ↓
AI model sees available tools (MCP + virtual)
    ↓
Model decides to call a tool with arguments
    ↓
MCPManager dispatches to the right MCP server
    ↓
Server executes and returns result
    ↓
Model uses the result to generate a response
```

Tools are discovered automatically at startup. The AI model sees tool names, descriptions, and parameter schemas, and decides when and how to use them.

## Configuration

MCP servers are defined in JSON config files. Qubito checks these locations in order:

| Priority | Path | Scope |
|----------|------|-------|
| 1 | `.qubito/mcp/servers.json` | Project-local |
| 2 | `~/.qubito/mcp/servers.json` | Global (user) |
| 3 | `.mcp.json` (project root) | Claude Code convention |

All found configs are merged. Project-local entries override global ones with the same server name.

### Config format

```json
{
  "server-name": {
    "command": "executable",
    "args": ["arg1", "arg2"],
    "env": {
      "API_KEY": "${MY_ENV_VAR}"
    }
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `command` | yes | Executable to run (e.g. `uv`, `npx`, `python`) |
| `args` | no | Command-line arguments |
| `env` | no | Environment variables. `${VAR}` syntax is substituted from `os.environ` |

This format is compatible with Claude Code's `.mcp.json` convention, so MCP server configs can be shared between Qubito and Claude Code.

## Built-in MCP servers

Qubito ships with three MCP servers built using [FastMCP](https://github.com/modelcontextprotocol/python-sdk):

### Shell (`src/mcp/shell_server.py`)

Runs bash commands with configurable timeout and working directory.

| Tool | Parameters | Description |
|------|-----------|-------------|
| `run_command` | `command`, `cwd?`, `timeout?` | Execute a shell command (default timeout: 60s) |

### File Manager (`src/mcp/file_server.py`)

File system operations with path safety.

| Tool | Parameters | Description |
|------|-----------|-------------|
| `read_file` | `path` | Read file contents |
| `list_directory` | `path?` | List files and directories |
| `create_file` | `path`, `content` | Create a new file (fails if exists) |
| `edit_file` | `path`, `old_text`, `new_text` | Find and replace text in a file |
| `delete_file` | `path` | Delete a file |

### LED Control (`src/mcp/led_server.py`)

Home LED remote control via BLE bridge.

| Tool | Parameters | Description |
|------|-----------|-------------|
| `set_room_mood` | `mood` | Set a predefined mood (cinema, romantic, party, etc.) |
| `set_led_color` | `r`, `g`, `b`, `brightness` | Custom RGB color |
| `set_brightness` | `percent` | Adjust brightness |
| `turn_off_lights` | — | Turn off all LEDs |

### DuckDuckGo Search (external)

Web search via the `@oevortex/ddg_search` npm package.

## Creating a custom MCP server

### 1. Write the server

Create a Python file using FastMCP:

```python
# my_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-tools")

@mcp.tool()
def lookup_user(email: str) -> str:
    """Look up a user by email address.

    Args:
        email: The user's email address.
    """
    # Your implementation here
    return f"User: {email} — found in database"

@mcp.tool()
def send_notification(user_id: str, message: str) -> str:
    """Send a push notification to a user.

    Args:
        user_id: The target user ID.
        message: Notification text.
    """
    # Your implementation here
    return f"Notification sent to {user_id}"

if __name__ == "__main__":
    mcp.run()
```

The docstring becomes the tool description the AI model sees. Argument types and descriptions come from the function signature and `Args:` section.

### 2. Register it in config

Add to `~/.qubito/mcp/servers.json` (global) or `.mcp.json` (project root):

```json
{
  "my-tools": {
    "command": "python",
    "args": ["path/to/my_server.py"]
  }
}
```

### 3. Test with MCP Inspector

Before connecting to qubito, test your server interactively:

```bash
# Web UI — opens browser at localhost:6274
npx @modelcontextprotocol/inspector python path/to/my_server.py

# Or use FastMCP's dev mode
uv run mcp dev path/to/my_server.py
```

The inspector lets you browse tools, view schemas, and invoke them manually.

### 4. Use it

Start qubito normally. Your tools are automatically discovered and available to the agent:

```bash
uv run qubito daemon start
uv run qubito chat
```

The agent sees your tool descriptions and will call them when relevant.

## Using external MCP servers

Any MCP-compatible server works. Popular examples:

```json
{
  "github": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
    }
  },
  "postgres": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"]
  },
  "brave-search": {
    "command": "npx",
    "args": ["-y", "@anthropic-ai/mcp-server-brave-search"],
    "env": {
      "BRAVE_API_KEY": "${BRAVE_API_KEY}"
    }
  }
}
```

Set the referenced environment variables in your `.env` file or shell.

## Virtual tools (local, no MCP)

For simple tools that don't need a separate server process, use virtual tools instead. These are Python functions registered directly on the agent:

```python
from src.genai.chat_response import VirtualTool

tool = VirtualTool(
    name="calculate",
    description="Evaluate a math expression.",
    input_schema={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression"}
        },
        "required": ["expression"],
    },
    handler=lambda args: str(eval(args["expression"])),
)

agent.ai_model.register_tool(tool)
```

Built-in virtual tools (registered on every agent automatically):

| Tool | Description |
|------|-------------|
| `document_search` | RAG search over indexed documents |
| `get_current_datetime` | Current date/time in any format |
| `python_eval` | Sandboxed Python expression evaluator |
| `reminder` | In-session reminder management |
| `system_info` | OS, hostname, Python version |
| `clipboard` | Read/write system clipboard |
| `json_format` | Pretty-print or minify JSON |

## Troubleshooting

**Server not connecting:** Check the command works standalone:
```bash
python src/mcp/shell_server.py  # Should start without errors
```

**Tools not appearing:** Enable debug logging:
```bash
LOGLEVEL=DEBUG uv run qubito chat
```

Look for `MCP tools available: ...` in the output.

**Tool call failing:** MCPManager retries once on failure and auto-reconnects. Check server logs for errors.

**Environment variables not resolving:** Only `${VAR}` syntax is substituted. Make sure the variable is exported in your shell or defined in `.env`.
