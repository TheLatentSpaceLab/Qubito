from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


@dataclass(frozen=True)
class SkillData:
    name: str
    description: str
    instructions: str        # body of the SKILL.md file


def _parse_skill_file(path: Path) -> SkillData:
    """Parse a skill markdown file with frontmatter."""
    text = path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        raise ValueError(f"Skill file {path.name} missing frontmatter")

    _, frontmatter, body = text.split("---", 2)

    meta: dict[str, str] = {}
    for line in frontmatter.strip().splitlines():
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        meta[key.strip()] = value

    required = ("name", "description")
    for field in required:
        if field not in meta:
            raise ValueError(f"Skill file {path.name} missing required field: {field}")

    return SkillData(
        name=meta["name"],
        description=meta["description"],
        instructions=body.strip(),
    )


def load_all_skills(dirs: list[Path] | None = None) -> list[SkillData]:
    """Discover and load all SKILL.md files from the given directories."""
    search_dirs = dirs if dirs else [_DEFAULT_DIR]
    seen: dict[str, Path] = {}
    for d in search_dirs:
        if d.is_dir():
            for p in sorted(d.glob("*/SKILL.md")):
                skill_dir_name = p.parent.name
                if skill_dir_name not in seen:
                    seen[skill_dir_name] = p
    return [_parse_skill_file(p) for p in sorted(seen.values(), key=lambda p: p.parent.name)]
