import os
from dotenv import load_dotenv
load_dotenv()

from src.ai import AIClient


class GeminiClient(AIClient):

    def __init__(self, api_key: str | None = None):
        from google import genai

        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is required to use Gemini.")

        self.genai = genai
        self.client = genai.Client(api_key=self.api_key)


    def chat(self, model: str, messages: list[dict[str, str]]) -> str:
        if not messages:
            raise ValueError("messages cannot be empty")

        system_instruction = None
        contents = []

        for message in messages:
            role = (message.get("role") or "").strip()
            content = (message.get("content") or "").strip()
            if not content:
                continue

            if role == "system":
                if system_instruction is None:
                    system_instruction = content
                else:
                    system_instruction += f"\n\n{content}"
                continue

            mapped_role = "model" if role == "assistant" else "user"
            contents.append(
                self.genai.types.Content(
                    role=mapped_role,
                    parts=[self.genai.types.Part(text=content)]
                )
            )

        if not contents:
            raise ValueError("No user/assistant content found in messages.")

        config = None
        if system_instruction:
            config = self.genai.types.GenerateContentConfig(
                system_instruction=system_instruction
            )

        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )

        text = (response.text or "").strip()
        if text:
            return text

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            candidate_content = getattr(candidate, "content", None)
            parts = getattr(candidate_content, "parts", None) or []
            joined = "".join(
                part.text for part in parts
                if getattr(part, "text", None)
            ).strip()
            if joined:
                return joined

        return ""
