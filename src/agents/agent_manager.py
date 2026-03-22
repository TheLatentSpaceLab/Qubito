from src.agents.agent import Agent
from src.agents.character_loader import load_random_character
from src.rules import load_all_rules


class AgentManager:
    """Factory/cache helper for selecting character agents."""

    AGENTS: dict[str, Agent] = {}

    @staticmethod
    def start_random_agent() -> Agent:
        """
        Randomly selects and starts an agent from the available characters.

        Returns
        -------
        Agent
            An instance of the randomly selected agent.
        """

        character = load_random_character()

        if character.name in AgentManager.AGENTS:
            return AgentManager.AGENTS[character.name]

        rules = load_all_rules()
        agent = Agent(character, rules=rules)
        AgentManager.AGENTS[character.name] = agent
        return agent
