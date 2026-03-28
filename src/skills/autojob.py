"""Autonomous job execution handler."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src.skills.guardrail import make_guardrail
from src.skills.security import DEFAULT_SECURITY_GROUP, SecurityGroup

logger = logging.getLogger(__name__)

_JOBS_DIR = Path(".qubito/jobs")

_LAST_PROGRAM_PATH: Path | None = None

PROGRAM_GENERATION_PROMPT = """\
You are generating a program.md — a structured job definition for autonomous \
execution. Given the user's task description, produce a markdown document with:

## Objective
One-sentence summary of what the job accomplishes.

## Steps
Numbered list of concrete steps. Each step should map to 1-3 tool calls.
Be specific about file paths, commands, and expected outputs.

## Expected Output
What files or artifacts will be created or modified.

## Constraints
Any limitations or safety boundaries to respect.

Output ONLY the program.md content, no preamble or commentary.
"""

EXECUTION_PROMPT = """\
You are executing an autonomous job. Follow the program below step by step.

Rules:
- Use the available tools (file operations, shell commands) to accomplish each step.
- After each major step, append your progress to {log_path}.
- If a tool call is denied by the guardrail, adapt your approach and continue.
- When all steps are complete, report a summary of what was accomplished.

--- PROGRAM START ---
{program}
--- PROGRAM END ---
"""


def handle_autojob(agent: object, user_input: str) -> None:
    """Orchestrate autonomous job execution.

    Parameters
    ----------
    agent : Agent
        The current session agent.
    user_input : str
        Raw user input starting with ``/autojob``.
    """
    from src.display import console

    action, arg = _parse_input(user_input)

    if action == "do":
        _handle_do(agent, arg, console)
    elif action == "run":
        _handle_run(agent, arg, console)
    else:
        console.print("[red]Usage: /autojob do <task> | /autojob run | /autojob --program <path>[/red]")


def _parse_input(user_input: str) -> tuple[str, str]:
    """Parse autojob subcommand and argument.

    Returns
    -------
    tuple of (str, str)
        The action (``do``, ``run``) and the remaining argument text.
    """
    parts = user_input.strip().split(None, 2)
    if len(parts) < 2:
        return "help", ""

    sub = parts[1] if len(parts) > 1 else ""
    rest = parts[2] if len(parts) > 2 else ""

    if sub == "do":
        return "do", rest
    if sub == "run":
        return "run", rest
    if sub == "--program" and rest:
        return "run", rest
    return "help", ""


def _handle_do(agent: object, task: str, console: object) -> None:
    """Generate a program from the task description and save it."""
    if not task:
        console.print("[red]Provide a task description: /autojob do <task>[/red]")
        return

    console.print("[dim]Generating program...[/dim]")
    program = agent.message(task, skill_instructions=PROGRAM_GENERATION_PROMPT)

    path = _save_program(program)
    console.print(f"\n[bold green]Program saved to:[/bold green] {path}")
    console.print("[dim]Review/edit the file, then run:[/dim] /autojob run")


def _handle_run(
    agent: object,
    program_path: str,
    console: object,
    policy: SecurityGroup | None = None,
) -> None:
    """Execute a program with guardrails."""
    global _LAST_PROGRAM_PATH

    path = Path(program_path) if program_path else _LAST_PROGRAM_PATH
    if not path or not path.exists():
        console.print("[red]No program found. Run /autojob do <task> first.[/red]")
        return

    program = path.read_text(encoding="utf-8")
    job_dir = path.parent
    log_path = job_dir / "log.md"
    policy = policy or DEFAULT_SECURITY_GROUP

    console.print(f"[bold]Executing program:[/bold] {path}")
    console.print(f"[dim]Security group: {policy.name} | Max rounds: {policy.max_tool_rounds}[/dim]")

    result = _execute_with_guardrails(agent, program, log_path, policy, console)
    console.print(f"\n[bold green]Job complete.[/bold green] Log: {log_path}")


def _execute_with_guardrails(
    agent: object,
    program: str,
    log_path: Path,
    policy: SecurityGroup,
    console: object,
) -> str:
    """Install guardrails, run the program, restore original state."""
    original_callback = agent.on_tool_call
    original_rounds = agent.ai_model.max_tool_rounds

    def _ask_user(tool_name: str, description: str, arguments: dict) -> bool:
        console.print(f"\n[bold yellow]Guardrail:[/bold yellow] {description}")
        try:
            answer = console.input("[bold yellow]Allow? (y/n): [/bold yellow]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in ("y", "yes", "s", "si", "sí")

    guardrail = make_guardrail(policy, on_user_decision=_ask_user)
    agent.on_tool_call = guardrail
    agent.ai_model.max_tool_rounds = policy.max_tool_rounds

    try:
        instructions = EXECUTION_PROMPT.format(
            program=program,
            log_path=str(log_path),
        )
        return agent.message("Execute the program.", skill_instructions=instructions)
    finally:
        agent.on_tool_call = original_callback
        agent.ai_model.max_tool_rounds = original_rounds


def _save_program(program: str) -> Path:
    """Save program content to a timestamped job directory."""
    global _LAST_PROGRAM_PATH

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_dir = _JOBS_DIR / timestamp
    job_dir.mkdir(parents=True, exist_ok=True)

    path = job_dir / "program.md"
    path.write_text(program, encoding="utf-8")
    _LAST_PROGRAM_PATH = path
    return path
