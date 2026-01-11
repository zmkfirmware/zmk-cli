"""
"zmk version" command.
"""

from typing import Annotated

import rich
import typer
from rich.table import Table

from ..config import get_config
from ..exceptions import FatalError
from ..remote import Remote
from ..repo import Repo


def version(
    ctx: typer.Context,
    revision: Annotated[
        str | None,
        typer.Argument(
            help="Switch to this ZMK version. Prints the current ZMK version if omitted.",
        ),
    ] = None,
    list_versions: Annotated[
        bool | None,
        typer.Option("--list", "-l", help="Print the available versions and exit."),
    ] = False,
) -> None:
    """Get or set the ZMK version."""

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    if list_versions:
        _print_versions(repo)
    elif revision is None:
        _print_current_version(repo)
    else:
        _set_version(repo, revision)


def _print_versions(repo: Repo):
    zmk = repo.get_west_zmk_project()
    remote = Remote(zmk.url)

    if not remote.repo_exists():
        raise FatalError(f"Invalid repository URL: {zmk.url}")

    tags = remote.get_tags()

    if not tags:
        raise FatalError(f"{zmk.url} does not have any tagged commits.")

    for tag in tags:
        print(tag)


def _print_current_version(repo: Repo):
    zmk = repo.get_west_zmk_project()

    grid = Table.grid()
    grid.add_column()
    grid.add_column()
    grid.add_row("[bright_blue]Remote: [/bright_blue]", zmk.url)
    grid.add_row("[bright_blue]Revision: [/bright_blue]", zmk.revision)

    rich.print(grid)


def _set_version(repo: Repo, revision: str):
    repo.set_zmk_version(revision)
    repo.run_west("update")

    rich.print()
    rich.print(f'ZMK is now using revision "{revision}"')
