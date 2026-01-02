"""
Hardware metadata discovery and processing.
"""

import re
from collections.abc import Generator, Iterable
from dataclasses import dataclass, field
from functools import reduce
from pathlib import Path
from typing import Any, Literal, Type, TypeAlias, TypedDict, TypeGuard, TypeVar

import dacite

from .menu import show_menu
from .repo import Repo
from .util import flatten
from .yaml import read_yaml

Feature: TypeAlias = (
    Literal["keys", "display", "encoder", "underglow", "backlight", "pointer", "studio"]
    | str
)
Output: TypeAlias = Literal["usb", "ble"]


class VariantDict(TypedDict):
    """Keyboard variant with custom options"""

    id: str
    features: list[Feature]


Variant: TypeAlias = str | VariantDict

# TODO: replace with typing.Self once minimum Python version is >= 3.11
_Self = TypeVar("_Self", bound="Hardware")

_HW = TypeVar("_HW", bound="Hardware")


@dataclass
class Hardware:
    """Base class for keyboard hardware"""

    directory: Path
    """Path to the directory containing this hardware"""

    type: str
    id: str
    name: str

    file_format: str | None = None
    url: str | None = None
    description: str | None = None
    manufacturer: str | None = None
    version: str | None = None

    def __str__(self) -> str:
        return self.id

    def __rich__(self) -> Any:
        return f"{self.id}  [dim]{self.name}"

    @classmethod
    def from_dict(cls: "Type[_Self]", data) -> _Self:
        """Read a hardware description from a dict"""
        return dacite.from_dict(cls, data)

    def has_id(self, hardware_id: str) -> bool:
        """Get whether this hardware has the given ID (case insensitive)"""
        return hardware_id.casefold() == self.id.casefold()

    def has_revision(self, revision: str) -> bool:
        """
        Get whether this hardware supports the given revision.

        Any empty string is treated as "default revision" and always returns True.
        """
        # By default, the only supported revision is no revision at all.
        return not revision

    def get_revisions(self) -> list[str]:
        """Get a list of supported revisions"""
        return []

    def get_default_revision(self) -> str | None:
        """Get the default item from get_revisions or None if no default is set"""
        return None


@dataclass
class Interconnect(Hardware):
    """Description of the connection between two pieces of hardware"""

    node_labels: dict[str, str] = field(default_factory=dict)
    design_guideline: str | None = None


@dataclass
class Keyboard(Hardware):
    """Base class for hardware that forms a keyboard"""

    siblings: list[str] | None = field(default_factory=list)
    """List of board/shield IDs for a split keyboard"""
    exposes: list[str] | None = field(default_factory=list)
    """List of interconnect IDs this board/shield provides"""
    features: list[Feature] | None = field(default_factory=list)
    """List of features this board/shield supports"""
    variants: list[Variant] | None = field(default_factory=list)

    def __post_init__(self):
        self.siblings = self.siblings or []
        self.exposes = self.exposes or []
        self.features = self.features or []
        self.variants = self.variants or []

    def get_config_path(self, revision: str | None = None) -> Path:
        """Path to the .conf file for this keyboard"""
        return self._get_keyboard_file(".conf", revision)

    def get_keymap_path(self, revision: str | None = None) -> Path:
        """Path to the .keymap file for this keyboard"""
        return self._get_keyboard_file(".keymap", revision)

    def _get_revision_suffixes(self, revision: str | None = None) -> Generator[str]:
        if revision:
            for rev in get_revision_forms(revision):
                yield "_" + rev.replace(".", "_")

    def _get_keyboard_file(self, extension: str, revision: str | None = None) -> Path:
        if revision:
            for rev in get_revision_forms(revision):
                path = self.directory / f"{self.id}_{rev.replace('.', '_')}{extension}"
                if path.exists():
                    return path

        return self.directory / f"{self.id}{extension}"


@dataclass
class Board(Keyboard):
    """Hardware with a processor. May be a keyboard or a controller."""

    arch: str | None = None
    outputs: list[Output] = field(default_factory=list)
    """List of methods by which this board supports sending HID data"""

    revisions: list[str] = field(default_factory=list)
    default_revision: str | None = None

    def __post_init__(self):
        super().__post_init__()
        self.outputs = self.outputs or []
        self.revisions = self.revisions or []

    def has_revision(self, revision: str):
        # Empty string means "use default revision"
        if not revision:
            return True

        revision = normalize_revision(revision)

        return any(normalize_revision(rev) == revision for rev in self.revisions)

    def get_revisions(self):
        return self.revisions

    def get_default_revision(self):
        return self.default_revision


def split_revision(identifier: str) -> tuple[str, str]:
    """
    Splits a string containing a hardware ID and optionally a revision into the
    ID and revision.

    Examples:
    "foo" -> "foo", ""
    "foo@2" -> "foo", "2"
    """
    hardware_id, _, revision = identifier.partition("@")
    return hardware_id, revision


def append_revision(identifier: str, revision: str | None):
    """
    Joins a hardware ID with a revision string.

    Examples:
    "foo" + None -> "foo"
    "foo" + "2" -> "foo@2"
    """
    return f"{identifier}@{revision}" if revision else identifier


def normalize_revision(revision: str | None) -> str:
    """
    Normalizes letter revisions to uppercase and shortens numeric versions to
    the smallest form with the same meaning.

    Examples:
    "a" -> "A"
    "1.2.0" -> "1.2"
    "2.0.0" -> "2"
    """
    if not revision:
        return ""

    return re.sub(r"(?:\.0){1,2}$", "", revision).upper()


