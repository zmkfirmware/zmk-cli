"""
"zmk keyboard list" command.
"""

from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated

import typer
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.table import Table

from zmk import styles

from ...build import BuildMatrix
from ...config import get_config
from ...exceptions import FatalError
from ...hardware import Board, BoardTarget, BuildItem, Hardware, Keyboard, Shield
from ...hardware_list import get_hardware
from ...util import spinner

# TODO: allow output as unformatted list
# TODO: allow output as more detailed metadata
# TODO: allow search for items by glob pattern


class ListType(StrEnum):
    """Type of hardware to display"""

    ALL = "all"
    KEYBOARD = "keyboard"
    CONTROLLER = "controller"
    INTERCONNECT = "interconnect"


def _list_build_matrix(ctx: typer.Context, *, value: bool):
    if not value:
        return

    console = Console(
        highlighter=styles.chain_highlighters(
            styles.BoardIdHighlighter(), styles.CommandLineHighlighter()
        ),
        theme=styles.THEME,
    )

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    matrix = BuildMatrix.from_repo(repo)
    include = matrix.include

    has_snippet = any(item.snippet for item in include)
    has_cmake_args = any(item.cmake_args for item in include)
    has_artifact_name = any(item.artifact_name for item in include)

    table = Table(
        box=box.ROUNDED,
        border_style="dim blue",
        header_style="bright_cyan",
        highlight=True,
    )
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
    *,
    _: Annotated[
        bool | None,
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
    ] = ListType.ALL,
    board: Annotated[
        str | None,
        typer.Option(
            "--board",
            "-b",
            metavar="BOARD",
            help="List keyboards compatible with this controller board.",
        ),
    ] = None,
    shield: Annotated[
        str | None,
        typer.Option(
            "--shield",
            "-s",
            metavar="SHIELD",
            help="List controllers compatible with this keyboard shield.",
        ),
    ] = None,
    interconnect: Annotated[
        str | None,
        typer.Option(
            "--interconnect",
            "-i",
            metavar="INTERCONNECT",
            help="List keyboards and controllers that use this interconnect.",
        ),
    ] = None,
    standalone: Annotated[
        bool,
        typer.Option(
            "--standalone", help="List only keyboards with onboard controllers."
        ),
    ] = False,
    revisions: Annotated[
        bool,
        typer.Option(
            "--revisions", "--rev", "-r", help="Display revisions for each board."
        ),
    ] = False,
) -> None:
    """List supported keyboards or keyboards in the build matrix."""

    console = Console(highlighter=styles.BoardIdHighlighter(), theme=styles.THEME)

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    with spinner("Finding hardware..."):
        groups = get_hardware(repo)

    if board:
        # Filter to keyboard shields compatible with a given controller.
        item = groups.find_controller(board)
        if item is None:
            raise FatalError(f'Could not find controller board "{board}".')

        keyboard = Keyboard()
        keyboard.add_component(item)
        groups.filter_compatible_keyboards(keyboard)
        list_type = ListType.KEYBOARD

    elif shield:
        # Filter to controllers compatible with a given keyboard shield.
        item = groups.find_keyboard(shield)
        if item is None:
            raise FatalError(f'Could not find keyboard "{shield}".')

        if not isinstance(item, Shield):
            raise FatalError(f'Keyboard "{shield}" is a standalone keyboard.')

        keyboard = Keyboard()
        keyboard.add_component(item)
        groups.filter_compatible_controllers(keyboard)
        list_type = ListType.CONTROLLER

    elif interconnect:
        # Filter to controllers that provide an interconnect and keyboards that
        # use or provide it.
        item = groups.find_interconnect(interconnect)
        if item is None:
            raise FatalError(f'Could not find interconnect "{interconnect}".')

        groups.filter_to_interconnect(item)

        # When filtering to an interconnect, don't show interconnects.
        groups.interconnects = []

    elif standalone:
        # Filter to keyboards with on-board controllers
        groups.keyboards = [kb for kb in groups.keyboards if isinstance(kb, Board)]
        list_type = ListType.KEYBOARD

    def print_items(header: str, items: Iterable[Hardware]):
        names: list[str] = []

        for item in items:
            if revisions and isinstance(item, Board):
                names.extend(
                    str(BoardTarget.parse(item.id).with_revision(rev))
                    for rev in item.revisions
                )
            else:
                names.append(item.id)

        if not names:
            return

        if list_type == ListType.ALL:
            console.print(header, style="green")

        columns = Columns(names, padding=(0, 2), equal=True, column_first=True)
        console.print(columns)
        console.print()

    # TODO: when filtering to an interconnect, we should specify which hardware
    # exposes vs. which requires. This would be useful if we start to add things
    # like non-keyboard shields to the hardware info.

    if list_type in (ListType.ALL, ListType.KEYBOARD):
        print_items("Keyboards:", groups.keyboards)

    if list_type in (ListType.ALL, ListType.CONTROLLER):
        print_items("Controllers:", groups.controllers)

    if list_type in (ListType.ALL, ListType.INTERCONNECT):
        print_items("Interconnects:", groups.interconnects)
