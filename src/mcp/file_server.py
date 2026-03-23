"""MCP server that exposes file management tools for the LLM."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("file-manager")


@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a file.

    Use this to view what's inside a file the user mentions.

    Args:
        path: Absolute or relative path to the file to read.
    """
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        return f"Error: '{path}' is not a file or does not exist."
    try:
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List files and directories at the given path.

    Use this to explore and navigate the filesystem.

    Args:
        path: Directory path to list. Defaults to current directory.
    """
    target = Path(path).expanduser().resolve()
    if not target.is_dir():
        return f"Error: '{path}' is not a directory or does not exist."
    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines: list[str] = [f"📂 {target}\n"]
        for entry in entries:
            prefix = "📁" if entry.is_dir() else "📄"
            lines.append(f"  {prefix} {entry.name}")
        return "\n".join(lines) if entries else f"(empty directory: {target})"
    except Exception as e:
        return f"Error listing directory: {e}"


@mcp.tool()
def create_file(path: str, content: str) -> str:
    """Create a new file with the given content.

    Use this when the user asks to create or write a new file.
    Parent directories are created automatically if they don't exist.

    Args:
        path: Path for the new file.
        content: Text content to write into the file.
    """
    target = Path(path).expanduser().resolve()
    if target.exists():
        return f"Error: '{path}' already exists. Use edit_file to modify it."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"File created: {target}"
    except Exception as e:
        return f"Error creating file: {e}"


@mcp.tool()
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file by replacing a text fragment.

    Use this to modify an existing file. Provide the exact text to find
    and the replacement text.

    Args:
        path: Path to the file to edit.
        old_text: The exact text to find in the file.
        new_text: The replacement text.
    """
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        return f"Error: '{path}' is not a file or does not exist."
    try:
        current = target.read_text(encoding="utf-8")
        if old_text not in current:
            return f"Error: the specified text was not found in '{path}'."
        count = current.count(old_text)
        updated = current.replace(old_text, new_text)
        target.write_text(updated, encoding="utf-8")
        return f"File edited: {target} ({count} replacement{'s' if count > 1 else ''})"
    except Exception as e:
        return f"Error editing file: {e}"


@mcp.tool()
def delete_file(path: str) -> str:
    """Delete a file.

    Use this when the user explicitly asks to remove a file.

    Args:
        path: Path to the file to delete.
    """
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        return f"Error: '{path}' is not a file or does not exist."
    try:
        target.unlink()
        return f"File deleted: {target}"
    except Exception as e:
        return f"Error deleting file: {e}"


if __name__ == "__main__":
    mcp.run()
