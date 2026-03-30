"""Handler for the /cron skill command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table
from src.display import console

if TYPE_CHECKING:
    from src.agents.agent import Agent


def handle_cron(agent: Agent, user_input: str) -> None:
    """Manage cron jobs: add, list, remove, enable, disable."""
    from src.scheduler.models import CronJob, load_cron_jobs, save_cron_jobs

    parts = user_input.strip().split(maxsplit=2)
    sub = parts[1] if len(parts) > 1 else "list"
    rest = parts[2] if len(parts) > 2 else ""

    if sub == "list":
        _list_jobs(load_cron_jobs())
    elif sub == "add":
        _add_job(rest)
    elif sub == "remove":
        _remove_job(rest.strip())
    elif sub in ("enable", "disable"):
        _toggle_job(rest.strip(), enabled=(sub == "enable"))
    else:
        console.print("[yellow]Usage: /cron add|list|remove|enable|disable[/yellow]")


def _list_jobs(jobs: list) -> None:
    if not jobs:
        console.print("[dim]No cron jobs configured.[/dim]")
        return

    table = Table(title="Cron Jobs", show_lines=True)
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Action")
    table.add_column("Enabled")
    table.add_column("Last Run", style="dim")

    for j in jobs:
        table.add_row(
            j.id[:8],
            j.name,
            j.cron_expression,
            j.action[:50],
            "yes" if j.enabled else "no",
            j.last_run or "never",
        )
    console.print(table)


def _add_job(rest: str) -> None:
    """Parse: /cron add <cron_expr> <name> :: <action>"""
    from src.scheduler.models import CronJob, load_cron_jobs, save_cron_jobs

    if "::" not in rest:
        console.print('[yellow]Usage: /cron add "0 8 * * *" morning-summary :: summarize my inbox[/yellow]')
        return

    schedule_and_name, _, action = rest.partition("::")
    tokens = schedule_and_name.strip().split()

    if len(tokens) < 6:
        console.print("[red]Need 5 cron fields + a name.[/red]")
        return

    cron_expr = " ".join(tokens[:5])
    name = " ".join(tokens[5:])

    job = CronJob(name=name, cron_expression=cron_expr, action=action.strip())
    jobs = load_cron_jobs()
    jobs.append(job)
    save_cron_jobs(jobs)
    console.print(f"[green]Created cron job '{name}' (id: {job.id[:8]})[/green]")


def _remove_job(job_id: str) -> None:
    from src.scheduler.models import load_cron_jobs, save_cron_jobs

    jobs = load_cron_jobs()
    new_jobs = [j for j in jobs if not j.id.startswith(job_id)]
    if len(new_jobs) == len(jobs):
        console.print(f"[red]Job '{job_id}' not found.[/red]")
        return
    save_cron_jobs(new_jobs)
    console.print(f"[green]Removed {len(jobs) - len(new_jobs)} job(s).[/green]")


def _toggle_job(job_id: str, enabled: bool) -> None:
    from src.scheduler.models import load_cron_jobs, save_cron_jobs

    jobs = load_cron_jobs()
    found = False
    for j in jobs:
        if j.id.startswith(job_id):
            j.enabled = enabled
            found = True
    if not found:
        console.print(f"[red]Job '{job_id}' not found.[/red]")
        return
    save_cron_jobs(jobs)
    state = "enabled" if enabled else "disabled"
    console.print(f"[green]Job {state}.[/green]")
