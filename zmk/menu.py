"""
Terminal menus
"""

from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager, suppress
from typing import Generic, Protocol, TypeVar, runtime_checkable

import rich
from rich.console import Console, RenderableType, group
from rich.control import Control
from rich.highlighter import Highlighter
from rich.live import Live
from rich.padding import Padding
from rich.style import Style, StyleType
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from . import terminal
from .styles import chain_highlighters
from .util import horizontal_group, splice


class StopMenu(KeyboardInterrupt):
    """
    Exception thrown when the user cancels the menu without making a selection
    """


@runtime_checkable
class MenuRow(Protocol):
    """
    An object that will display multiple values in a menu.

    __menu_row__() functions like __rich__(), except it returns any number of
    renderables, and each must be no more than one line tall. They will be
    aligned in columns in the menu.
    """

    def __menu_row__(self) -> Iterable[RenderableType]: ...


T = TypeVar("T", bound=RenderableType | MenuRow)

_MenuRow = tuple[list[RenderableType], StyleType | None]
"""Type alias for a list of values to render for a row and the style to apply to them"""


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

    title: str | None
    items: list[T]
    default_index: int

    _filter_func: Callable[[T, str], bool] | None
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
        title: str | None,
        items: Iterable[T],
        *,
        default_index=0,
        filter_func: Callable[[T, str], bool] | None = None,
        console: Console | None = None,
        theme: Theme | None = None,
        padding=3,
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
        :param padding: Number of spaces between columns.
        """
        self.title = title
        self.items = list(items)
        self.console = console or rich.get_console()
        self.theme = theme or self.DEFAULT_THEME
        self.default_index = default_index
        self.padding = padding

        self._filter_func = filter_func
        self._filter_text = ""
        self._filter_items = []
        self._cursor_index = 0
        self._focus_index = 0
        self._scroll_index = 0

        if self.title:
            title_lines = self.console.render_lines(self.title, pad=False)
            self._num_title_lines = len(title_lines)
            self._last_title_line_len = 1 + sum(s.cell_length for s in title_lines[-1])
        else:
            self._num_title_lines = 0
            self._last_title_line_len = 0

        if self._get_display_count() == self._max_items_per_page:
            self._top_row = 1
        else:
            _, y = terminal.get_cursor_pos()
            self._top_row = min(y, self.console.height - self._get_menu_height())

        self._apply_filter()

    def show(self) -> T:
        """
        Displays the menu.

        :return: The selected item.
        :raises StopMenu: The user canceled the menu without making a selection.
        """

        self._focus_index = self.default_index

        with self._context() as live:
            while True:
                self._scroll_index = self._get_scroll_index()
                live.update(self._render_menu(), refresh=True)

                with self._move_cursor_to_filter():
                    if self._handle_input():
                        # _focus_index may be invalid if _filter_items is empty.
                        with suppress(IndexError):
                            return self._filter_items[self._focus_index]

    @property
    def has_filter(self) -> bool:
        """Get whether a filter function is set"""
        return bool(self._filter_func)

    def highlight(self, text: Text) -> None:
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
        controls = Text(self.CONTROLS, style="dim", no_wrap=True, overflow="crop")
        if self.has_filter:
            controls.append(self.FILTER_CONTROLS)

        old_highlighter = self.console.highlighter
        try:
            self.console.show_cursor(show=False)

            # Merge the console's existing highlighter with the menu highlighter
            self.console.highlighter = chain_highlighters(old_highlighter, self)

            # Display the title and menu items in a live view, which we will
            # update as the user interacts with the menu. Below that, display
            # the control help text. This never gets updated, but it uses a
            # transient live view to it gets hidden when the menu is closed.
            # Both need redirect_stdout=False because the default behavior will
            # conflict with our cursor position modifications, resulting in the
            # rendered menu not being cleaned up properly on Esc/Ctrl+C.
            with (
                self.console.use_theme(self.theme),
                Live(
                    console=self.console,
                    redirect_stdout=False,
                    auto_refresh=False,
                ) as live,
                Live(
                    controls,
                    console=self.console,
                    redirect_stdout=False,
                    auto_refresh=False,
                    transient=True,
                ),
            ):
                yield live
        finally:
            self.console.highlighter = old_highlighter
            self.console.show_cursor(show=True)

            # Add one blank line when the menu is closed to give some space
            # between the menu and whatever follows it.
            self.console.print()

    def _apply_filter(self):
        if self._filter_func:
            try:
                old_focus = self._filter_items[self._focus_index]
            except IndexError:
                old_focus = None

            self._filter_items = [
                i for i in self.items if self._filter_func(i, self._filter_text)
            ]

            # If the previously-focused item is still visible, update the focus
            # index to that item's new index. Update the scroll index as well to
            # try to keep that item in the same place on the screen.
            if old_focus is not None:
                with suppress(ValueError):
                    scroll_offset = self._focus_index - self._scroll_index
                    self._focus_index = self._filter_items.index(old_focus)
                    self._scroll_index = self._focus_index - scroll_offset
        else:
            self._filter_items = self.items

        self._clamp_focus_index()

    @group()
    def _render_menu(self):
        if self.title:
            yield Text.assemble(
                (self.title, "title"), " ", (self._filter_text, "filter")
            )

        # Find the items that are visible and render them to a list of rows.
        # Organize the rows into a grid to align columns of data.
        grid = Table.grid(padding=(0, self.padding))
        grid.highlight = True

        if rows := list(self._render_rows()):
            max_columns = max(len(row) for row, _ in rows)

            for _ in range(max_columns):
                grid.add_column(no_wrap=True)

            for row, style in rows:
                grid.add_row(*row, style=style)

        # Wrap the grid in a Padding() so it clears the entire width of the terminal.
        # (expand=True on the grid would also work, but that affects column widths.)
        yield Padding(grid)

    def _render_rows(self) -> Generator[_MenuRow]:
        display_count = self._get_display_count()

        # If the filter doesn't match any items, display a message on the first
        # line and blank the rest of the menu.
        if not self._filter_items:
            yield (["No matching items"], Style(dim=True))
            for _ in range(display_count - 1):
                yield ([], None)

            return

        scroll_at_top = self._scroll_index == 0
        scroll_at_bottom = self._scroll_index + display_count >= len(self._filter_items)

        for row in range(display_count):
            index = self._scroll_index + row
            focused = index == self._focus_index

            is_top_ellipsis = row == 0 and not scroll_at_top
            is_bottom_ellipsis = row == display_count - 1 and not scroll_at_bottom

            if is_top_ellipsis or is_bottom_ellipsis:
                yield (["  ..."], "ellipsis")
            else:
                try:
                    yield self._render_item(self._filter_items[index], focused=focused)
                except IndexError:
                    yield ([], None)

    def _render_item(self, item: T | str, *, focused: bool) -> _MenuRow:
        style = "focus" if focused else "unfocus"

        columns: list[RenderableType]
        if isinstance(item, MenuRow):
            columns = list(item.__menu_row__()) or [""]
        else:
            columns = [item]

        # The table has larger padding between columns than we want for the
        # focused item indicator or indent on unfocused items, so modify the
        # value in the first column to contain the indicator/indent instead of
        # putting it in a separate column.
        indent = "> " if focused else "  "
        columns[0] = horizontal_group(indent, columns[0])

        return ([*columns], style)

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

        if items_count <= display_count:
            # There is enough space to show the whole menu without scrolling.
            return 0

        first_displayed = self._scroll_index
        last_displayed = first_displayed + display_count - 1

        if last_displayed >= items_count:
            # There are more items in the menu than available space, but the
            # current scroll position would leave blank spaces at the bottom.
            # Scroll up enough to fill every row of the menu with an item.
            first_displayed = items_count - display_count
            last_displayed = first_displayed + display_count - 1

        if self._focus_index <= first_displayed + self.SCROLL_MARGIN:
            # The focused item is off the top of the screen. Scroll up enough to
            # get it in view. Also fit as many menu items in as possible so we
            # don't get just a couple visible when there's room for more.
            start = min(
                items_count - display_count,
                self._focus_index - 1 - self.SCROLL_MARGIN,
            )
            return max(0, start)

        if self._focus_index >= last_displayed - self.SCROLL_MARGIN:
            # Focused item is off the bottom of the screen. Scroll down enough
            # to get it in view.
            end = min(items_count - 1, self._focus_index + 1 + self.SCROLL_MARGIN)
            return end - (display_count - 1)

        return first_displayed

    @contextmanager
    def _move_cursor_to_filter(self):
        """
        Context manager which move the cursor to the filter text field and shows
        it, runs the context, then sets the cursor back where it was and hides it.
        """

        if not self.has_filter:
            yield
            return

        orig_x, orig_y = terminal.get_cursor_pos()

        x = self._last_title_line_len + self._cursor_index
        y = self._top_row + self._num_title_lines - 1

        try:
            self.console.control(Control.move_to(x, y))
            self.console.show_cursor(show=True)
            yield
        finally:
            self.console.show_cursor(show=False)
            self.console.control(Control.move_to(orig_x, orig_y))


def show_menu(
    title: str | None,
    items: Iterable[T],
    *,
    default_index=0,
    filter_func: Callable[[T, str], bool] | None = None,
    console: Console | None = None,
    theme: Theme | None = None,
) -> T:
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
    """A menu item with a description."""

    data: T
    detail: str

    def __init__(self, data: T, detail: str):
        self.data = data
        self.detail = detail

    def __menu_row__(self) -> Iterable[RenderableType]:
        if isinstance(self.data, MenuRow):
            yield from self.data.__menu_row__()
        else:
            yield self.data

        yield f"[dim]{self.detail}"


def detail_list(items: Iterable[tuple[T, str]]) -> list[Detail[T]]:
    """
    Create a list of menu items with a description next to each item.
    """
    return [Detail(item, desc) for item, desc in items]
