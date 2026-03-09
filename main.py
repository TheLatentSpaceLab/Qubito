from src.agents.agent_manager import AgentManager
from src.display import console, print_response

if __name__ == '__main__':

    agent = AgentManager.start_random_agent()

    response = agent.start_message()
    print_response(agent.name, agent.emoji, agent.color, response)

    while True:

        console.print()
        
        user_input = console.input("[bold green]?>[/bold green] ")

        lower_input = user_input.lower()
        if lower_input in ['/exit', '/quit']:
            console.print("[dim]Exiting...[/dim]")
            break
        
        if lower_input == '/help':
            # show details of agents & models
            ...

        response = agent.message(user_input)
        print_response(agent.name, agent.emoji, agent.color, response)
