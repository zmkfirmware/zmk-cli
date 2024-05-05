"""
CLI tool to setup up ZMK Firmware.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer

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
    force_home: Annotated[
        bool,
        typer.Option(
            "--home",
            help="Use the home directory, even if the current directory is a repo.",
        ),
    ] = False,
):
    """
    Set up ZMK Firmware

    Run "zmk init" to set up a user config repo. All other "zmk" commands will
    run in this repo unless the current working directory is a different repo.

    Once you have a config repo, run "zmk keyboard add" to add a keyboard to it.
    """
    cfg = Config(config_file, force_home=force_home)
    ctx.obj = cfg
