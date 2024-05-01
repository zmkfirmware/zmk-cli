"""
"zmk config" command.
"""

from typing import Annotated, Optional

import typer
from rich.console import Console

from .. import styles
from ..config import Config

console = Console(
    highlighter=styles.SeparatorHighlighter(), theme=styles.DIM_SEPARATORS
)


def config(
    ctx: typer.Context,
    settings: Annotated[
        Optional[list[str]],
        typer.Argument(
            metavar="[SETTING | SETTING=VALUE]",
            help="One or more settings to get or set.",
        ),
    ] = None,
    path: Annotated[
        bool,
        typer.Option(
            "--path",
            "-p",
            help="Print the path to the ZMK CLI configuration file and exit.",
        ),
    ] = False,
    unset: Annotated[
        bool,
        typer.Option("--unset", "-u", help="Unset the given settings."),
    ] = False,
):
    """Read or write ZMK CLI configuration. Lists all settings if run with no arguments."""

    cfg = ctx.find_object(Config)

    if path:
        print(cfg.path)
        return

    if unset:
        _unset_settings(cfg, settings)
    elif settings:
        _set_settings(cfg, settings)
    else:
        _list_settings(cfg)


def _set_settings(cfg: Config, settings: list[str]):
    show_name = len(settings) > 1
    do_write = False

    for setting in settings:
        name, equals, value = (_strip_quotes(s) for s in setting.partition("="))

        if equals:
            do_write = True
            _set(cfg, name, value)
        else:
            _get(cfg, name, show_name=show_name)

    if do_write:
        _write(cfg)


def _unset_settings(cfg: Config, settings: list[str]):
    for setting in settings:
        cfg.remove(setting)

    _write(cfg)


def _list_settings(cfg: Config):
    for name, value in sorted(cfg.items()):
        console.print(f"{name}={value}")


def _get(cfg: Config, name: str, show_name: bool):
    value = cfg.get(name, fallback="")
    if show_name:
        console.print(f"{name}={value}")
    else:
        console.print(value)


def _set(cfg: Config, name: str, value: str):
    previous = cfg.get(name, fallback=None)

    cfg.set(name, value)
    console.print(f"{name}: {previous} -> {value}")


def _write(cfg: Config):
    cfg.write()
    console.print(f"Configuration saved to {cfg.path}", highlight=False)


def _strip_quotes(value: str):
    value = value.strip()

    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]

    return value
