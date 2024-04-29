"""
Console styling utilities.
"""

from rich.highlighter import RegexHighlighter
from rich.theme import Theme


class SeparatorHighlighter(RegexHighlighter):
    """Highlight anything that looks like a separator"""

    highlights = [r"(?P<separator>[:=]|->)"]


DIM_SEPARATORS = Theme({"separator": "blue"})
