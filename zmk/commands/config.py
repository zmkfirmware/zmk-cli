"""
"zmk config" command.
"""

from typing import Annotated, Optional

import typer
from rich.console import Console

from .. import styles
from ..config import Config

console = Console(
    highlighter=styles.KeyValueHighlighter(), theme=styles.KEY_VALUE_THEME
)


def _path_callback(ctx: typer.Context, value: bool):
    if value:
        cfg = ctx.find_object(Config)
        print(cfg.path)
        raise typer.Exit()


def config(
    ctx: typer.Context,
    name: Annotated[
        Optional[str],
        typer.Argument(
            help="Setting name. Prints all setting values if omitted.",
        ),
    ] = None,
    value: Annotated[
        Optional[str],
        typer.Argument(help="New setting value. Prints the current value if omitted."),
    ] = None,
    unset: Annotated[
        bool,
        typer.Option("--unset", "-u", help="Remove the setting with the given name."),
    ] = False,
    _: Annotated[
        Optional[bool],
        typer.Option(
            "--path",
            "-p",
            help="Print the path to the ZMK CLI configuration file and exit.",
            is_eager=True,
            callback=_path_callback,
        ),
    ] = False,
):
    """Get and set ZMK CLI settings."""

    cfg = ctx.find_object(Config)

    if name is None:
        _list_settings(cfg)
    elif unset:
        _unset_setting(cfg, name)
    elif value:
        _set_setting(cfg, name, value)
    else:
        _get_setting(cfg, name)


def _list_settings(cfg: Config):
    for name, value in sorted(cfg.items()):
        console.print(f"{name}={value}")


def _unset_setting(cfg: Config, name: str):
    cfg.remove(name)
    cfg.write()


def _set_setting(cfg: Config, name: str, value: str):
    cfg.set(name, value)
    cfg.write()


def _get_setting(cfg: Config, name: str):
    if value := cfg.get(name, fallback=None):
        console.print(value)
