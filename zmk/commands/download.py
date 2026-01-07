"""
"zmk download" command.
"""

import webbrowser

import giturlparse
import typer

from ..config import get_config
from ..exceptions import FatalError
from ..repo import Repo


def download(ctx: typer.Context) -> None:
    """Open the web page to download firmware from GitHub."""

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    actions_url = _get_actions_url(repo)

    webbrowser.open(actions_url)


def _get_actions_url(repo: Repo):
    remote_url = repo.get_remote_url()

    p = giturlparse.parse(remote_url)

    match p.platform:
        case "github":
            return f"https://github.com/{p.owner}/{p.repo}/actions/workflows/build.yml"

        case _:
            raise FatalError(f"Unsupported remote URL: {remote_url}")
