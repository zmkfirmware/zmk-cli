"""
Terminal menus
"""

from contextlib import contextmanager
from typing import Any, Callable, Generic, Iterable, Optional, TypeVar

import rich
from rich.console import Console
from rich.highlighter import Highlighter
from rich.style import Style
from rich.text import Text
from rich.theme import Theme

from . import terminal
from .util import splice


class StopMenu(KeyboardInterrupt):
    """
    Exception thrown when the user cancels the menu without making a selection
    """


T = TypeVar("T")


class TerminalMenu(Generic[T], Highlighter):
    """
    Manages an interactive menu in a terminal window.
    """

    CONTROLS = "[↑↓: select] [Enter: confirm] [Esc: cancel]"
    FILTER_CONTROLS = " [Type to search]"

    TOP_MARGIN = 1  # Number of lines of context to display before the menu
    CONTROL_LINES = 1  # number of lines for displaying controls
    SCROLL_MARGIN = 1  # Start scrolling when cursor is this many lines from the end

    DEFAULT_THEME = Theme(
        {
            "title": "bright_magenta",  # Prompt text
            "filter": "default",  # Search/filter text
            "unfocus": "default",  # Unfocused item
            "focus": "bright_cyan",  # Focused item
            "highlight": Style(bgcolor="grey19"),  # Text in item that matches filter
            "ellipsis": "dim",  # '...' to indicate more items
            "controls": "dim",  # Bottom text which lists controls
        }
    )

    title: Any
    items: list[T]
    default_index: int

    _filter_func: Optional[Callable[[T, str], bool]]
    _filter_text: str
    _filter_items: list[T]
    _cursor_index: int

    _top_row: int
    _focus_index: int
    _scroll_index: int
    _num_title_lines: int
    _last_title_line_len: int

    def __init__(
        self,
        title: Any,
        items: Iterable[T],
        *,
        default_index=0,
        filter_func: Optional[Callable[[T, str], bool]] = None,
        console: Optional[Console] = None,
        theme: Optional[Theme] = None,
    ):
        """
        An interactive terminal menu.

        :param title: Text to display at the top of the menu.
        :param items: List of items to display. Items should either be strings or
            implement __rich__() to return the data to display.
        :param default_index: Index of the item to focus initially.
        :param filter_func: Function which takes an item and a filter string and
            returns whether the item should be displayed. If set, a text entry
            field will be displayed after the menu title.
        :param console: Console in which to display the menu.
        :param theme: Theme to apply. See TerminalMenu.DEFAULT_THEME for style names.
        """
        self.title = title
        self.items = list(items)
        self.console = console or rich.get_console()
        self.theme = theme or self.DEFAULT_THEME
        self.default_index = default_index

        self._filter_func = filter_func
        self._filter_text = ""
        self._filter_items = []
        self._cursor_index = 0
        self._focus_index = 0
        self._scroll_index = 0

        title_lines = self.console.render_lines(self.title, pad=False)
        self._num_title_lines = len(title_lines)
        self._last_title_line_len = 1 + sum(s.cell_length for s in title_lines[-1])

        if self._get_display_count() == self._max_items_per_page:
            self._top_row = 1
        else:
            row, _ = terminal.get_cursor_pos()
            self._top_row = min(row, self.console.height - self._get_menu_height())

        self._apply_filter()

    def show(self):
        """
        Displays the menu.

        :return: The selected item.
        :raises StopMenu: The user canceled the menu without making a selection.
        """

        self._focus_index = self.default_index

        try:
            with self._context():
                while True:
                    self._scroll_index = self._get_scroll_index()
                    self._print_menu()
                    self._move_cursor_to_filter()

                    if self.has_filter:
                        terminal.show_cursor()

                    if self._handle_input():
                        try:
                            return self._filter_items[self._focus_index]
                        except IndexError:
                            pass

                    if self.has_filter:
                        terminal.hide_cursor()

                    self._move_cursor_to_top()
        finally:
            self._erase_controls()

    @property
    def has_filter(self):
        """Get whether a filter function is set"""
        return bool(self._filter_func)

    def highlight(self, text: Text):
        normfilter = self._filter_text.casefold().strip()
        if not normfilter:
            return

        normtext = text.plain.casefold()
        prev = 0
        while True:
            start = normtext.find(normfilter, prev)
            if start < 0:
                break

            end = start + len(normfilter)
            text.stylize("highlight", start=start, end=end)
            prev = end

    @contextmanager
    def _context(self):
        old_highlighter = self.console.highlighter
        try:
            terminal.hide_cursor()
            self.console.highlighter = self

            with self.console.use_theme(self.theme):
                yield
        finally:
            terminal.show_cursor()
            self.console.highlighter = old_highlighter

    def _apply_filter(self):
        if self.has_filter:
            try:
                old_focus = self._filter_items[self._focus_index]
            except IndexError:
                old_focus = None

            self._filter_items = [
                i for i in self.items if self._filter_func(i, self._filter_text)
            ]

            try:
                self._focus_index = self._filter_items.index(old_focus)
            except ValueError:
                pass
        else:
            self._filter_items = self.items

        self._clamp_focus_index()

    def _print_menu(self):
        self.console.print(
            f"[title]{self.title}[/title] [filter]{self._filter_text}[/filter]",
            justify="left",
            highlight=False,
        )

        display_count = self._get_display_count()

        for row in range(display_count):
            if row == 0 and not self._filter_items:
                self.console.print(
                    "[dim]No matching items",
                    justify="left",
                    highlight=False,
                    no_wrap=True,
                )
                continue

            index = self._scroll_index + row
            focused = index == self._focus_index

            at_start = self._scroll_index == 0
            at_end = self._scroll_index + display_count >= len(self._filter_items)
            show_more = (not at_start and row == 0) or (
                not at_end and row == display_count - 1
            )

            try:
                item = self._filter_items[index]
                self._print_item(item, focused=focused, show_more=show_more)
            except IndexError:
                self.console.print(justify="left")

        controls = self.CONTROLS
        if self.has_filter:
            controls += self.FILTER_CONTROLS

        self.console.print(
            controls,
            style="controls",
            end="",
            highlight=False,
            no_wrap=True,
            overflow="crop",
        )

    def _print_item(self, item: T, focused: bool, show_more: bool):
        style = "ellipsis" if show_more else "focus" if focused else "unfocus"

        indent = "> " if focused else "  "
        item = "..." if show_more else item

        self.console.print(
            indent,
            item,
            sep="",
            style=style,
            highlight=True,
            justify="left",
            no_wrap=True,
            overflow="ellipsis",
        )

    def _clamp_focus_index(self):
        self._focus_index = min(max(0, self._focus_index), len(self._filter_items) - 1)

    def _clamp_cursor_index(self):
        self._cursor_index = min(max(0, self._cursor_index), len(self._filter_text))

    def _handle_input(self):
        """
        Process one key of input.

        :return: True if the user pressed enter or False otherwise.
        :raises StopMenu: The user pressed escape.
        """
        key = terminal.read_key()

        match key:
            case terminal.TAB:
                pass

            case terminal.RETURN:
                return True
            case terminal.ESCAPE:
                raise StopMenu()

            case terminal.UP:
                self._focus_index -= 1
            case terminal.DOWN:
                self._focus_index += 1

            case terminal.PAGE_UP:
                self._focus_index -= self._max_items_per_page
            case terminal.PAGE_DOWN:
                self._focus_index += self._max_items_per_page

            case terminal.HOME:
                self._focus_index = 0
            case terminal.END:
                self._focus_index = len(self._filter_items) - 1

            case terminal.LEFT:
                self._cursor_index -= 1
            case terminal.RIGHT:
                self._cursor_index += 1

            case terminal.BACKSPACE:
                self._handle_backspace()
            case terminal.DELETE:
                self._handle_delete()

            case _:
                self._handle_text(key)

        self._clamp_cursor_index()
        self._clamp_focus_index()
        return False

    def _handle_backspace(self):
        if self._cursor_index == 0:
            return

        self._filter_text = splice(self._filter_text, self._cursor_index - 1, count=1)
        self._cursor_index -= 1
        self._apply_filter()

    def _handle_delete(self):
        if self._cursor_index == len(self._filter_text):
            return

        self._filter_text = splice(self._filter_text, self._cursor_index, count=1)
        self._apply_filter()

    def _handle_text(self, key: bytes):
        text = key.decode()
        self._filter_text = splice(
            self._filter_text, self._cursor_index, insert_text=text
        )
        self._cursor_index += len(text)
        self._apply_filter()

    @property
    def _max_items_per_page(self):
        """Maximum number of items that can be displayed at once"""
        return (
            self.console.height
            - self.TOP_MARGIN
            - self.CONTROL_LINES
            - self._num_title_lines
        )

    def _get_display_count(self):
        """Number of items to display in the menu"""
        return min(len(self.items), self._max_items_per_page)

    def _get_menu_height(self):
        """Total height of the menu, including"""
        return self._get_display_count() + self.CONTROL_LINES + self._num_title_lines

    def _get_scroll_index(self):
        """Calculate the scroll index according to the focus index and items list"""
        items_count = len(self._filter_items)
        display_count = self._get_display_count()

        if items_count < display_count:
            return 0

        first_displayed = self._scroll_index
        last_displayed = first_displayed + display_count - 1

        if self._focus_index <= first_displayed + self.SCROLL_MARGIN:
            return max(0, self._focus_index - 1 - self.SCROLL_MARGIN)

        if self._focus_index >= last_displayed - self.SCROLL_MARGIN:
            end = min(items_count - 1, self._focus_index + 1 + self.SCROLL_MARGIN)
            return end - (display_count - 1)

        return self._scroll_index

    def _move_cursor_to_top(self):
        """Move the cursor to the start of the menu"""
        terminal.set_cursor_pos(row=self._top_row)

    def _move_cursor_to_filter(self):
        """Move the cursor to the filter text field"""
        row = self._top_row + self._num_title_lines - 1
        col = self._last_title_line_len + self._cursor_index

        terminal.set_cursor_pos(row, col)

    def _erase_controls(self):
        """Hide the controls text and reset the cursor to after the menu"""
        row = self.console.height - 1

        terminal.set_cursor_pos(row=row, col=0)
        self.console.print(justify="left")

        terminal.set_cursor_pos(self._top_row + len(self._filter_items) + 1)


