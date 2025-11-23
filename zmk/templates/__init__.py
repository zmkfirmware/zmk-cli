"""
File templates.

Templates will be provided the following parameters:

    id: str -- The board/shield ID
    name: str -- The keyboard display name
    shortname: str -- A name abbreviated to <= 16 characters
    keyboard_type: str -- "board" or "shield"
    interconnect: str -- The interconnect ID for the controller board. May be empty.
    arch: str -- The board architecture, e.g "arm". May be empty.
    gpio: str -- The default node label for GPIO, e.g. "&gpio0".

"""

import re
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

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
    lookup = TemplateLookup(
        directories=[str(_ROOT_PATH)],
        preprocessor=_remove_tag_newlines,
        strict_undefined=True,
    )
    template_path = _ROOT_PATH / folder

    for file in template_path.rglob("*"):
        name_template = Template(text=file.name, strict_undefined=True)
        name = cast(str, name_template.render_unicode(**data))

        # Board identifiers can contain forward slashes. File names cannot.
        name = name.replace("/", "_")

        file_template_name = str(file.relative_to(_ROOT_PATH))
        file_template = lookup.get_template(file_template_name)
        text = _ensure_trailing_newline(cast(str, file_template.render_unicode(**data)))

        yield name, text


# Matches <%tag ...>, </%tag ...>, and <%tag ... />. Group 1 is the tag name.
_MAKO_TAG_RE = re.compile(r"\s*<\/?%\s*([\w:]+)(?:\s+.*?)?\/?>\s*")
_IGNORE_TAGS = [
    "include",  # Includes seem to get trimmed, so keep the \n at the include site.
    "text",  # "<%text>\" would insert a "\" as text instead of trimming the \n.
]


def _remove_tag_newlines(text: str) -> str:
    """
    Template preprocessor that finds Mako <%...> </%...> and <%.../> tags on a
    line by themselves and escapes the trailing \\n so they do not create a
    blank line in the rendered output.
    """

    def escape(line: str):
        if m := _MAKO_TAG_RE.fullmatch(line):
            if m.group(1) not in _IGNORE_TAGS:
                return line + "\\"
        return line

    lines = text.splitlines()

    # Do not escape the final line, since there is not a \n to escape there.
    escaped = [escape(line) for line in lines[:-1]] + lines[-1:]

    return "\n".join(escaped)


def _ensure_trailing_newline(text: str) -> str:
    """Trim whitespace from a string, then add a \\n to the end."""
    return text.strip() + "\n"
