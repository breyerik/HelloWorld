import json

import pytest

from stockcheck.checks import analyse
from stockcheck.model import Assumptions, StockData
from stockcheck.report import render_json, render_text
from stockcheck.valuation import cagr, cost_of_equity, dcf_two_stage, excess_returns


def make(**overrides) -> StockData:
    """A cheap, growing, debt-light dividend payer."""
    base = dict(
        ticker="TEST", name="Test AG", sector="Industrials", currency="EUR",
        price=50.0, shares=100.0, beta=1.0,
        years=[2022, 2023, 2024, 2025],
        revenue=[2000.0, 2200.0, 2500.0, 3000.0],
        net_income=[200.0, 240.0, 300.0, 420.0],
        ebit=[280.0, 330.0, 410.0, 560.0],
        ebitda=[340.0, 400.0, 490.0, 650.0],
        interest_expense=[10.0, 10.0, 10.0, 10.0],
        free_cash_flow=[180.0, 220.0, 280.0, 400.0],
        operating_cash_flow=[250.0, 300.0, 370.0, 500.0],
        dividends_paid=[60.0, 70.0, 85.0, 100.0],
        equity=[1000.0, 1100.0, 1250.0, 1500.0],
        total_debt=[400.0, 380.0, 350.0, 300.0],
        cash=[150.0, 170.0, 200.0, 250.0],
        total_assets=[2000.0, 2200.0, 2500.0, 2900.0],
        current_assets=[900.0, 1000.0, 1100.0, 1300.0],
        current_liabilities=[400.0, 420.0, 450.0, 500.0],
        long_term_liabilities=[600.0, 680.0, 800.0, 900.0],
        net_income_ttm=420.0,
        earnings_growth_est=0.25, revenue_growth_est=0.22, market_growth_est=0.10,
        annual_dividends={2015 + i: 0.5 + 0.05 * i for i in range(11)},
        dividend_ttm=1.0,
    )
    base.update(overrides)
    return StockData(**base)


def test_dcf_without_growth_equals_perpetuity():
    # constant cash flow forever is worth fcf / r
    assert dcf_two_stage(100, 0.0, 0.10, 0.0, 10) == pytest.approx(1000)


def test_dcf_rises_with_growth_and_rejects_bad_rates():
    assert dcf_two_stage(100, 0.15, 0.09, 0.02) > dcf_two_stage(100, 0.05, 0.09, 0.02)
    with pytest.raises(ValueError):
        dcf_two_stage(100, 0.05, 0.02, 0.03)


def test_cost_of_equity_clamps_beta():
    a = Assumptions(risk_free=0.04, equity_premium=0.05)
    assert cost_of_equity(0.1, a) == pytest.approx(0.08)
    assert cost_of_equity(5.0, a) == pytest.approx(0.14)
    assert cost_of_equity(None, a) == pytest.approx(0.09)


def test_excess_returns_equals_book_when_roe_matches_cost():
    assert excess_returns(100, 0.09, 0.09, 0.02) == pytest.approx(100)


def test_cagr():
    assert cagr([100.0, None, 121.0]) == pytest.approx(0.10)
    assert cagr([-5.0, 10.0]) is None
    assert cagr([5.0]) is None


def test_strong_company_scores():
    a = analyse(make())
    assert a.valuation.fair_value > 50 * 1.25
    assert a.score("Bewertung") == 6
    assert a.score("Zukunft") == 6
    assert a.score("Vergangenheit") == 6
    assert a.score("Gesundheit") == 6
    # yield 2 %: above the low threshold, below the high one
    assert a.score("Dividende") == 5
    assert (a.total, a.max_total) == (29, 30)


def test_no_dividend_scores_zero():
    a = analyse(make(dividend_ttm=0.0, annual_dividends={}))
    assert a.score("Dividende") == 0
    assert a.rated("Dividende")


def test_dividend_cut_and_short_history():
    cut = {2015 + i: 1.0 for i in range(11)} | {2020: 0.5}
    checks = {c.name: c.passed for c in analyse(make(annual_dividends=cut)).sections["Dividende"]}
    assert checks["Stabil: keine Kürzung über 10 % in 10 Jahren"] is False
    short = analyse(make(annual_dividends={2024: 1.0, 2025: 1.0})).sections["Dividende"]
    assert short[2].passed is None and short[3].passed is None


def test_loss_maker_with_negative_fcf():
    a = analyse(make(net_income=[-50.0, -80.0, -120.0, -150.0], net_income_ttm=-150.0,
                     free_cash_flow=[-10.0, -20.0, -30.0, -40.0],
                     dividend_ttm=0.0, annual_dividends={}))
    assert a.valuation.fair_value is None
    value = a.sections["Bewertung"]
    assert value[0].passed is None      # no fair value -> not decidable
    assert value[2].passed is False     # no earnings -> P/E check fails
    past = a.sections["Vergangenheit"]
    assert past[0].passed is False and past[1].passed is False
    assert "nicht berechenbar" in render_text(a)


def test_missing_data_is_not_a_pass():
    a = analyse(make(earnings_growth_est=None, revenue_growth_est=None))
    assert all(c.passed is None for c in a.sections["Zukunft"])
    assert not a.rated("Zukunft")
    assert a.max_total == 24


def test_financials_use_excess_returns_and_skip_health():
    a = analyse(make(sector="Financial Services"))
    assert a.valuation.method == "Excess-Returns-Modell"
    assert a.valuation.fair_value > 0
    assert not a.rated("Gesundheit")
    assert "nicht bewertbar" in render_text(a)


def test_negative_equity_fails_debt_check():
    a = analyse(make(equity=[100.0, 50.0, -20.0, -80.0]))
    assert a.sections["Gesundheit"][2].passed is False


def test_json_output_roundtrips():
    data = json.loads(render_json(analyse(make())))
    assert data["total"] == 29 and data["scores"]["Bewertung"] == 6
    assert len(data["checks"]["Gesundheit"]) == 6
