"""
"zmk module add" command.
"""

import subprocess
from typing import Annotated, Optional

import rich
import typer
from rich.console import Console
from rich.prompt import InvalidResponse, Prompt, PromptBase
from west.manifest import ImportFlag, Manifest

from ...config import Config
from ...exceptions import FatalError
from ...prompt import UrlPrompt
from ...util import spinner
from ...yaml import YAML


def module_add(
    ctx: typer.Context,
    url: Annotated[
        Optional[str],
        typer.Argument(help="URL of the Git repository to add.", show_default=False),
    ] = None,
    revision: Annotated[
        Optional[str],
        typer.Argument(help="Revision to track.", show_default="main"),
    ] = None,
    name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Name of the module.", show_default=False),
    ] = None,
):
    """Add a Zephyr module to the build."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    manifest = Manifest.from_topdir(
        topdir=repo.west_path, import_flags=ImportFlag.IGNORE
    )

    if name:
        _error_if_existing_name(manifest, name)

    if url:
        _error_if_existing_url(manifest, url)
        revision = revision or _get_default_branch(url)
        name = name or _get_name_from_url(url)
        _error_if_existing_name(manifest, name)
    else:
        url = UrlPrompt.ask("Enter the module's Git repository URL")
        _error_if_existing_url(manifest, url)

        default = _get_default_branch(url)
        revision = Prompt.ask("Enter the revision to track", default=default)
        name = name or _get_name_from_url(url)

        if _has_project_with_name(manifest, name):
            rich.print(
                f'[prompt.invalid]There is already a module with the name "{name}".'
            )
            name = NamePrompt.ask(manifest)

    yaml = YAML()
    data = yaml.load(repo.project_manifest_path)

    project = yaml.map()
    project["name"] = name
    project["url"] = url
    project["revision"] = revision
    project["path"] = f"modules/{name}"

    if not "manifest" in data:
        data["manifest"] = yaml.map()

    if not "projects" in data["manifest"]:
        data["manifest"]["projects"] = yaml.seq()

    data["manifest"]["projects"].append(project)

    yaml.dump(data, repo.project_manifest_path)
    repo.run_west("update", name)


def _get_name_from_url(repo_url: str):
    return repo_url.split("/")[-1].removesuffix(".git")


class NamePrompt(PromptBase):
    """Prompt for a module name."""

    _manifest: Manifest

    def __init__(self, manifest: Manifest, *, console: Optional[Console] = None):
        super().__init__("Enter a new name", console=console)
        self._manifest = manifest

    # pylint: disable=arguments-renamed, arguments-differ
    @classmethod
    def ask(cls, manifest: Manifest, *, console: Optional[Console] = None):
        prompt = cls(manifest, console=console)
        return prompt()

    def process_response(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise InvalidResponse("[prompt.invalid]Enter a name.")

        if _has_project_with_name(self._manifest, value):
            raise InvalidResponse(
                f'[prompt.invalid]There is already a module with the name "{value}".'
            )

        return value


def _get_default_branch(repo_url: str):
    with spinner("Finding default branch."):
        # TODO: if the URL is to github, use the github API to get the default branch.
        # For now, just assume that if a repo has a "main" branch, that is the default
        # branch, else it is "master".
        try:
            result = subprocess.check_output(
                ["git", "ls-remote", repo_url, "refs/heads/*"],
                encoding="utf-8",
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            raise FatalError(exc.stderr.strip()) from exc

        for line in result.splitlines():
            _, ref = line.split()
            ref = ref.removeprefix("refs/heads/")

            if ref == "main":
                return "main"

        return "master"


def _has_project_with_name(manifest: Manifest, name: str):
    return any(p for p in manifest.projects[1:] if p.name == name)


def _has_project_with_url(manifest: Manifest, url: str):
    return any(p for p in manifest.projects[1:] if p.url == url)


def _error_if_existing_name(manifest: Manifest, name: str):
    if _has_project_with_name(manifest, name):
        raise FatalError(
            f'There is already a module with the name "{name}". '
            "Add --name=<newname> if you still want to add this module."
        )


def _error_if_existing_url(manifest: Manifest, url: str):
    if _has_project_with_url(manifest, url):
        raise FatalError(f'There is already a module with the URL "{url}".')
