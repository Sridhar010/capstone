#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Loan Approval System — Service Launcher
# Starts the FastAPI backend and Streamlit UI
# MCP servers are started on-demand by the agents (stdio transport)
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)] $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] $1${NC}"; }
err()  { echo -e "${RED}[$(date +%H:%M:%S)] ERROR: $1${NC}"; }

cleanup() {
    echo ""
    warn "Stopping all services..."
    kill "${API_PID:-}" "${UI_PID:-}" 2>/dev/null || true
    log "All services stopped."
}
trap cleanup EXIT INT TERM

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   🏦  Agentic AI Loan Approval System                    ║"
echo "║   Multi-Agent Architecture with LangGraph + FastMCP      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Pre-flight checks ──────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        warn ".env not found — copying from .env.example"
        cp .env.example .env
        warn "Please edit .env and set your ANTHROPIC_API_KEY, then re-run."
        exit 1
    fi
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    # Try loading from .env
    set -a; source .env 2>/dev/null || true; set +a
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    err "ANTHROPIC_API_KEY is not set. Add it to .env"
    exit 1
fi

log "API key found: ${ANTHROPIC_API_KEY:0:15}..."

# ── Check dependencies ─────────────────────────────────────────────────────────
if ! python3 -c "import anthropic, fastmcp, mcp, langgraph, fastapi, streamlit" 2>/dev/null; then
    warn "Missing dependencies detected. Installing..."
    pip3 install -r requirements.txt --break-system-packages -q
    log "Dependencies installed."
fi

# ── Start FastAPI backend ──────────────────────────────────────────────────────
log "Starting FastAPI backend on port ${API_PORT:-8000}..."
set -a; source .env 2>/dev/null || true; set +a
python3 -m uvicorn api.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --log-level "${LOG_LEVEL:-info}" \
    > logs/api.log 2>&1 &
API_PID=$!
log "FastAPI PID: $API_PID"

# Wait for API to be ready
log "Waiting for FastAPI to be ready..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${API_PORT:-8000}/health" > /dev/null 2>&1; then
        log "FastAPI ready! ✅"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        err "FastAPI failed to start. Check logs/api.log"
        cat logs/api.log
        exit 1
    fi
done

# ── Start Streamlit UI ─────────────────────────────────────────────────────────
log "Starting Streamlit UI on port 8501..."
streamlit run ui/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --theme.base dark \
    > logs/ui.log 2>&1 &
UI_PID=$!
log "Streamlit PID: $UI_PID"

sleep 3

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗"
echo "║   ✅ All services are running!                            ║"
echo "║                                                          ║"
echo "║   🌐 Streamlit UI:  http://localhost:8501                ║"
echo "║   ⚡ FastAPI Docs:  http://localhost:8000/docs           ║"
echo "║   🏥 Health Check:  http://localhost:8000/health         ║"
echo "║                                                          ║"
echo "║   Press Ctrl+C to stop all services                      ║"
echo -e "╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Monitor services ───────────────────────────────────────────────────────────
while true; do
    if ! kill -0 "$API_PID" 2>/dev/null; then
        err "FastAPI crashed! Check logs/api.log"
        cat logs/api.log | tail -20
        exit 1
    fi
    if ! kill -0 "$UI_PID" 2>/dev/null; then
        warn "Streamlit stopped. Check logs/ui.log"
        break
    fi
    sleep 5
done
