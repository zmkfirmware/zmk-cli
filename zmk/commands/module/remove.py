from typing import Annotated, Optional

import typer

from ...config import Config


def module_remove(
    ctx: typer.Context,
    name: Annotated[
        Optional[str],
        typer.Argument(help="Name of the module to remove."),
    ] = None,
):
    """Remove a Zephyr module from the build."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    # TODO
