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
    """Set up ZMK Firmware"""
    cfg = Config(config_file)
    ctx.obj = cfg
