"""
"zmk keyboard add" command.
"""

import itertools
import shutil
from pathlib import Path
from typing import Annotated, Optional

import rich
import typer

from ...build import BuildItem, BuildMatrix
from ...exceptions import FatalError
from ...hardware import Board, Keyboard, Shield, get_hardware, is_compatible
from ...menu import show_menu
from ...repo import Repo
from ...util import spinner
from ..config import Config


def keyboard_add(
    ctx: typer.Context,
    controller_id: Annotated[
        Optional[str],
        typer.Option(
            "--controller",
            "-c",
            metavar="CONTROLLER",
            help="ID of the controller board to add.",
        ),
    ] = None,
    keyboard_id: Annotated[
        Optional[str],
        typer.Option(
            "--keyboard",
            "--kb",
            "-k",
            metavar="KEYBOARD",
            help="ID of the keyboard board/shield to add.",
        ),
    ] = None,
):
    """Add configuration for a keyboard and add it to the build."""

    console = rich.get_console()

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    with spinner("Finding hardware..."):
        hardware = get_hardware(repo)

    keyboard = None
    controller = None

    if keyboard_id:
        keyboard = hardware.find_keyboard(keyboard_id)
        _check_keyboard_found(keyboard, keyboard_id)

        if controller_id:
            if not isinstance(keyboard, Shield):
                raise FatalError(
                    f'Keyboard "{keyboard.id}" has an onboard controller '
                    "and does not require a controller board."
                )

            controller = hardware.find_controller(controller_id)
            _check_controller_found(controller, controller_id)

    elif controller_id:
        # User specified a controller but not a keyboard. Filter the keyboard
        # list to just those compatible with the controller.
        controller = hardware.find_controller(controller_id)
        _check_controller_found(controller, controller_id)

        hardware.keyboards = [
            kb
            for kb in hardware.keyboards
            if isinstance(kb, Shield) and is_compatible(controller, kb)
        ]

    # Prompt the user for any necessary components they didn't specify
    if keyboard is None:
        keyboard = show_menu(
            "Select a keyboard:", hardware.keyboards, filter_func=_filter
        )

    if isinstance(keyboard, Shield) and controller is None:
        hardware.controllers = [
            c for c in hardware.controllers if is_compatible(c, keyboard)
        ]
        controller = show_menu(
            "Select a controller:", hardware.controllers, filter_func=_filter
        )

    # Sanity check that everything is compatible
    if keyboard and controller and not is_compatible(controller, keyboard):
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


def _filter(item: Board | Shield, text: str):
    text = text.casefold().strip()
    return text in item.id.casefold() or text in item.name.casefold()


def _check_keyboard_found(keyboard: Optional[Keyboard], keyboard_id: str):
    if keyboard is None:
        raise FatalError(f'Could not find a keyboard with ID "{keyboard_id}"')


def _check_controller_found(controller: Optional[Board], controller_id: str):
    if controller is None:
        raise FatalError(f'Could not find a controller board with ID "{controller_id}"')


def _copy_keyboard_file(repo: Repo, path: Path):
    dest_path = repo.config_path / path.name
    if path.exists() and not dest_path.exists():
        shutil.copy2(path, dest_path)


def _get_build_items(keyboard: Keyboard, controller: Optional[Board]):
    boards = []
    shields = []

    match keyboard:
        case Shield(id=shield_id, siblings=siblings):
            shields = siblings or [shield_id]
            boards = [controller.id]

        case Board(id=board_id, siblings=siblings):
            boards = siblings or [board_id]

        case _:
            raise ValueError("Unexpected keyboard/controller combination")

    return [BuildItem(board=b, shield=s) for b, s in itertools.product(boards, shields)]


def _add_keyboard(repo: Repo, keyboard: Keyboard, controller: Optional[Board]):
    _copy_keyboard_file(repo, keyboard.keymap_path)
    _copy_keyboard_file(repo, keyboard.config_path)

    items = _get_build_items(keyboard, controller)

    matrix = BuildMatrix.from_repo(repo)
    added = matrix.append(items)
    matrix.write()

    return added
