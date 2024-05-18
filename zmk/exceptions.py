"""
Exception types.
"""

from pathlib import Path

from click import ClickException
from rich.highlighter import Highlighter, ReprHighlighter
from rich.text import Text


class FatalError(ClickException):
    """
    Exception which terminates the program.

    Exception message supports rich markup.
    """

    highlighter: Highlighter

    def __init__(self, message: str, highlighter: Highlighter = None) -> None:
        self.highlighter = highlighter or ReprHighlighter()
        super().__init__(message)

    def format_message(self) -> str:
        return self.highlighter(Text.from_markup(self.message))


class FatalHomeNotSet(FatalError):
    """
    Exception which indicates that the command requires a home directory, but the
    "user.home" setting is not set.
    """

    def __init__(self):
        super().__init__(
            'Home directory not set. Run "zmk init" to create a new config repo.'
        )


class FatalHomeMissing(FatalError):
    """
    Exception which indicates that the "user.home" setting points to a directory
    that no longer exists.
    """

    def __init__(self, path: Path):
        super().__init__(
            f'Home directory "{path}" is missing.\n'
            'Run "zmk config user.home=/path/to/zmk-config" if you moved it, '
            'or run "zmk init" to create a new config repo.'
        )
