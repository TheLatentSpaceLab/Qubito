import logging
import time

from src.agents.agent import Agent
from src.agents.agent_manager import AgentManager
from src.mcp import get_mcp_manager
from src.skills import load_all_skills, SkillRegistry
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


def _logging_setup() -> None:
    """Configure application and dependency logging levels."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)


def main() -> None:
    """Run the interactive assistant terminal loop."""

    _logging_setup()

    skills = SkillRegistry(load_all_skills())
    agent: Agent = AgentManager.start_random_agent()

    mcp_tools: list[str] | None = None
    if agent.mcp_manager:
        mcp_tools = [t["name"] for t in agent.mcp_manager.get_tools()]

    set_commands([(s.name, s.description) for s in skills.list_all()])

    greeting = agent.get_start_message()
    print_welcome(agent.name, agent.emoji, agent.color, greeting, mcp_tools)

    try:
        while True:
            user_input = prompt_input(agent.emoji)

            if not user_input:
                continue

            if user_input in ['q', '/exit', '/quit']:
                print_goodbye(agent.name, agent.emoji)
                break

            print_user_message(user_input)

            # Skill dispatch
            if user_input.startswith('/'):
                command = user_input.split()[0].lstrip('/')

                # aliases
                if command == "ctx":
                    command = "context"

                skill = skills.get(command)

                if skill is None:
                    console.print(f"[red]Unknown command: /{command}[/red]. Type /help for available commands.")
                    continue

                if skill.skill_type == "handler":
                    skills.execute_handler(skill, agent, user_input)
                    continue

                if skill.skill_type == "llm":
                    user_msg = user_input[len(f"/{command}"):].strip()
                    t0 = time.monotonic()
                    with thinking_spinner():
                        response = agent.message(
                            user_msg or skill.instructions,
                            skill_instructions=skill.instructions,
                        )
                    elapsed = time.monotonic() - t0
                    agent.response_times.append(elapsed)
                    print_response(agent.name, agent.emoji, agent.color, response, elapsed)
                    continue

            # Regular conversation
            t0 = time.monotonic()
            with thinking_spinner():
                response = agent.message(user_input)
            elapsed = time.monotonic() - t0
            agent.response_times.append(elapsed)
            print_response(agent.name, agent.emoji, agent.color, response, elapsed)

    finally:
        mcp = get_mcp_manager()
        if mcp:
            mcp.close()


if __name__ == '__main__':
    main()
