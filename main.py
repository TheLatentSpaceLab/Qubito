import logging
import shlex
import json
from pathlib import Path

from src.agents.agent import Agent
from src.agents.agent_manager import AgentManager
from src.display import console, print_response, thinking_spinner


def _logging_setup() -> None:
    """
    Configure application and dependency logging levels.

    Parameters
    ----------
    None
        This function does not receive arguments.

    Returns
    -------
    None
        Logging configuration is applied globally.
    """
    
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _handle_context_request(agent: Agent) -> None:
    """
    Print the currently loaded retrieval context.

    Parameters
    ----------
    agent : Agent
        Active agent instance serving the conversation.

    Returns
    -------
    None
        Context information is printed to the terminal.
    """
    
    context_view = agent.get_context()
    if not context_view:
        console.print("[yellow]No context loaded yet. Use /load <path> first.[/yellow]")
    console.print("[bold cyan]Loaded context chunks:[/bold cyan]")
    console.print(json.dumps(context_view, indent=2, ensure_ascii=False))


def _handle_history_request(agent: Agent) -> None:
    """
    Print the conversation history for the active agent.

    Parameters
    ----------
    agent : Agent
        Active agent instance serving the conversation.

    Returns
    -------
    None
        History content is printed to the terminal.
    """

    console.print("[bold cyan]Conversation history:[/bold cyan]")
    console.print(json.dumps(agent.get_history(), indent=2, ensure_ascii=False))


def _handle_document_loading_request(agent: Agent, user_input: str) -> None:
    """
    Parse and execute a document loading command.

    Parameters
    ----------
    agent : Agent
        Active agent instance that will index the loaded document.
    user_input : str
        Raw command text provided by the user, expected as
        ``/load <path-to-file>``.

    Returns
    -------
    None
        A status response is printed to the terminal.
    """

    try:
        parts = shlex.split(user_input)
    except ValueError:
        console.print("[red]Invalid command format. Use: /load <path-to-file>[/red]")
        return

    if len(parts) < 2:
        console.print("[yellow]Usage: /load <path-to-file>[/yellow]")
        return

    file_path = Path(" ".join(parts[1:])).expanduser()
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    if not file_path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        return

    if not file_path.is_file():
        console.print(f"[red]Path is not a file:[/red] {file_path}")
        return

    try:
        file_content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        console.print("[red]Could not read file as UTF-8 text.[/red]")
        return
    except OSError as err:
        console.print(f"[red]Failed to read file:[/red] {err}")
        return

    _, chunks, stats = agent.read_document(str(file_path), file_content)
    print_response(
        agent.name,
        agent.emoji,
        agent.color,
        (
            f"Loaded {file_path.name} into memory. "
            f"Indexed {chunks} chunks "
            f"({stats['documents']} docs / {stats['chunks']} chunks total)."
        ),
    )


def _handle_qa_request(agent: Agent, user_input: str) -> None:
    """
    Send a user message to the agent and print the response.

    Parameters
    ----------
    agent : Agent
        Active agent instance serving the conversation.
    user_input : str
        User message text.

    Returns
    -------
    None
        The generated response is printed to the terminal.
    """
    
    with thinking_spinner():
        response = agent.message(user_input)
    print_response(agent.name, agent.emoji, agent.color, response)


def main() -> None:
    """
    Run the interactive Friends bot terminal loop.

    Parameters
    ----------
    None
        This function does not receive arguments.

    Returns
    -------
    None
        The function runs until the user exits the loop.
    """

    _logging_setup()

    agent: Agent = AgentManager.start_random_agent()
    good_morning_msg = agent.get_start_message()
    print_response(agent.name, agent.emoji, agent.color, good_morning_msg)

    while True:

        console.print()
        user_input = console.input("[bold green]?>[/bold green] ")

        if user_input in ['/exit', '/quit']:
            console.print("[dim]Exiting...[/dim]")
            break

        if user_input.startswith('/load'):
            _handle_document_loading_request(agent, user_input)
            continue

        if user_input in ['/history', '/histpry']:
            _handle_history_request(agent)
            continue

        if user_input in ['/context', '/ctx']:
            _handle_context_request(agent)
            continue

        else:
            _handle_qa_request(agent, user_input)


if __name__ == '__main__':
    main()
