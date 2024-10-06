"""
Build matrix processing.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypeVar, cast, overload

import dacite

from .repo import Repo
from .yaml import YAML

T = TypeVar("T")


@dataclass
class BuildItem:
    """An item in the build matrix"""

    board: str
    shield: str | None = None
    snippet: str | None = None
    cmake_args: str | None = None
    artifact_name: str | None = None

    def __rich__(self) -> str:
        parts = []
        parts.append(self.board)

        if self.shield:
            parts.append(self.shield)

        if self.snippet:
            parts.append(f"[dim]snippet: {self.snippet}[/dim]")

        if self.artifact_name:
            parts.append(f"[dim]artifact-name: {self.artifact_name}[/dim]")

        if self.cmake_args:
            parts.append(f"[dim]cmake-args: {self.cmake_args}[/dim]")

        return "[dim], [/dim]".join(parts)


@dataclass
class _BuildMatrixWrapper:
    include: list[BuildItem] = field(default_factory=list)


class BuildMatrix:
    """Interface to read and edit ZMK's build.yaml file"""

    _path: Path
    _yaml: YAML
    _data: dict[str, Any] | None

    @classmethod
    def from_repo(cls, repo: Repo) -> "BuildMatrix":
        """Get the build matrix for a repo"""
        return cls(repo.build_matrix_path)

    def __init__(self, path: Path):
        self._path = path
        self._yaml = YAML(typ="rt")
        self._yaml.indent(mapping=2, sequence=4, offset=2)
        try:
            self._data = cast(dict[str, Any], self._yaml.load(self._path))
        except FileNotFoundError:
            self._data = None

    def write(self) -> None:
        """Updated the YAML file, creating it if necessary"""
        self._yaml.dump(self._data, self._path)

    @property
    def path(self) -> Path:
        """Path to the matrix's YAML file"""
        return self._path

    @property
    def include(self) -> list[BuildItem]:
        """List of build items in the matrix"""
        normalized = _keys_to_python(self._data)
        if not normalized:
            return []

        wrapper = dacite.from_dict(_BuildMatrixWrapper, normalized)
        return wrapper.include

    def has_item(self, item: BuildItem) -> bool:
        """Get whether the matrix has a build item"""
        return item in self.include

    def append(self, items: BuildItem | Iterable[BuildItem]) -> list[BuildItem]:
        """
        Add build items to the matrix.

        :return: the items that were added.
        """
        items = [items] if isinstance(items, BuildItem) else items

        include = self.include
        items = [i for i in items if i not in include]

        if not items:
            return []

        if not self._data:
            self._data = cast(dict[str, Any], self._yaml.map())

        if "include" not in self._data:
            self._data["include"] = self._yaml.seq()

        self._data["include"].extend([_to_yaml(i) for i in items])
        return items

    def remove(self, items: BuildItem | Iterable[BuildItem]) -> list[BuildItem]:
        """
        Remove build items from the matrix.

        :return: the items that were removed.
        """
        if not self._data or "include" not in self._data:
            return []

        removed = []
        items = [items] if isinstance(items, BuildItem) else items

        # TODO: there's probably a more efficient way to do this, but this is easy
        for item in items:
            try:
                index = self.include.index(item)
                del self._data["include"][index]
                removed.append(item)
            except ValueError:
                pass

        return removed


@overload
def _keys_to_python(data: str) -> str: ...


@overload
def _keys_to_python(
    data: Sequence[T],
) -> Sequence[T]: ...


@overload
def _keys_to_python(data: Mapping[str, T]) -> Mapping[str, T]: ...


@overload
def _keys_to_python(data: T) -> T: ...


def _keys_to_python(data: Any) -> Any:
    """
    Fix any keys with hyphens to underscores so that dacite.from_dict() will
    work correctly.
    """

    def fix_key(key: str):
        return key.replace("-", "_")

    match data:
        case str():
            return data

        case Sequence():
            return [_keys_to_python(i) for i in data]

        case Mapping():
            return {fix_key(k): _keys_to_python(v) for k, v in data.items()}

        case _:
            return data


def _to_yaml(item: BuildItem):
    """
    Convert a BuildItem to a dict with keys changed back from underscores to hyphens.
    """

    def fix_key(key: str):
        return key.replace("_", "-")

    data = asdict(item)

    return {fix_key(k): v for k, v in data.items() if v is not None}
