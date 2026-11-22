"""Plain data containers, independent of the data source."""
from dataclasses import dataclass, field
from typing import Optional

Series = list[Optional[float]]  # one value per fiscal year, oldest first


@dataclass
class StockData:
    """Everything the analysis needs. All money values are in `currency`."""
    ticker: str
    name: str
    sector: str
    currency: str
    price: float
    shares: float
    beta: Optional[float] = None

    years: list[int] = field(default_factory=list)
    revenue: Series = field(default_factory=list)
    net_income: Series = field(default_factory=list)
    ebit: Series = field(default_factory=list)
    ebitda: Series = field(default_factory=list)
    interest_expense: Series = field(default_factory=list)
    free_cash_flow: Series = field(default_factory=list)
    operating_cash_flow: Series = field(default_factory=list)
    dividends_paid: Series = field(default_factory=list)  # positive numbers
    equity: Series = field(default_factory=list)
    total_debt: Series = field(default_factory=list)
    cash: Series = field(default_factory=list)
    total_assets: Series = field(default_factory=list)
    current_assets: Series = field(default_factory=list)
    current_liabilities: Series = field(default_factory=list)
    long_term_liabilities: Series = field(default_factory=list)

    net_income_ttm: Optional[float] = None

    # Analyst consensus (next fiscal year, as fractions: 0.12 = 12 %)
    earnings_growth_est: Optional[float] = None
    revenue_growth_est: Optional[float] = None
    market_growth_est: Optional[float] = None

    # Dividend per share by complete calendar year, plus trailing 12 months
    annual_dividends: dict[int, float] = field(default_factory=dict)
    dividend_ttm: float = 0.0

    @property
    def market_cap(self) -> float:
        return self.price * self.shares

    @property
    def is_financial(self) -> bool:
        return self.sector == "Financial Services"


@dataclass
class Assumptions:
    """Tunable inputs for valuation and benchmarks."""
    risk_free: float = 0.04         # 10y government bond yield
    equity_premium: float = 0.05    # equity risk premium
    terminal_growth: float = 0.025  # perpetual growth after the forecast
    forecast_years: int = 10
    max_growth: float = 0.20        # cap for first-year growth in the DCF
    market_pe: float = 20.0         # P/E of the broad market
    market_earnings_growth: float = 0.10  # used if no index estimate exists
    market_revenue_growth: float = 0.05
    dividend_low: float = 0.015     # yield of the bottom 25 % of payers
    dividend_high: float = 0.04     # yield of the top 25 % of payers


@dataclass
class Check:
    name: str
    passed: Optional[bool]  # None = not enough data to decide
    detail: str


@dataclass
class Valuation:
    method: str
    fair_value: Optional[float]
    cost_of_equity: float
    note: str


@dataclass
class Analysis:
    stock: StockData
    valuation: Valuation
    sections: dict[str, list[Check]]

    def score(self, section: str) -> int:
        return sum(1 for c in self.sections[section] if c.passed)

    def rated(self, section: str) -> bool:
        """False if not a single check of the section could be evaluated."""
        return any(c.passed is not None for c in self.sections[section])

    @property
    def total(self) -> int:
        return sum(self.score(s) for s in self.sections)

    @property
    def max_total(self) -> int:
        return 6 * sum(self.rated(s) for s in self.sections)
