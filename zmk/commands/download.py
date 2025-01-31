"""
"zmk download" command.
"""

import typer

from ..config import get_config
from ..repo import Repo


def download(ctx: typer.Context) -> None:
    """Open the web page to download firmware from GitHub."""

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    actions_url = _get_actions_url(repo)

    typer.launch(actions_url)


def _get_actions_url(repo: Repo):
    remote = repo.git("remote", capture_output=True).strip()
    remote_url = repo.git("remote", "get-url", remote, capture_output=True).strip()
    remote_url = remote_url.replace("git@github.com:", "https://github.com/").replace(".git", "")
    
    return f"{remote_url}/actions/workflows/build.yml"
