"""Fair value estimates: 2-stage FCFE discounted cash flow, and an
excess-returns model for banks and insurers (where FCF is meaningless)."""
from typing import Optional

from .fmt import pct
from .model import Assumptions, StockData, Valuation


def last(xs) -> Optional[float]:
    return next((x for x in reversed(xs) if x is not None), None)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def cagr(xs) -> Optional[float]:
    """Compound annual growth between first and last known value."""
    pts = [(i, x) for i, x in enumerate(xs) if x is not None]
    if len(pts) < 2:
        return None
    (i0, a), (i1, b) = pts[0], pts[-1]
    if a <= 0 or b <= 0:
        return None
    return (b / a) ** (1 / (i1 - i0)) - 1


def cost_of_equity(beta: Optional[float], a: Assumptions) -> float:
    """CAPM. Beta is clamped so that noisy estimates don't dominate."""
    b = clamp(beta if beta is not None else 1.0, 0.8, 2.0)
    return a.risk_free + b * a.equity_premium


def dcf_two_stage(fcf: float, growth: float, discount: float,
                  terminal_growth: float, years: int = 10) -> float:
    """Present value of cash flows whose growth fades linearly from
    `growth` (year 1) to `terminal_growth` (final year), plus a
    Gordon-growth terminal value."""
    if discount <= terminal_growth:
        raise ValueError("discount rate must exceed terminal growth")
    total = 0.0
    for year in range(1, years + 1):
        fade = (year - 1) / (years - 1) if years > 1 else 1.0
        fcf *= 1 + growth + (terminal_growth - growth) * fade
        total += fcf / (1 + discount) ** year
    terminal = fcf * (1 + terminal_growth) / (discount - terminal_growth)
    return total + terminal / (1 + discount) ** years


def excess_returns(book_value: float, roe: float, discount: float,
                   terminal_growth: float) -> float:
    """Book value plus the capitalised return earned above cost of equity."""
    return book_value + (roe - discount) * book_value / (discount - terminal_growth)


def start_growth(s: StockData, a: Assumptions) -> float:
    g = s.earnings_growth_est
    if g is None:
        g = cagr(s.revenue)
    if g is None:
        g = a.terminal_growth
    return clamp(g, 0.0, a.max_growth)


def value_stock(s: StockData, a: Assumptions) -> Valuation:
    coe = cost_of_equity(s.beta, a)
    if s.is_financial:
        method = "Excess-Returns-Modell"
        equity = last(s.equity)
        roes = [n / e for n, e in zip(s.net_income, s.equity)
                if n is not None and e is not None and e > 0]
        if equity is None or equity <= 0 or not roes:
            return Valuation(method, None, coe, "Eigenkapital/ROE nicht verfügbar")
        roe = sum(roes) / len(roes)
        fair = excess_returns(equity, roe, coe, a.terminal_growth) / s.shares
        return Valuation(method, max(fair, 0.0), coe,
                         f"Ø ROE {pct(roe)}, ewiges Wachstum {pct(a.terminal_growth)}")

    method = "2-Stufen-DCF (Free Cash Flow to Equity)"
    fcf = last(s.free_cash_flow)
    if fcf is None or fcf <= 0:
        return Valuation(method, None, coe,
                         "Free Cash Flow negativ oder nicht verfügbar – DCF nicht anwendbar")
    g = start_growth(s, a)
    fair = dcf_two_stage(fcf, g, coe, a.terminal_growth, a.forecast_years) / s.shares
    return Valuation(method, fair, coe,
                     f"Startwachstum {pct(g)}, ewiges Wachstum {pct(a.terminal_growth)}")
