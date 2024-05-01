"""
"zmk cd" command.
"""

import os
import subprocess
import sys
from pathlib import Path

import shellingham
import typer
from rich.markdown import Markdown

from ..config import Config, fatal_home_not_set
from ..util import fatal_error


def cd(ctx: typer.Context):
    """Go to the ZMK config repo."""
    if not sys.stdout.isatty():
        fatal_error(
            Markdown(
                "This command can only be used from an interactive shell. "
                "Use `cd $(zmk config user.home)` instead."
            )
        )

    cfg = ctx.find_object(Config)
    home = cfg.home_path

    if home is None:
        fatal_home_not_set()

    if home == Path(os.getcwd()):
        # Already in the home directory. Nothing to do.
        return

    os.chdir(home)

    try:
        _, shell = shellingham.detect_shell()
    except shellingham.ShellDetectionFailure:
        shell = _default_shell()

    if os.name == "nt":
        subprocess.run([shell], env=os.environ.copy(), check=False)
    else:
        os.execl(shell, shell)


def _default_shell():
    if os.name == "posix":
        return os.environ["SHELL"]
    if os.name == "nt":
        return os.environ["COMSPEC"]
    raise NotImplementedError(f"Don't know how to get a shell for OS {os.name!r}")
