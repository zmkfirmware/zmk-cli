import typer

from ..config import Config


def pull(ctx: typer.Context):
    """Run "git pull" in the config repo."""

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()
    # TODO


def push(ctx: typer.Context):
    """Run "git push" in the config repo."""

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()
    # TODO
