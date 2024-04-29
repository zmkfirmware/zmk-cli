from typing import Optional
import typer
from typing_extensions import Annotated

from ..config import Config


def keyboard_add(
    ctx: typer.Context,
    board: Annotated[
        Optional[str],
        typer.Option("--board", "-b", metavar="BOARD", help="ID of the board to add."),
    ] = None,
    shield: Annotated[
        Optional[str],
        typer.Option(
            "--shield", "-s", metavar="SHIELD", help="ID of the shield to add."
        ),
    ] = None,
):
    """Add configuration for a keyboard and add it to the build."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()
