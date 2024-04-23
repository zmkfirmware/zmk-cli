from collections import defaultdict
from configparser import ConfigParser
from itertools import chain
from pathlib import Path
from typing import Optional
import platformdirs


class KnownSettings:
    """List of setting names used by commands"""

    USER_HOME = "user.home"
    USER_NAME = "user.name"


class InvalidHomeError(Exception):
    pass


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

    def set(self, name: str, value: Optional[str] = None):
        """Set a setting"""
        section, option = self._split_option(name)

        if value is None:
            self._parser.remove_option(section, option)
        else:
            self._parser.set(section, option, value)

        try:
            del self._vars(section)[option]
        except KeyError:
            pass

    def set_override(self, name: str, value: Optional[str] = None):
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
    def home_path(self) -> Path:
        """
        Path to ZMK config repo.

        Raised InvalidHomeError if the home directory is not set or no longer exists.
        """
        home = self.get(KnownSettings.USER_HOME, fallback=None)
        return Path(home) if home else None

    @home_path.setter
    def home_path(self, value: Path):
        self.set_override(KnownSettings.USER_HOME, str(value.resolve()))

    def ensure_home(self) -> Path:
        """
        Verifies that home_path is set and points to a valid directory.
        If so, returns it. Otherwise, raises InvalidHomeError.
        """
        home = self.home_path
        if home is None:
            raise InvalidHomeError(
                "Home directory not set. Run 'zmk init' to create a new config repo."
            )

        home_path = Path(home)
        if not home_path.exists():
            raise InvalidHomeError(
                f'Home directory "{home_path}" is missing. '
                "Run 'zmk config user.home=/path/to/zmk-config' to fix it, "
                "or run 'zmk init' to create a new config repo."
            )

        return home_path


def _default_config_path():
    return platformdirs.user_config_path(appname="zmk") / "zmk.ini"
