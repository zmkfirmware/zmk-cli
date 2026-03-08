import itertools
import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Self, TypeAlias, TypedDict, cast

import dacite
from rich.console import RenderableType
from rich.measure import Measurement

from .revision import Revision
from .util import horizontal_group, union

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


@dataclass
class BoardTarget:
    """
    Zephyr board target. Identifies a unique combination of board name,
    board revision, and board qualifiers (SoC, CPU cluster, and variant).
    """

    name: str = ""
    """Zephyr Board ID (not the ZMK display name)"""
    revision: Revision = field(default_factory=Revision)
    """Optional board revision"""
    qualifiers: str = ""
    """Optional board qualifiers (including forward slashes)"""

    @classmethod
    def parse(cls, target: str):
        """
        Parse a board target into its parts.

        Examples:
        ```
        BoardTarget.parse("nice_nano//zmk")
        # returns
        BoardTarget(name="nice_nano", revision=Revision(), qualifiers="//zmk")

        BoardTarget.parse("bl5340_dvk@1.2.0/nrf5340/cpuapp/ns")
        # returns
        BoardTarget(
            name="bl5340_dvk",
            revision=Revision("1.2.0"),
            qualifiers="/nrf5340/cpuapp/ns"
        )
        ```
        """
        name, qualifiers = split_board_qualifiers(target)
        name, _, revision = name.partition("@")

        return BoardTarget(
            name=name, revision=Revision(revision), qualifiers=qualifiers
        )

    def __str__(self):
        return self.name + self.revision.at_str + self.qualifiers

    # Can't use just __rich__ here, or this won't display properly in tables.
    # https://github.com/Textualize/rich/issues/3188

    def __rich_console__(self, console, options):
        yield str(self)

    def __rich_measure__(self, console, options):
        length = len(str(self))
        return Measurement(length, length)

    def with_revision(self, revision: Revision):
        """Get a copy of this BoardTarget() with a different revision."""
        return replace(self, revision=revision)


@dataclass
class BuildItem:
    """Entry in the build.yaml file"""

    board: BoardTarget
    shield: str | None = None
    snippet: str | None = None
    cmake_args: str | None = None
    artifact_name: str | None = None

    def __rich__(self):
        return horizontal_group(
            *(item for item in self.__menu_row__() if item), padding=(0, 2)
        )

    def __menu_row__(self) -> Iterable[RenderableType]:
        yield self.board
        yield self.shield or ""

        extras = []
        if self.snippet:
            extras.append(f"snippet: {self.snippet}")

        if self.artifact_name:
            extras.append(f"artifact-name: {self.artifact_name}")

        if self.cmake_args:
            extras.append(f"cmake-args: {self.cmake_args}")

        if extras:
            yield f"[dim]{', '.join(extras)}"


@dataclass
class Hardware:
    """Base class for keyboard hardware"""

    directory: Path
    """Path to the directory containing this hardware"""
    file_format: str | None

    type: str
    id: str
    """Zephyr identifier for the hardware. Board IDs include board qualifiers."""
    name: str
    """Display name for the hardware"""
    url: str | None
    description: str | None
    manufacturer: str | None

    @classmethod
    def from_dict(cls, data) -> Self:
        config = dacite.Config(cast=[set, Revision])
        return dacite.from_dict(data_class=cls, data=data, config=config)

    def __str__(self) -> str:
        return self.id

    def __rich__(self) -> RenderableType:
        return f"{self.id}  [dim]{self.name}"

    def __menu_row__(self) -> Iterable[RenderableType]:
        return [self.id, self.name]

    def get_normalized_ids(self) -> list[str]:
        """
        Returns a list of names by which this hardware can be matched, for example
        in command line parameters. All results are casefolded.
        """
        return [self.id.casefold()]


@dataclass
class Interconnect(Hardware):
    """
    Description of the connection between two pieces of hardware.

    Matches #/$defs/interconnect from
    https://github.com/zmkfirmware/zmk/blob/main/schema/hardware-metadata.schema.json
    """

    node_labels: dict[str, str] = field(default_factory=dict)
    design_guideline: str | None = None


@dataclass
class KeyboardComponent(Hardware):
    """Base class for hardware that forms a keyboard"""

    siblings: list[str] = field(default_factory=list)
    """List of board/shield IDs for a split keyboard. Board IDs include board qualifiers"""
    exposes: set[str] = field(default_factory=set)
    """List of interconnect IDs this board/shield provides"""
    features: set[Feature] = field(default_factory=set)
    """List of features this board/shield supports"""
    variants: list[Variant] = field(default_factory=list)

    @property
    def has_keys(self) -> bool:
        """Get whether this hardware has the "keys" feature."""
        return "keys" in self.features


