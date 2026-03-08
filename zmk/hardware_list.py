from collections.abc import Generator, Iterable
from dataclasses import dataclass, field
from functools import reduce
from pathlib import Path
from typing import TypeVar

from rich.console import Console

from .hardware import Board, BoardTarget, Hardware, Interconnect, Keyboard, Shield
from .menu import show_menu
from .repo import Repo
from .revision import Revision
from .styles import MENU_THEME, BoardIdHighlighter
from .util import flatten
from .yaml import read_yaml

_HW = TypeVar("_HW", bound=Hardware)


@dataclass
class HardwareGroups:
    """Hardware grouped by type."""

    keyboards: list[Board | Shield] = field(default_factory=list)
    """List of boards/shields that are keyboard PCBs"""
    controllers: list[Board] = field(default_factory=list)
    """List of boards that are controllers for keyboards"""
    interconnects: list[Interconnect] = field(default_factory=list)
    """List of interconnect descriptions"""

    # TODO: add displays and other peripherals?

    def find_keyboard(self, item_id: str) -> Board | Shield | None:
        """Find a keyboard by ID"""
        # Ignore any board revision provided
        target = BoardTarget.parse(item_id).with_revision(Revision())
        return _find_by_id(self.keyboards, str(target))

    def find_controller(self, item_id: str) -> Board | None:
        """Find a controller by ID"""
        # Ignore any board revision provided
        target = BoardTarget.parse(item_id).with_revision(Revision())
        return _find_by_id(self.controllers, str(target))

    def find_interconnect(self, item_id: str) -> Interconnect | None:
        """Find an interconnect by ID"""
        return _find_by_id(self.interconnects, item_id)

    def filter_compatible_keyboards(self, keyboard: Keyboard):
        """
        Modifies the "keyboards" list so it contains only shields compatible with
        the boards and shields in a given keyboard object.
        """
        self.keyboards = [
            kb
            for kb in self.keyboards
            if isinstance(kb, Shield) and keyboard.is_compatible(kb)
        ]

    def filter_compatible_controllers(self, keyboard: Keyboard):
        """
        Modifies the "controllers" list so it contains only boards compatible
        with the shields on a given keyboard object.
        """
        self.controllers = [c for c in self.controllers if keyboard.is_compatible(c)]

    def filter_to_interconnect(self, interconnect: Interconnect):
        """
        Modifies the "controllers" list so it contains only boards that expose
        the given interconnect.

        Modifies the "keyboards" list so it contains only shields that require
        the given interconnect and boards/shields that provide it.
        """
        self.controllers = [c for c in self.controllers if interconnect.id in c.exposes]
        self.keyboards = [
            kb
            for kb in self.keyboards
            if interconnect.id in kb.exposes
            or (isinstance(kb, Shield) and interconnect.id in kb.requires)
        ]


def _find_by_id(hardware: Iterable[_HW], item_id: str) -> _HW | None:
    norm_id = item_id.casefold()
    return next((hw for hw in hardware if norm_id in hw.get_normalized_ids()), None)


def _find_hardware(path: Path) -> Generator[Hardware, None, None]:
    for meta_path in path.rglob("*.zmk.yml"):
        meta = read_yaml(meta_path)
        meta["directory"] = meta_path.parent

        match meta.get("type"):
            case "board":
                yield Board.from_dict(meta)

            case "shield":
                yield Shield.from_dict(meta)

            case "interconnect":
                yield Interconnect.from_dict(meta)


def get_board_roots(repo: Repo) -> Iterable[Path]:
    """Get the paths that contain hardware definitions for a repo"""
    roots = set()

    if root := repo.board_root:
        roots.add(root)

    for module in repo.get_modules():
        if root := module.board_root:
            roots.add(root)

    return roots


def get_hardware(repo: Repo) -> HardwareGroups:
    """Get lists of hardware descriptions, grouped by type, for a repo"""
    hardware = flatten(_find_hardware(root) for root in get_board_roots(repo))

    def func(groups: HardwareGroups, item: Hardware):
        if isinstance(item, (Shield, Board)) and item.has_keys:
            groups.keyboards.append(item)
        elif isinstance(item, Board):
            groups.controllers.append(item)
        elif isinstance(item, Interconnect):
            groups.interconnects.append(item)

        return groups

    groups = reduce(func, hardware, HardwareGroups())

    groups.controllers = sorted(groups.controllers, key=lambda x: x.id)
    groups.keyboards = sorted(groups.keyboards, key=lambda x: x.id)
    groups.interconnects = sorted(groups.interconnects, key=lambda x: x.id)

    return groups


def show_hardware_menu(
    title: str,
    items: Iterable[_HW],
    console: Console | None = None,
    **kwargs,
) -> _HW:
    """
    Show a menu to select from a list of Hardware objects.

    kwargs are passed through to zmk.menu.show_menu(), except for filter_func,
    which is set to a function appropriate for filtering Hardware objects.
    """
    if console is None:
        console = Console(theme=MENU_THEME, highlighter=BoardIdHighlighter())

    def filter_hardware(item: Hardware, text: str):
        text = text.casefold().strip()
        return text in item.id.casefold() or text in item.name.casefold()

    return show_menu(
        title=title,
        items=items,
        console=console,
        filter_func=filter_hardware,
        **kwargs,
    )


def show_revision_menu(
    board: Board, title: str | None = None, console: Console | None = None, **kwargs
) -> Revision:
    """
    Show a menu to select from a list of revisions for a board.

    If the board has no revisions, returns Revision() without showing a menu.
    If the board has only one revision, returns it without showing a menu.

    kwargs are passed through to zmk.menu.show_menu(), except for default_index,
    which is set based on the board's default revision.
    """

    # Revisions could be listed in the .zmk.yml file in any order. Sort them
    # descending so the latest revisions appear at the top.
    revisions = sorted(board.revisions, reverse=True)
    if not revisions:
        return Revision()

    if len(revisions) == 1:
        return revisions[0]

    default_revision = board.default_revision
    default_index = revisions.index(default_revision) if default_revision else 0

    if console is None:
        # Disable the default highlighter so it doesn't colorize numbers
        console = Console(highlighter=None)

    return show_menu(
        title=title or f"Select a {board.name} revision:",
        items=revisions,
        default_index=default_index,
        console=console,
        **kwargs,
    )
