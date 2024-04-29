import typer
from . import cd
from . import config
from . import init
from . import keyboard
from . import west


def register(app: typer.Typer):
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
