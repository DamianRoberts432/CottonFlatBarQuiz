#!/usr/bin/env bash
set -uo pipefail

REPO_DIR="/home/d/CottonFlatBarQuiz"
BRANCH="main"
LOG_FILE="$REPO_DIR/update.log"

cd "$REPO_DIR" || exit 0

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

if [ ! -d .git ]; then
    log "update-quiz: $REPO_DIR is not a git repository, skipping update"
    exit 0
fi

log "update-quiz: waiting for internet connectivity..."
ONLINE=0
for i in $(seq 1 60); do
    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 || ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
        ONLINE=1
        break
    fi
    sleep 2
done

CURRENT_SSID="$(iwgetid -r 2>/dev/null || echo unknown)"

if [ "$ONLINE" -ne 1 ]; then
    log "update-quiz: no internet after waiting (currently on SSID: $CURRENT_SSID), skipping update and starting quiz with existing code"
    exit 0
fi

log "update-quiz: internet is up (on SSID: $CURRENT_SSID), fetching origin/$BRANCH"

if ! git fetch origin "$BRANCH" >>"$LOG_FILE" 2>&1; then
    log "update-quiz: git fetch failed, skipping update and starting quiz with existing code"
    exit 0
fi

OLD_COMMIT="$(git rev-parse HEAD)"
NEW_COMMIT="$(git rev-parse "origin/$BRANCH")"

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    log "update-quiz: already up to date at $(git rev-parse --short HEAD)"
    exit 0
fi

# Keep the Pi's local checkout exactly aligned with GitHub.
git reset --hard "origin/$BRANCH" >>"$LOG_FILE" 2>&1
git clean -fd >>"$LOG_FILE" 2>&1

# Do not allow a syntactically broken Quiz.py to become the boot-time service.
if ! /usr/bin/python3 -m py_compile "$REPO_DIR/Quiz.py" >>"$LOG_FILE" 2>&1; then
    log "update-quiz: Quiz.py syntax check failed; restoring previous commit $OLD_COMMIT"
    git reset --hard "$OLD_COMMIT" >>"$LOG_FILE" 2>&1
    exit 0
fi

log "update-quiz: updated successfully to $(git rev-parse --short HEAD); Quiz.py syntax check passed"
