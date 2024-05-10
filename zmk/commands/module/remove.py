"""
"zmk module remove" command.
"""

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from typing import Annotated, Any, Optional

import rich
import typer
from west.manifest import ImportFlag, Manifest, Project

from ...config import Config
from ...exceptions import FatalError
from ...menu import Detail, detail_list, show_menu
from ...repo import Repo
from ...util import spinner
from ...yaml import YAML


def module_remove(
    ctx: typer.Context,
    module: Annotated[
        Optional[str],
        typer.Argument(help="Name or URL of the module to remove.", show_default=False),
    ] = None,
):
    """Remove a Zephyr module from the build."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    manifest = Manifest.from_topdir(
        topdir=repo.west_path, import_flags=ImportFlag.IGNORE
    )

    # Don't allow deleting ZMK, or the repo won't build anymore.
    projects = [p for p in manifest.projects[1:] if p.name != "zmk"]

    if not projects:
        rich.print("There are no modules that can be removed.")
        raise typer.Exit()

    project = _find_project(projects, module) if module else _prompt_project(projects)

    yaml = YAML()
    data = yaml.load(repo.project_manifest_path)

    items: list[dict[str, Any]] = data["manifest"]["projects"]
    items = [i for i in items if not i["name"] == project.name]

    data["manifest"]["projects"] = items
    yaml.dump(data, repo.project_manifest_path)

    _delete_project_files(repo, project)

    rich.print(f'Removed module "{project.name}".')


def _find_project(projects: list[Project], module: str):
    try:
        return next(p for p in projects if module in (p.name, p.url))
    except StopIteration as exc:
        raise FatalError(f'No module with name or URL "{module}" found.') from exc


def _delete_project_files(repo: Repo, project: Project):
    # Workaround for shutil.rmtree() failing on Windows.
    def remove_readonly(func, path, _):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    module_path = repo.west_path / project.path
    if not module_path.is_dir():
        return

    with spinner("Deleting module files."):
        try:
            # Make sure Git isn't locking the folder first.
            subprocess.call(["git", "fsmonitor--daemon", "stop"], cwd=module_path)

            shutil.rmtree(module_path, onexc=remove_readonly)
        except FileNotFoundError:
            pass
        except OSError as exc:
            rich.print(exc)
            rich.print(
                f'[red]Could not clean up module files. Please manually delete "{module_path}".'
            )


def _prompt_project(projects: list[Project]):
    items = detail_list((ProjectWrapper(p), p.url) for p in projects)

    result = show_menu("Select the module to remove:", items, filter_func=_filter)
    return result.data.project


@dataclass
class ProjectWrapper:
    """Wraps a west project to format it for menu items."""

    project: Project

    def __str__(self):
        return self.project.name


def _filter(item: Detail[ProjectWrapper], text: str):
    text = text.casefold()
    return text in item.data.project.name.casefold() or text in item.detail
