"""
"zmk remove" command.
"""

import rich
import typer

from ...build import BuildMatrix
from ...menu import show_menu
from ..config import Config


# TODO: add options to select items from command line
def keyboard_remove(ctx: typer.Context):
    """Remove a keyboard from the build."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    matrix = BuildMatrix.from_repo(repo)
    items = matrix.include

    item = show_menu("Select a build to remove:", items)

    if removed := matrix.remove(item):
        items = ", ".join(f'"{item.__rich__()}"' for item in removed)
        rich.print(f"Removed {items} from the build.")

    matrix.write()
