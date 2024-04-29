"""
CLI tool to setup up ZMK Firmware.
"""

from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from . import commands
from .config import Config

app = typer.Typer(short_help="h")
commands.register(app)


@app.callback()
def main(
    ctx: typer.Context,
    config_file: Annotated[
        Optional[Path],
        typer.Option(
            envvar="ZMK_CLI_CONFIG", help="Path to the ZMK CLI configuration file."
        ),
    ] = None,
):
    """
    Set up ZMK Firmware

    Run "zmk init" to set up a user config repo. All other "zmk" commands will
    run in this repo unless the current working directory is a different repo.

    Once you have a config repo, run "zmk keyboard add" to add a keyboard to it.
    """
    cfg = Config(config_file)
    ctx.obj = cfg
