"""
"zmk remove" command.
"""

from typing import Annotated, Optional

import typer

from ..config import Config


def keyboard_remove(
    ctx: typer.Context,
    board: Annotated[
        Optional[str],
        typer.Option(
            "--board", "-b", metavar="BOARD", help="ID of the board to remove."
        ),
    ] = None,
    shield: Annotated[
        Optional[str],
        typer.Option(
            "--shield", "-s", metavar="SHIELD", help="ID of the shield to remove."
        ),
    ] = None,
):
    """Remove a keyboard from the build."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()
