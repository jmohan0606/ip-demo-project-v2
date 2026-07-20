"""Shared number formatting (ABSOLUTE RULE 8): negatives in parentheses,
never a minus sign — everywhere a figure is rendered into text."""
from __future__ import annotations


def fmt_money(value: float, decimals: int = 0) -> str:
    """($90,685) / $43,430."""
    text = f"${abs(value):,.{decimals}f}"
    return f"({text})" if value < 0 else text


def fmt_money_k(value: float) -> str:
    """($44.1k) / $12.3k — thousands with one decimal."""
    text = f"${abs(value) / 1000:,.1f}k"
    return f"({text})" if value < 0 else text


def fmt_pct(value: float, decimals: int = 1) -> str:
    """(17.7%) / 9.3%."""
    text = f"{abs(value):,.{decimals}f}%"
    return f"({text})" if value < 0 else text
