"""
"zmk init" command.
"""

import typer

from ..config import Config


def init(ctx: typer.Context):
    """Create a new ZMK config repo or clone an existing one."""

    cfg = ctx.find_object(Config)
