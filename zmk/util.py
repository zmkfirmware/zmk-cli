"""
General utilities.
"""

import functools
import operator
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, TypeVar

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
