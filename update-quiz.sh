#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/d/CottonFlatBarQuiz"
BRANCH="main"
LOG_FILE="$REPO_DIR/update.log"

cd "$REPO_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# Make sure this is actually a git repo; if not, nothing to update.
if [ ! -d .git ]; then
    log "update-quiz: $REPO_DIR is not a git repository, skipping update"
    exit 0
fi

log "update-quiz: fetching latest changes from origin/$BRANCH"
git fetch origin "$BRANCH"

# Reset any local changes and fast-forward to the latest commit on the branch,
# so the Pi always runs exactly what's in GitHub.
git reset --hard "origin/$BRANCH"
git clean -fd

log "update-quiz: now at $(git rev-parse --short HEAD)"
