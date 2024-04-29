"""
ZMK CLI subcommands.
"""

import typer

from . import cd, config, init, keyboard, west


def register(app: typer.Typer):
    """Register all commands with the app"""
    app.command()(cd.cd)
    app.command()(config.config)
    app.command()(init.init)
    app.command(
        add_help_option=False,
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
        },
    )(west.west)

    app.add_typer(keyboard.app)
