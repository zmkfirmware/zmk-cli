"""
"zmk init" command.
"""

import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import rich
import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..build import BuildMatrix
from ..config import Config, get_config, set_context_repo
from ..exceptions import FatalError
from ..menu import show_menu
from ..prompt import UrlPrompt
from ..repo import Repo, find_containing_repo, is_repo
from .keyboard.add import keyboard_add

TEMPLATE_URL = (
    "https://github.com/new?template_name=unified-zmk-config-template"
    "&template_owner=zmkfirmware&name=zmk-config"
)
TEXT_WIDTH = 80


def init(
    ctx: typer.Context,
    url: Annotated[
        str | None, typer.Argument(help="URL of an existing repository to clone.")
    ] = None,
    name: Annotated[
        str | None,
        typer.Argument(help="Directory name where the repo should be cloned."),
    ] = None,
    revision: Annotated[
        str | None,
        typer.Option(
            "--zmk-version",
            metavar="REVISION",
            help="Use the specified version of ZMK instead of the default.",
        ),
    ] = None,
) -> None:
    """Create a new ZMK config repo or clone an existing one."""

    console = rich.get_console()
    cfg = get_config(ctx)

    _check_dependencies()
    _check_for_existing_repo(cfg)

    if url is None:
        url = _get_repo_url()

    if name is None:
        name = _get_directory_name(url)

    _clone_repo(url, name)

    repo = Repo(Path() / name)

    # Make sure everything we do after this point applies to this new repo.
    set_context_repo(ctx, repo)

    if revision:
        try:
            repo.ensure_west_ready()
            repo.set_zmk_version(revision)
        except ValueError as ex:
            console.print()
            console.print(
                f'[yellow]Failed to switch to ZMK revision "{revision}":[/yellow]'
            )
            console.print(ex)
            console.print()

    repo.run_west("update")

    console.print()
    console.print(f'Your repo has been cloned to "{repo.path}".')

    if not cfg.home_path or Confirm.ask("Make this your default repo?", default=True):
        cfg.home_path = repo.path
        cfg.write()

    console.print()
    console.print("[bright_magenta]Here are some things you can do now:")

    table = Table(box=None)
    table.add_row('[green]"zmk keyboard add"', "Add a keyboard.")
    table.add_row('[green]"zmk code"', "Edit the repo files.")
    table.add_row('[green]"zmk cd"', "Move to the repo directory.")
    console.print(table)

    _add_first_keyboard(ctx, console, repo)

    if repo.path != cfg.home_path:
        console.print()
        console.print("[yellow]The new repo is not your default repo.")
        console.print('Run the following command before any other "zmk" commands:')
        console.print()
        console.print(f'    [green]cd "{repo.path}"')
        console.print()

    # TODO: add some help for how to commit and push changes


def _git_download_url():
    match platform.system():
        case "Linux":
            return "https://git-scm.com/download/linux"
        case "Windows":
            return "https://git-scm.com/download/win"
        case "Darwin":
            return "https://git-scm.com/download/mac"
        case _:
            return "https://git-scm.com/downloads"


def _check_dependencies():
    if not shutil.which("git"):
        raise FatalError(
            f"Could not find Git. Please install it from {_git_download_url()} "
            "and restart this terminal."
        )


def _check_for_existing_repo(cfg: Config):
    if find_containing_repo():
        rich.print("The current directory is already a ZMK config repo.")
        raise typer.Exit()

    if cfg.home_path and is_repo(cfg.home_path):
        rich.print(f'You already have a ZMK config repo at "{cfg.home_path}".')
        if not Confirm.ask("Initialize a new repo?", default=False):
            raise typer.Exit()

        rich.print()


_CREATE_NEW_REPO = "Create a new ZMK config repo"
_CLONE_REPO = "Clone an existing repo"


def _get_repo_url():
    console = rich.get_console()

    response = show_menu(title=None, items=[_CREATE_NEW_REPO, _CLONE_REPO])

    if response == _CLONE_REPO:
        console.print("Enter the URL of your ZMK config repo.")
        return UrlPrompt.ask("Repository URL")

    console.print(
        "To create your ZMK config repo, we will open a GitHub page in your web "
        "browser to create a repo from a template. Log in to GitHub if necessary, "
        "then click the green [green]Create repository[/green] button."
        "\n\n"
        "Once it finishes creating the repo, Click the green [green]<> Code[/green] "
        "button, then copy the HTTPS URL and paste it here. "
        "Press [green]Enter[/green] to when you're ready.",
        width=TEXT_WIDTH,
    )
    input()

    if not webbrowser.open(TEMPLATE_URL):
        console.print(
            "[yellow]Failed to open a browser. Please open the following link in a web browser:"
        )
        console.print("")
        console.print(TEMPLATE_URL)
        console.print("")

    return UrlPrompt.ask("Repository URL")


def _get_directory_name(url: str):
    # Default name is the last path component of the URL without any ".git" suffix
    default = urlparse(url).path.split("/")[-1].removesuffix(".git")

    return Prompt.ask("Enter a directory name", default=default)


def _clone_repo(url: str, name: str):
    try:
        subprocess.check_call(["git", "clone", url, name])
    except subprocess.CalledProcessError as ex:
        raise typer.Exit(code=ex.returncode)


def _add_first_keyboard(ctx: typer.Context, console: Console, repo: Repo):
    matrix = BuildMatrix.from_repo(repo)
    if matrix.include:
        return

    console.print()
    console.print("This looks like a new repo.")

    if Confirm.ask("Would you like to add a keyboard now?", default=True):
        keyboard_add(ctx)
