import re


class Revision:
    """
    Represents a Zephyr board revision.

    Revisions are automatically normalized, so comparing two objects for equality
    works even if the same revision is spelled differently, e.g.
    ```
    Revision("1") == Revision("1.1")  # false
    Revision("1") == Revision("1.0")  # true
    Revision("1.0.0") in {Revision("1"), Revision("2")}  # true
    ```

    `Revision()` represents the lack of a revision. Truth testing a revision with
    an empty string value returns false, so `Revision | None` is not needed to
    represent an optional revision.
    """

    def __init__(self, value: str = ""):
        self._value = _normalize(value)

    def __bool__(self):
        return bool(self._value)

    def __hash__(self):
        return hash(self._value)

    def __eq__(self, other):
        return isinstance(other, Revision) and other._value == self._value

    def __lt__(self, other):
        if not isinstance(other, Revision):
            raise TypeError()
        return _revision_lt(self, other)

    def __str__(self):
        return self._value

    def __rich__(self):
        return str(self)

    def __repr__(self):
        return f'Revision("{self._value})"' if self else "Revision()"

    def __menu_row__(self):
        # In menus, use the most specific spelling so adjacent items don't have
        # varying widths.
        return [self.specific_str]

    @property
    def at_str(self) -> str:
        """
        The revision prefixed with "@" if this object has a value, else "".
        """
        return f"@{self}" if self else ""

    @property
    def specific_str(self) -> str:
        """
        The most specific spelling of this revision, e.g. Revision("1") -> "1.0.0"
        """
        if not self:
            return ""

        if self._value.isalpha():
            return self._value

        result = self._value
        for _ in range(2 - self._value.count(".")):
            result += ".0"

        return result

    def get_spellings(self) -> list[str]:
        """
        Returns a list of all equivalent spellings of this revision. This may be
        necessary for example when you have a normalized revision and need to find
        board files that apply to it (e.g. board_1_0_0.overlay).

        Return values are ordered from most to least specific.

        Examples:
        ```
        "A"     -> ["A", "a"]
        "1"     -> ["1.0.0", "1.0", "1"]
        "1.2"   -> ["1.2.0", "1.2"]
        "1.2.3" -> ["1.2.3"]
        ```
        """
        if not self:
            return [""]

        if self._value.isalpha():
            return [self._value, self._value.lower()]

        value = self.specific_str
        result = [value]

        while value.endswith(".0"):
            value = value[:-2]
            result.append(value)

        return result


def _normalize(revision: str) -> str:
    """
    Normalizes letter revisions to uppercase and shortens numeric versions to
    the smallest form with the same meaning.

    Examples:
    ```
    "" -> ""
    "a" -> "A"
    "1.2.0" -> "1.2"
    "2.0.0" -> "2"
    ```
    """
    return re.sub(r"(?:\.0){1,2}$", "", revision.strip()).upper()


def _to_number_list(revision: str) -> list[int]:
    """
    Splits a revision string into a list of numbers. Must not be an alphabetical
    revision.
    """
    return [int(part) for part in revision.split(".")]


def _revision_lt(lhs: Revision, rhs: Revision) -> bool:
    """ """
    lhs_str = lhs.specific_str
    rhs_str = rhs.specific_str

    # Place Revision() before Revision("...")
    if not lhs_str:
        return bool(rhs_str)

    if not rhs_str:
        return False

    # Place Revision("A") before Revision("1").
    if lhs_str.isalpha():
        if rhs_str.isalpha():
            # Both revisions are alphabetical. Can compare directly.
            return lhs_str < rhs_str

        return True

    if rhs_str.isalpha():
        return False

    # Both revisions are numerical. Can compare as a list of numbers.
    return _to_number_list(lhs_str) < _to_number_list(rhs_str)
