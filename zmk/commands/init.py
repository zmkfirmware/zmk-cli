import typer

from ..config import Config
from ..subcommands import command


@command
def init(ctx: typer.Context):
    """Create a new ZMK config repo or clone an existing one."""