def show_menu(
    title: str,
    items: Iterable[T],
    *,
    default_index=0,
    filter_func: Optional[Callable[[T, str], bool]] = None,
    console: Optional[Console] = None,
    theme: Optional[Theme] = None,
):
    """
    Displays an interactive menu.

    :param title: Text to display at the top of the menu.
    :param items: List of items to display. Items should either be strings or
        implement __rich__() to return the data to display.
    :param default_index: Index of the item to focus initially.
    :param filter_func: Function which takes an item and a filter string and
        returns whether the item should be displayed. If set, a text entry
        field will be displayed after the menu title.
    :param console: Console in which to display the menu.
    :param theme: Theme to apply. See TerminalMenu.DEFAULT_THEME for style names.
    :return: The selected item.
    :raises StopMenu: The user canceled the menu without making a selection.
    """
    menu = TerminalMenu(
        title=title,
        items=items,
        default_index=default_index,
        filter_func=filter_func,
        console=console,
        theme=theme,
    )
    return menu.show()


class Detail(Generic[T]):
    """A menu item with a description appended to the end."""

    MIN_PAD = 2

    data: T
    detail: str
    _pad_len: int

    def __init__(self, data: T, detail: str):
        self.data = data
        self.detail = detail
        self._pad_len = self.MIN_PAD

    def __rich__(self):
        text = Text.assemble(str(self.data), " " * self._pad_len, (self.detail, "dim"))
        # Returning the Text object directly works, but it doesn't get highlighted.
        return text.markup

    # pylint: disable=protected-access
    @classmethod
    def align(cls, items: Iterable["Detail[T]"], console: Optional[Console] = None):
        """Set the padding for each item in the list to align the detail strings."""
        items = list(items)
        console = console or rich.get_console()

        for item in items:
            item._pad_len = console.measure(str(item.data)).minimum

        width = max(item._pad_len for item in items)

        for item in items:
            item._pad_len = width - item._pad_len + cls.MIN_PAD

        return items


def detail_list(
    items: Iterable[tuple[T, str]], console: Optional[Console] = None
) -> list[Detail[T]]:
    """
    Create a list of menu items with a description appended to each item.
    """
    return Detail.align([Detail(item, desc) for item, desc in items], console=console)
