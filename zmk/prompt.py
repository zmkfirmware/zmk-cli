"""
Prompt classes.
"""

from rich.prompt import InvalidResponse, PromptBase


class UrlPrompt(PromptBase):
    """Prompt for a URL."""

    def process_response(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise InvalidResponse("[prompt.invalid]Enter a URL.")

        return value
