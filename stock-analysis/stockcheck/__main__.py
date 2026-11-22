"""Usage: python -m stockcheck AAPL [SAP.DE ...] [--json]"""
import argparse
import sys

from .checks import analyse
from .data import fetch
from .model import Assumptions
from .report import render_json, render_text


def main(argv=None) -> int:
    d = Assumptions()
    p = argparse.ArgumentParser(prog="stockcheck", description=(
        "Fundamentalanalyse einer Aktie in fünf Dimensionen (je 6 Checks) "
        "inkl. Fair-Value-Schätzung. Ticker in Yahoo-Finance-Schreibweise."))
    p.add_argument("tickers", nargs="+", metavar="TICKER", help="z. B. AAPL, SAP.DE, NESN.SW")
    p.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    p.add_argument("--risk-free", type=float, default=d.risk_free,
                   help=f"risikoloser Zins (Standard {d.risk_free})")
    p.add_argument("--equity-premium", type=float, default=d.equity_premium,
                   help=f"Aktienrisikoprämie (Standard {d.equity_premium})")
    p.add_argument("--terminal-growth", type=float, default=d.terminal_growth,
                   help=f"ewiges Wachstum im DCF (Standard {d.terminal_growth})")
    p.add_argument("--market-pe", type=float, default=d.market_pe,
                   help=f"Vergleichs-KGV des Marktes (Standard {d.market_pe})")
    args = p.parse_args(argv)
    assumptions = Assumptions(risk_free=args.risk_free, equity_premium=args.equity_premium,
                              terminal_growth=args.terminal_growth, market_pe=args.market_pe)
    if assumptions.risk_free + 0.8 * assumptions.equity_premium <= assumptions.terminal_growth:
        p.error("Eigenkapitalkosten müssen über dem ewigen Wachstum liegen")

    failed = False
    for i, ticker in enumerate(args.tickers):
        try:
            result = analyse(fetch(ticker), assumptions)
        except Exception as e:  # keep going with the remaining tickers
            print(f"{ticker}: {e}", file=sys.stderr)
            failed = True
            continue
        if i and not args.json:
            print("\n" + "═" * 72 + "\n")
        print(render_json(result) if args.json else render_text(result))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
