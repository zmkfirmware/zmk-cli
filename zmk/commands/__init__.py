"""
ZMK CLI subcommands.
"""

import typer

from . import cd, code, config, download, init, keyboard, module, west


def register(app: typer.Typer):
    """Register all commands with the app"""
    app.command()(cd.cd)
    app.command()(code.code)
    app.command()(config.config)
    app.command()(download.download)
    app.command(name="dl")(download.download)
    app.command()(init.init)
    app.command()(west.update)
    app.command(
        add_help_option=False,
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
        },
    )(west.west)

    app.add_typer(keyboard.app)
    app.add_typer(module.app)
