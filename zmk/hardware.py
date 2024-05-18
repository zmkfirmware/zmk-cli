"""
Hardware metadata discovery and processing.
"""

from dataclasses import dataclass, field
from functools import reduce
from pathlib import Path
from typing import Any, Generator, Iterable, Literal, Optional, TypeAlias, TypeGuard

import dacite

from .repo import Repo
from .util import flatten
from .yaml import read_yaml

Feature: TypeAlias = Literal[
    "keys", "display", "encoder", "underglow", "backlight", "pointer"
]
Output: TypeAlias = Literal["usb", "ble"]

# TODO: dict should match { id: str, features: list[Feature] }
Variant: TypeAlias = str | dict[str, str]


@dataclass
class Hardware:
    """Base class for keyboard hardware"""

    directory: Path
    """Path to the directory containing this hardware"""

    type: str
    id: str
    name: str

    file_format: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    version: Optional[str] = None

    def __str__(self) -> str:
        return self.id

    def __rich__(self) -> Any:
        return f"{self.id}  [dim]{self.name}"

    @classmethod
    def from_dict(cls, data):
        """Read a hardware description from a dict"""
        return dacite.from_dict(cls, data)


@dataclass
class Interconnect(Hardware):
    """Description of the connection between two pieces of hardware"""

    node_labels: dict[str, str] = field(default_factory=dict)
    design_guideline: Optional[str] = None


@dataclass
class Keyboard(Hardware):
    """Base class for hardware that forms a keyboard"""

    siblings: Optional[list[str]] = field(default_factory=list)
    """List of board/shield IDs for a split keyboard"""
    exposes: Optional[list[str]] = field(default_factory=list)
    """List of interconnect IDs this board/shield provides"""
    features: Optional[list[Feature]] = field(default_factory=list)
    """List of features this board/shield supports"""
    variants: Optional[list[Variant]] = field(default_factory=list)

    def __post_init__(self):
        self.siblings = self.siblings or []
        self.exposes = self.exposes or []
        self.features = self.features or []
        self.variants = self.variants or []

    @property
    def config_path(self):
        """Path to the .conf file for this keyboard"""
        return self.directory / f"{self.id}.conf"

    @property
    def keymap_path(self):
        """Path to the .keymap file for this keyboard"""
        return self.directory / f"{self.id}.keymap"


@dataclass
class Board(Keyboard):
    """Hardware with a processor. May be a keyboard or a controller."""

    arch: Optional[str] = None
    outputs: list[Output] = field(default_factory=list)
    """List of methods by which this board supports sending HID data"""

    def __post_init__(self):
        super().__post_init__()
        self.outputs = self.outputs or []


@dataclass
class Shield(Keyboard):
    """Hardware that attaches to a board. May be a keyboard or a peripheral."""

    requires: Optional[list[str]] = field(default_factory=list)
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

    def find_keyboard(self, item_id: str):
        """Find a keyboard by ID"""
        item_id = item_id.casefold()
        return next((i for i in self.keyboards if i.id.casefold() == item_id), None)

    def find_controller(self, item_id: str):
        """Find a controller by ID"""
        item_id = item_id.casefold()
        return next((i for i in self.controllers if i.id.casefold() == item_id), None)

    def find_interconnect(self, item_id: str):
        """Find an interconnect by ID"""
        item_id = item_id.casefold()
        return next(
            (i for i in self.interconnects if i.id.casefold() == item_id),
            None,
        )


def is_keyboard(hardware: Hardware) -> TypeGuard[Keyboard]:
    """Test whether an item is a keyboard (board or shield supporting keys)"""
    match hardware:
        case Keyboard(features=feat) if "keys" in feat:
            return True

        case _:
            return False


def is_controller(hardware: Hardware) -> TypeGuard[Board]:
    """Test whether an item is a keyboard controller (board which isn't a keyboard)"""
    return isinstance(hardware, Board) and not is_keyboard(hardware)


def is_interconnect(hardware: Hardware) -> TypeGuard[Interconnect]:
    """Test whether an item is an interconnect description"""
    return isinstance(hardware, Interconnect)


def is_compatible(base: Board | Shield | Iterable[Board | Shield], shield: Shield):
    """
    Get whether a shield can be attached to the given hardware.

    This simply checks whether all the interconnects required by "shield" are
    provided by the hardware in "base". If "base" is a list of hardware, it does
    not account for the fact that one of the items in "base" may already be using
    an interconnect provided by another item.
    """

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
