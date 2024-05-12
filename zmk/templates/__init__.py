"""
File templates.
"""

from pathlib import Path
from typing import Any, Generator

from mako.template import Template

_ROOT_PATH = Path(__file__).parent


def get_template_files(
    folder: str, **data: Any
) -> Generator[tuple[Path, str], None, None]:
    """
    Yield (filename, data) tuples for all the template files within the given
    folder (relative to the "templates" folder).
    """
    template_path = _ROOT_PATH / folder

    for file in template_path.rglob("*"):
        file_name = Template(
            str(file.relative_to(template_path)), strict_undefined=True
        )
        template = Template(filename=str(file), strict_undefined=True)

        yield (Path(file_name.render_unicode(**data)), template.render_unicode(**data))
