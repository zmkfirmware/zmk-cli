"""
"zmk remove" command.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Generic, Optional, TypeVar

import rich
import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.text import Text

from ...menu import show_menu
from ...templates import get_template_files
from ...util import fatal_error
from ..config import Config

T = TypeVar("T")


class KeyboardType(StrEnum):
    SHIELD = "shield"
    BOARD = "board"


class KeyboardLayout(StrEnum):
    UNIBODY = "unibody"
    SPLIT = "split"


@dataclass
class TemplateData:
    folder: str = ""
    dest: str = ""
    data: dict[str, str] = field(default_factory=dict)


class Detail(Generic[T]):
    MIN_PAD = 2

    data: T
    detail: str
    _pad_len: int

    def __init__(self, data: T, detail: str):
        self.data = data
        self.detail = detail
        self._pad_len = self.MIN_PAD

    def __rich__(self):
        return Text.assemble(self.data, " " * self._pad_len, (self.detail, "dim"))

    # pylint: disable=protected-access
    @classmethod
    def align(cls, items: list["Detail[T]"], console: Optional[Console] = None):
        console = console or rich.get_console()

        for item in items:
            item._pad_len = console.measure(item.data).minimum

        width = max(item._pad_len for item in items)

        for item in items:
            item._pad_len = width - item._pad_len + cls.MIN_PAD

        return items


ID_PATTERN = re.compile(r"[a-z_]\w*")
ID_HELP = (
    "Keyboard ID must use only lowercase letters, numbers, and underscores "
    "and must not start with a number."
)

MAX_NAME_LENGTH = 16
SHORT_NAME_HELP = f"Short name must be <= {MAX_NAME_LENGTH} characters."


def _is_valid_id(keyboard_id: str):
    return ID_PATTERN.fullmatch(keyboard_id)


def _is_valid_name(name: str):
    return bool(name)


def _is_valid_short_name(name: str):
    return 1 <= len(name) <= MAX_NAME_LENGTH


def _check_id(keyboard_id: Optional[str]):
    if keyboard_id and not _is_valid_id(keyboard_id):
        fatal_error(ID_HELP)


def _check_short_name(name: Optional[str]):
    if name and not _is_valid_short_name(name):
        fatal_error(SHORT_NAME_HELP)


def keyboard_new(
    ctx: typer.Context,
    keyboard_id: Annotated[
        Optional[str],
        typer.Option("--id", "-i", help="Board/shield ID.", callback=_check_id),
    ] = None,
    keyboard_name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Keyboard name."),
    ] = None,
    short_name: Annotated[
        Optional[str],
        typer.Option(
            "--shortname",
            "-s",
            help=f"Abbreviated keyboard name (<= {MAX_NAME_LENGTH} characters).",
            callback=_check_short_name,
        ),
    ] = None,
    keyboard_type: Annotated[
        Optional[KeyboardType],
        typer.Option(
            "--type",
            "-t",
            help="Type of keyboard to create.",
        ),
    ] = None,
    keyboard_layout: Annotated[
        Optional[KeyboardLayout],
        typer.Option("--layout", "-l", help="Keyboard hardware layout."),
    ] = None,
):
    """Create a new keyboard from a template."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    board_root = repo.board_root
    if not board_root:
        fatal_error('Cannot find repo\'s "boards" folder.')

    if not keyboard_name:
        keyboard_name = _prompt_keyboard_name()

    if not short_name:
        if len(keyboard_name) <= MAX_NAME_LENGTH:
            short_name = keyboard_name
        else:
            short_name = _prompt_keyboard_short_name()

    if not keyboard_id:
        keyboard_id = _prompt_keyboard_id(short_name)

    if not keyboard_type:
        keyboard_type = _prompt_keyboard_type()

    if not keyboard_layout:
        keyboard_layout = _prompt_keyboard_layout()

    template = _get_template(
        keyboard_type,
        keyboard_layout,
        keyboard_name=keyboard_name,
        short_name=short_name,
        keyboard_id=keyboard_id,
    )

    dest: Path = board_root / template.dest

    try:
        dest.mkdir(parents=True)
    except FileExistsError as exc:
        if not Confirm.ask(
            "This keyboard already exists. Overwrite it?", default=False
        ):
            raise typer.Exit() from exc

    for name, data in get_template_files(template.folder, **template.data):
        file = dest / name
        file.write_bytes(data.encode())

    rich.print()
    rich.print(f'Files were written to "{dest}".')
    rich.print(
        "Open this folder and edit the files to finish setting up the new keyboard."
    )
    rich.print("See https://zmk.dev/docs/development/new-shield for help.")


def _prompt_keyboard_type():
    items = Detail.align(
        [
            Detail(KeyboardType.SHIELD, "A PCB which uses a separate controller board"),
            Detail(KeyboardType.BOARD, "A standalone PCB with onboard controller"),
        ]
    )

    result = show_menu("Select a keyboard type:", items)
    return result.data


def _prompt_keyboard_layout():
    items = Detail.align(
        [
            Detail(KeyboardLayout.UNIBODY, "A keyboard with a single controller"),
            Detail(
                KeyboardLayout.SPLIT, "A keyboard with separate left/right controllers"
            ),
        ]
    )

    result = show_menu("Select a keyboard layout:", items)
    return result.data


def _prompt_keyboard_name():
    while True:
        result = Prompt.ask("[bright_magenta]Enter the keyboard name")

        if _is_valid_name(result):
            return result


def _prompt_keyboard_short_name():
    # TODO: reimplement this loop using PromptBase
    while True:
        result = Prompt.ask(
            f"[bright_magenta]Enter an abbreviated name (<= {MAX_NAME_LENGTH} chars)"
        )

        if _is_valid_short_name(result):
            return result

        rich.print(f"[red]{SHORT_NAME_HELP}")


def _prompt_keyboard_id(short_name: str):
    default_id = re.sub(r"\W+", "_", short_name).lower()

    # TODO: reimplement this loop using PromptBase
    while True:
        result = Prompt.ask("[bright_magenta]Enter a keyboard ID", default=default_id)

        if _is_valid_id(result):
            return result

        rich.print(f"[red]{ID_HELP}")


def _get_template(
    keyboard_type: KeyboardType,
    keyboard_layout: KeyboardLayout,
    keyboard_name: str,
    short_name: str,
    keyboard_id: str,
):
    template = TemplateData()
    template.data["name"] = keyboard_name
    template.data["shortname"] = short_name

    match keyboard_type:
        case KeyboardType.SHIELD:
            template.data["shield"] = keyboard_id
            template.folder = "shield/"
            template.dest = f"shields/{keyboard_id}"

        case _:
            template.data["board"] = keyboard_id
            template.folder = "board/"
            template.dest = f"arm/{keyboard_id}"

    match keyboard_layout:
        case KeyboardLayout.UNIBODY:
            template.folder += "unibody"

        case KeyboardLayout.SPLIT:
            template.folder += "split"

        case _:
            raise NotImplementedError()

    return template
