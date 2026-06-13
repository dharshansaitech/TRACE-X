#!/bin/bash
# demo/run_demo.sh
# End-to-end TRACE-X demo runner
# Starts infrastructure, seeds data, runs the travel bot with all failure modes,
# then opens the dashboard.
#
# Usage:
#   ./demo/run_demo.sh           # Full demo with Docker
#   ./demo/run_demo.sh --local   # Assumes backend already running on :8000
#   ./demo/run_demo.sh --quick   # Skip seeding, just inject failures

set -euo pipefail

BACKEND_URL="${TRACEX_BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="http://localhost:3000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODE="full"
for arg in "$@"; do
  case "$arg" in
    --local) MODE="local" ;;
    --quick) MODE="quick" ;;
    --help) echo "Usage: $0 [--local|--quick|--help]"; exit 0 ;;
  esac
done

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

section() { echo -e "\n${BOLD}${BLUE}━━━ $1 ━━━${NC}"; }
ok()      { echo -e "  ${GREEN}✓${NC} $1"; }
info()    { echo -e "  ${CYAN}▸${NC} $1"; }
warn()    { echo -e "  ${YELLOW}⚠${NC} $1"; }
error()   { echo -e "  ${RED}✗${NC} $1"; }

# ── Banner ─────────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
cat << 'BANNER'
 ████████╗██████╗  █████╗  ██████╗███████╗      ██╗  ██╗
    ██╔══╝██╔══██╗██╔══██╗██╔════╝██╔════╝      ╚██╗██╔╝
    ██║   ██████╔╝███████║██║     █████╗    ████╗╚███╔╝
    ██║   ██╔══██╗██╔══██║██║     ██╔══╝    ╚════╝██╔██╗
    ██║   ██║  ██║██║  ██║╚██████╗███████╗       ██╔╝ ██╗
    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝       ╚═╝  ╚═╝
  The Flight Recorder For AI Agents
BANNER
echo -e "${NC}"
echo -e "  Mode: ${BOLD}${MODE}${NC}"
echo -e "  Backend: ${CYAN}${BACKEND_URL}${NC}"
echo -e "  Dashboard: ${CYAN}${FRONTEND_URL}${NC}"
echo ""

cd "${PROJECT_ROOT}"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Start infrastructure (skip if --local or --quick)
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "full" ]]; then
  section "Starting Infrastructure"

  if ! command -v docker &>/dev/null; then
    error "Docker not found. Install Docker Desktop or use --local flag."
    exit 1
  fi

  info "Starting backend + frontend with docker-compose..."
  docker-compose up -d backend frontend

  info "Waiting for backend to be healthy..."
  MAX_WAIT=60
  WAITED=0
  while ! curl -sf "${BACKEND_URL}/health" >/dev/null 2>&1; do
    if [[ $WAITED -ge $MAX_WAIT ]]; then
      error "Backend did not start within ${MAX_WAIT}s"
      docker-compose logs backend | tail -20
      exit 1
    fi
    echo -n "."
    sleep 2
    WAITED=$((WAITED + 2))
  done
  echo ""
  ok "Backend healthy at ${BACKEND_URL}"

  info "Waiting for frontend..."
  sleep 3
  ok "Frontend should be at ${FRONTEND_URL}"

elif [[ "$MODE" == "local" ]]; then
  section "Checking Local Backend"
  if curl -sf "${BACKEND_URL}/health" >/dev/null 2>&1; then
    ok "Backend is running at ${BACKEND_URL}"
  else
    error "Backend not reachable at ${BACKEND_URL}"
    echo "  Start it with: uvicorn api.main:app --host 0.0.0.0 --port 8000"
    exit 1
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Seed historical data (skip if --quick)
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$MODE" != "quick" ]]; then
  section "Seeding Historical Data"
  info "Generating 48h of trace history (300 traces)..."
  python "${SCRIPT_DIR}/seed_data.py" --hours 48 --count 300
  ok "Historical data seeded"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Run travel bot — success case
# ─────────────────────────────────────────────────────────────────────────────
section "Demo: Successful Agent Run"
info "Running travel bot (no failures)..."
python "${SCRIPT_DIR}/agents/travel_bot.py" \
  --message "Book me a round-trip from JFK to LAX for 2 passengers next month, mid-range budget"
ok "Success trace ingested"

sleep 1

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Run travel bot — tool failure
# ─────────────────────────────────────────────────────────────────────────────
section "Demo: Tool Failure Injection"
info "Running travel bot with tool_failure mode..."
python "${SCRIPT_DIR}/agents/travel_bot.py" \
  --inject tool_failure \
  --message "Find me the cheapest flights from JFK to Chicago this weekend for 3 people" || true
ok "Tool failure trace ingested"

sleep 1

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Inject all failure scenarios via inject_failure.py
# ─────────────────────────────────────────────────────────────────────────────
section "Demo: Direct Failure Injection"
info "Injecting staleness, hallucination, and tool_error traces..."
python "${SCRIPT_DIR}/inject_failure.py" --all
ok "All failure scenarios injected"

sleep 1

# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Run hallucination scenario
# ─────────────────────────────────────────────────────────────────────────────
section "Demo: Hallucination Scenario"
info "Running travel bot with hallucination injection..."
python "${SCRIPT_DIR}/agents/travel_bot.py" \
  --inject hallucination \
  --message "Find me the absolute cheapest flight to LAX, I don't care about quality" || true
ok "Hallucination trace ingested"

# ─────────────────────────────────────────────────────────────────────────────
# Step 7: Summary
# ─────────────────────────────────────────────────────────────────────────────
section "Demo Complete!"

echo ""
echo -e "  ${BOLD}What to explore in the dashboard:${NC}"
echo ""
echo -e "  ${CYAN}1. Flight Deck${NC}    → ${FRONTEND_URL}"
echo -e "     Check the MetricCards and error rate graph"
echo ""
echo -e "  ${CYAN}2. Traces${NC}         → ${FRONTEND_URL}/traces"
echo -e "     Filter by agent or status to find failures"
echo ""
echo -e "  ${CYAN}3. Replay Center${NC}  → Click any failed trace → 'Replay'"
echo -e "     Watch the agent execute frame-by-frame"
echo ""
echo -e "  ${CYAN}4. Repair Queue${NC}   → ${FRONTEND_URL}/repairs"
echo -e "     Review and approve AI-generated fixes"
echo ""
echo -e "  ${CYAN}5. Simulator${NC}      → ${FRONTEND_URL}/simulator"
echo -e "     Run What-If scenarios with failure injection"
echo ""

echo -e "  ${BOLD}API Endpoints:${NC}"
echo -e "    ${BACKEND_URL}/docs          → Interactive API docs"
echo -e "    ${BACKEND_URL}/api/v1/traces → Trace list"
echo -e "    ${BACKEND_URL}/health        → Health check"
echo ""

if [[ "$MODE" == "full" ]]; then
  echo -e "  ${YELLOW}To stop:${NC} docker-compose down"
fi

echo ""
