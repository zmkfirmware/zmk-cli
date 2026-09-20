"""
Terminal utilities for things not already provided by Rich.
"""

# Ignore missing attributes for platform-specific modules
# pyright: reportAttributeAccessIssue = false

# Ignore alternative declarations of the same functions
# pyright: reportRedeclaration = false

import os
import sys
import time
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

    _getch = msvcrt.getch
    _kbhit = msvcrt.kbhit

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

    def _vt_supported() -> bool:
        """
        Get whether this terminal supports virtual terminal escape sequences.
        """
        kernel32 = windll.kernel32
        stdout_handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)

        stdout_mode = wintypes.DWORD()
        kernel32.GetConsoleMode(stdout_handle, byref(stdout_mode))

        return bool(stdout_mode.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING)


except ImportError:
    import select
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

    def _getch() -> bytes:
        return os.read(sys.stdin.fileno(), 1)

    def _kbhit() -> bool:
        return bool(select.select([sys.stdin], [], [], 0)[0])

    def _vt_supported() -> bool:
        """
        Get whether this terminal supports virtual terminal escape sequences.
        """
        return True


def send_csi(command: str, timeout=0.5) -> str:
    """
    Attempt to send a CSI command and get the response.

    The "\\x1b[" prefix and "R" suffix will not be included in the response.

    If the terminal is not a TTY or does not support VT sequences, or if the
    timeout expires without getting a full response, this returns "".

    :param: The command (not including \\x1b[ prefix).
    :timeout: Time to wait for a response in seconds.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty() or not _vt_supported():
        return ""

    with disable_echo():
        # Discard any data already in stdin
        sys.stdin.flush()
        while _kbhit():
            _getch()

        sys.stdout.write("\x1b[" + command)
        sys.stdout.flush()

        response = b""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if _kbhit():
                c = _getch()
                response += c

                if c == b"R":
                    # R indicates the end of the response
                    break
            else:
                time.sleep(0.001)

    if response.startswith(b"\x1b[") and response.endswith(b"R"):
        return response[2:-1].decode(errors="ignore")

    return ""


def get_cursor_pos_supported() -> bool:
    """
    Get whether this terminal supports the virtual terminal escape sequence for
    getting the cursor position.
    """
    return bool(send_csi("6n"))


def get_cursor_pos() -> tuple[int, int]:
    """
    Get the cursor position as a tuple (x, y). Positions are 0-based.

    If the terminal does not support this function, this may return (0, 0) after
    a timeout. Use cursor_control_supported() to check if the command is supported
    and avoid calling this function if it is not supported to avoid delays.
    """
    if result := send_csi("6n"):
        row, _, col = result.partition(";")
        return (int(col) - 1, int(row) - 1)

    return (0, 0)
