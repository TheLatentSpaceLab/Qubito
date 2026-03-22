import logging

from src.agents.agent import Agent
from src.agents.agent_manager import AgentManager
from src.mcp import get_mcp_manager
from src.skills import load_all_skills, SkillRegistry
from src.display import console, print_response, thinking_spinner


def _logging_setup() -> None:
    """Configure application and dependency logging levels."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    """Run the interactive assistant terminal loop."""

    _logging_setup()

    skills = SkillRegistry(load_all_skills())
    agent: Agent = AgentManager.start_random_agent()

    if agent.mcp_manager:
        tool_names = [t["name"] for t in agent.mcp_manager.get_tools()]
        console.print(f"[dim]🔌 MCP tools: {', '.join(tool_names)}[/dim]")

    good_morning_msg = agent.get_start_message()
    print_response(agent.name, agent.emoji, agent.color, good_morning_msg)

    try:
        while True:

            console.print()
            user_input = console.input("[bold green]?>[/bold green] ").strip()

            if not user_input:
                continue

            if user_input in ['q', '/exit', '/quit']:
                console.print("[dim]Bye...[/dim]")
                break

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
                    with thinking_spinner():
                        response = agent.message(
                            user_msg or skill.instructions,
                            skill_instructions=skill.instructions,
                        )
                    print_response(agent.name, agent.emoji, agent.color, response)
                    continue

            # Regular conversation
            with thinking_spinner():
                response = agent.message(user_input)
            print_response(agent.name, agent.emoji, agent.color, response)

    finally:
        mcp = get_mcp_manager()
        if mcp:
            mcp.close()


if __name__ == '__main__':
    main()
