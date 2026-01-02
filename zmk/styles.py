"""
Console styling utilities.
"""

from rich.console import HighlighterType
from rich.highlighter import RegexHighlighter
from rich.text import Text
from rich.theme import Theme


class KeyValueHighlighter(RegexHighlighter):
    """Highlight "key=value" items."""

    highlights = [r"(?P<key>[\w.]+)(?P<equals>=)(?P<value>.*)"]


class BoardIdHighlighter(RegexHighlighter):
    """Highlights Zephyr board IDs"""

    base_style = "board."

    highlights = [
        r"(?P<separator>[/])",
        r"(?P<revision>@(?:[A-Z]|([0-9]+(\.[0-9]+){0,2})))",
    ]


class CommandLineHighlighter(RegexHighlighter):
    """Highlights command line arguments"""

    base_style = "cmd."

    highlights = [r"(?P<flag>-[a-zA-Z]|--[a-zA-Z-_]+)"]


THEME = Theme(
    {
        "key": "bright_blue",
        "equals": "dim blue",
        "value": "default",
        "board.separator": "dim",
        "board.revision": "sky_blue2",
        "cmd.flag": "dim",
    }
)


def chain_highlighters(highlighters: list[HighlighterType]) -> HighlighterType:
    """Return a new highlighter which runs each of the given highlighters in order"""

    def run_all_highlighters(text: str | Text):
        text = text if isinstance(text, Text) else Text(text)

        for item in highlighters:
            text = item(text)

        return text

    return run_all_highlighters
