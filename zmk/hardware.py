from dataclasses import dataclass, field
from functools import reduce
import inspect
from pathlib import Path
from typing import Generator, Iterable, Literal, Optional, TypeAlias, TypeGuard

from .util import flatten, read_yaml
from .repo import Repo


Feature: TypeAlias = Literal[
    "keys", "display", "encoder", "underglow", "backlight", "pointer"
]
Output: TypeAlias = Literal["usb", "ble"]

# TODO: dict should match { id: str, features: list[Feature] }
Variant: TypeAlias = str | dict[str, str]


@dataclass
class HardwareBase:
    base_path: Path
    directory: Path
    type: str
    id: str
    name: str

    file_format: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    version: Optional[str] = None

    @classmethod
    def from_dict(cls, data):
        return cls(
            **{k: v for k, v in data.items() if k in inspect.signature(cls).parameters}
        )


@dataclass
class Interconnect(HardwareBase):
    node_labels: dict[str, str] = field(default_factory=dict)
    design_guideline: Optional[str] = None


@dataclass
class KeyboardBase(HardwareBase):
    siblings: list[str] = field(default_factory=list)
    features: list[Feature] = field(default_factory=list)
    variants: list[Variant] = field(default_factory=list)
    exposes: list[str] = field(default_factory=list)


@dataclass
class Board(KeyboardBase):
    arch: Optional[str] = None
    outputs: list[Output] = field(default_factory=list)


@dataclass
class Shield(KeyboardBase):
    requires: list[str] = field(default_factory=list)


Keyboard: TypeAlias = Board | Shield
Hardware: TypeAlias = Keyboard | Interconnect


@dataclass
class GroupedHardware:
    keyboards: list[Keyboard] = field(default_factory=list)
    controllers: list[Board] = field(default_factory=list)
    interconnects: list[Interconnect] = field(default_factory=list)
    # TODO: add displays and other peripherals?

    def find_keyboard(self, name: str):
        return next((i for i in self.keyboards if i.id == name), None)

    def find_controller(self, name: str):
        return next((i for i in self.controllers if i.id == name), None)

    def find_interconnect(self, name: str):
        return next((i for i in self.interconnects if i.id == name), None)


@dataclass
class KeyboardFiles:
    config_path: Optional[Path] = None
    keymap_path: Optional[Path] = None


def is_keyboard(hardware: Hardware) -> TypeGuard[Keyboard]:
    match hardware:
        case KeyboardBase(features=feat) if "keys" in feat:
            return True

        case _:
            return False


def is_controller(hardware: Hardware) -> TypeGuard[Board]:
    return isinstance(hardware, Board) and not is_keyboard(hardware)


def is_interconnect(hardware: Hardware) -> TypeGuard[Interconnect]:
    return isinstance(hardware, Interconnect)


def is_compatible(board: Board, shield: Shield):
    return all(ic in board.exposes for ic in shield.requires)


def get_board_roots(repo: Repo) -> Iterable[Path]:
    roots = set()

    if root := repo.board_root:
        roots.add(root)

    for module in repo.get_modules():
        if root := module.board_root:
            roots.add(root)

    return roots


def get_hardware(repo: Repo) -> GroupedHardware:
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
        meta["base_path"] = path
        meta["directory"] = meta_path.parent

        match meta.get("type"):
            case "board":
                yield Board.from_dict(meta)

            case "shield":
                yield Shield.from_dict(meta)

            case "interconnect":
                yield Interconnect.from_dict(meta)
