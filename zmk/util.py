"""
General utilities.
"""

import functools
import operator
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Optional, TypeVar

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

T = TypeVar("T")


def flatten(items: Iterable[T | Iterable[T]]) -> Iterable[T]:
    """Flatten a list of lists into one list"""
    return functools.reduce(operator.iconcat, items, [])


def splice(text: str, index: int, count: int = 0, insert_text: str = ""):
    """
    Remove `count` characters starting from `index` in `text` and replace them
    with `insert_text`.
    """
    return text[0:index] + insert_text + text[index + count :]


@contextmanager
def set_directory(path: Path):
    """Context manager to temporarily change the working directory"""
    original = Path().absolute()

    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)


@contextmanager
def spinner(message: str, console: Optional[Console] = None, transient: bool = True):
    """Context manager which displays a loading spinner for its duration"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=transient,
    ) as progress:
        progress.add_task(message, total=None)
        yield
