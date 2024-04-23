from typing import Optional
from typing_extensions import Annotated
from rich.console import Console
import typer

from .. import styles
from ..config import Config
from ..subcommands import command

console = Console(
    highlighter=styles.SeparatorHighlighter(), theme=styles.DIM_SEPARATORS
)


@command
def config(
    ctx: typer.Context,
    settings: Annotated[
        Optional[list[str]],
        typer.Argument(
            metavar="[SETTING | SETTING=VALUE]",
            help="One or more settings to get or set.",
        ),
    ] = None,
):
    """Read or write ZMK CLI configuration. Lists all settings if run with no arguments."""

    cfg = ctx.find_object(Config)

    if not settings:
        _list(cfg)
        return

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
        cfg.write()
        console.print(f"Configuration saved to {cfg.path}", highlight=False)


def _list(cfg: Config):
    for name, value in sorted(cfg.items()):
        console.print(f"{name}={value}")


def _get(cfg: Config, name: str, show_name: bool):
    value = cfg.get(name, fallback="")
    if show_name:
        console.print(f"{name}={value}")
    else:
        console.print(value)


def _set(cfg: Config, name: str, value: Optional[str] = None):
    value = value or None
    previous = cfg.get(name, fallback=None)

    cfg.set(name, value)
    console.print(f"{name}: {previous} -> {value}")


def _strip_quotes(value: str):
    value = value.strip()

    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]

    return value
