#!/usr/bin/env bash
# =============================================================================
# NCRB Criminal Network Analysis System — one-command launcher (Linux / macOS)
#
#   ./run.sh          start the platform (builds the UI if missing)
#   ./run.sh dev      run backend + Vite dev server with hot reload
#   ./run.sh test     run the test suite
#   ./run.sh reset    discard the database and re-ingest from scratch
# =============================================================================
set -euo pipefail
export PYTHONHASHSEED=0

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
PORT="${PORT:-8000}"
MODE="${1:-start}"

info() { printf '  \033[36m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m%s\033[0m\n' "$1"; }
warn() { printf '  \033[33m%s\033[0m\n' "$1"; }

echo
echo "  NCRB Criminal Network Analysis System"
echo "  National Crime Records Bureau | Women Safety Division | MHA"
echo

# --- 1. Python environment -----------------------------------------------
if [ ! -x "$PY" ]; then
  info "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

STAMP="$VENV/.deps-installed"
REQS="$ROOT/backend/requirements.txt"
if [ ! -f "$STAMP" ] || [ "$REQS" -nt "$STAMP" ]; then
  info "Installing Python dependencies..."
  "$PY" -m pip install --quiet --disable-pip-version-check --upgrade pip
  "$PY" -m pip install --quiet --disable-pip-version-check -r "$REQS"
  date > "$STAMP"
  ok "Dependencies ready."
fi

# --- 2. Reset -------------------------------------------------------------
if [ "$MODE" = "reset" ]; then
  warn "Removing existing database; the corpus will be rebuilt on next start."
  rm -f "$ROOT"/runtime/ncrb.db*
  MODE="start"
fi

# --- 3. Tests -------------------------------------------------------------
if [ "$MODE" = "test" ]; then
  info "Running test suite..."
  cd "$ROOT/backend"
  exec "$PY" -m pytest tests/ -v --tb=short
fi

# --- 4. Frontend ----------------------------------------------------------
FRONTEND="$ROOT/frontend"
if command -v npm >/dev/null 2>&1; then
  if [ ! -d "$FRONTEND/node_modules" ]; then
    info "Installing frontend dependencies (first run only)..."
    (cd "$FRONTEND" && npm install --no-audit --no-fund --silent)
  fi
  if [ "$MODE" != "dev" ] && [ ! -f "$FRONTEND/dist/index.html" ]; then
    info "Building dashboard..."
    (cd "$FRONTEND" && npm run build)
    ok "Dashboard built."
  fi
else
  warn "npm not found. The API will run, but the dashboard will not be available."
fi

# --- 5. Launch ------------------------------------------------------------
echo
if [ "$MODE" = "dev" ]; then
  ok "Starting in development mode."
  echo "    Dashboard : http://localhost:5173"
  echo "    API docs  : http://localhost:$PORT/docs"
  echo
  (cd "$ROOT/backend" && "$PY" -m uvicorn app.main:app --reload --port "$PORT") &
  BACKEND_PID=$!
  trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT
  sleep 3
  cd "$FRONTEND" && npm run dev
else
  ok "Starting the platform."
  echo "    Dashboard : http://localhost:$PORT/app"
  echo "    API docs  : http://localhost:$PORT/docs"
  echo "    Health    : http://localhost:$PORT/health"
  echo
  echo "    Sign in as investigator / invest123!  (or admin / admin123!)"
  echo "    First start ingests the corpus and runs full analytics (~15s)."
  echo
  cd "$ROOT/backend"
  exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi
