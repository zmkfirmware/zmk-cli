"""
Console styling utilities.
"""

from rich.console import HighlighterType
from rich.highlighter import RegexHighlighter
from rich.text import Text
from rich.theme import Theme


class KeyValueHighlighter(RegexHighlighter):
    """Highlight "key=value" items."""

    base_style = "kv."

    highlights = [  # noqa: RUF012 https://github.com/astral-sh/ruff/issues/5429
        r"(?P<key>[\w.]+)(?P<equals>=)(?P<value>.*)"
    ]


class BoardIdHighlighter(RegexHighlighter):
    """Highlights Zephyr board IDs"""

    base_style = "board."

    highlights = [  # noqa: RUF012 https://github.com/astral-sh/ruff/issues/5429
        r"(?P<qualifier>/[a-zA-Z_]?\w*/[a-zA-Z_]\w*\b)",
        r"(?P<revision>@(?:[A-Z]|([0-9]+(\.[0-9]+){0,2})))",
    ]


class CommandLineHighlighter(RegexHighlighter):
    """Highlights command line arguments"""

    base_style = "cmd."

    highlights = [  # noqa: RUF012 https://github.com/astral-sh/ruff/issues/5429
        r"(?<!\S)(?P<flag>-[a-zA-Z]|--[a-zA-Z-_]+)"
    ]


THEME = Theme(
    {
        "title": "bright_magenta",
        "kv.key": "bright_blue",
        "kv.equals": "dim blue",
        "value": "default",
        "board.revision": "rgb(135,95,175)",
        "board.qualifier": "rgb(135,95,175)",
        "cmd.flag": "dim",
    }
)

# Don't use colors in menus, as that will override the focus style.
MENU_THEME = Theme({"board.revision": "dim", "board.qualifier": "dim"})


def chain_highlighters(*highlighters: HighlighterType | None) -> HighlighterType:
    """
    Return a new highlighter which runs each of the given highlighters in order.

    Arguments that are None will be skipped.
    """

    def run_all_highlighters(text: str | Text):
        text = text if isinstance(text, Text) else Text(text)

        for item in highlighters:
            if item:
                text = item(text)

        return text

    return run_all_highlighters
