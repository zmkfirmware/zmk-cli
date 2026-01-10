"""
"zmk download" command.
"""

import webbrowser

import typer

from ..config import get_config


def download(ctx: typer.Context) -> None:
    """Open the web page to download firmware from GitHub."""

    cfg = get_config(ctx)
    repo = cfg.get_repo()

    webbrowser.open(repo.get_remote().firmware_download_url)
