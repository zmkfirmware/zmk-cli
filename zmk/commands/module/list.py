"""
"zmk module list" command.
"""

import rich
import typer
from rich import box
from rich.table import Table

from ...config import get_config


def module_list(ctx: typer.Context) -> None:
    """Print a list of installed Zephyr modules."""

    console = rich.get_console()

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    manifest = repo.get_west_manifest()

    table = Table(box=box.SQUARE, border_style="dim blue", header_style="bright_cyan")
    table.add_column("Name")
    table.add_column("URL")
    table.add_column("Revision")

    for project in manifest.projects[1:]:
        table.add_row(project.name, project.url, project.revision)

    console.print(table)
