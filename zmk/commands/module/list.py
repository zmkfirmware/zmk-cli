"""
"zmk module list" command.
"""

import rich
import typer
from rich import box
from rich.table import Table
from west.manifest import ImportFlag, Manifest

from ...config import Config


def module_list(
    ctx: typer.Context,
):
    """Print a list of installed Zephyr modules."""

    console = rich.get_console()

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    manifest = Manifest.from_topdir(
        topdir=repo.west_path, import_flags=ImportFlag.IGNORE
    )

    table = Table(box=box.SQUARE, border_style="dim blue", header_style="bright_cyan")
    table.add_column("Name")
    table.add_column("URL")
    table.add_column("Revision")

    for project in manifest.projects[1:]:
        table.add_row(project.name, project.url, project.revision)

    console.print(table)
