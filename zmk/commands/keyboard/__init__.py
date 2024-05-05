"""
"zmk keyboard" command.
"""

import typer

from .add import keyboard_add
from .list import keyboard_list
from .new import keyboard_new
from .remove import keyboard_remove

app = typer.Typer(name="keyboard")
app.command(name="add")(keyboard_add)
app.command(name="list")(keyboard_list)
app.command(name="new")(keyboard_new)
app.command(name="remove")(keyboard_remove)


@app.callback()
def keyboard():
    """Add or remove keyboards from the build."""
