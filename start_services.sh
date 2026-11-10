#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Loan Approval System — Service Launcher
# Services run detached from the terminal (survive session close).
# Use ./stop_services.sh to stop them.
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/.pids"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date +%H:%M:%S)] $*${NC}"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] $*${NC}"; }
err()  { echo -e "${RED}[$(date +%H:%M:%S)] ERROR: $*${NC}"; exit 1; }

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         🏦  Loan Approval Portal — Service Launcher      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Kill any already-running instances ────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
    warn "Stopping previous services..."
    while IFS= read -r pid; do
        kill "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    sleep 2
fi

# ── Pre-flight: .env ──────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        warn ".env not found — copying from .env.example"
        cp .env.example .env
        warn "Please set ANTHROPIC_API_KEY in .env, then re-run."
        exit 1
    fi
fi

# Load .env into this shell
set -a; source .env 2>/dev/null || true; set +a

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    err "ANTHROPIC_API_KEY is not set. Add it to .env"
fi

log "API key loaded: ${ANTHROPIC_API_KEY:0:5}..."

# ── Check dependencies ────────────────────────────────────────────────────────
if ! python3 -c "import anthropic, fastmcp, mcp, langgraph, fastapi, streamlit" 2>/dev/null; then
    warn "Missing dependencies — installing..."
    pip3 install -r requirements.txt --break-system-packages -q
    log "Dependencies installed."
fi

mkdir -p logs

# ── Start FastAPI (detached, logs appended) ───────────────────────────────────
log "Starting FastAPI backend on port ${API_PORT:-8000}..."
nohup python3 -m uvicorn api.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --log-level "${LOG_LEVEL:-info}" \
    >> logs/api.log 2>&1 &
API_PID=$!
echo "$API_PID" >> "$PID_FILE"
log "FastAPI PID: $API_PID"

# Wait for API to be ready
log "Waiting for FastAPI to be ready..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${API_PORT:-8000}/health" > /dev/null 2>&1; then
        log "FastAPI ready ✅"
        break
    fi
    sleep 1
    if [ "$i" -eq 30 ]; then
        err "FastAPI failed to start. Check logs/api.log"
    fi
done

# ── Start Streamlit (detached, logs appended) ─────────────────────────────────
log "Starting Streamlit UI on port 8501..."
nohup python3 -m streamlit run ui/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    >> logs/ui.log 2>&1 &
UI_PID=$!
echo "$UI_PID" >> "$PID_FILE"
log "Streamlit PID: $UI_PID"

sleep 3

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗"
echo "║   ✅  Services are running in the background             ║"
echo "║                                                          ║"
echo "║   🌐  Loan Portal:   http://localhost:8501               ║"
echo "║   ⚡  API Docs:      http://localhost:8000/docs          ║"
echo "║   🏥  Health:        http://localhost:8000/health        ║"
echo "║                                                          ║"
echo "║   They will keep running after you close this terminal.  ║"
echo "║   Run ./stop_services.sh to stop them.                   ║"
echo -e "╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Logs:  tail -f logs/api.log"
echo "         tail -f logs/ui.log"
