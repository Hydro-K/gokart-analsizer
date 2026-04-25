#!/usr/bin/env bash
# Strat-OS Auto Updater — runs at boot before main service
# Checks for internet, pulls from git if new commits available, rebuilds.
set -e

APP_DIR="/home/pi/strat-os"
VENV_DIR="$APP_DIR/.venv"
LOG="/var/log/strat-os-update.log"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

# No internet → skip silently
ping -c 1 -W 3 8.8.8.8 &>/dev/null || exit 0

cd "$APP_DIR"

# Fetch remote without merging
git fetch origin main 2>/dev/null || exit 0

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log "Already up to date ($LOCAL)"
    exit 0
fi

log "New version available: $LOCAL → $REMOTE"
log "Pulling update..."

git pull origin main

log "Updating Python dependencies..."
"$VENV_DIR/bin/pip" install -r backend/requirements.txt -q

log "Rebuilding frontend..."
cd frontend
npm ci --prefer-offline --silent
npm run build --silent
cd ..

log "Update complete. Restarting strat-os service..."
systemctl restart strat-os || true
log "Done."
