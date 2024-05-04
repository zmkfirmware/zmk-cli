"""
"zmk west" command.
"""

import typer

from ..config import Config


def west(ctx: typer.Context):
    """Run "west" in the config repo."""

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    # TODO: detect this better
    if ctx.args and ctx.args[0] == "init":
        repo.ensure_west_ready()
        return

    repo.run_west(*ctx.args)


def update(ctx: typer.Context):
    """Get the latest versions of dependencies (run "west update")."""

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    repo.run_west("update")
