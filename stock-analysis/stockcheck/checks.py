"""The five dimensions, six pass/fail checks each (max. 30 points)."""
from typing import Optional

from .fmt import num, pct, times
from .model import Analysis, Assumptions, Check, StockData
from .valuation import cagr, last, value_stock

NOT_FOR_FINANCIALS = "bei Banken/Versicherern nicht aussagekräftig"


def ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def gt(a, b) -> Optional[bool]:
    return None if a is None or b is None else a > b


def lt(a, b) -> Optional[bool]:
    return None if a is None or b is None else a < b


def prev(xs) -> Optional[float]:
    """Second-to-last known value."""
    known = [x for x in xs if x is not None]
    return known[-2] if len(known) >= 2 else None


def bn(x: Optional[float]) -> str:
    return num(None if x is None else x / 1e9, 2)


def first(xs) -> Optional[float]:
    return next((x for x in xs if x is not None), None)


# --------------------------------------------------------------- Bewertung
def value_checks(s: StockData, a: Assumptions, fair: Optional[float]) -> list[Check]:
    earnings = s.net_income_ttm if s.net_income_ttm is not None else last(s.net_income)
    pe = ratio(s.market_cap, earnings) if earnings and earnings > 0 else None
    growth = s.earnings_growth_est
    peg = ratio(pe, growth * 100) if pe and growth and growth > 0 else None
    debt, cash = last(s.total_debt) or 0.0, last(s.cash) or 0.0
    ebitda = s.latest_ebitda
    ev_ebitda = ratio(s.market_cap + debt - cash, ebitda) if ebitda and ebitda > 0 else None
    fcf_yield = ratio(s.latest_fcf, s.market_cap)
    discount = None if fair is None else 1 - s.price / fair if fair > 0 else -1.0

    fv = f"Fair Value {num(fair, 2)} {s.currency}, Kurs {num(s.price, 2)}"
    unprofitable = earnings is not None and earnings <= 0
    return [
        Check("Kurs unter Fair Value", gt(discount, 0), fv),
        Check("Kurs mehr als 20 % unter Fair Value", gt(discount, 0.20),
              f"Abschlag {pct(discount)}"),
        Check(f"KGV unter Marktniveau ({num(a.market_pe, 0)})",
              False if unprofitable else lt(pe, a.market_pe),
              "kein Gewinn" if unprofitable else f"KGV {num(pe)}"),
        Check("PEG-Ratio unter 1 (KGV im Verhältnis zum Wachstum)",
              False if pe and growth is not None and growth <= 0 else lt(peg, 1),
              f"PEG {num(peg, 2)} bei erwartetem Gewinnwachstum {pct(growth)}"),
        Check("EV/EBITDA unter 12", lt(ev_ebitda, 12),
              NOT_FOR_FINANCIALS if s.is_financial else f"EV/EBITDA {num(ev_ebitda)}"),
        Check("Free-Cashflow-Rendite über 5 %", None if s.is_financial else gt(fcf_yield, 0.05),
              NOT_FOR_FINANCIALS if s.is_financial else f"FCF-Rendite {pct(fcf_yield)}"),
    ]


# ----------------------------------------------------------------- Zukunft
def future_checks(s: StockData, a: Assumptions) -> list[Check]:
    eg, rg = s.earnings_growth_est, s.revenue_growth_est
    market = s.market_growth_est if s.market_growth_est is not None else a.market_earnings_growth
    ni, eq = last(s.net_income), last(s.equity)
    fwd_roe = ratio(ni * (1 + eg), eq) if None not in (ni, eg, eq) and eq > 0 else None
    return [
        Check("Gewinnwachstum über risikolosem Zins", gt(eg, a.risk_free),
              f"erwartet {pct(eg)} p. a., Zins {pct(a.risk_free)}"),
        Check("Gewinnwachstum über Gesamtmarkt", gt(eg, market),
              f"erwartet {pct(eg)}, Markt {pct(market)}"),
        Check("Hohes Gewinnwachstum (über 20 %)", gt(eg, 0.20), f"erwartet {pct(eg)}"),
        Check("Umsatzwachstum über Gesamtmarkt", gt(rg, a.market_revenue_growth),
              f"erwartet {pct(rg)}, Markt {pct(a.market_revenue_growth)}"),
        Check("Hohes Umsatzwachstum (über 20 %)", gt(rg, 0.20), f"erwartet {pct(rg)}"),
        Check("Erwartete Eigenkapitalrendite über 20 %", gt(fwd_roe, 0.20),
              f"ROE nächstes Jahr ca. {pct(fwd_roe)}"),
    ]


