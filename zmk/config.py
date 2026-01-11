"""
User configuration.
"""

from collections import defaultdict
from collections.abc import Generator
from configparser import ConfigParser
from itertools import chain
from pathlib import Path

import typer

from .backports import StrEnum
from .exceptions import FatalHomeMissing, FatalHomeNotSet
from .repo import Repo, find_containing_repo, is_repo


class Settings(StrEnum):
    """List of setting names used by commands"""

    USER_HOME = "user.home"  # Path to the ZMK config repo

    CORE_EDITOR = "core.editor"  # Text editor tool
    CORE_EXPLORER = "core.explorer"  # Directory editor tool


_PATH_SETTINGS = (Settings.USER_HOME,)


class Config:
    """Wrapper around ConfigParser to store CLI configuration"""

    path: Path
    force_home: bool

    override_repo_path: Path | None = None
    "Set this to override the path used for get_repo() without changing home_path."

    def __init__(self, path: Path | None, force_home=False):
        self.path = path or _default_config_path()
        self.force_home = force_home

        self._overrides: defaultdict[str, dict[str, str]] = defaultdict(dict)
        self._parser = ConfigParser(interpolation=None)
        self._parser.read(self.path, encoding="utf-8")

    def write(self) -> None:
        """Write back to the same file used when calling read()"""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.path.open("w", encoding="utf-8") as fp:
            self._parser.write(fp)

    def get(self, name: str, **kwargs) -> str:
        """Get a setting"""
        section, option = self._split_option(name)
        return self._parser.get(section, option, **kwargs)

    def getboolean(self, name: str, **kwargs) -> bool:
        """Get a setting as a boolean"""
        section, option = self._split_option(name)
        return self._parser.getboolean(section, option, **kwargs)

    def set(self, name: str, value: str) -> None:
        """Set a setting"""
        section, option = self._split_option(name)
        if name in _PATH_SETTINGS:
            value = str(Path(value).resolve())
        self._parser.set(section, option, value)

    def remove(self, name: str) -> None:
        """Remove a setting"""
        section, option = self._split_option(name)
        self._parser.remove_option(section, option)

    def items(self) -> Generator[tuple[str, str], None, None]:
        """Yields ('section.option', 'value') tuples for all settings"""
        sections = set(chain(self._overrides.keys(), self._parser.sections()))

        for section in sections:
            items = self._parser.items(section)

            for option, value in items:
                yield f"{section}.{option}", value

    def _split_option(self, name: str):
        section, _, option = name.partition(".")

        if not self._parser.has_section(section):
            self._parser.add_section(section)

        return section, option

    # Shortcuts for commonly-used settings:

    @property
    def home_path(self) -> Path | None:
        """
        Path to ZMK config repo.
        """
        home = self.get(Settings.USER_HOME, fallback=None)
        return Path(home) if home else None

    @home_path.setter
    def home_path(self, value: Path) -> None:
        self.set(Settings.USER_HOME, str(value))

    def get_repo(self) -> Repo:
        """
        Return an object representing the repo at the current working directory
        or the home path setting.

        Exits the program if neither the current directory nor the home path
        point to a valid directory.

        If override_repo_path is set, this takes priority over all other methods
        of finding the repo.
        """
        if self.override_repo_path:
            return Repo(self.override_repo_path)

        if not self.force_home:
            if home := find_containing_repo():
                return Repo(home)

        home = self.home_path
        if not home:
            raise FatalHomeNotSet()

        if not is_repo(home):
            raise FatalHomeMissing(home)

        return Repo(home)


def get_config(ctx: typer.Context) -> Config:
    """Get the Config object for the given context"""

    cfg = ctx.find_object(Config)
    if cfg is None:
        raise RuntimeError("Could not find Config for current context")
    return cfg


def set_context_repo(ctx: typer.Context, repo: Repo) -> None:
    """
    Set the override_repo_path on the Config object for the given context to
    point to a given repo. All subsequent calls to get_config(ctx).get_repo()
    will return a Repo instance with the same path as the given one.

    This should be used when a command wants to apply changes to a specific repo
    that isn't necessarily what get_config(ctx).get_repo() would normally use
    (e.g. when creating a new repo with "zmk init"), and when that command
    calls another command that gets its repo from the context.
    """
    get_config(ctx).override_repo_path = repo.path


def _default_config_path():
    return Path(typer.get_app_dir("zmk", roaming=False)) / "zmk.ini"
