from typing import Annotated, Optional

import typer

from ...config import Config


def module_add(
    ctx: typer.Context,
    url: Annotated[
        Optional[str],
        typer.Argument(help="URL of the module to add."),
    ] = None,
    revision: Annotated[
        Optional[str],
        typer.Argument(help="Branch/revision to track."),
    ] = "main",
):
    """Add a Zephyr module to the build."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    # TODO