def get_revision_forms(revision: str) -> list[str]:
    """
    Returns a list of all equivalent spellings of a revision.

    Examples:
    "a" -> ["A", "a"]
    "1.2.3" -> ["1.2.3"]
    "1.2.0" -> ["1.2", "1.2.0"]
    "2.0.0" -> ["2", "2.0", "2.0.0"]
    """
    revision = normalize_revision(revision)

    if revision.isalpha():
        return [revision.upper(), revision.lower()]

    result = []

    dot_count = revision.count(".")
    if dot_count == 0:
        result.append(revision + ".0.0")
    if dot_count <= 1:
        result.append(revision + ".0")

    result.append(revision)

    return result


@dataclass
class Shield(Keyboard):
    """Hardware that attaches to a board. May be a keyboard or a peripheral."""

    requires: list[str] | None = field(default_factory=list)
    """List of interconnects to which this shield attaches"""

    def __post_init__(self):
        super().__post_init__()
        self.requires = self.requires or []


@dataclass
class GroupedHardware:
    """Hardware grouped by type."""

    keyboards: list[Keyboard] = field(default_factory=list)
    """List of boards/shields that are keyboard PCBs"""
    controllers: list[Board] = field(default_factory=list)
    """List of boards that are controllers for keyboards"""
    interconnects: list[Interconnect] = field(default_factory=list)
    """List of interconnect descriptions"""

    # TODO: add displays and other peripherals?

    def find_keyboard(self, item_id: str) -> Keyboard | None:
        """Find a keyboard by ID"""
        item_id = item_id.casefold()
        return next((i for i in self.keyboards if i.id.casefold() == item_id), None)

    def find_controller(self, item_id: str) -> Board | None:
        """Find a controller by ID"""
        item_id = item_id.casefold()
        return next((i for i in self.controllers if i.id.casefold() == item_id), None)

    def find_interconnect(self, item_id: str) -> Interconnect | None:
        """Find an interconnect by ID"""
        item_id = item_id.casefold()
        return next(
            (i for i in self.interconnects if i.id.casefold() == item_id),
            None,
        )


def is_keyboard(hardware: Hardware) -> TypeGuard[Keyboard]:
    """Test whether an item is a keyboard (board or shield supporting keys)"""
    match hardware:
        case Keyboard(features=feat) if feat and "keys" in feat:
            return True

        case _:
            return False


def is_controller(hardware: Hardware) -> TypeGuard[Board]:
    """Test whether an item is a keyboard controller (board which isn't a keyboard)"""
    return isinstance(hardware, Board) and not is_keyboard(hardware)


def is_interconnect(hardware: Hardware) -> TypeGuard[Interconnect]:
    """Test whether an item is an interconnect description"""
    return isinstance(hardware, Interconnect)


def is_compatible(
    base: Board | Shield | Iterable[Board | Shield], shield: Shield
) -> bool:
    """
    Get whether a shield can be attached to the given hardware.

    This simply checks whether all the interconnects required by "shield" are
    provided by the hardware in "base". If "base" is a list of hardware, it does
    not account for the fact that one of the items in "base" may already be using
    an interconnect provided by another item.
    """

    if not shield.requires:
        return True

    base = [base] if isinstance(base, Keyboard) else base
    exposed = flatten(b.exposes for b in base)

    return all(ic in exposed for ic in shield.requires)


def get_board_roots(repo: Repo) -> Iterable[Path]:
    """Get the paths that contain hardware definitions for a repo"""
    roots = set()

    if root := repo.board_root:
        roots.add(root)

    for module in repo.get_modules():
        if root := module.board_root:
            roots.add(root)

    return roots


def get_hardware(repo: Repo) -> GroupedHardware:
    """Get lists of hardware descriptions, grouped by type, for a repo"""
    hardware = flatten(_find_hardware(root) for root in get_board_roots(repo))

    def func(groups: GroupedHardware, item: Hardware):
        if is_keyboard(item):
            groups.keyboards.append(item)
        elif is_controller(item):
            groups.controllers.append(item)
        elif is_interconnect(item):
            groups.interconnects.append(item)

        return groups

    groups = reduce(func, hardware, GroupedHardware())

    groups.controllers = sorted(groups.controllers, key=lambda x: x.id)
    groups.keyboards = sorted(groups.keyboards, key=lambda x: x.id)
    groups.interconnects = sorted(groups.interconnects, key=lambda x: x.id)

    return groups


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


def _filter_hardware(item: Hardware, text: str):
    text = text.casefold().strip()
    return text in item.id.casefold() or text in item.name.casefold()


def show_hardware_menu(
    title: str,
    items: Iterable[_HW],
    **kwargs,
) -> _HW:
    """
    Show a menu to select from a list of Hardware objects.

    kwargs are passed through to zmk.menu.show_menu(), except for filter_func,
    which is set to a function appropriate for filtering Hardware objects.
    """
    return show_menu(title=title, items=items, **kwargs, filter_func=_filter_hardware)


def show_revision_menu(
    board: Hardware, title: str | None = None, **kwargs
) -> str | None:
    """
    Show a menu to select from a list of revisions for a board.

    If the board has no revisions, returns None without showing a menu.
    If the board has only one revision, returns it without showing a menu.

    kwargs are passed through to zmk.menu.show_menu(), except for default_index,
    which is set based on the board's default revision.
    """

    revisions = board.get_revisions()
    if not revisions:
        return None

    if len(revisions) == 1:
        return revisions[0]

    default_revision = board.get_default_revision()
    default_index = revisions.index(default_revision) if default_revision else 0

    return show_menu(
        title=title or f"Select a {board.name} revision:",
        items=revisions,
        default_index=default_index,
        **kwargs,
    )
