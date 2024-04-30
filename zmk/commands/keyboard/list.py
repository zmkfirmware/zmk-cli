"""
"zmk keyboard list" command.
"""

from enum import StrEnum
from typing import Annotated, Iterable, Optional

import typer
from rich.columns import Columns
from rich.console import Console

from ...hardware import Board, Hardware, Shield, get_hardware, is_compatible
from ..config import Config

# TODO: allow filtering output by interconnect
# TODO: allow output as unformatted list
# TODO: allow output as more detailed metadata
# TODO: allow search for items by glob pattern


class ListType(StrEnum):
    ALL = "all"
    KEYBOARD = "keyboard"
    CONTROLLER = "controller"
    INTERCONNECT = "interconnect"


def keyboard_list(
    ctx: typer.Context,
    list_type: Annotated[
        ListType,
        typer.Option(
            "--type",
            "-t",
            help="List only items of this type.",
        ),
    ] = "all",
    board: Annotated[
        Optional[str],
        typer.Option(
            "--board",
            "-b",
            metavar="BOARD",
            help="List only keyboards compatible with this controller board.",
        ),
    ] = None,
    shield: Annotated[
        Optional[str],
        typer.Option(
            "--shield",
            "-s",
            metavar="SHIELD",
            help="List only controllers compatible with this keyboard shield.",
        ),
    ] = None,
    standalone: Annotated[
        bool,
        typer.Option(
            "--standalone", help="List only keyboards with onboard controllers."
        ),
    ] = False,
):
    """Print a list of supported keyboards."""

    console = Console()

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()
    groups = get_hardware(repo)

    if board:
        # Filter to keyboard shields compatible with a given controller.
        item = groups.find_controller(board)
        if item is None:
            console.print(f'Could not find controller board "{board}".')
            raise typer.Exit(code=1)

        groups.keyboards = [kb for kb in groups.keyboards if is_compatible(item, kb)]
        list_type = ListType.KEYBOARD

    elif shield:
        # Filter to controllers compatible with a given keyboard shield.
        item = groups.find_keyboard(shield)
        if item is None:
            console.print(f'Could not find keyboard "{shield}".')
            raise typer.Exit(code=1)

        if not isinstance(item, Shield):
            console.print(f'Keyboard "{shield}" is a standalone keyboard.')
            raise typer.Exit(code=1)

        groups.controllers = [c for c in groups.controllers if is_compatible(c, item)]
        list_type = ListType.CONTROLLER

    elif standalone:
        # Filter to keyboards with on-board controllers
        groups.keyboards = [kb for kb in groups.keyboards if isinstance(kb, Board)]
        list_type = ListType.KEYBOARD

    def print_items(header: str, items: Iterable[Hardware]):
        if list_type == ListType.ALL:
            console.print(header, style="green")

        names = [item.id for item in items]

        columns = Columns(names, padding=(0, 2), equal=True, column_first=True)
        console.print(columns)
        console.print()

    if list_type in (ListType.ALL, ListType.KEYBOARD):
        print_items("Keyboards:", groups.keyboards)

    if list_type in (ListType.ALL, ListType.CONTROLLER):
        print_items("Controllers:", groups.controllers)

    if list_type in (ListType.ALL, ListType.INTERCONNECT):
        print_items("Interconnects:", groups.interconnects)
