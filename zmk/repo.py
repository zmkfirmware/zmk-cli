"""
Config repo and Zephyr module utilities.
"""

import os
import shutil
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, Generator, Optional

from west.app.main import main as west_main

from .util import read_yaml, set_directory

_APP_DIR_NAME = "app"
_CONFIG_DIR_NAME = "config"
_PROJECT_MANIFEST_PATH = f"{_CONFIG_DIR_NAME}/west.yml"
_MODULE_MANIFEST_PATH = "zephyr/module.yml"
_WEST_STAGING_PATH = ".zmk"
_WEST_CONFIG_PATH = ".west/config"


def is_repo(path: Path):
    return _is_config_repo(path) or _is_module_repo(path)


class Module:
    path: Path

    def __init__(self, path: Path):
        self.path = path

    @property
    def module_manifest_path(self) -> Path:
        """Path to the "zephyr/module.yml" file."""
        return self.path / _MODULE_MANIFEST_PATH

    @property
    def board_root(self) -> Optional[Path]:
        """Path to the "boards" folder."""

        # Check for board_root from module manifest
        try:
            manifest = self.get_module_yaml()

            path: str = manifest["build"]["settings"]["board_root"]
            root = self.path / path / "boards"

            return root if root.is_dir() else None

        except (FileNotFoundError, KeyError):
            pass

        # Check for Zephyr repo app/boards
        root = self.path / _APP_DIR_NAME / "boards"
        return root if root.is_dir() else None

    def get_module_yaml(self) -> Any:
        return read_yaml(self.module_manifest_path)


class Repo(Module):
    _west_ready: bool

    def __init__(self, path: Path):
        super().__init__(path)
        self._west_ready = False

    @property
    def project_manifest_path(self) -> Optional[Path]:
        """Path to the "west.yml" file."""
        return self.path / _PROJECT_MANIFEST_PATH

    @property
    def board_root(self) -> Optional[Path]:
        if root := super().board_root:
            return root

        # Fallback for old-style repos
        root = self.project_manifest_path.parent / "boards"

        return root if root.is_dir() else None

    def get_project_yaml(self) -> Any:
        return read_yaml(self.project_manifest_path)

    def get_modules(self) -> Generator[Module, None, None]:
        modules = self.run_west("list", "-f", "{path}", capture_output=True)
        for line in modules.splitlines():
            yield Module(self.west_path / line)

    @property
    def config_path(self) -> Path:
        """Path to the "config" folder."""
        return self.path / _CONFIG_DIR_NAME

    @property
    def west_path(self) -> Path:
        """Path to the west staging folder."""
        return self.path / _WEST_STAGING_PATH

    def run_west(self, *args: list[str], capture_output: bool = False) -> str | None:
        """
        Run west in the west staging folder.

        If capture_output is True, the command is run silently in the background
        and this returns the output as a string.

        Automatically calls ensure_west_ready().
        """
        self.ensure_west_ready()
        return self._run_west(*args, capture_output=capture_output)

    def ensure_west_ready(self):
        """
        Ensures the west application is correctly initialized.
        """
        if self._west_ready:
            return

        self._update_gitignore()
        self._update_west_manifest()

        config_path = self.path / _WEST_STAGING_PATH / _WEST_CONFIG_PATH
        if not config_path.exists():
            self._init_west_app()

        self._west_ready = True

    def _run_west(self, *args: list[str], capture_output=False):
        if capture_output:
            with redirect_stdout(StringIO()) as output:
                self.run_west(*args, capture_output=False)
                return output.getvalue()

        with set_directory(self.west_path):
            west_main(args)
            return None

    def _update_gitignore(self):
        gitignore = self.path / ".gitignore"

        with gitignore.open("r+", encoding="utf-8") as f:
            if any(line.strip() == _WEST_STAGING_PATH for line in f):
                return

            f.seek(0, os.SEEK_END)
            f.write(f"\n{_WEST_STAGING_PATH}\n")

    def _update_west_manifest(self):
        symlink_dir = self.west_path / _CONFIG_DIR_NAME
        symlink_dir.mkdir(parents=True, exist_ok=True)

        target = self.project_manifest_path
        symlink = self.west_path / _PROJECT_MANIFEST_PATH

        if symlink.is_symlink():
            if symlink.readlink().samefile(target):
                return

            # Symlink is to the wrong file. Delete and recreate it.
            symlink.unlink()

        elif symlink.is_file():
            symlink.unlink()

        try:
            symlink.symlink_to(target)
        except OSError:
            # Might not have permissions to symlink? Copy the file instead.
            shutil.copy(target, symlink)

    def _init_west_app(self):
        print("Initializing west application. This may take a while...")
        self._run_west("init", "-l", _CONFIG_DIR_NAME)

        # TODO: can we filter the modules to ignore ZMK dependencies that aren't needed?
        self._run_west("update")


def _is_config_repo(path: Path):
    return (path / _PROJECT_MANIFEST_PATH).is_file()


def _is_module_repo(path: Path):
    return (path / _MODULE_MANIFEST_PATH).is_file()


def _run_west(path: Path, args: list[str], capture_output=False):
    if capture_output:
        with redirect_stdout(StringIO()) as output:
            _run_west(path, args, capture_output=False)
            return output.getvalue()

    with set_directory(path):
        west_main(args)
        return None
