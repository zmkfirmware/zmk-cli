"""
"zmk code" command.
"""

import platform
import shlex
import shutil
import subprocess
from configparser import NoOptionError
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Annotated, Callable, Optional

import rich
import typer
from rich.markdown import Markdown

from ..config import Config, Settings
from ..exceptions import FatalError
from ..menu import show_menu
from ..repo import Repo


def code(
    ctx: typer.Context,
    keyboard: Annotated[
        Optional[str],
        typer.Argument(
            help="Name of the keyboard to edit. If omitted, opens the repo directory.",
        ),
    ] = None,
    open_conf: Annotated[
        bool,
        typer.Option("--conf", "-c", help="Open the .conf file instead of the keymap."),
    ] = False,
    open_build_matrix: Annotated[
        bool,
        typer.Option(
            "--build", "-b", help="Open the build matrix instead of a keymap."
        ),
    ] = False,
):
    """Open the repo or a .keymap or .conf file in a text editor."""

    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    if open_build_matrix:
        path = repo.build_matrix_path
    else:
        path = _get_file(repo, keyboard, open_conf)

    editor = _get_editor(cfg, path.is_dir())

    cmd = shlex.split(editor) + [path]
    subprocess.call(cmd, shell=True)


def _get_file(repo: Repo, keyboard: str, open_conf: bool):
    if not keyboard:
        return repo.path

    ext = ".conf" if open_conf else ".keymap"
    return repo.config_path / f"{keyboard}{ext}"


def _get_editor(cfg: Config, is_directory: bool):
    if is_directory:
        try:
            return cfg.get(Settings.CORE_EXPLORER)
        except NoOptionError:
            pass
    try:
        return cfg.get(Settings.CORE_EDITOR)
    except NoOptionError:
        pass

    # No editor found. Prompt the user to select one and try again.
    _select_editor(cfg)
    return _get_editor(cfg, is_directory)


class Support(Flag):
    """Types of files an editor supports"""

    FILE = auto()
    DIR = auto()

    ALL = FILE | DIR


@dataclass
class Editor:
    """File editing tool"""

    name: str
    cmd: str
    "Executable name or command line to execute this tool"
    support: Support = Support.FILE
    "Types of files this tool supports editing"
    test: Callable[[], bool] = None
    """
    Function that returns true if the tool is installed.
    Defaults to `which {self.cmd}`.
    """
    paths: list[str] = field(default_factory=list)
    "Extra paths to search for the executable if `test` is not set"

    def __rich__(self):
        return self.name

    def get_command(self):
        """Get the command to execute the tool, or None if it is not installed"""
        if self.test and self.test():
            return self.cmd

        if shutil.which(self.cmd):
            return self.cmd

        for path in self.paths:
            if cmd := shutil.which(self.cmd, path=path):
                return shlex.quote(cmd)

        return None


def _mac():
    return platform.system() == "Darwin"


_NPP_PATHS = ["C:\\Program Files\\Notepad++", "C:\\Program Files (x86)\\Notepad++"]
_SUBL_PATHS = [
    "C:\\Program Files\\sublime text 3",
    "C:\\Program Files (x86)\\sublime text 3",
]


_EDITORS: list[Editor] = [
    # Graphical text editors
    Editor("Visual Studio Code", cmd="code", support=Support.ALL),
    Editor("Sublime Text", cmd="subl", support=Support.ALL, paths=_SUBL_PATHS),
    Editor("Emacs", cmd="emacs", support=Support.ALL),
    Editor("Gedit", cmd="gedit"),
    Editor("Notepad", cmd="notepad"),
    Editor("Notepad++", cmd="notepad++", paths=_NPP_PATHS),
    Editor("TextEdit", cmd="open -a TextEdit", test=_mac),
    Editor("TextMate", cmd="mate", support=Support.ALL),
    # Terminal text editors
    Editor("Nano", cmd="nano"),
    Editor("Neovim", cmd="nvim", support=Support.ALL),
    Editor("Vim", cmd="vim", support=Support.ALL),
    # File explorers
    Editor("File Explorer", cmd="explorer", support=Support.DIR),
    Editor("Nautilus", cmd="nautilus", support=Support.DIR),
    Editor("Finder", cmd="open", support=Support.DIR, test=_mac),
]


def _select_editor(cfg: Config):
    available = [e for e in _EDITORS if e.get_command()]
    file_editors = [e for e in available if e.support & Support.FILE]
    dir_editors = [e for e in available if e.support & Support.DIR]

    if not file_editors:
        raise FatalError(
            "Could not find a known text editor.\n"
            "Run \"zmk config core.editor='<command>'\" "
            'replacing "<command>" with the path to a text editor.'
        )

    editor = show_menu("Select a text editor:", file_editors, filter_func=_filter)
    cfg.set(Settings.CORE_EDITOR, editor.get_command())

    explorer = None
    if editor.support & Support.DIR:
        cfg.remove(Settings.CORE_EXPLORER)
    elif dir_editors:
        explorer = show_menu(
            "This text editor only supports opening files.\n"
            "Select another tool for opening directories:",
            dir_editors,
            filter_func=_filter,
        )
        cfg.set(Settings.CORE_EXPLORER, explorer.get_command())

    cfg.write()

    rich.print("Editor saved:")
    rich.print(Markdown(f'`zmk config core.editor="{editor.get_command()}"`'))
    if explorer:
        rich.print(Markdown(f'`zmk config core.explorer="{explorer.get_command()}"`'))

    rich.print()


def _filter(editor: Editor, text: str):
    return text.casefold() in editor.name.casefold()
