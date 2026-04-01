"""Generator handlers for scaffolding new agents, skills, and rules.

Every handler has the signature: (agent: Agent, user_input: str) -> None
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.display import console

if TYPE_CHECKING:
    from src.agents.agent import Agent

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENTS_DIR = _PROJECT_ROOT / "agents"
_SKILLS_DIR = _PROJECT_ROOT / "skills"
_RULES_DIR = _PROJECT_ROOT / "rules"

# Module-level config set by the CLI at startup; generators use these paths
# when available, falling back to the legacy project-root directories.
_config_agents_dir: Path | None = None
_config_skills_dir: Path | None = None
_config_rules_dir: Path | None = None


def set_output_dirs(agents: Path | None = None, skills: Path | None = None, rules: Path | None = None) -> None:
    """Configure where generators write new files."""
    global _config_agents_dir, _config_skills_dir, _config_rules_dir
    _config_agents_dir = agents
    _config_skills_dir = skills
    _config_rules_dir = rules


def _agents_dir() -> Path:
    return _config_agents_dir or _AGENTS_DIR


def _skills_dir() -> Path:
    return _config_skills_dir or _SKILLS_DIR


def _rules_dir() -> Path:
    return _config_rules_dir or _RULES_DIR


def _prompt(label: str, default: str = "") -> str:
    """Prompt the user for input with an optional default."""
    suffix = f" [{default}]" if default else ""
    value = console.input(f"  [cyan]{label}{suffix}:[/cyan] ").strip()
    return value or default


def handle_new_agent(agent: Agent, user_input: str) -> None:
    """Interactively scaffold a new character markdown file."""
    console.print("\n[bold]Create a new agent[/bold]\n")

    name = _prompt("Character name (e.g. Rachel Green)")
    if not name:
        console.print("[red]Name is required.[/red]")
        return

    emoji = _prompt("Emoji", "🤖")
    color = _prompt("Color (Rich markup)", "bold white")
    hi_message = _prompt("Greeting message", f"Hey, I'm {name}!")
    console.print("  [cyan]Personality (multi-line, empty line to finish):[/cyan]")
    personality_lines: list[str] = []
    while True:
        line = console.input("  ")
        if not line:
            break
        personality_lines.append(line)

    if not personality_lines:
        console.print("[red]Personality description is required.[/red]")
        return

    filename = name.lower().replace(" ", "-") + ".md"
    target = _agents_dir()
    target.mkdir(parents=True, exist_ok=True)
    filepath = target / filename

    if filepath.exists():
        console.print(f"[red]Agent file already exists:[/red] {filepath}")
        return

    content = (
        f"---\n"
        f"name: {name}\n"
        f'emoji: "{emoji}"\n'
        f"color: {color}\n"
        f"hi_message: \"{hi_message}\"\n"
        f"---\n\n"
        + "\n".join(personality_lines)
        + "\n"
    )

    filepath.write_text(content, encoding="utf-8")
    console.print(f"\n[green]Created agent:[/green] {filepath}")


def handle_new_skill(agent: Agent, user_input: str) -> None:
    """Interactively scaffold a new skill directory with SKILL.md."""
    console.print("\n[bold]Create a new skill[/bold]\n")

    name = _prompt("Skill name (e.g. translate)")
    if not name:
        console.print("[red]Name is required.[/red]")
        return

    description = _prompt("Description")

    console.print("  [cyan]Instructions / body (multi-line, empty line to finish):[/cyan]")
    body_lines: list[str] = []
    while True:
        line = console.input("  ")
        if not line:
            break
        body_lines.append(line)

    skill_dir_name = name.lower().replace(" ", "-")
    target = _skills_dir()
    skill_dir = target / skill_dir_name
    filepath = skill_dir / "SKILL.md"

    if skill_dir.exists():
        console.print(f"[red]Skill directory already exists:[/red] {skill_dir}")
        return

    skill_dir.mkdir(parents=True, exist_ok=True)

    content = (
        f"---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"---\n\n"
        + "\n".join(body_lines)
        + "\n"
    )

    filepath.write_text(content, encoding="utf-8")
    console.print(f"\n[green]Created skill:[/green] {filepath}")


def handle_new_rule(agent: Agent, user_input: str) -> None:
    """Interactively scaffold a new rule markdown file."""
    console.print("\n[bold]Create a new rule[/bold]\n")

    name = _prompt("Rule name (e.g. no-spoilers)")
    if not name:
        console.print("[red]Name is required.[/red]")
        return

    priority = _prompt("Priority (lower = loaded first)", "50")

    console.print("  [cyan]Rule content (multi-line, empty line to finish):[/cyan]")
    body_lines: list[str] = []
    while True:
        line = console.input("  ")
        if not line:
            break
        body_lines.append(line)

    if not body_lines:
        console.print("[red]Rule content is required.[/red]")
        return

    filename = name.lower().replace(" ", "-") + ".md"
    target = _rules_dir()
    target.mkdir(parents=True, exist_ok=True)
    filepath = target / filename

    if filepath.exists():
        console.print(f"[red]Rule file already exists:[/red] {filepath}")
        return

    content = (
        f"---\n"
        f"name: {name}\n"
        f"priority: {priority}\n"
        f"---\n\n"
        + "\n".join(body_lines)
        + "\n"
    )

    filepath.write_text(content, encoding="utf-8")
    console.print(f"\n[green]Created rule:[/green] {filepath}")
