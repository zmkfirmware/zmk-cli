"""
CLI tool to setup up ZMK Firmware.
"""

from importlib import metadata
from pathlib import Path
from typing import Annotated, Optional

import typer

from . import commands
from .config import Config

app = typer.Typer(rich_markup_mode="rich")
commands.register(app)


def _version_callback(version: bool):
    if version:
        print(metadata.version("zmk"))
        raise typer.Exit()


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
    _: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
):
    """
    ZMK Firmware command line tool

    Run "zmk init" to set up a ZMK config repo. All other "zmk" commands will
    run in this repo unless the current working directory is a different repo.
    """
    cfg = Config(config_file, force_home=force_home)
    ctx.obj = cfg
