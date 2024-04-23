from typing import Optional
import typer
from typing_extensions import Annotated

from ..config import Config
from ..subcommands import command


@command
def add(
    ctx: typer.Context,
    board: Annotated[
        Optional[str],
        typer.Option("--board", "-b", metavar="BOARD", help="ID of the board to use."),
    ] = None,
    shield: Annotated[
        Optional[str],
        typer.Option(
            "--shield", "-s", metavar="SHIELD", help="ID of the shield to use."
        ),
    ] = None,
):
    """Add configuration for a keyboard."""
    cfg = ctx.find_object(Config)
    home = cfg.ensure_home()
