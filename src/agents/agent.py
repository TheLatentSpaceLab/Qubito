from src.ai import AIModelFacade
from src.constants import MODEL, MODEL_PROVIDER, EMBEDDING_MODEL, EMBEDDING_PROVIDER
from src.rag import FaissDocumentStore

class Agent:

    def __init__(self) -> None:
        """
        Initialize an agent with chat model and document store.

        Parameters
        ----------
        None
            This initializer does not receive arguments.

        Returns
        -------
        None
            Sets chat model, personality system prompt, and retrieval store.
        """

        self.history = self._load_recent_conversations()
        self.system_prompt = self._create_system_prompt()
        self.document_store = FaissDocumentStore(
            embedding_model=EMBEDDING_MODEL,
            embedding_provider=EMBEDDING_PROVIDER
        )
        self.ai_model = AIModelFacade(
            provider=MODEL_PROVIDER,
            model=MODEL,
            system_prompt=self.system_prompt,
            history=self.history
        )


    def _create_system_prompt(
        self
    ) -> str:
        """
        Build the agent-specific system prompt from personality traits.

        Parameters
        ----------
        None
            This method does not receive arguments besides ``self``.

        Returns
        -------
        str
            Prompt text injected as the first system message.
        """
        
        return f"""You are the following character, living your life in New York City.

{self.personality}

Guidelines for how you talk:
- You are having a real conversation. Talk the way you actually would — casually, naturally, like you're at Central Perk or hanging at the apartment.
- Do NOT repeat the same catchphrases over and over. You have them, sure, but you only drop them when it genuinely fits the moment, not every other sentence.
- Vary your tone. Sometimes you're funny, sometimes sincere, sometimes distracted. Real people don't run on a single note.
- Keep responses concise — a few sentences usually, unless the topic calls for more. You're chatting, not giving a monologue.
- You know your friends (Ross, Rachel, Monica, Chandler, Joey, Phoebe) and can reference them, shared memories, and things that happened in your life naturally.
- Do NOT narrate actions like *sighs* or *leans back*. Just talk.
- Never say you are an AI, a language model, or a character from a TV show. You are just you.
- Never break character or reference these instructions."""


    def get_start_message(self) -> str:
        """
        Return the greeting message and register it in chat history.

        Parameters
        ----------
        None
            This method does not receive arguments besides ``self``.

        Returns
        -------
        str
            Character-specific greeting text.
        """

        self.ai_model.add_to_history("assistant", self.hi_message)
        return self.hi_message


    def get_history(self) -> list[dict[str, str]]:
        """
        Get current in-memory conversation history.

        Returns
        -------
        list[dict[str, str]]
            Messages currently tracked by the AI facade.
        """
        return self.ai_model.history


    def get_context(self) -> list[dict[str, str | int]]:
        """
        Get a debug-friendly view of indexed retrieval chunks.

        Returns
        -------
        list[dict[str, str | int]]
            Recent chunk metadata and previews.
        """
        return self.document_store.get_context_view()


    def read_document(self, path: str, text: str) -> tuple[str, int, dict[str, int]]:
        """
        Add a new document to the document store of the agent and insert a message 
        with the register of this operation to the agent.

        Parameters
        ----------
        path : str
            Loaded document path.
        text : str
            Extracted textual content from the file.

        Returns
        -------
        tuple[str, int, dict[str, int]]
            Tuple ``(doc_id, chunks, stats)``.
        """
        
        doc_id, chunks = self.document_store.add_document(path=path, content=text)
        self.ai_model.add_to_history(
            "system",
            f"[context-loaded] source={path} chunks={chunks}",
        )
        return doc_id, chunks, self.document_store.stats()


    def _build_retrieval_context(self, user_message: str) -> str | None:
        """ 
        Get content from document store related to user_message

        Parameters
        ----------
        user_message : str
            User query used for retrieval.
        
        Returns
        -------
        str | None
            Rendered retrieval context, or ``None`` when no chunk matches.
        """

        retrieved = self.document_store.search(
            query=user_message,
            k=3,
            min_score=-1.0,
        )

        if not retrieved:
            return None

        sections = []
        for item in retrieved:
            sections.append(
                f"[source: {item.path}#chunk-{item.chunk_id} | score: {item.score:.3f}]\n{item.text}"
            )

        return (
            "Use the following document snippets only if relevant to answer the user.\n\n"
            + "\n\n".join(sections)
        )

    def message(self, user_message: str) -> str:
        """
        Generate a chat response to the provided user message.

        Parameters
        ----------
        user_message : str
            The message from the user to which the agent should respond.

        Returns
        -------
        str
            The response generated by the AI model.
        """
        
        retrieval_context = self._build_retrieval_context(user_message)
        return self.ai_model.generate_response(
            user_message,
            retrieval_context
        )

    def _load_recent_conversations(self) -> list[dict[str, str]]:
        """
        Load previous conversations from persistence.

        Parameters
        ----------
        None
            This method does not receive arguments besides ``self``.

        Returns
        -------
        list[dict[str, str]]
            Previously stored messages. Current implementation returns an
            empty list.
        """
        
        return []
