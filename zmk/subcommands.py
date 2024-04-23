import importlib
from pathlib import Path

from typer import Typer
from typer.models import CommandFunctionType


class _commands:
    commands: list[CommandFunctionType] = []


def command(func: CommandFunctionType):
    """
    Decorator to mark a function as a top-level command
    """
    _commands.commands.append(func)
    return func


def register(app: Typer):
    """
    Imports all files in the "commands" subdirectory, then registers all functions
    decorated with @command as subcommands of the given app.
    """
    commands_dir = Path(__file__).parent / "commands"

    for module in commands_dir.glob("*.py"):
        name = module.with_suffix("").name

        importlib.import_module(f".{commands_dir.name}.{name}", package=__package__)

    for cmd in _commands.commands:
        app.command()(cmd)
