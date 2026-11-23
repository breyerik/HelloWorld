"""German number formatting."""
from typing import Optional


def pct(x: Optional[float]) -> str:
    return "n/v" if x is None else f"{x * 100:.1f} %".replace(".", ",")


def num(x: Optional[float], digits: int = 1) -> str:
    return "n/v" if x is None else f"{x:.{digits}f}".replace(".", ",")


def times(x: Optional[float], digits: int = 1) -> str:
    return "n/v" if x is None else num(x, digits) + "x"
