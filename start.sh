#!/bin/bash
# Start both the API backend and React frontend

echo "Starting Meta Ads Dashboard..."

# Kill any stale processes on our ports
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
sleep 1

# Start FastAPI backend
cd "$(dirname "$0")"
.venv/bin/python -m uvicorn api.main:app --reload --port 8000 &
API_PID=$!
echo "API started (pid $API_PID) → http://localhost:8000"

# Start React frontend
cd dashboard
npm run dev &
VITE_PID=$!
echo "Dashboard starting → http://localhost:5173"

# Trap Ctrl+C to kill both
trap "kill $API_PID $VITE_PID 2>/dev/null; exit" INT TERM
wait
