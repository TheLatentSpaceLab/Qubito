"""Autonomous job execution handler."""

from __future__ import annotations

import logging
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

from src.skills.guardrail import make_guardrail
from src.skills.security import DEFAULT_SECURITY_GROUP, SecurityGroup

logger = logging.getLogger(__name__)

_JOBS_DIR = Path.home() / ".qubito" / "jobs"

_LAST_PROGRAM_PATH: Path | None = None

PROGRAM_GENERATION_PROMPT = """\
You are generating a program.md — a structured markdown job definition for \
autonomous execution. You MUST respond with ONLY a markdown document using \
the exact format below. Do NOT output JSON, code blocks, or tool calls.

FORMAT (copy this structure exactly):

## Objective
One-sentence summary of what the job accomplishes.

## Steps
1. First concrete step — describe what to do, which tool to use, what arguments.
2. Second step — be specific about file paths, search queries, commands.
3. Continue numbering...

## Expected Output
Describe what files or artifacts will be created.

## Constraints
Any limitations or safety boundaries to respect.

RULES:
- Output ONLY the markdown document, nothing else.
- Each step must be a plain-English instruction, NOT a JSON object or code.
- Be specific: include exact search queries, file paths, and expected results.
- If the user provided file contents, use that information to write better steps.
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


def _clean_program(text: str) -> str:
    """Strip wrapping code fences if the LLM added them."""
    import re
    stripped = text.strip()
    stripped = re.sub(r"^```(?:markdown|md)?\s*\n", "", stripped)
    stripped = re.sub(r"\n```\s*$", "", stripped)
    return stripped.strip()


def _is_valid_program(text: str) -> bool:
    """Check that the program looks like a markdown document with steps."""
    return "##" in text and any(
        marker in text for marker in ("1.", "- ", "* ")
    )


def handle_autojob(agent: object, user_input: str) -> None:
    """Orchestrate autonomous job execution.

    Supports:
      /autojob <task>          — generate plan, review, then run
      /autojob do <task>       — generate plan only
      /autojob run [job-name]  — execute an existing plan
    """
    from src.display import console

    action, arg = _parse_input(user_input)

    if action == "plan":
        _handle_plan(agent, arg, console)
    elif action == "do":
        _handle_do(agent, arg, console)
    elif action == "run":
        _handle_run(agent, arg, console)
    else:
        console.print("[yellow]Usage:[/yellow]")
        console.print("  /autojob <task>          — plan & run")
        console.print("  /autojob do <task>       — plan only")
        console.print("  /autojob run [job-name]  — run existing plan")


def _parse_input(user_input: str) -> tuple[str, str]:
    """Parse autojob subcommand and argument."""
    parts = user_input.strip().split(None, 2)
    if len(parts) < 2:
        return "help", ""

    sub = parts[1] if len(parts) > 1 else ""
    rest = parts[2] if len(parts) > 2 else ""

    if sub == "do":
        return "do", rest
    if sub == "run":
        return "run", rest
    # Everything else is treated as a task → plan mode
    # Rejoin sub + rest as the full task text
    task = user_input.strip().split(None, 1)[1] if len(parts) >= 2 else ""
    return "plan", task


def _handle_plan(agent: object, task: str, console: object) -> None:
    """Generate a plan, show it, and prompt to execute."""
    if not task:
        console.print("[red]Provide a task: /autojob <task>[/red]")
        return

    # Step 1: Generate
    path = _generate_program(agent, task, console)
    if not path:
        return

    # Step 2: Ask to run
    console.print("[dim]Edit the plan if needed, then:[/dim]")
    console.print("  [green]y[/green] [dim]— run now[/dim]")
    console.print("  [green]e[/green] [dim]— open in editor[/dim]")
    console.print("  [dim]anything else — skip (run later with /autojob run)[/dim]")

    try:
        choice = console.input("[bold green]  > [/bold green]").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "e":
        import os
        editor = os.environ.get("EDITOR", "nano")
        os.system(f"{editor} {path}")
        console.print("[dim]Plan updated. Running...[/dim]")
        _handle_run(agent, str(path), console)
    elif choice in ("y", "yes", "s", "si", "sí"):
        _handle_run(agent, str(path), console)


def _generate_program(
    agent: object, task: str, console: object,
) -> Path | None:
    """Generate a program.md from a task and return its path."""
    enriched_task = _enrich_task_with_files(task, console)

    console.print("[dim]Generating plan...[/dim]")
    program = agent.message(enriched_task, skill_instructions=PROGRAM_GENERATION_PROMPT)

    if not program or not program.strip():
        console.print("[red]Plan generation returned empty. Try again.[/red]")
        return None

    program = _clean_program(program)
    if not _is_valid_program(program):
        console.print("[red]LLM returned invalid output. Try again.[/red]")
        console.print(f"[dim]Raw output:[/dim]\n{program[:300]}")
        return None

    path = _save_program(program, task=task)
    console.print(f"\n[bold green]Plan saved to:[/bold green] {path}")
    console.print(f"\n{program}\n")
    return path


def _handle_do(agent: object, task: str, console: object) -> None:
    """Generate a program from the task description (plan only)."""
    if not task:
        console.print("[red]Provide a task: /autojob do <task>[/red]")
        return

    path = _generate_program(agent, task, console)
    if path:
        console.print("[dim]Review/edit the file, then run:[/dim] /autojob run")


def _enrich_task_with_files(task: str, console: object) -> str:
    """Detect file paths in the task and append their contents."""
    from src.files import extract_file_paths, read_file

    paths = extract_file_paths(task)
    if not paths:
        return task

    attachments: list[str] = []
    for path in paths:
        console.print(f"[dim]Reading {path.name}...[/dim]")
        try:
            content = read_file(path)
            attachments.append(
                f"--- FILE: {path.name} ---\n{content}\n--- END FILE ---"
            )
        except (ValueError, FileNotFoundError, ImportError) as exc:
            console.print(f"[yellow]Could not read {path.name}: {exc}[/yellow]")

    if not attachments:
        return task

    return task + "\n\n" + "\n\n".join(attachments)


def _resolve_program_path(user_path: str) -> Path | None:
    """Resolve a user-provided path to a program.md file."""
    if not user_path:
        return _LAST_PROGRAM_PATH

    p = Path(user_path)
    # Direct path to program.md
    if p.exists() and p.is_file():
        return p
    # Job directory name under .qubito/jobs/
    job_dir = _JOBS_DIR / user_path
    candidate = job_dir / "program.md"
    if candidate.exists():
        return candidate
    # Full path to a directory containing program.md
    if p.is_dir() and (p / "program.md").exists():
        return p / "program.md"
    return None


def _handle_run(
    agent: object,
    program_path: str,
    console: object,
    policy: SecurityGroup | None = None,
) -> None:
    """Execute a program with guardrails."""
    global _LAST_PROGRAM_PATH

    path = _resolve_program_path(program_path)
    if not path or not path.exists():
        console.print("[red]No program found. Run /autojob do <task> first.[/red]")
        return

    program = path.read_text(encoding="utf-8")
    job_dir = path.parent
    log_path = job_dir / "log.md"
    policy = policy or DEFAULT_SECURITY_GROUP

    console.print(f"[bold]Executing program:[/bold] {path}")
    console.print(
        f"[dim]Security group: {policy.name} | "
        f"Max rounds: {policy.max_tool_rounds} | "
        f"Timeout: {policy.max_timeout}s[/dim]"
    )

    result = _execute_with_guardrails(agent, program, log_path, policy, console)

    # Always write the log file with the agent's output
    log_path.write_text(result, encoding="utf-8")

    console.print(f"\n[bold green]Job complete.[/bold green] Log: {log_path}")
    console.print(f"\n{result}\n")


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
    deadline = time.monotonic() + policy.max_timeout
    timed_out = False

    def _ask_user(tool_name: str, description: str, arguments: dict) -> bool:
        logger.info("Guardrail auto-approved: %s", description)
        return True

    guardrail = make_guardrail(policy, on_user_decision=_ask_user)

    def _guardrail_with_timeout(tool_name: str, arguments: dict) -> bool:
        nonlocal timed_out
        if time.monotonic() > deadline:
            timed_out = True
            console.print(f"[bold red]Job timed out after {policy.max_timeout}s[/bold red]")
            return False
        return guardrail(tool_name, arguments)

    agent.on_tool_call = _guardrail_with_timeout
    agent.ai_model.max_tool_rounds = policy.max_tool_rounds

    try:
        instructions = EXECUTION_PROMPT.format(
            program=program,
            log_path=str(log_path),
        )
        result = agent.message("Execute the program.", skill_instructions=instructions)
        if timed_out:
            return f"[Job stopped — exceeded {policy.max_timeout}s timeout]\n\n{result}"
        return result
    finally:
        agent.on_tool_call = original_callback
        agent.ai_model.max_tool_rounds = original_rounds


def _slugify(text: str, max_words: int = 4) -> str:
    """Turn a task description into a short kebab-case slug."""
    import re
    # strip file paths before extracting words
    cleaned = re.sub(r"~?/[\w.\-/]+\.\w{1,5}", "", text)
    words = re.sub(r"[^\w\s]", "", cleaned.lower()).split()
    stop = {"the", "a", "an", "and", "or", "on", "in", "at", "to", "my", "me", "do", "i"}
    meaningful = [w for w in words if w not in stop][:max_words]
    return "-".join(meaningful) if meaningful else "job"


def _save_program(program: str, task: str = "") -> Path:
    """Save program content to a titled job directory."""
    global _LAST_PROGRAM_PATH

    slug = _slugify(task) if task else "job"
    job_dir = _JOBS_DIR / slug
    # append a numeric suffix if the directory already exists
    if job_dir.exists():
        counter = 2
        while (_JOBS_DIR / f"{slug}-{counter}").exists():
            counter += 1
        job_dir = _JOBS_DIR / f"{slug}-{counter}"
    job_dir.mkdir(parents=True, exist_ok=True)

    path = job_dir / "program.md"
    path.write_text(program, encoding="utf-8")
    _LAST_PROGRAM_PATH = path
    return path
