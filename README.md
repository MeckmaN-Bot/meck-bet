# Meck-Bet — NBA Value Betting Analyzer

Lokale Web-App zur systematischen Erkennung von **Quoten-Fehlern** (Value Bets & Arbitrage) bei NBA-Spielen. Vollautomatische tägliche Wetten-Simulation mit einem **selbstlernenden KI-Modell**.

---

## Schnellinstallation (Linux)

```bash
# 1. Repository klonen
git clone https://github.com/MeckmaN-Bot/meck-bet.git
cd meck-bet

# 2. Installer starten (interaktiver Setup-Wizard)
chmod +x install.sh
./install.sh

# 3. Dashboard öffnen
http://localhost:8000
```

Der Installer:
- Prüft Python 3.10+ und Node 18+
- Erstellt Python venv + installiert alle Abhängigkeiten
- Baut das Frontend als statische Dateien
- Startet den interaktiven Setup-Wizard
- Richtet optional einen Systemd-Service ein (Autostart beim Boot)

---

## Manuelle Einrichtung

```bash
# Abhängigkeiten (Ubuntu/Debian)
sudo apt install python3.11 python3.11-venv nodejs npm

# Installation
make install

# Oder manuell
cd backend && python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ../frontend && npm install && npm run build

# Konfiguration (interaktiv)
python3 setup.py

# Starten
make start
```

---

## Wichtige Befehle

```bash
make start        # Im Hintergrund starten (screen)
make stop         # Stoppen
make restart      # Neu starten
make status       # Status prüfen
make logs         # Logs verfolgen

make dev          # Dev-Modus mit Auto-Reload (Vordergrund)
make build        # Frontend neu bauen
make update       # Git pull + rebuild + restart

make setup        # Konfiguration erneut einrichten
make test-api     # API-Verbindung testen
make demo-data    # 30 Tage Demo-Daten einfügen
make reset-model  # KI-Modell zurücksetzen
```

---

## Architektur

```
┌─────────────────────────────────────────────────────┐
│               The Odds API                          │
│  40+ Buchmacher inkl. Pinnacle (Sharp Reference)    │
└─────────────────┬───────────────────────────────────┘
                  │  Polling alle 10 Min
┌─────────────────▼───────────────────────────────────┐
│           FastAPI Backend (Python)                  │
│                                                     │
│  APScheduler:                                       │
│  ├── 08:00 UTC  → Settlement + Modell-Update       │
│  ├── 11:00 UTC  → Tägliche NBA-Picks generieren    │
│  └── alle 10m   → Odds-Scan (EV + Arbitrage)       │
│                                                     │
│  EV Engine:                                         │
│  ├── Devigging (Multiplicative/Power/Additive)     │
│  ├── EV = p_true × odds − 1                       │
│  ├── Kelly: f* = (b·p − q) / b                    │
│  └── Arbitrage: Σ(1/odds_i) < 1                   │
│                                                     │
│  Learning Model (Online Logistic Regression):       │
│  ├── 12 Features pro Wette                         │
│  ├── P(win) = σ(w·x) via SGD-Updates              │
│  ├── Score = P_model(win) × (1 + EV)              │
│  └── Gewichte in SQLite persistiert                │
│                                                     │
│  SQLite DB: Picks · Simulations · ModelWeights      │
│                                                     │
│  Serves frontend/dist/ als statische Dateien        │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│         React Dashboard (TypeScript)                │
│  NBA Bot · Performance · Value Bets · Arbitrage     │
│  Kelly Rechner · Wettenbuch                         │
└─────────────────────────────────────────────────────┘
```

---

## Mathematik

### Value Bet Erkennung

**1. Devigging** (Wahre Wahrscheinlichkeit aus Pinnacle-Quoten):
```
p_true(i) = p_implied(i) / Σ p_implied(j)
```

**2. Expected Value**:
```
EV = p_true × dezimalquote − 1    (>0 = Vorteil für Wetter)
```

**3. Kelly-Kriterium** (optimale Einsatzgröße):
```
f* = (b·p − q) / b     × Kelly-Fraktion (Standard: 0.25)
```

### Selbstlernendes KI-Modell

**Modell**: Logistische Regression mit 12 Features:

| Feature | Bedeutung |
|---------|-----------|
| `ev_percent` | Mathematischer Edge |
| `true_prob` | Deviggerte Wahrscheinlichkeit |
| `pick_team_wp` | Win% des getippten Teams |
| `pick_team_form` | Letzte-5-Formkurve |
| `rest_advantage` | Ausruhtage-Vorteil |
| `offense_edge` | Angriffsstärke vs. Gegnerdefense |
| u.v.m. | ... |

**Lernprozess** (nach jedem Spiel):
```
Verlust = Binary Cross-Entropy: -[y·log(p) + (1-y)·log(1-p)]
Update:  w ← w − η·(p−y)·x − λ·w    (SGD + L2-Regularisierung)
```

**Trefferquote** steigt über Zeit, da das Modell lernt welche Faktoren wirklich wichtig sind.

### Arbitrage
```
Arb existiert wenn: Σ(1/best_odds_i) < 1
Garantierter Gewinn: (1/Σ − 1) × 100%
Einsatz_i = (1/odds_i) / Σ(1/odds_j) × Gesamteinsatz
```

---

## Konfiguration (`backend/.env`)

| Variable | Standard | Beschreibung |
|----------|----------|--------------|
| `ODDS_API_KEY` | — | The Odds API Key (kostenlos) |
| `DEFAULT_BANKROLL` | 1000 | Simuliertes Bankroll in € |
| `DAILY_PICKS` | 5 | NBA-Picks pro Tag |
| `KELLY_FRACTION` | 0.25 | Quarter Kelly (konservativ) |
| `MIN_EV_THRESHOLD` | 0.02 | Minimum 2% Edge |
| `POLL_INTERVAL_MINUTES` | 10 | Odds-Refresh-Intervall |

---

## Datenquellen

| Quelle | Zweck | Kosten |
|--------|-------|--------|
| [The Odds API](https://the-odds-api.com) | Live-Quoten von 40+ Buchmachern | Free: 500 req/Monat |
| [balldontlie.io](https://www.balldontlie.io) | NBA Team-Stats, Spielergebnisse | Kostenlos |

---

## API Endpunkte

```
GET  /api/health                       → System-Status
GET  /api/config                       → Konfiguration
GET  /api/dashboard/summary            → KPIs & Übersicht
GET  /api/bets/value                   → Aktive Value Bets
GET  /api/bets/arbitrage               → Arbitrage-Möglichkeiten
POST /api/bets/kelly                   → Kelly-Kalkulator
POST /api/nba/picks/run                → Tagespicks jetzt generieren
POST /api/nba/settle                   → Ergebnisse abrechnen
GET  /api/nba/performance/summary      → Gesamtperformance
GET  /api/nba/model/weights            → KI-Modell Gewichte
POST /api/nba/demo/inject              → Demo-Daten einfügen
GET  /api/docs                         → Swagger UI
```
