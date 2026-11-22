"""Text and JSON output."""
import json

from .fmt import num, pct
from .model import Analysis

MARK = {True: "✓", False: "✗", None: "–"}


def render_text(a: Analysis) -> str:
    s, v = a.stock, a.valuation
    out = [f"{s.name} ({s.ticker}) · {s.sector}",
           f"Kurs: {num(s.price, 2)} {s.currency}"]
    if v.fair_value is None:
        out.append(f"Fair Value: nicht berechenbar ({v.note})")
    else:
        diff = s.price / v.fair_value - 1 if v.fair_value > 0 else None
        verdict = "n/v" if diff is None else \
            f"Kurs {pct(abs(diff))} {'über' if diff > 0 else 'unter'} Fair Value"
        out.append(f"Fair Value: {num(v.fair_value, 2)} {s.currency} → {verdict}")
        out.append(f"  Methode: {v.method}; Eigenkapitalkosten {pct(v.cost_of_equity)}, "
                   f"{v.note}")
    out.append("")
    for name in a.sections:
        pts = a.score(name)
        out.append(f"  {name:<14}{'●' * pts}{'○' * (6 - pts)}  {pts}/6" if a.rated(name)
                   else f"  {name:<14}nicht bewertbar")
    out.append(f"  {'Gesamt':<14}{a.total}/{a.max_total}")
    for name, checks in a.sections.items():
        out += ["", f"{name} ({a.score(name)}/6)" if a.rated(name) else f"{name} (nicht bewertbar)"]
        out += [f"  {MARK[c.passed]} {c.name}  [{c.detail}]" for c in checks]
    if any(c.passed is None for cs in a.sections.values() for c in cs):
        out += ["", "– = mangels Daten nicht bewertbar (zählt nicht als Punkt)"]
    return "\n".join(out)


def render_json(a: Analysis) -> str:
    s, v = a.stock, a.valuation
    return json.dumps({
        "ticker": s.ticker, "name": s.name, "sector": s.sector,
        "currency": s.currency, "price": s.price,
        "fair_value": v.fair_value, "valuation_method": v.method,
        "cost_of_equity": v.cost_of_equity,
        "scores": {name: a.score(name) if a.rated(name) else None for name in a.sections},
        "total": a.total, "max_total": a.max_total,
        "checks": {name: [vars(c) for c in checks] for name, checks in a.sections.items()},
    }, ensure_ascii=False, indent=2)
