#!/bin/bash
# Meck-Bet Startup Script
set -e

echo "🎯 Meck-Bet Value Betting Analyzer"
echo "===================================="

# Backend
echo ""
echo "▶ Backend starten..."
cd backend

if [ ! -d ".venv" ]; then
  echo "  Python venv erstellen..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "  Dependencies installieren..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  ⚠️  .env aus Beispieldatei erstellt. API-Key in backend/.env eintragen!"
fi

echo "  Backend startet auf http://localhost:8000 ..."
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Frontend
echo ""
echo "▶ Frontend starten..."
cd ../frontend

if [ ! -d "node_modules" ]; then
  echo "  npm install..."
  npm install
fi

echo "  Frontend startet auf http://localhost:5173 ..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Meck-Bet läuft!"
echo "   Dashboard: http://localhost:5173"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "Beenden mit Ctrl+C"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