@dataclass
class Board(KeyboardComponent):
    """
    Description of a Zephyr board. May be a controller or a standalone keyboard.

    Matches #/$defs/board from
    https://github.com/zmkfirmware/zmk/blob/main/schema/hardware-metadata.schema.json
    """

    arch: str | None = None
    outputs: set[Output] = field(default_factory=set)
    """List of methods by which this board supports sending HID data"""

    revisions: list[Revision] = field(default_factory=list)
    default_revision: Revision = field(default_factory=Revision)

    def get_normalized_ids(self) -> list[str]:
        """
        Returns a list of names by which this hardware can be matched, for example
        in command line parameters. All results are casefolded.

        To make specifying board IDs as command line parameters easier, the "zmk"
        board qualifier is optional, e.g. "nice_nano" matches a board with
        `id="nice_nano//zmk"`, and "nrfmicro/nrf52840" matches a board with
        `id="nrfmicro/nrf52840/zmk"`.
        """
        norm_id = self.id.casefold()

        result = [norm_id]
        if norm_id.endswith("//zmk"):
            result.append(norm_id.removesuffix("//zmk"))
        elif norm_id.endswith("/zmk"):
            result.append(norm_id.removesuffix("/zmk"))

        return result


@dataclass
class Shield(KeyboardComponent):
    """
    Description of a Zephyr shield. May be a keyboard or a peripheral.

    Matches #/$defs/shield from
    https://github.com/zmkfirmware/zmk/blob/main/schema/hardware-metadata.schema.json

    """

    requires: set[str] = field(default_factory=set)
    """List of interconnects this shield requires to be attached to"""


class IncompleteKeyboardError(Exception):
    pass


@dataclass
class Keyboard:
    """
    Collection of information needed to determine how to build keyboard firmware.

    This consists of:
    - A board
    - Optionally, a specific board revision to use
    - Optionally, some number of shields.

    At least one item between the board and shields is required to have the "keys"
    before the keyboard is considered "complete" and can be used to build firmware.
    """

    board: Board | None = None
    """The controller board"""
    board_revision: Revision = field(default_factory=Revision)
    """The board revision selected to build"""
    shields: list[Shield] = field(default_factory=list)
    """List of shields to attach to the board"""

    @property
    def board_targets(self) -> list[BoardTarget]:
        """
        The Zephyr board target(s) from board and board_revision.

        If board.siblings is not empty, this returns one item per sibling.
        Otherwise, it returns a single item for board.id.

        :raises IncompleteKeyboardError: if board is not set.
        """
        if not self.board:
            raise IncompleteKeyboardError("Cannot get board_target when board is None")

        board_ids = self.board.siblings or [self.board.id]
        revision = self.board_revision or self.board.default_revision

        return [
            BoardTarget.parse(board_id).with_revision(revision)
            for board_id in board_ids
        ]

    @property
    def board_revisions(self) -> list[Revision]:
        """The board's supported revisions."""
        return self.board.revisions if self.board else []

    @property
    def keys_component(self) -> Board | Shield | None:
        """The first item in [board, *shields] which has the "keys" feature."""
        if self.board and self.board.has_keys:
            return self.board

        return next((s for s in self.shields if s.has_keys), None)

    @property
    def exposes(self) -> set[str]:
        """Set of interconnects exposed by the board and shields."""
        board_exposes = self.board.exposes if self.board else set()

        return board_exposes | union(s.exposes for s in self.shields)

    @property
    def requires(self) -> set[str]:
        """Set of interconnects required by shields."""
        return union(s.requires for s in self.shields)

    @property
    def missing_requirements(self) -> set[str]:
        """
        Gets any interconnects in self.requires that are not satisfied by
        self.exposes.

        This does not attempt to account for multiple instances of the same
        interconnect.
        """
        return self.requires - self.exposes

    @property
    def revisions(self) -> list[Revision]:
        """List of available board revisions"""
        return self.board.revisions if self.board else []

    @property
    def default_revision(self) -> Revision:
        """Board revision that will be used if one isn't explicitly selected"""
        return self.board.default_revision if self.board else Revision()

    def add_component(self, component: KeyboardComponent):
        """Add a board or shield to the keyboard."""
        match component:
            case Board():
                self.board = component

            case Shield():
                self.shields.append(component)

            case _:
                raise TypeError("Unknown component type")

    def is_compatible(self, component: Board | Shield):
        """
        Get whether a board or shield can be attached to the keyboard and all
        interconnect requirements would be satisfied.

        If given a shield, this checks whether all the interconnects required by
        the shield are provided by the board and/or shields already in the keyboard.

        If given a board, this checks whether adding the board would satisfy all
        the requirements for the shields already in the keyboard.
        """
        match component:
            case Board():
                # This assumes we're replacing any existing board, so determine
                # the new set of exposed interconnects with the new board and
                # without any existing board.
                new_exposes = component.exposes | union(s.exposes for s in self.shields)
                return not (self.requires - new_exposes)

            case Shield():
                return not (component.requires - self.exposes)

    def get_build_items(self) -> list[BuildItem]:
        """
        Get the individual builds needed to make the firmware. This currently
        accounts for splits but not more complex configurations where each build
        may need different options.

        Each build item will contain the board and every shield. If any board or
        shield has siblings, then this will return one item per possible
        combination of siblings. For example:
        ```
        self.board = Board(id="nice_nano//zmk", default_revision="2")
        self.shields = [Shield(id="two_percent_milk")]
        # returns
        [BuildItem(board_target="nice_nano@2//zmk", shield="two_percent_milk")]

        self.board = Board(id="nice_nano//zmk", default_revision="2")
        self.shields = [Shield(siblings=["a_left", "a_right"]), Shield(id="display")]
        # returns
        [
            BuildItem(board_target="nice_nano@2//zmk", shield="a_left display"),
            BuildItem(board_target="nice_nano@2//zmk", shield="a_right display"),
        ]
        ```

        :raises IncompleteKeyboardError: if board is not set or there is no
        component with the "keys" feature.
        """
        if not self.board or not self.keys_component:
            raise IncompleteKeyboardError(
                "Cannot get build items for an incomplete keyboard"
            )

        build_items: list[BuildItem] = []
        shield_lists = (shield.siblings or [shield.id] for shield in self.shields)

        for combination in itertools.product(self.board_targets, *shield_lists):
            # Python's type system can't represent that the first item is always a
            # BoardTarget and the rest are always str, so explicit casts are needed.
            target = cast("BoardTarget", combination[0])
            shields = cast("tuple[str, ...]", combination[1:])
            shield_str = " ".join(shields) if shields else None

            build_items.append(BuildItem(board=target, shield=shield_str))

        return build_items

    def get_config_path(self) -> Path:
        """
        Get the path to the keyboard's .conf file.

        :raises IncompleteKeyboardError: if there is no component with the "keys" feature.
        """
        return _get_keyboard_file(self.keys_component, self.board_revision, ".conf")

    def get_keymap_path(self) -> Path:
        """
        Get the path to the keyboard's .keymap file.

        :raises IncompleteKeyboardError: if there is no component with the "keys" feature.
        """
        return _get_keyboard_file(self.keys_component, self.board_revision, ".keymap")


