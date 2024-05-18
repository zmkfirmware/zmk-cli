"""
Terminal utilities
"""

import os
import sys
from contextlib import contextmanager


def hide_cursor():
    """Hides the terminal cursor."""
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()


def show_cursor():
    """Unhides the terminal cursor."""
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()


ESCAPE = b"\x1b"
BACKSPACE = b"\b"
RETURN = b"\n"
TAB = b"\t"
UP = b"\x1b[A"
DOWN = b"\x1b[B"
RIGHT = b"\x1b[C"
LEFT = b"\x1b[D"
END = b"\x1b[F"
HOME = b"\x1b[H"
DELETE = b"\x1b[3~"
PAGE_UP = b"\x1b[5~"
PAGE_DOWN = b"\x1b[6~"


try:
    import msvcrt
    from ctypes import byref, windll, wintypes

    _STD_INPUT_HANDLE = -10
    _STD_OUTPUT_HANDLE = -11

    _ENABLE_PROCESSED_OUTPUT = 1
    _ENABLE_WRAP_AT_EOL_OUTPUT = 2
    _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 4
    _VT_FLAGS = (
        _ENABLE_PROCESSED_OUTPUT
        | _ENABLE_WRAP_AT_EOL_OUTPUT
        | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
    )

    _WINDOWS_SPECIAL_KEYS = {
        71: HOME,
        72: UP,
        73: PAGE_UP,
        75: LEFT,
        77: RIGHT,
        79: END,
        80: DOWN,
        81: PAGE_DOWN,
        83: DELETE,
    }

    def read_key():
        """
        Waits for a key to be pressed and returns it.

        Special keys such as arrow keys return xterm or vt escape sequences.
        """
        key = msvcrt.getch()

        if key == b"\x03":  # CTRL+C
            raise KeyboardInterrupt()

        if key == b"\r":  # Windows uses \r instead of \n
            return RETURN

        if key in (b"\x00", b"\xe0"):
            code = ord(msvcrt.getch())
            return _WINDOWS_SPECIAL_KEYS.get(code, b"")

        return key

    @contextmanager
    def enable_vt_mode():
        """
        Context manager which enables virtual terminal processing.
        """
        kernel32 = windll.kernel32
        stdout_handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)

        old_stdout_mode = wintypes.DWORD()
        kernel32.GetConsoleMode(stdout_handle, byref(old_stdout_mode))

        new_stdout_mode = old_stdout_mode.value | _VT_FLAGS

        try:
            kernel32.SetConsoleMode(stdout_handle, new_stdout_mode)
            yield
        finally:
            kernel32.SetConsoleMode(stdout_handle, old_stdout_mode)

    @contextmanager
    def disable_echo():
        """
        Context manager which disables console echo
        """
        kernel32 = windll.kernel32
        stdin_handle = kernel32.GetStdHandle(_STD_INPUT_HANDLE)

        old_stdin_mode = wintypes.DWORD()
        kernel32.GetConsoleMode(stdin_handle, byref(old_stdin_mode))

        try:
            kernel32.SetConsoleMode(stdin_handle, 0)
            yield
        finally:
            kernel32.SetConsoleMode(stdin_handle, old_stdin_mode)

except ImportError:
    import termios

    @contextmanager
    def enable_vt_mode():
        """
        Context manager which enables virtual terminal processing.
        """
        # Assume that Unix terminals support VT escape sequences by default.
        yield

    @contextmanager
    def disable_echo():
        """
        Context manager which disables console echo
        """
        oldattr = termios.tcgetattr(sys.stdin)
        newattr = oldattr[:]
        newattr[3] &= ~(termios.ECHO | termios.ICANON)

        try:
            termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, newattr)
            yield
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, oldattr)

    def read_key():
        """
        Waits for a key to be pressed and returns it.

        Special keys such as arrow keys return xterm or vt escape sequences.
        """
        with disable_echo():
            return os.read(sys.stdin.fileno(), 4)


def get_cursor_pos() -> tuple[int, int]:
    """
    Returns the cursor position as a tuple (row, column). Positions are 0-based.
    """
    with disable_echo():
        sys.stdout.write("\x1b[6n")
        sys.stdout.flush()

        result = ""
        while not result.endswith("R"):
            result += sys.stdin.read(1)

        row, _, col = result.removeprefix("\x1b[").removesuffix("R").partition(";")
        return (int(row) - 1, int(col) - 1)


def set_cursor_pos(row=0, col=0):
    """
    Sets the cursor to the given row and column. Positions are 0-based.
    """
    with disable_echo():
        sys.stdout.write(f"\x1b[{row + 1};{col + 1}H")
        sys.stdout.flush()
