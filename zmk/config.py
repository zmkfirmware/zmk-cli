"""
User configuration.
"""

from collections import defaultdict
from configparser import ConfigParser
from enum import StrEnum
from itertools import chain
from pathlib import Path
from typing import NoReturn, Optional

import typer
from rich.markdown import Markdown

from .repo import Repo, is_repo
from .util import fatal_error


class Settings(StrEnum):
    """List of setting names used by commands"""

    USER_HOME = "user.home"
    USER_NAME = "user.name"

    CORE_EDITOR = "core.editor"  # Text editor tool
    CORE_EXPLORER = "core.explorer"  # Directory editor tool


def fatal_home_not_set() -> NoReturn:
    """Exits with a message indicating the home directory is not set."""
    fatal_error(
        Markdown("Home directory not set. Run `zmk init` to create a new config repo.")
    )


def fatal_home_missing(path: Path) -> NoReturn:
    """Exits with a message indicating the home directory is missing."""
    fatal_error(
        Markdown(
            f'Home directory "{path}" is missing or no longer looks like a config repo. '
            "Run `zmk config user.home=/path/to/zmk-config` if you moved it, "
            "or run `zmk init` to create a new config repo."
        )
    )


class Config:
    """Wrapper around ConfigParser to store CLI configuration"""

    path: Path
    force_home: bool

    def __init__(self, path: Path, force_home=False) -> None:
        self.path = path or _default_config_path()
        self.force_home = force_home

        self._overrides: defaultdict[str, dict[str, str]] = defaultdict(dict)
        self._parser = ConfigParser()
        self._parser.read(self.path, encoding="utf-8")

    def write(self):
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

    def set(self, name: str, value: str):
        """Set a setting"""
        section, option = self._split_option(name)
        self._parser.set(section, option, value)

    def remove(self, name: str):
        """Remove a setting"""
        section, option = self._split_option(name)
        self._parser.remove_option(section, option)

    def items(self):
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
    def home_path(self) -> Optional[Path]:
        """
        Path to ZMK config repo.
        """
        home = self.get(Settings.USER_HOME, fallback=None)
        return Path(home) if home else None

    @home_path.setter
    def home_path(self, value: Path):
        self.set(Settings.USER_HOME, str(value.resolve()))

    def get_repo(self) -> Repo:
        """
        Return an object representing the repo at the current working directory
        or the home path setting.

        Exits the program if neither the current directory nor the home path
        point to a valid directory.
        """
        if not self.force_home:
            if home := _find_cwd_repo():
                return Repo(home)

        home = self.home_path
        if not home:
            fatal_home_not_set()

        if not is_repo(home):
            fatal_home_missing(home)

        return Repo(home)


def _default_config_path():
    return Path(typer.get_app_dir("zmk", roaming=False)) / "zmk.ini"


def _find_cwd_repo():
    cwd = Path().absolute()

    for path in [cwd, *cwd.parents]:
        if is_repo(path):
            return path

    return None
