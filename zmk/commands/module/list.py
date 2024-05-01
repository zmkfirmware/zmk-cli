import typer

from ...config import Config


def module_list(
    ctx: typer.Context,
):
    """Print a list of installed Zephyr modules."""

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    # TODO
