"""Interactive terminal chat loop."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.display import (
    console,
    print_goodbye,
    print_response,
    print_user_message,
    print_welcome,
    prompt_input,
    set_commands,
    thinking_spinner,
)

if TYPE_CHECKING:
    from src.config.resolver import QConfig


def run_chat(config: QConfig) -> None:
    """Run the interactive assistant terminal loop.

    Connects to the daemon if running, otherwise falls back to in-process mode.
    """
    from src.daemon.client import DaemonClient

    client = DaemonClient()
    if client.is_daemon_running():
        _run_chat_via_daemon(config, client)
    else:
        client.close()
        _run_chat_in_process(config)


def _run_chat_via_daemon(config: QConfig, client: "DaemonClient") -> None:
    """Chat loop that delegates to the daemon HTTP API."""
    from src.daemon.client import DaemonClient

    session = client.create_session()
    set_commands([])

    print_welcome(
        session.character_name,
        session.emoji,
        session.color,
        session.hi_message,
        tools=None,
    )

    try:
        while True:
            user_input = prompt_input(session.emoji)
            if not user_input:
                continue
            if user_input in ["q", "/exit", "/quit"]:
                print_goodbye(session.character_name, session.emoji, "has left the chat.")
                break

            print_user_message(user_input)

            with thinking_spinner():
                response, elapsed = client.send_message(session.id, user_input)
            print_response(session.character_name, session.emoji, session.color, response, elapsed)
    finally:
        client.delete_session(session.id)
        client.close()


def _run_chat_in_process(config: QConfig) -> None:
    """Original in-process chat loop (no daemon)."""
    from src.agents.agent import Agent
    from src.agents.agent_manager import AgentManager
    from src.mcp import get_mcp_manager
    from src.skills import SkillRegistry, load_all_skills
    from src.skills.generators import set_output_dirs

    if config.global_dir.exists():
        set_output_dirs(
            agents=config.global_dir / "agents",
            skills=config.global_dir / "skills",
            rules=config.global_dir / "rules",
        )

    skills = SkillRegistry(load_all_skills(dirs=config.skills_dirs))
    agent: Agent = AgentManager.start_agent(config=config)

    mcp_tools: list[str] | None = None
    if agent.mcp_manager:
        mcp_tools = [t["name"] for t in agent.mcp_manager.get_tools()]

    set_commands([(s.name, s.description) for s in skills.list_all()])

    greeting = agent.get_start_message()
    print_welcome(agent.name, agent.emoji, agent.color, greeting, mcp_tools)

    try:
        _in_process_loop(agent, skills)
    finally:
        mcp = get_mcp_manager()
        if mcp:
            mcp.close()


def _in_process_loop(agent: "Agent", skills: "SkillRegistry") -> None:
    """The main read-eval-print loop for in-process mode."""
    from src.agents.agent import Agent

    while True:
        user_input = prompt_input(agent.emoji)
        if not user_input:
            continue
        if user_input in ["q", "/exit", "/quit"]:
            print_goodbye(agent.name, agent.emoji, agent.bye_message)
            break

        print_user_message(user_input)

        if user_input.startswith("/"):
            if _handle_skill(agent, skills, user_input):
                continue

        t0 = time.monotonic()
        with thinking_spinner():
            response = agent.message(user_input)
        elapsed = time.monotonic() - t0
        agent.response_times.append(elapsed)
        print_response(agent.name, agent.emoji, agent.color, response, elapsed)


def _handle_skill(agent: "Agent", skills: "SkillRegistry", user_input: str) -> bool:
    """Dispatch a slash command. Returns True if handled."""
    command = user_input.split()[0].lstrip("/")
    if command == "ctx":
        command = "context"

    skill = skills.get(command)
    if skill is None:
        console.print(f"[red]Unknown command: /{command}[/red]. Type /help for available commands.")
        return True

    if skill.skill_type == "handler":
        skills.execute_handler(skill, agent, user_input)
        return True

    if skill.skill_type == "llm":
        user_msg = user_input[len(f"/{command}"):].strip()
        t0 = time.monotonic()
        with thinking_spinner(agent.thinking, agent.color):
            response = agent.message(
                user_msg or skill.instructions,
                skill_instructions=skill.instructions,
            )
        elapsed = time.monotonic() - t0
        agent.response_times.append(elapsed)
        print_response(agent.name, agent.emoji, agent.color, response, elapsed)
        return True

    return False
