"""
User configuration.
"""

from collections import defaultdict
from configparser import ConfigParser
from enum import StrEnum
from itertools import chain
from pathlib import Path
from typing import NoReturn, Optional

import platformdirs
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
    fatal_error(
        Markdown("Home directory not set. Run `zmk init` to create a new config repo.")
    )


def fatal_home_missing(path: Path) -> NoReturn:
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

    def __init__(self, path: Path) -> None:
        self.path = path or _default_config_path()
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
        return self._parser.get(section, option, vars=self._vars(section), **kwargs)

    def getboolean(self, name: str, **kwargs) -> bool:
        """Get a setting as a boolean"""
        section, option = self._split_option(name)
        return self._parser.getboolean(
            section, option, vars=self._vars(section), **kwargs
        )

    def set(self, name: str, value: Optional[str]):
        """Set a setting. Set to None to remove the setting"""
        section, option = self._split_option(name)

        if value is None:
            self._parser.remove_option(section, option)
        else:
            self._parser.set(section, option, value)

        try:
            del self._vars(section)[option]
        except KeyError:
            pass

    # TODO: is this still necessary?
    def set_override(self, name: str, value: Optional[str]):
        """
        Set a temporary override for a a setting.

        Calling write() will not save the overridden value to the config file.

        Calling set() will clear any corresponding override.
        """
        section, option = self._split_option(name)
        self._vars(section)[option] = value

    def items(self):
        """Yields ('section.option', 'value') tuples for all settings"""
        sections = set(chain(self._overrides.keys(), self._parser.sections()))

        for section in sections:
            items = self._parser.items(section, vars=self._vars(section))

            for option, value in items:
                yield f"{section}.{option}", value

    def _vars(self, section: str):
        return self._overrides[section]

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
        cwd = Path()
        if is_repo(cwd):
            return Repo(cwd)

        home = self.home_path
        if not home:
            fatal_home_not_set()

        if is_repo(home):
            return Repo(home)

        fatal_home_missing(home)


def _default_config_path():
    return platformdirs.user_config_path(appname="zmk") / "zmk.ini"
