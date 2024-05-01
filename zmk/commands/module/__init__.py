"""
"zmk module" command.
"""

import typer

from .add import module_add
from .list import module_list
from .remove import module_remove

app = typer.Typer(name="module")
app.command(name="add")(module_add)
app.command(name="list")(module_list)
app.command(name="remove")(module_remove)


@app.callback()
def keyboard():
    """Add or remove Zephyr modules from the build."""
