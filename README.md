# Meck-Bet — Automated Sports Betting Value Analyzer

Lokale Web-App zur systematischen Erkennung von **Quoten-Fehlern** (Value Bets & Arbitrage) bei Sportwetten-Buchmachern.

## Architektur

```
┌─────────────────────────────────────────────────────┐
│                   The Odds API                      │
│         (40+ Buchmacher, Live-Quoten)               │
└─────────────────┬───────────────────────────────────┘
                  │ Polling alle 5 Min
┌─────────────────▼───────────────────────────────────┐
│              FastAPI Backend (Python)                │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                │
│  │  EV Engine   │  │  APScheduler │                │
│  │              │  │  (Cron)      │                │
│  │ • Devigging  │  └──────────────┘                │
│  │ • EV Calc    │                                   │
│  │ • Kelly      │  ┌──────────────┐                │
│  │ • Arbitrage  │  │   SQLite DB  │                │
│  └──────────────┘  │              │                │
│                    │ • Snapshots  │                │
│  REST API (/api/*) │ • ValueBets  │                │
│                    │ • Arbs       │                │
└─────────────────┬──│ • BetLog    │────────────────┘
                  │  └──────────────┘
┌─────────────────▼───────────────────────────────────┐
│            React Frontend (TypeScript)               │
│                                                     │
│  Dashboard → Value Bets → Arbitrage → Kelly         │
│              → Bet Tracker (CLV, ROI)               │
└─────────────────────────────────────────────────────┘
```

## Mathematische Methodik

### 1. Value Bets (Positive EV)
**Grundprinzip**: Wenn die _wahre_ Wahrscheinlichkeit eines Ereignisses größer ist als die vom Buchmacher implizierte Wahrscheinlichkeit, hat die Wette einen positiven Erwartungswert.

```
EV = p_true × odds − 1
```

**Wahrheitsfindung (Devigging)**:
Pinnacle und Betfair Exchange dienen als "Sharp" Referenz — diese Märkte sind effizient, weil scharfe Wettersfachleute Fehler sofort korrigieren. Wir entfernen die Vig (Buchmacher-Marge) um die wahre Wahrscheinlichkeit zu ermitteln:

```
p_true(i) = p_implied(i) / Σ p_implied(j)    [Multiplikative Methode]
```

### 2. Kelly-Kriterium
```
f* = (b·p − q) / b
```
wobei: `b = odds − 1`, `p = wahre Wahrscheinlichkeit`, `q = 1 − p`

System verwendet Quarter Kelly (0.25×) für konservatives Risikomanagement.

### 3. Arbitrage
```
Arb existiert wenn: Σ(1/odds_i) < 1
Garantierter Gewinn: (1/Σ(1/odds_i) − 1) × 100%
Stake_i = (1/odds_i) / Σ(1/odds_j) × Gesamteinsatz
```

### 4. Closing Line Value (CLV)
Langfristig-Indikator für Qualität der Wettenauswahl:
```
CLV% = (eigene_Quote / Schluss-Quote − 1) × 100
```
Konsistent positive CLV = langfristig profitabel.

## Setup

```bash
# 1. Repo klonen und starten
chmod +x start.sh
./start.sh

# 2. API-Key eintragen
# → https://the-odds-api.com (kostenlos: 500 Req/Monat)
# → In backend/.env: ODDS_API_KEY=dein_key

# 3. Dashboard aufrufen
# → http://localhost:5173
```

## API

```
GET  /api/dashboard/summary     → KPIs, beste Value Bets, Arbitrage
GET  /api/bets/value            → Aktive Value Bets (sortiert nach EV%)
GET  /api/bets/arbitrage        → Aktive Arbitrage-Möglichkeiten
POST /api/bets/kelly            → Kelly-Kalkulation
POST /api/bets/log              → Wette erfassen
GET  /api/bets/stats            → ROI, Win Rate, CLV
POST /api/scan/run              → Manuellen Scan starten
GET  /api/scan/status           → Scan-Status

Swagger UI: http://localhost:8000/docs
```

## Konfiguration (`backend/.env`)

| Variable | Standard | Beschreibung |
|----------|----------|--------------|
| `ODDS_API_KEY` | — | The Odds API Key |
| `POLL_INTERVAL_MINUTES` | 5 | Polling-Frequenz |
| `MIN_EV_THRESHOLD` | 0.02 | Minimum 2% Edge |
| `KELLY_FRACTION` | 0.25 | Quarter Kelly |
| `DEFAULT_BANKROLL` | 1000 | Bankroll in € |
