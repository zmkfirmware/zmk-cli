"""
Backports from Python > 3.10.
"""

try:
    from enum import StrEnum
except ImportError:
    from backports.strenum import StrEnum
