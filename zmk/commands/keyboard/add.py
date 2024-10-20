"""
"zmk keyboard add" command.
"""

import itertools
import shutil
from pathlib import Path
from typing import Annotated

import rich
import typer

from ...build import BuildItem, BuildMatrix
from ...config import get_config
from ...exceptions import FatalError
from ...hardware import (
    Board,
    Keyboard,
    Shield,
    get_hardware,
    is_compatible,
    show_hardware_menu,
)
from ...repo import Repo
from ...util import spinner


def keyboard_add(
    ctx: typer.Context,
    controller_id: Annotated[
        str | None,
        typer.Option(
            "--controller",
            "-c",
            metavar="CONTROLLER",
            help="ID of the controller board to add.",
        ),
    ] = None,
    keyboard_id: Annotated[
        str | None,
        typer.Option(
            "--keyboard",
            "--kb",
            "-k",
            metavar="KEYBOARD",
            help="ID of the keyboard board/shield to add.",
        ),
    ] = None,
) -> None:
    """Add configuration for a keyboard and add it to the build."""

    console = rich.get_console()

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    with spinner("Finding hardware..."):
        hardware = get_hardware(repo)

    keyboard = None
    controller = None

    if keyboard_id:
        keyboard = hardware.find_keyboard(keyboard_id)
        if keyboard is None:
            raise KeyboardNotFound(keyboard_id)

        if controller_id:
            if not isinstance(keyboard, Shield):
                raise FatalError(
                    f'Keyboard "{keyboard.id}" has an onboard controller '
                    "and does not require a controller board."
                )

            controller = hardware.find_controller(controller_id)
            if controller is None:
                raise ControllerNotFound(controller_id)

    elif controller_id:
        # User specified a controller but not a keyboard. Filter the keyboard
        # list to just those compatible with the controller.
        controller = hardware.find_controller(controller_id)
        if controller is None:
            raise ControllerNotFound(controller_id)

        hardware.keyboards = [
            kb
            for kb in hardware.keyboards
            if isinstance(kb, Shield) and is_compatible(controller, kb)
        ]

    # Prompt the user for any necessary components they didn't specify
    if keyboard is None:
        keyboard = show_hardware_menu("Select a keyboard:", hardware.keyboards)

    if isinstance(keyboard, Shield):
        if controller is None:
            hardware.controllers = [
                c for c in hardware.controllers if is_compatible(c, keyboard)
            ]
            controller = show_hardware_menu(
                "Select a controller:", hardware.controllers
            )

        # Sanity check that everything is compatible
        if not is_compatible(controller, keyboard):
            raise FatalError(
                f'Keyboard "{keyboard.id}" is not compatible with controller "{controller.id}"'
            )

    name = keyboard.id
    if controller:
        name += ", " + controller.id

    if _add_keyboard(repo, keyboard, controller):
        console.print(f'Added "{name}".')
    else:
        console.print(f'"{name}" is already in the build matrix.')

    console.print(f'Run "zmk code {keyboard.id}" to edit the keymap.')


class KeyboardNotFound(FatalError):
    """Fatal error for an invalid keyboard ID"""

    def __init__(self, keyboard_id: str):
        super().__init__(f'Could not find a keyboard with ID "{keyboard_id}"')


class ControllerNotFound(FatalError):
    """Fatal error for an invalid controller ID"""

    def __init__(self, controller_id: str):
        super().__init__(f'Could not find a controller board with ID "{controller_id}"')


def _copy_keyboard_file(repo: Repo, path: Path):
    dest_path = repo.config_path / path.name
    if path.exists() and not dest_path.exists():
        shutil.copy2(path, dest_path)


def _get_build_items(keyboard: Keyboard, controller: Board | None):
    boards = []
    shields = []

    match keyboard:
        case Shield(id=shield_id, siblings=siblings):
            if controller is None:
                raise ValueError("controller may not be None if keyboard is a shield")

            shields = siblings or [shield_id]
            boards = [controller.id]

        case Board(id=board_id, siblings=siblings):
            boards = siblings or [board_id]

        case _:
            raise ValueError("Unexpected keyboard/controller combination")

    return [BuildItem(board=b, shield=s) for b, s in itertools.product(boards, shields)]


def _add_keyboard(repo: Repo, keyboard: Keyboard, controller: Board | None):
    _copy_keyboard_file(repo, keyboard.keymap_path)
    _copy_keyboard_file(repo, keyboard.config_path)

    items = _get_build_items(keyboard, controller)

    matrix = BuildMatrix.from_repo(repo)
    added = matrix.append(items)
    matrix.write()

    return added
