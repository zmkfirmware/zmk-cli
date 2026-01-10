"""
Config repo and Zephyr module utilities.
"""

import shutil
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal, overload

import west.manifest

from .remote import Remote
from .yaml import YAML, read_yaml

_APP_DIR_NAME = "app"
_BUILD_MATRIX_PATH = "build.yaml"
_BUILD_WORKFLOW_PATH = ".github/workflows/build.yml"
_CONFIG_DIR_NAME = "config"
_PROJECT_MANIFEST_PATH = f"{_CONFIG_DIR_NAME}/west.yml"
_MODULE_MANIFEST_PATH = "zephyr/module.yml"
_WEST_STAGING_PATH = ".zmk"
_WEST_CONFIG_PATH = ".west/config"

# Don't clone projects from ZMK's manifest that aren't needed for discovering keyboards
_PROJECT_BLOCKLIST = [
    "lvgl",
    "nanopb",
    "zephyr",
    "zmk-studio-messages",
]
_GROUP_BLOCKLIST = [
    "hal",
]


def is_repo(path: Path) -> bool:
    """Get whether a path is a ZMK config repo."""
    return (path / _PROJECT_MANIFEST_PATH).is_file()


def find_containing_repo(path: Path | None = None) -> Path | None:
    """Search upwards from the given path for a ZMK config repo."""
    path = path or Path()
    path = path.absolute()

    return next((p for p in [path, *path.parents] if is_repo(p)), None)


class Module:
    """
    Zephyr module repository.
    """

    path: Path

    def __init__(self, path: Path):
        self.path = path.resolve()

    @property
    def module_manifest_path(self) -> Path:
        """Path to the "zephyr/module.yml" file."""
        return self.path / _MODULE_MANIFEST_PATH

    @property
    def board_root(self) -> Path | None:
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
        """Get the "zephyr/module.yml" file data."""
        return read_yaml(self.module_manifest_path)


