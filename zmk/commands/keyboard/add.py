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
    Hardware,
    Keyboard,
    Shield,
    append_revision,
    get_hardware,
    is_compatible,
    normalize_revision,
    show_hardware_menu,
    show_revision_menu,
    split_revision,
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
    revision = None

    if keyboard_id:
        keyboard_id, keyboard_revision = split_revision(keyboard_id)

        keyboard = hardware.find_keyboard(keyboard_id)
        if keyboard is None:
            raise KeyboardNotFound(keyboard_id)

        # If the keyboard ID contained a revision, use that.
        # Make sure it is valid before continuing to any other prompts.
        if keyboard_revision:
            revision = keyboard_revision
            _check_revision(keyboard, revision)

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
        controller_id, controller_revision = split_revision(controller_id)

        # User specified a controller but not a keyboard. Filter the keyboard
        # list to just those compatible with the controller.
        controller = hardware.find_controller(controller_id)
        if controller is None:
            raise ControllerNotFound(controller_id)

        # If the controller ID contained a revision, use that.
        # Make sure it is valid before continuing to any other prompts.
        if controller_revision:
            revision = controller_revision
            _check_revision(controller, revision)

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

        # Check if the controller needs a revision.
        revision = _get_revision(controller, revision)
    else:
        # If the keyboard isn't a shield, it may need a revision.
        revision = _get_revision(keyboard, revision)

    name = keyboard.id
    if controller:
        name += ", " + controller.id

    if revision:
        revision = normalize_revision(revision)
        name = append_revision(name, revision)

    if _add_keyboard(repo, keyboard, controller, revision):
        console.print(f'Added "{name}".')
    else:
        console.print(f'"{name}" is already in the build matrix.')

    keymap_name = keyboard.get_keymap_path(revision).with_suffix("").name

    console.print(f'Run "zmk code {keymap_name}" to edit the keymap.')


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


def _get_build_items(
    keyboard: Keyboard, controller: Board | None, revision: str | None
):
    boards = []
    shields = []

    match keyboard:
        case Shield(id=shield_id, siblings=siblings):
            if controller is None:
                raise FatalError("controller may not be None if keyboard is a shield")

            shields = siblings or [shield_id]
            boards = [append_revision(controller.id, revision)]

        case Board(id=board_id, siblings=siblings):
            boards = siblings or [board_id]
            boards = [append_revision(board, revision) for board in boards]

        case _:
            raise FatalError("Unexpected keyboard/controller combination")

    if shields:
        return [
            BuildItem(board=b, shield=s) for b, s in itertools.product(boards, shields)
        ]

    return [BuildItem(board=b) for b in boards]


def _get_revision(board: Hardware, revision: str | None):
    # If no revision was specified and the board uses revisions, prompt to
    # select a revision.
    return revision if revision else show_revision_menu(board)


def _check_revision(board: Hardware, revision: str):
    if board.has_revision(revision):
        # Revision is OK
        return

    supported_revisions = board.get_revisions()

    if not supported_revisions:
        raise FatalError(f"{board.id} does not have any revisions.")

    raise FatalError(
        f'{board.id} does not support revision "@{revision}". Use one of:\n'
        + "\n".join(f"  @{normalize_revision(rev)}" for rev in supported_revisions)
    )


def _add_keyboard(
    repo: Repo, keyboard: Keyboard, controller: Board | None, revision: str | None
):
    _copy_keyboard_file(repo, keyboard.get_keymap_path(revision))
    _copy_keyboard_file(repo, keyboard.get_config_path(revision))

    items = _get_build_items(keyboard, controller, revision)

    matrix = BuildMatrix.from_repo(repo)
    added = matrix.append(items)
    matrix.write()

    return added
