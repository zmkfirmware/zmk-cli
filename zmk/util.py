"""
General utilities.
"""

import functools
import operator
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, TypeVar

import rich
import typer
from ruamel.yaml import YAML

T = TypeVar("T")


def flatten(items: Iterable[T | Iterable[T]]) -> Iterable[T]:
    """Flatten a list of lists into one list"""
    return functools.reduce(operator.iconcat, items, [])


def read_yaml(path: Path):
    """Parse a YAML file"""
    with path.open(encoding="utf-8") as f:
        yaml = YAML()
        return yaml.load(f)


@contextmanager
def set_directory(path: Path):
    """Context manager to temporarily change the working directory"""
    original = Path().absolute()

    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)


def fatal_error(message: Any):
    """Print an error message and exit"""
    rich.print(message, file=sys.stderr)
    raise typer.Exit(code=1)