class Repo(Module):
    """
    ZMK config repository.
    """

    _west_ready: bool

    def __init__(self, path: Path):
        super().__init__(path)
        self._west_ready = False

    @property
    def project_manifest_path(self) -> Path:
        """Path to the "west.yml" file."""
        return self.path / _PROJECT_MANIFEST_PATH

    @property
    def board_root(self) -> Path | None:
        if root := super().board_root:
            return root

        # Fallback for old-style repos
        root = self.project_manifest_path.parent / "boards"

        return root if root.is_dir() else None

    def get_project_yaml(self) -> Any:
        """Get the "west.yml" file data."""
        return read_yaml(self.project_manifest_path)

    def get_modules(self) -> Generator[Module, None, None]:
        """Get the modules imported by the repo."""
        modules = self.run_west("list", "-f", "{path}", capture_output=True)
        for line in modules.splitlines():
            yield Module(self.west_path / line)

    def get_remote_url(self) -> str:
        """Get the remote URL for the checked out Git branch."""
        remote = self.git("remote", capture_output=True).strip()
        return self.git("remote", "get-url", remote, capture_output=True).strip()

    def get_remote(self) -> Remote:
        """Get a Remote object for the checked out Git branch's remote URL."""
        return Remote(self.get_remote_url())

    def get_west_manifest(self) -> west.manifest.Manifest:
        """Return the parsed contents of the "west.yml" file."""
        return west.manifest.Manifest.from_topdir(
            topdir=self.west_path, import_flags=west.manifest.ImportFlag.IGNORE
        )

    def get_west_zmk_project(self) -> west.manifest.Project:
        """Return the West project for the "zmk" repo."""
        manifest = self.get_west_manifest()
        projects = manifest.get_projects(["zmk"])

        try:
            return projects[0]
        except IndexError as ex:
            raise RuntimeError(
                f'{self.project_manifest_path} is missing "zmk" project.'
            ) from ex

    @property
    def build_matrix_path(self) -> Path:
        """Path to the "build.yaml" file."""
        return self.path / _BUILD_MATRIX_PATH

    @property
    def build_workflow_path(self) -> Path:
        """Path to the GitHub workflow build.yml file."""
        return self.path / _BUILD_WORKFLOW_PATH

    @property
    def config_path(self) -> Path:
        """Path to the "config" folder."""
        return self.path / _CONFIG_DIR_NAME

    @property
    def west_path(self) -> Path:
        """Path to the west staging folder."""
        return self.path / _WEST_STAGING_PATH

    @overload
    def git(self, *args: str, capture_output: Literal[False] = False) -> None: ...

    @overload
    def git(self, *args: str, capture_output: Literal[True]) -> str: ...

    @overload
    def git(self, *args: str, capture_output: bool) -> str | None: ...

    def git(self, *args: str, capture_output: bool = False) -> str | None:
        """
        Run Git in the repo.

        If capture_output is True, the command is run silently in the background
        and this returns the output as a string.
        """
        args = ("git", *args)

        if capture_output:
            return subprocess.check_output(
                args, encoding="utf-8", stderr=subprocess.PIPE, cwd=self.path
            )

        subprocess.check_call(args, encoding="utf-8")
        return None

    @overload
    def run_west(self, *args: str, capture_output: Literal[False] = False) -> None: ...

    @overload
    def run_west(self, *args: str, capture_output: Literal[True]) -> str: ...

    @overload
    def run_west(self, *args: str, capture_output: bool) -> str | None: ...

    def run_west(self, *args: str, capture_output: bool = False):
        """
        Run west in the west staging folder.

        If capture_output is True, the command is run silently in the background
        and this returns the output as a string.

        Automatically calls ensure_west_ready().
        """
        self.ensure_west_ready()
        return self._run_west(*args, capture_output=capture_output)

    def ensure_west_ready(self) -> None:
        """
        Ensures the west application is correctly initialized.
        """
        if self._west_ready:
            return

        self._update_gitignore()
        self._update_west_manifest()

        config_path = self.path / _WEST_STAGING_PATH / _WEST_CONFIG_PATH
        if config_path.exists():
            self._update_filters()
        else:
            self._init_west_app()

        self._west_ready = True

    def set_zmk_version(self, revision: str) -> None:
        """
        Modifies the "west.yml" file to change the default revision for projects
        and modifies the GitHub workflow file to match.

        This does not automatically check out the new revision. Run
        Repo.run_west("update") after calling this.

        :raises ValueError: if the given revision does not exist in the remote repo.
        """
        zmk = self.get_west_zmk_project()

        remote = Remote(zmk.url)
        if not remote.revision_exists(revision):
            raise ValueError(f'Revision "{revision}" does not exist in {zmk.url}')

        # Update the project manifest
        yaml = YAML()
        data = yaml.load(self.project_manifest_path)

        if not "defaults" in data["manifest"]:
            data["manifest"]["defaults"] = yaml.map()

        data["manifest"]["defaults"]["revision"] = revision

        for project in data["manifest"]["projects"]:
            if project["name"] == "zmk":
                try:
                    del project["revision"]
                except KeyError:
                    pass
                break

        yaml.dump(data, self.project_manifest_path)

        # Update the build workflow to match. The user may have customized this
        # file, so only update it if it looks like it's using the default workflow,
        # and ignore any errors to read or update it.
        try:
            yaml = YAML()
            data = yaml.load(self.build_workflow_path)

            build = data["jobs"]["build"]
            workflow, _, _ = build["uses"].rpartition("@")

            if workflow.endswith(".github/workflows/build-user-config.yml"):
                build["uses"] = f"{workflow}@{revision}"

                yaml.dump(data, self.build_workflow_path)
        except KeyError:
            pass

    def get_west_config(self, name: str) -> str:
        """Get the value of a West configuration setting"""
        try:
            return self._run_west(
                "config", "--local", name, capture_output=True
            ).removesuffix("\n")
        except subprocess.CalledProcessError:
            return ""

    def set_west_config(self, name: str, value: str) -> None:
        """Set the value of a West configuration setting"""
        self._run_west("config", "--local", name, "--", value)

    @overload
    def _run_west(self, *args: str, capture_output: Literal[False] = False) -> None: ...

    @overload
    def _run_west(self, *args: str, capture_output: Literal[True]) -> str: ...

    @overload
    def _run_west(self, *args: str, capture_output: bool) -> str | None: ...

    def _run_west(self, *args: str, capture_output=False):
        command = [sys.executable, "-m", "west", *args]

        if capture_output:
            return subprocess.check_output(
                command, cwd=self.west_path, text=True, stderr=subprocess.STDOUT
            )

        subprocess.check_call(command, cwd=self.west_path)
        return None

    def _update_gitignore(self):
        gitignore = self.path / ".gitignore"
        ignore_line = _WEST_STAGING_PATH + "/"

        with gitignore.open("a+", encoding="utf-8") as f:
            f.seek(0)

            if any(line.strip() == ignore_line for line in f):
                return

            f.write(f"\n{ignore_line}\n")

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

        self._update_filters()
        self._run_west("update")

    def _update_filters(self):
        current_group_filter = self.get_west_config("manifest.group-filter")
        current_project_filter = self.get_west_config("manifest.project-filter")

        new_group_filter = _blocklist_to_filter(_GROUP_BLOCKLIST)
        new_project_filter = _blocklist_to_filter(_PROJECT_BLOCKLIST)

        if current_group_filter != new_group_filter:
            self.set_west_config("manifest.group-filter", new_group_filter)

        if current_project_filter != new_project_filter:
            self.set_west_config("manifest.project-filter", new_project_filter)


def _blocklist_to_filter(blocklist: list[str]) -> str:
    return ",".join("-" + item for item in blocklist)