# ----------------------------------------------------------- Vergangenheit
def past_checks(s: StockData) -> list[Check]:
    ni, ni_prev, ni_first = last(s.net_income), prev(s.net_income), first(s.net_income)
    n = sum(x is not None for x in s.net_income)
    span = f"{n - 1} Jahre" if n > 1 else "n/v"
    growth = cagr(s.net_income)
    last_year = ratio(ni - ni_prev, abs(ni_prev)) if None not in (ni, ni_prev) else None
    grown = None if n < 2 else ni > ni_first
    eq, assets, cur_liab = last(s.equity), last(s.total_assets), last(s.current_liabilities)
    roe = ratio(ni, eq) if eq and eq > 0 else None
    capital = assets - cur_liab if None not in (assets, cur_liab) else None
    roce = ratio(last(s.ebit), capital) if capital and capital > 0 else None
    margins = [m for m in map(ratio, s.net_income, s.revenue) if m is not None]
    m_now, m_prev = (margins[-1], margins[-2]) if len(margins) >= 2 else (None, None)
    if roce is not None:
        quality = Check("Rendite auf eingesetztes Kapital über 15 %", gt(roce, 0.15),
                        f"ROCE {pct(roce)}")
    else:  # e.g. banks, which report no current liabilities
        quality = Check("Nettomarge gegenüber Vorjahr verbessert", gt(m_now, m_prev),
                        f"{pct(m_now)} nach {pct(m_prev)}")
    return [
        Check("Aktuell profitabel", gt(ni, 0), f"Jahresergebnis {bn(ni)} Mrd. {s.currency}"),
        Check(f"Ergebnis gestiegen ({span})", grown,
              f"{bn(ni_first)} → {bn(ni)} Mrd. {s.currency}"),
        Check("Gewinnwachstum über 10 % p. a.",
              False if grown is False else gt(growth, 0.10), f"{pct(growth)} p. a."),
        Check("Wachstum zuletzt beschleunigt", gt(last_year, growth),
              f"letztes Jahr {pct(last_year)}, Durchschnitt {pct(growth)}"),
        Check("Eigenkapitalrendite über 20 %", gt(roe, 0.20), f"ROE {pct(roe)}"),
        quality,
    ]


# -------------------------------------------------------------- Gesundheit
def health_checks(s: StockData) -> list[Check]:
    if s.is_financial:
        # Deposits and insurance reserves are the business, not leverage;
        # a real assessment needs regulatory ratios that Yahoo doesn't offer.
        return [Check(n, None, NOT_FOR_FINANCIALS) for n in (
            "Kurzfristiges Vermögen deckt kurzfristige Verbindlichkeiten",
            "Kurzfristiges Vermögen deckt langfristige Verbindlichkeiten",
            "Nettoverschuldung unter 40 % des Eigenkapitals",
            "Verschuldungsgrad im Zeitverlauf gesunken",
            "Schulden durch operativen Cashflow gedeckt (über 20 %)",
            "Zinsen gut gedeckt")]
    ca, cl, ltl = last(s.current_assets), last(s.current_liabilities), last(s.long_term_liabilities)
    debt, cash, eq = last(s.total_debt), last(s.cash), last(s.equity)
    net_debt = debt - (cash or 0.0) if debt is not None else None
    positive_eq = eq is not None and eq > 0
    nde = ratio(net_debt, eq) if positive_eq else None
    de_series = [ratio(d, e) if e and e > 0 else None for d, e in zip(s.total_debt, s.equity)]
    de_now, de_then = last(de_series), first(de_series)
    ocf_cover = ratio(last(s.operating_cash_flow), debt) if debt else None
    ebit, interest = last(s.ebit), last(s.interest_expense)
    cover = ratio(ebit, interest) if interest and interest > 0 else None
    debt_free = debt is not None and debt == 0
    more_cash = None not in (cash, debt) and cash >= debt

    if debt_free or more_cash:
        interest_check = Check("Zinsen gut gedeckt", True, "mehr Cash als Schulden")
    else:
        interest_check = Check("Zinsen gut gedeckt (EBIT über 3x Zinsaufwand)",
                               gt(cover, 3), f"Zinsdeckung {times(cover)}")
    return [
        Check("Kurzfristiges Vermögen deckt kurzfristige Verbindlichkeiten", gt(ca, cl),
              times(ratio(ca, cl), 2)),
        Check("Kurzfristiges Vermögen deckt langfristige Verbindlichkeiten", gt(ca, ltl),
              times(ratio(ca, ltl), 2)),
        Check("Nettoverschuldung unter 40 % des Eigenkapitals",
              False if eq is not None and not positive_eq else lt(nde, 0.40),
              "negatives Eigenkapital" if eq is not None and not positive_eq
              else f"Nettoschulden/Eigenkapital {pct(nde)}"),
        Check("Verschuldungsgrad im Zeitverlauf gesunken",
              True if debt_free else None if len([x for x in de_series if x is not None]) < 2
              else de_now < de_then,
              f"Schulden/Eigenkapital {pct(de_now)} nach {pct(de_then)}"),
        Check("Schulden durch operativen Cashflow gedeckt (über 20 %)",
              True if debt_free else gt(ocf_cover, 0.20),
              "schuldenfrei" if debt_free else f"Cashflow/Schulden {pct(ocf_cover)}"),
        interest_check,
    ]


