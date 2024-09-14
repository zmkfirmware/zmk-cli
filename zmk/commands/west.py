"""
"zmk west" command.
"""

from typing import Annotated

import typer

from ..config import get_config


def west(ctx: typer.Context) -> None:
    # pylint: disable=line-too-long
    """
    Run [link=https://docs.zephyrproject.org/latest/develop/west/index.html]west[/link] in the config repo.
    """

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    # TODO: detect this better
    if ctx.args and ctx.args[0] == "init":
        repo.ensure_west_ready()
        return

    repo.run_west(*ctx.args)


def update(
    ctx: typer.Context,
    modules: Annotated[
        list[str] | None,
        typer.Argument(
            help="Names of modules to update. Updates all modules if omitted."
        ),
    ] = None,
) -> None:
    """Fetch the latest keyboard data."""

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    modules = modules or []

    repo.run_west("update", *modules)
