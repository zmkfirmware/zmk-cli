"""
Console styling utilities.
"""

from rich.highlighter import RegexHighlighter
from rich.theme import Theme


class KeyValueHighlighter(RegexHighlighter):
    """Highlight "key=value" items."""

    highlights = [r"(?P<key>[\w.]+)(?P<equals>=)(?P<value>.*)"]


KEY_VALUE_THEME = Theme(
    {
        "key": "bright_blue",
        "equals": "dim blue",
        "value": "default",
    }
)
