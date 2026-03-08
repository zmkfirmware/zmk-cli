"""
"zmk remove" command.
"""

import typer
from rich.console import Console
from rich.padding import Padding

from ...build import BuildMatrix
from ...config import get_config
from ...menu import show_menu
from ...styles import MENU_THEME, THEME, BoardIdHighlighter


# TODO: add options to select items from command line
def keyboard_remove(ctx: typer.Context) -> None:
    """Remove a keyboard from the build."""
    cfg = get_config(ctx)
    repo = cfg.get_repo()

    matrix = BuildMatrix.from_repo(repo)
    items = matrix.include

    console = Console(theme=THEME, highlighter=BoardIdHighlighter())

    with console.use_theme(MENU_THEME):
        item = show_menu("Select a build to remove:", items, console=console)

    if removed := matrix.remove(item):
        console.print("[title]Removed:")
        for item in removed:
            console.print(Padding.indent(item, 2))

    matrix.write()
