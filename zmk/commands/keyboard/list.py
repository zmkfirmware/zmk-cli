"""
"zmk keyboard list" command.
"""

from typing import Annotated, Iterable, Optional

import rich
import typer
from rich import box
from rich.columns import Columns
from rich.table import Table

from ...backports import StrEnum
from ...build import BuildItem, BuildMatrix
from ...exceptions import FatalError
from ...hardware import Board, Hardware, Shield, get_hardware, is_compatible
from ...util import spinner
from ..config import Config

# TODO: allow output as unformatted list
# TODO: allow output as more detailed metadata
# TODO: allow search for items by glob pattern


class ListType(StrEnum):
    """Type of hardware to display"""

    ALL = "all"
    KEYBOARD = "keyboard"
    CONTROLLER = "controller"
    INTERCONNECT = "interconnect"


def _list_build_matrix(ctx: typer.Context, value: bool):
    if not value:
        return

    console = rich.get_console()

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    matrix = BuildMatrix.from_repo(repo)
    include = matrix.include

    has_snippet = any(item.snippet for item in include)
    has_cmake_args = any(item.cmake_args for item in include)
    has_artifact_name = any(item.artifact_name for item in include)

    table = Table(box=box.SQUARE, border_style="dim blue", header_style="bright_cyan")
    table.add_column("Board")
    table.add_column("Shield")
    if has_snippet:
        table.add_column("Snippet")
    if has_artifact_name:
        table.add_column("Artifact Name")
    if has_cmake_args:
        table.add_column("CMake Args")

    def add_row(item: BuildItem):
        cols = [item.board, item.shield]
        if has_snippet:
            cols.append(item.snippet)
        if has_artifact_name:
            cols.append(item.artifact_name)
        if has_cmake_args:
            cols.append(item.cmake_args)

        table.add_row(*cols)

    for item in include:
        add_row(item)

    console.print(table)

    raise typer.Exit()


def keyboard_list(
    ctx: typer.Context,
    _: Annotated[
        Optional[bool],
        typer.Option(
            "--build",
            help="Show the build matrix.",
            is_eager=True,
            callback=_list_build_matrix,
        ),
    ] = None,
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
    interconnect: Annotated[
        Optional[str],
        typer.Option(
            "--interconnect",
            "-i",
            metavar="INTERCONNECT",
            help="List only keyboards and controllers that have this interconnect.",
        ),
    ] = None,
    standalone: Annotated[
        bool,
        typer.Option(
            "--standalone", help="List only keyboards with onboard controllers."
        ),
    ] = False,
):
    """List supported keyboards or keyboards in the build matrix."""

    console = rich.get_console()

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    with spinner("Finding hardware..."):
        groups = get_hardware(repo)

    if board:
        # Filter to keyboard shields compatible with a given controller.
        item = groups.find_controller(board)
        if item is None:
            raise FatalError(f'Could not find controller board "{board}".')

        groups.keyboards = [kb for kb in groups.keyboards if is_compatible(item, kb)]
        list_type = ListType.KEYBOARD

    elif shield:
        # Filter to controllers compatible with a given keyboard shield.
        item = groups.find_keyboard(shield)
        if item is None:
            raise FatalError(f'Could not find keyboard "{shield}".')

        if not isinstance(item, Shield):
            raise FatalError(f'Keyboard "{shield}" is a standalone keyboard.')

        groups.controllers = [c for c in groups.controllers if is_compatible(c, item)]
        list_type = ListType.CONTROLLER

    elif interconnect:
        # Filter to controllers that provide an interconnect and keyboards that use it.
        item = groups.find_interconnect(interconnect)
        if item is None:
            raise FatalError(f'Could not find interconnect "{interconnect}".')

        groups.controllers = [c for c in groups.controllers if item.id in c.exposes]
        groups.keyboards = [
            kb
            for kb in groups.keyboards
            if isinstance(kb, Shield) and item.id in kb.requires
        ]
        groups.interconnects = []

    elif standalone:
        # Filter to keyboards with on-board controllers
        groups.keyboards = [kb for kb in groups.keyboards if isinstance(kb, Board)]
        list_type = ListType.KEYBOARD

    def print_items(header: str, items: Iterable[Hardware]):
        names = [item.id for item in items]
        if not names:
            return

        if list_type == ListType.ALL:
            console.print(header, style="green")

        columns = Columns(names, padding=(0, 2), equal=True, column_first=True)
        console.print(columns)
        console.print()

    if list_type in (ListType.ALL, ListType.KEYBOARD):
        print_items("Keyboards:", groups.keyboards)

    if list_type in (ListType.ALL, ListType.CONTROLLER):
        print_items("Controllers:", groups.controllers)

    if list_type in (ListType.ALL, ListType.INTERCONNECT):
        print_items("Interconnects:", groups.interconnects)
