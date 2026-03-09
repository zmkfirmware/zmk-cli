"""
General utilities.
"""

import functools
import operator
from collections.abc import Iterable
from contextlib import contextmanager
from typing import TypeVar

from rich.console import Console, RenderableType
from rich.padding import PaddingDimensions
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

T = TypeVar("T")


def flatten(items: Iterable[T | Iterable[T]]) -> Iterable[T]:
    """Flatten a list of lists into one list"""
    return functools.reduce(operator.iconcat, items, [])


def union(items: Iterable[set[T]]) -> set[T]:
    """Compute the union of any number of sets"""
    return functools.reduce(operator.or_, items, set())


def splice(text: str, index: int, count: int = 0, insert_text: str = "") -> str:
    """
    Remove `count` characters starting from `index` in `text` and replace them
    with `insert_text`.
    """
    return text[0:index] + insert_text + text[index + count :]


def horizontal_group(
    *renderables: RenderableType,
    padding: PaddingDimensions = 0,
    collapse_padding=True,
    pad_edge=False,
    expand=False,
    highlight=True,
) -> Table:
    """
    Similar to rich.group.Group, but uses a table to place renderables in a row
    instead of a column.
    """
    grid = Table.grid(
        padding=padding,
        collapse_padding=collapse_padding,
        pad_edge=pad_edge,
        expand=expand,
    )
    grid.highlight = highlight
    grid.add_row(*renderables)
    return grid


@contextmanager
def spinner(message: str, console: Console | None = None, *, transient: bool = True):
    """Context manager which displays a loading spinner for its duration"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=transient,
    ) as progress:
        progress.add_task(message, total=None)
        yield
