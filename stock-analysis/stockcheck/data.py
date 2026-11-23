"""Loads a StockData from Yahoo Finance (via yfinance)."""
import datetime as dt
import math
import time
from typing import Optional

from .model import StockData

# Exchanges that quote in 1/100 of the main currency unit
MINOR_UNITS = {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ILA": "ILS"}


def _num(x) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def _series(df, dates, *names, scale=1.0, sign=1.0):
    """Row `names[0]` (or first fallback) aligned to `dates`, oldest first."""
    for name in names:
        if df is not None and name in df.index:
            row = df.loc[name]
            out = []
            for d in dates:
                v = _num(row.get(d))
                out.append(None if v is None else v * scale * sign)
            return out
    return [None] * len(dates)


def _ttm(df, *names, scale=1.0) -> Optional[float]:
    """Sum of the four most recent reported quarters, else None.
    (Yahoo often lists the newest quarter before its figures are filled in.)"""
    for name in names:
        if df is not None and name in df.index:
            quarters = [v for d in sorted(df.columns)
                        if (v := _num(df.loc[name].get(d))) is not None]
            if len(quarters) >= 4:
                return sum(quarters[-4:]) * scale
    return None


def _estimate(table, column, period="+1y") -> Optional[float]:
    try:
        return _num(table.loc[period, column])
    except Exception:
        return None


def fetch(ticker: str) -> StockData:
    import yfinance as yf

    # When throttled, Yahoo answers with a stripped-down record (price only).
    # Analysing that would silently change the result, so retry, then give up.
    for pause in (0, 5, 20):
        time.sleep(pause)
        t = yf.Ticker(ticker)
        info = t.info or {}
        if info.get("financialCurrency") and info.get("marketCap"):
            break
    else:
        if _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice")):
            raise ValueError("Yahoo liefert gerade nur unvollständige Daten "
                             "(Rate-Limit oder kein Einzelunternehmen) – später erneut versuchen")
    raw_price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    if raw_price is None:
        raise ValueError(f"Keine Kursdaten für '{ticker}' gefunden")

    quote_cur = info.get("currency") or "?"
    unit = 1.0
    if quote_cur in MINOR_UNITS:
        quote_cur, unit = MINOR_UNITS[quote_cur], 0.01
    price = raw_price * unit

    # Market cap / price covers all share classes and ADR ratios.
    mcap = _num(info.get("marketCap"))
    shares = mcap / price if mcap else _num(info.get("sharesOutstanding"))
    if not shares:
        raise ValueError(f"Aktienanzahl für '{ticker}' nicht verfügbar")

    # Statements may be reported in another currency than the quote.
    fin_cur = info.get("financialCurrency") or quote_cur
    fx = 1.0
    if fin_cur != quote_cur:
        fx = _num(yf.Ticker(f"{fin_cur}{quote_cur}=X").fast_info["lastPrice"])
        if not fx:
            raise ValueError(f"Wechselkurs {fin_cur}/{quote_cur} nicht verfügbar")

    def table(name):
        try:
            return getattr(t, name)
        except Exception:
            return None

    inc, bal, cf = t.income_stmt, t.balance_sheet, t.cashflow
    dates = sorted(inc.columns) if inc is not None and len(inc.columns) else []
    row = lambda df, *names, sign=1.0: _series(df, dates, *names, scale=fx, sign=sign)

    # Dividends per share: complete calendar years and trailing 12 months
    annual, ttm = {}, 0.0
    divs = t.dividends
    if divs is not None and len(divs):
        today = dt.date.today()
        for stamp, amount in divs.items():
            day = stamp.date()
            amount = float(amount) * unit
            if day.year < today.year:
                annual[day.year] = annual.get(day.year, 0.0) + amount
            if (today - day).days <= 365:
                ttm += amount

    growth = table("growth_estimates")
    ni_ttm = _num(info.get("netIncomeToCommon"))

    return StockData(
        ticker=ticker.upper(),
        name=info.get("longName") or info.get("shortName") or ticker.upper(),
        sector=info.get("sector") or "Unbekannt",
        currency=quote_cur,
        price=price,
        shares=shares,
        beta=_num(info.get("beta")),
        years=[d.year for d in dates],
        revenue=row(inc, "Total Revenue"),
        net_income=row(inc, "Net Income Common Stockholders", "Net Income"),
        ebit=row(inc, "EBIT", "Operating Income"),
        ebitda=row(inc, "EBITDA", "Normalized EBITDA"),
        interest_expense=row(inc, "Interest Expense"),
        free_cash_flow=row(cf, "Free Cash Flow"),
        operating_cash_flow=row(cf, "Operating Cash Flow"),
        dividends_paid=row(cf, "Cash Dividends Paid", "Common Stock Dividend Paid", sign=-1.0),
        equity=row(bal, "Stockholders Equity", "Common Stock Equity"),
        total_debt=row(bal, "Total Debt"),
        cash=row(bal, "Cash Cash Equivalents And Short Term Investments",
                 "Cash And Cash Equivalents"),
        total_assets=row(bal, "Total Assets"),
        current_assets=row(bal, "Current Assets"),
        current_liabilities=row(bal, "Current Liabilities"),
        long_term_liabilities=row(bal, "Total Non Current Liabilities Net Minority Interest"),
        net_income_ttm=None if ni_ttm is None else ni_ttm * fx,
        free_cash_flow_ttm=_ttm(table("quarterly_cashflow"), "Free Cash Flow", scale=fx),
        ebitda_ttm=_ttm(table("quarterly_income_stmt"), "EBITDA", "Normalized EBITDA", scale=fx),
        earnings_growth_est=_estimate(table("earnings_estimate"), "growth"),
        revenue_growth_est=_estimate(table("revenue_estimate"), "growth"),
        market_growth_est=_estimate(growth, "indexTrend"),
        annual_dividends=annual,
        dividend_ttm=ttm,
    )
