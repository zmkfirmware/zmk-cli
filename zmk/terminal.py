"""
Terminal utilities for things not already provided by Rich.
"""

# Ignore missing attributes for platform-specific modules
# pyright: reportAttributeAccessIssue = false

# Ignore alternative declarations of the same functions
# pyright: reportRedeclaration = false

import os
import sys
from collections.abc import Generator
from contextlib import contextmanager

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

    _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 4

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

    def read_key() -> bytes:
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
    def disable_echo() -> Generator[None, None, None]:
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

    def cursor_control_supported() -> bool:
        """
        Gets whether this terminal supports the virtual terminal escape sequence
        for getting the cursor position.
        """
        kernel32 = windll.kernel32
        stdout_handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)

        stdout_mode = wintypes.DWORD()
        kernel32.GetConsoleMode(stdout_handle, byref(stdout_mode))

        return bool(stdout_mode.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING)


except ImportError:
    import termios

    @contextmanager
    def disable_echo() -> Generator[None, None, None]:
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

    def read_key() -> bytes:
        """
        Waits for a key to be pressed and returns it.

        Special keys such as arrow keys return xterm or vt escape sequences.
        """
        with disable_echo():
            key = os.read(sys.stdin.fileno(), 4)

            if key == b"\x7f":  # Bash uses DELETE instead of BACKSPACE
                return BACKSPACE

            return key

    def cursor_control_supported() -> bool:
        """
        Gets whether this terminal supports the virtual terminal escape sequence
        for getting the cursor position.
        """
        # Assume that Unix terminals support VT escape sequences by default.
        return True


def get_cursor_pos() -> tuple[int, int]:
    """
    Returns the cursor position as a tuple (x, y). Positions are 0-based.

    This function may not work properly if cursor_control_supported() returns False.
    """
    with disable_echo():
        sys.stdout.write("\x1b[6n")
        sys.stdout.flush()

        result = ""
        while not result.endswith("R"):
            result += sys.stdin.read(1)

        row, _, col = result.removeprefix("\x1b[").removesuffix("R").partition(";")
        return (int(col) - 1, int(row) - 1)
