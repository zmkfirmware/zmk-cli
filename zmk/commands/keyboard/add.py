"""
"zmk keyboard add" command.
"""

import shutil
from pathlib import Path
from typing import Annotated

import rich
import typer
from rich.padding import Padding

from ...build import BuildMatrix
from ...config import get_config
from ...exceptions import FatalError
from ...hardware import Board, BoardTarget, Keyboard, Shield
from ...hardware_list import get_hardware, show_hardware_menu, show_revision_menu
from ...repo import Repo
from ...revision import Revision
from ...styles import THEME, BoardIdHighlighter, chain_highlighters
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
    console.push_theme(THEME)
    console.highlighter = chain_highlighters(console.highlighter, BoardIdHighlighter())

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    with spinner("Finding hardware..."):
        hardware = get_hardware(repo)

    keyboard = Keyboard()

    if keyboard_id:
        # User specified a keyboard. It might be either a board (with optional
        # revision and board qualifiers) or a shield.
        target = BoardTarget.parse(keyboard_id)
        keyboard_id = target.name + target.qualifiers

        keys_component = hardware.find_keyboard(keyboard_id)
        if not keys_component:
            raise KeyboardNotFoundError(keyboard_id)

        keyboard.add_component(keys_component)
        if target.revision:
            _check_revision(keys_component, target.revision)
            keyboard.board_revision = target.revision

        if controller_id:
            # User also specified a controller board (with optional revision and
            # board qualifiers). If the specified keyboard was already a board,
            # then this is invalid because we can't have two boards.
            if keyboard.board:
                raise FatalError(
                    f'Keyboard "{keys_component.id}" has an onboard controller '
                    "and does not require a controller board."
                )

            target = BoardTarget.parse(controller_id)
            controller_id = target.name + target.qualifiers

            controller = hardware.find_controller(controller_id)
            if not controller:
                raise ControllerNotFoundError(controller_id)

            keyboard.add_component(controller)
            if target.revision:
                _check_revision(controller, target.revision)
                keyboard.board_revision = target.revision

    elif controller_id:
        # User specified a controller but not a keyboard. Find the controller.
        # We will prompt for the shield later.

        target = BoardTarget.parse(controller_id)

        controller = hardware.find_controller(controller_id)
        if not controller:
            raise ControllerNotFoundError(controller_id)

        keyboard.add_component(controller)
        if target.revision:
            _check_revision(controller, target.revision)
            keyboard.board_revision = target.revision

        # When prompting for a keyboard later, it should only display the shields
        # that are compatible with the chosen board.
        hardware.filter_compatible_keyboards(keyboard)

    # Prompt the user for any necessary components they didn't specify
    if not keyboard.keys_component:
        keyboard.add_component(
            show_hardware_menu("Select a keyboard:", hardware.keyboards)
        )

    if not keyboard.board:
        hardware.filter_compatible_controllers(keyboard)

        keyboard.add_component(
            show_hardware_menu("Select a controller:", hardware.controllers)
        )

    # Sanity check the resulting hardware compatibility
    if not keyboard.board:
        raise FatalError(
            "Controller board is missing (this is probably a bug in ZMK CLI)."
        )

    if not keyboard.keys_component:
        raise FatalError(
            "Component with 'keys' feature is missing (this is probably a bug in ZMK CLI)."
        )

    if keyboard.missing_requirements:
        raise FatalError(
            f'Keyboard "{keyboard.keys_component}" is not compatible with controller "{keyboard.board}". '
            f"Required interconnects are missing: {', '.join(keyboard.missing_requirements)}"
        )

    # If a revision wasn't already set from the command line, the user may need
    # to choose a revision.
    if not keyboard.board_revision and keyboard.board_revisions:
        keyboard.board_revision = show_revision_menu(keyboard.board)

    if added := _add_keyboard(repo, keyboard):
        console.print("[title]Added:")

        for item in added:
            console.print(Padding.indent(item, 2))

        console.print()
    else:
        name = keyboard.keys_component.name
        console.print(f'"{name}" is already in the build matrix.')

    keymap_name = keyboard.get_keymap_path().with_suffix("").name

    console.print(f'Run "zmk code {keymap_name}" to edit the keymap.')


class KeyboardNotFoundError(FatalError):
    """Fatal error for an invalid keyboard ID"""

    def __init__(self, keyboard_id: str):
        super().__init__(f'Could not find a keyboard with ID "{keyboard_id}"')


class ControllerNotFoundError(FatalError):
    """Fatal error for an invalid controller ID"""

    def __init__(self, controller_id: str):
        super().__init__(f'Could not find a controller board with ID "{controller_id}"')


def _copy_keyboard_file(repo: Repo, path: Path):
    dest_path = repo.config_path / path.name
    if path.exists() and not dest_path.exists():
        shutil.copy2(path, dest_path)


def _check_revision(board: Board | Shield, revision: Revision):
    if not isinstance(board, Board):
        raise FatalError(f"{board.id} is a shield. Only boards support revisions.")

    if revision in board.revisions:
        # Revision is OK
        return

    if not board.revisions:
        raise FatalError(f"{board.id} does not have any revisions.")

    raise FatalError(
        f'{board.id} does not support revision "@{revision}". Use one of:\n'
        + "\n".join(f"  @{rev}" for rev in board.revisions)
    )


def _add_keyboard(repo: Repo, keyboard: Keyboard):
    items = keyboard.get_build_items()

    _copy_keyboard_file(repo, keyboard.get_keymap_path())
    _copy_keyboard_file(repo, keyboard.get_config_path())

    matrix = BuildMatrix.from_repo(repo)
    added = matrix.append(items)
    matrix.write()

    return added
