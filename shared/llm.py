"""Claude API wrapper for Plumtree agents."""

import anthropic

from config.settings import Settings


class ClaudeClient:
    """Thin wrapper around the Anthropic SDK for agent use."""

    MODEL = "claude-sonnet-4-20250514"

    def __init__(self, settings: Settings):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 8192,
        temperature: float = 0.3,
    ) -> str:
        """Send a prompt to Claude and return the text response."""
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict = {
            "model": self.MODEL,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text
