# stockcheck – Aktienanalyse in fünf Dimensionen

Bewertet eine Aktie nach dem Prinzip der „Snowflake“ von Simply Wall St:
fünf Dimensionen mit je sechs Ja/Nein-Checks (max. 30 Punkte) plus eine
Fair-Value-Schätzung. Die Daten kommen von Yahoo Finance (`yfinance`).

Die Checks sind eine eigene, vereinfachte Umsetzung – die Ergebnisse
stimmen nicht mit denen von Simply Wall St überein. Keine Anlageberatung.

## Benutzung

```bash
pip install -r requirements.txt
python -m stockcheck AAPL            # Ticker in Yahoo-Schreibweise
python -m stockcheck SAP.DE NESN.SW  # mehrere Aktien
python -m stockcheck AAPL --json     # maschinenlesbar
python -m stockcheck AAPL --risk-free 0.03 --terminal-growth 0.02 --market-pe 18
python -m pytest                     # Tests (ohne Netzwerk)
```

## Die Dimensionen

| Dimension | Was geprüft wird |
|---|---|
| **Bewertung** | Kurs unter Fair Value (und >20 % darunter), KGV unter Markt, PEG < 1, EV/EBITDA < 12, FCF-Rendite > 5 % |
| **Zukunft** | Analystenschätzung fürs nächste Geschäftsjahr: Gewinnwachstum über Zins / über Markt / über 20 %, Umsatzwachstum über Markt / über 20 %, erwartete Eigenkapitalrendite > 20 % |
| **Vergangenheit** | profitabel, Ergebnis gestiegen, Wachstum > 10 % p. a., zuletzt beschleunigt, ROE > 20 %, ROCE > 15 % |
| **Gesundheit** | kurzfristiges Vermögen deckt kurz- und langfristige Verbindlichkeiten, Nettoschulden < 40 % des Eigenkapitals, Verschuldung gesunken, Schulden durch Cashflow gedeckt, Zinsdeckung > 3x |
| **Dividende** | Rendite über 1,5 % / über 4 %, keine Kürzung > 10 % in 10 Jahren, in 10 Jahren gestiegen, durch Gewinn und durch Free Cash Flow gedeckt |

`✓` bestanden, `✗` nicht bestanden, `–` mangels Daten nicht bewertbar
(zählt nicht als Punkt).

## Fair Value

- **Standard:** 2-Stufen-DCF auf den Free Cash Flow to Equity. Der FCF der
  letzten vier Quartale (ersatzweise des letzten Geschäftsjahres) wächst 10 Jahre lang; die Rate fällt linear von der
  Analystenschätzung (gedeckelt auf 0–20 %) auf das ewige Wachstum (2,5 %).
  Diskontiert wird mit den Eigenkapitalkosten nach CAPM
  (4 % Zins + Beta × 5 % Risikoprämie, Beta begrenzt auf 0,8–2,0).
- **Banken/Versicherer:** Excess-Returns-Modell (Buchwert plus kapitalisierte
  Überrendite des ROE über die Eigenkapitalkosten).

Alle Annahmen stehen in `stockcheck/model.py` (`Assumptions`).

## Grenzen

- Der Fair Value reagiert stark auf Wachstums- und Zinsannahmen und auf
  den FCF eines einzelnen Jahres. Bei negativem FCF gibt es keinen Wert.
- Yahoo liefert nur 4 Geschäftsjahre; Wachstumsraten sind entsprechend kurz.
- Vergleichswerte (Markt-KGV, Dividendenschwellen) sind feste Parameter,
  kein echter Branchen- oder Peer-Vergleich.
- Sonderdividenden können den Stabilitäts-Check auslösen.
- Bei Banken/Versicherern wird die Dimension „Gesundheit“ nicht bewertet.
