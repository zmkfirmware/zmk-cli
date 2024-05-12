"""
File templates.

Templates will be provided the following parameters:

    id: str -- The board/shield ID
    name: str -- The keyboard display name
    shortname: str -- A name abbreviated to <= 16 characters
    keyboard_type: str -- "board" or "shield"
    arch: Optional[str] -- The board architecture, e.g "arm"

"""

from pathlib import Path
from typing import Any, Generator

from mako.lookup import TemplateLookup
from mako.template import Template

_ROOT_PATH = Path(__file__).parent


def get_template_files(
    folder: str, **data: Any
) -> Generator[tuple[str, str], None, None]:
    """
    Yield (filename, data) tuples for all the template files within the given
    folder (relative to the "templates" folder).
    """
    lookup = TemplateLookup(directories=[str(_ROOT_PATH)], strict_undefined=True)
    template_path = _ROOT_PATH / folder

    for file in template_path.rglob("*"):
        template_name = str(file.relative_to(_ROOT_PATH))
        template = lookup.get_template(template_name)

        file_name = Template(text=file.name, strict_undefined=True)

        yield (
            file_name.render_unicode(**data),
            template.render_unicode(**data),
        )
