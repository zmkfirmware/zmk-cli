"""
"zmk west" command.
"""

from typing import Annotated, Optional

import typer

from ..config import Config


def west(ctx: typer.Context):
    # pylint: disable=line-too-long
    """
    Run [link=https://docs.zephyrproject.org/latest/develop/west/index.html]west[/link] in the config repo.
    """

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    # TODO: detect this better
    if ctx.args and ctx.args[0] == "init":
        repo.ensure_west_ready()
        return

    repo.run_west(*ctx.args)


def update(
    ctx: typer.Context,
    modules: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Names of modules to update. Updates all modules if omitted."
        ),
    ] = None,
):
    """Fetch the latest keyboard data."""

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    modules = modules or []

    repo.run_west("update", *modules)
