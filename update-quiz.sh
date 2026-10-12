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
    log "update-quiz: $REPO_DIR is not a git repository; skipping update"
    exit 0
fi

log "update-quiz: waiting for GitHub HTTPS connectivity..."

READY=0
for attempt in $(seq 1 30); do
    if getent hosts github.com >/dev/null 2>&1 &&
       curl --silent --show-error --head --max-time 5 \
       https://github.com >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 2
done

CURRENT_SSID="$(iwgetid -r 2>/dev/null || echo unknown)"

if [ "$READY" -ne 1 ]; then
    log "update-quiz: GitHub HTTPS unavailable after 60 seconds; SSID=$CURRENT_SSID"
    exit 0
fi

log "update-quiz: GitHub reachable on SSID=$CURRENT_SSID"

if ! git fetch --prune origin "$BRANCH" >>"$LOG_FILE" 2>&1; then
    log "update-quiz: git fetch failed; keeping current code"
    exit 0
fi

OLD_COMMIT="$(git rev-parse HEAD)"
NEW_COMMIT="$(git rev-parse "origin/$BRANCH")"

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    log "update-quiz: already up to date at $(git rev-parse --short HEAD)"
    exit 0
fi

# quiz.db is tracked in git, so a hard reset would replace the live database
# (edits, answers, tokens, scores) with the committed copy. Preserve it.
DB_BACKUP="$HOME/.cotton-flat-quiz.db.bak"
if [ -f quiz.db ]; then
    cp -p quiz.db "$DB_BACKUP"
fi

git reset --hard "origin/$BRANCH" >>"$LOG_FILE" 2>&1
git clean -fd >>"$LOG_FILE" 2>&1

if [ -f "$DB_BACKUP" ]; then
    cp -p "$DB_BACKUP" quiz.db
    log "update-quiz: restored live quiz.db after update"
fi

if ! /usr/bin/python3 -m py_compile "$REPO_DIR/Quiz.py" >>"$LOG_FILE" 2>&1; then
    log "update-quiz: Quiz.py syntax check failed; restoring $OLD_COMMIT"
    git reset --hard "$OLD_COMMIT" >>"$LOG_FILE" 2>&1
    exit 0
fi

log "update-quiz: updated successfully to $(git rev-parse --short HEAD)"
