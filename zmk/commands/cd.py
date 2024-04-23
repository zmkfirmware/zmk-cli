import os
from pathlib import Path
import subprocess
import sys
import shellingham
import typer

from ..config import Config
from ..subcommands import command


@command
def cd(ctx: typer.Context):
    """Go to the ZMK config repo."""
    if not sys.stdout.isatty():
        print(
            "This command can only be used from an interactive shell. "
            "Use 'cd $(zmk config user.home)' instead.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    cfg = ctx.find_object(Config)
    home = cfg.ensure_home()

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