def split_board_qualifiers(identifier: str) -> tuple[str, str]:
    """
    Splits a string into a board ID and board qualifiers. If the string contains
    a revision, it is ignored and returned as part of the first value.

    Examples:
    "foo" -> "foo", ""
    "foo/bar/baz" -> "foo", "/bar/baz"
    "foo@2/bar/baz" -> "foo@2", "/bar/baz"
    """
    try:
        index = identifier.index("/")
        return identifier[0:index], identifier[index:]
    except ValueError:
        return identifier, ""


def _get_filename(name: str):
    """
    Replaces all special characters used in revisions and board qualifiers that
    are not valid in a filename with underscores.
    """
    return re.sub(r"[./]+", "_", name)


def _get_keyboard_file(
    keys_component: Board | Shield | None, revision: Revision, suffix: str
) -> Path:
    if not keys_component:
        raise IncompleteKeyboardError("Cannot get file path for an incomplete keyboard")

    search_names: list[str] = [keys_component.id]
    search_revisions: list[str] = []
    directory = keys_component.directory

    if isinstance(keys_component, Board):
        # If the keyboard has board qualifiers, also search without them.
        target = BoardTarget.parse(keys_component.id)
        if target.qualifiers:
            search_names.append(target.name)

        # If the keyboard has revisions, search for files with each possible
        # spelling of the revision.
        revision = revision or keys_component.default_revision
        if revision:
            search_revisions = revision.get_spellings()

    # Combine everything into a list of paths to search from most to least
    # specific.
    search_paths: list[Path] = []

    for name in search_names:
        for rev in search_revisions:
            # Despite Zephyr board targets having the revision before the
            # qualifiers, paths have the revision at the end for some reason.
            path = (directory / _get_filename(name + "_" + rev)).with_suffix(suffix)
            search_paths.append(path)

        path = (directory / _get_filename(name)).with_suffix(suffix)
        search_paths.append(path)

    for path in search_paths:
        if path.exists():
            return path

    # If none of these files exists, then just return the most general of
    # the possible paths. For a shield, this will just be the shield ID itself.
    # For a board, it will be the ID without revisions or qualifiers.
    return search_paths[-1]
