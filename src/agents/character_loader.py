from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_CHARACTERS_DIR = Path(__file__).resolve().parent.parent.parent / "agents"


@dataclass(frozen=True)
class CharacterData:
    name: str
    emoji: str
    color: str
    hi_message: str
    personality: str
    bye_message: str = "has left the chat."
    thinking: tuple[str, ...] = ()


def _parse_character_file(path: Path) -> CharacterData:
    """Parse a character markdown file with YAML-like frontmatter."""
    text = path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        raise ValueError(f"Character file {path.name} missing frontmatter")

    _, frontmatter, body = text.split("---", 2)

    meta: dict[str, str] = {}
    for line in frontmatter.strip().splitlines():
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        meta[key.strip()] = value

    required = ("name", "emoji", "color", "hi_message")
    for field in required:
        if field not in meta:
            raise ValueError(f"Character file {path.name} missing required field: {field}")

    thinking = tuple(
        t.strip() for t in meta.get("thinking", "").split("|") if t.strip()
    )

    return CharacterData(
        name=meta["name"],
        emoji=meta["emoji"],
        color=meta["color"],
        hi_message=meta["hi_message"],
        personality=body.strip(),
        bye_message=meta.get("bye_message", "has left the chat."),
        thinking=thinking,
    )


def load_all_characters() -> list[CharacterData]:
    """Discover and load all .md character files from the characters directory."""
    return [
        _parse_character_file(path)
        for path in sorted(_CHARACTERS_DIR.glob("*.md"))
    ]


def load_character_by_filename(filename: str) -> CharacterData:
    """Load a specific character by its .md filename (without extension)."""
    path = _CHARACTERS_DIR / f"{filename}.md"
    if not path.exists():
        available = [p.stem for p in sorted(_CHARACTERS_DIR.glob("*.md"))]
        raise FileNotFoundError(
            f"Character '{filename}' not found. Available: {', '.join(available)}"
        )
    return _parse_character_file(path)


def load_random_character() -> CharacterData:
    """Pick a random .md file and parse only that one."""
    import random
    paths = list(_CHARACTERS_DIR.glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"No character .md files found in {_CHARACTERS_DIR}")
    return _parse_character_file(random.choice(paths))
