#!/usr/bin/env bash
# Run Strat-OS test suite on a laptop before deploying to Pi.
# Usage: bash scripts/run_tests.sh
set -e
cd "$(dirname "$0")/.."

echo "============================================================"
echo "  Strat-OS Laptop Test Suite"
echo "============================================================"

# ── Activate venv if present ──────────────────────────────────────────────────
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# ── Backend unit + integration tests ─────────────────────────────────────────
echo ""
echo ">>> Backend tests (pytest)"
pytest backend/tests/ -v --tb=short --no-header -q 2>&1
BACKEND_RC=$?

# ── Frontend type check ───────────────────────────────────────────────────────
if command -v npx &> /dev/null && [ -f "frontend/package.json" ]; then
    echo ""
    echo ">>> Frontend type check (tsc)"
    cd frontend
    npx tsc --noEmit 2>&1
    TS_RC=$?
    cd ..
else
    echo ">>> Frontend type check SKIPPED (no node/npm found)"
    TS_RC=0
fi

# ── Smoke test ────────────────────────────────────────────────────────────────
echo ""
echo ">>> End-to-end smoke test"
python scripts/smoke_test.py
SMOKE_RC=$?

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
if [ $BACKEND_RC -eq 0 ] && [ $TS_RC -eq 0 ] && [ $SMOKE_RC -eq 0 ]; then
    echo "  ALL TESTS PASSED — safe to deploy to Pi"
    exit 0
else
    echo "  TESTS FAILED"
    [ $BACKEND_RC -ne 0 ] && echo "  - Backend tests FAILED"
    [ $TS_RC -ne 0 ]      && echo "  - TypeScript type check FAILED"
    [ $SMOKE_RC -ne 0 ]   && echo "  - Smoke test FAILED"
    exit 1
fi
