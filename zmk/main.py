from pathlib import Path
from typing import Optional
import typer
from typing_extensions import Annotated

from .config import Config
from . import subcommands

app = typer.Typer(short_help="h")
subcommands.register(app)


@app.callback()
def main(
    ctx: typer.Context,
    home: Annotated[
        Optional[Path],
        typer.Option(envvar="ZMK_HOME", help="Path to the ZMK config repo."),
    ] = None,
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

    if home:
        cfg.home_path = home
