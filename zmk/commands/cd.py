"""
"zmk cd" command.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import shellingham
import typer

from ..config import get_config
from ..exceptions import FatalError, FatalHomeMissing, FatalHomeNotSet


def cd(ctx: typer.Context) -> None:
    """Go to the ZMK config repo."""
    if not sys.stdout.isatty():
        raise FatalError(
            "This command can only be used from an interactive shell. "
            'Use "cd $(zmk config user.home)" instead.'
        )

    cfg = get_config(ctx)
    home = cfg.home_path

    if home is None:
        raise FatalHomeNotSet()

    if not home.is_dir():
        raise FatalHomeMissing(home)

    if home == Path(os.getcwd()):
        # Already in the home directory. Nothing to do.
        return

    os.chdir(home)

    try:
        _, shell = shellingham.detect_shell()
        shell = shutil.which(shell) or _default_shell()
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
