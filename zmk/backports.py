"""
Backports from Python > 3.10.
"""

try:
    # pylint: disable=unused-import
    from enum import StrEnum
except ImportError:
    # pylint: disable=unused-import
    from backports.strenum import StrEnum