# --------------------------------------------------------------- Dividende
def dividend_checks(s: StockData, a: Assumptions) -> list[Check]:
    names = [
        f"Rendite über dem unteren Viertel der Zahler ({pct(a.dividend_low)})",
        f"Rendite im oberen Viertel der Zahler (über {pct(a.dividend_high)})",
        "Stabil: keine Kürzung über 10 % in 10 Jahren",
        "Dividende in 10 Jahren gestiegen",
        "Durch Gewinn gedeckt (Ausschüttung unter 90 %)",
        "Durch Free Cash Flow gedeckt (unter 90 %)",
    ]
    if s.dividend_ttm <= 0:
        return [Check(n, False, "keine Dividende") for n in names]

    dy = s.dividend_ttm / s.price
    years = sorted(s.annual_dividends)[-11:]
    # only a gap-free run of years counts as history
    history = [s.annual_dividends[y] for y in years] if years and \
        years == list(range(years[0], years[-1] + 1)) else []
    enough = len(history) >= 6
    span = f"{len(history) - 1} Jahre Historie" if history else "lückenhafte Historie"
    stable = all(b >= 0.9 * x for x, b in zip(history, history[1:])) if enough else None
    grown = history[-1] > history[0] if enough else None

    total = s.dividend_ttm * s.shares
    earnings = s.net_income_ttm if s.net_income_ttm is not None else last(s.net_income)
    payout = ratio(total, earnings)
    # the cash-flow statement lags after a dividend change, so take the higher figure
    fcf_payout = ratio(max(last(s.dividends_paid) or 0.0, total), s.latest_fcf)
    return [
        Check(names[0], dy > a.dividend_low, f"Rendite {pct(dy)}"),
        Check(names[1], dy > a.dividend_high, f"Rendite {pct(dy)}"),
        Check(names[2], stable, span),
        Check(names[3], grown,
              f"{num(history[0], 2)} → {num(history[-1], 2)} {s.currency} je Aktie" if history else span),
        Check(names[4], None if payout is None else 0 < payout < 0.90,
              f"Ausschüttungsquote {pct(payout)}"),
        Check(names[5], None if s.is_financial or fcf_payout is None else 0 < fcf_payout < 0.90,
              NOT_FOR_FINANCIALS if s.is_financial else f"{pct(fcf_payout)} des Free Cash Flow"),
    ]


def analyse(s: StockData, a: Optional[Assumptions] = None) -> Analysis:
    a = a or Assumptions()
    valuation = value_stock(s, a)
    return Analysis(s, valuation, {
        "Bewertung": value_checks(s, a, valuation.fair_value),
        "Zukunft": future_checks(s, a),
        "Vergangenheit": past_checks(s),
        "Gesundheit": health_checks(s),
        "Dividende": dividend_checks(s, a),
    })
