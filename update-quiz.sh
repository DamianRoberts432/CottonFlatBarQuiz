#!/usr/bin/env bash
set -uo pipefail

REPO_DIR="/home/d/CottonFlatBarQuiz"
BRANCH="main"
LOG_FILE="$REPO_DIR/update.log"

cd "$REPO_DIR" || exit 0

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# Make sure this is actually a git repo; if not, nothing to update.
if [ ! -d .git ]; then
    log "update-quiz: $REPO_DIR is not a git repository, skipping update"
    exit 0
fi

# Wait for real internet access before trying to fetch. The Pi may join any
# of three Wi-Fi networks (Cotton Flat, work, home) depending on location,
# and it can take a few seconds after boot for the link to actually route
# traffic, so poll instead of failing immediately.
log "update-quiz: waiting for internet connectivity..."
ONLINE=0
for i in $(seq 1 30); do
    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 || ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
        ONLINE=1
        break
    fi
    sleep 2
done

CURRENT_SSID="$(iwgetline 2>/dev/null || true)"
CURRENT_SSID="$(iwgetid -r 2>/dev/null || echo unknown)"

if [ "$ONLINE" -ne 1 ]; then
    log "update-quiz: no internet after waiting (currently on SSID: $CURRENT_SSID), skipping update and starting quiz with existing code"
    exit 0
fi

log "update-quiz: internet is up (on SSID: $CURRENT_SSID), fetching latest changes from origin/$BRANCH"

if ! git fetch origin "$BRANCH" >>"$LOG_FILE" 2>&1; then
    log "update-quiz: git fetch failed, skipping update and starting quiz with existing code"
    exit 0
fi

# Reset any local changes and fast-forward to the latest commit on the branch,
# so the Pi always runs exactly what's in GitHub.
git reset --hard "origin/$BRANCH" >>"$LOG_FILE" 2>&1
git clean -fd >>"$LOG_FILE" 2>&1

log "update-quiz: now at $(git rev-parse --short HEAD)"
