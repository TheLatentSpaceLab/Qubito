from src.agents.agent import Agent
from src.agents.character_loader import load_character_by_filename, load_random_character
from src.constants import DEFAULT_CHARACTER
from src.rules import load_all_rules


class AgentManager:
    """Factory/cache helper for selecting character agents."""

    AGENTS: dict[str, Agent] = {}

    @staticmethod
    def start_agent() -> Agent:
        """Start the default character agent, or a random one if unset.

        Uses the ``DEFAULT_CHARACTER`` env var (filename without .md).
        Falls back to a random character when the variable is empty.
        """
        if DEFAULT_CHARACTER:
            character = load_character_by_filename(DEFAULT_CHARACTER)
        else:
            character = load_random_character()

        if character.name in AgentManager.AGENTS:
            return AgentManager.AGENTS[character.name]

        rules = load_all_rules()
        agent = Agent(character, rules=rules)
        AgentManager.AGENTS[character.name] = agent
        return agent
