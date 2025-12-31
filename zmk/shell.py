"""
Shell command execution utilities.
"""

import shutil
import subprocess
from pathlib import Path


def get_subprocess_args(cmd: list[str | Path]) -> list[str | Path]:
    """
    Return an argument list with the first argument as a full path to an
    executable as determined by shutil.which(). If no matching executable is
    found, the original list is returned unmodified.
    """

    if executable := shutil.which(cmd[0]):
        return [executable] + cmd[1:]

    return cmd


def call(cmd: list[str | Path], *args, **kwargs):
    """
    Runs subprocess.call(cmd) with shell=False, but supporting looking up the
    first argument as an executable in PATH directories as if shell=True.

    On POSIX shells, shell=True requires the command to be a string, but
    shlex.join() may quote and/or escape strings in ways that are not correct
    for non-POSIX shells. This provides a more shell-agnostic way to run commands.
    """

    if kwargs.get("shell", False):
        raise ValueError("shell.call() cannot be called with shell=True")

    cmd = get_subprocess_args(cmd)
    return subprocess.call(cmd, *args, **kwargs)
