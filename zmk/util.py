from contextlib import contextmanager
import functools
import operator
from pathlib import Path
import os
from typing import Iterable, TypeVar

from ruamel.yaml import YAML

T = TypeVar("T")


def flatten(items: Iterable[T | Iterable[T]]) -> Iterable[T]:
    return functools.reduce(operator.iconcat, items, [])


def read_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        yaml = YAML()
        return yaml.load(f)


@contextmanager
def set_directory(path: Path):
    original = Path().absolute()

    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)
