#!/usr/bin/env bash
set -uo pipefail

REPO_DIR="/home/d/CottonFlatBarQuiz"
BRANCH="main"
LOG_FILE="$REPO_DIR/update.log"

cd "$REPO_DIR" || exit 0

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# The ESP32 access point ("Cotton Flat Bar Quiz") answers every DNS query
# with its own address (captive portal behavior). That breaks Raspberry Pi
# Connect and any other service that needs real DNS resolution once the Pi
# joins that network. Force the NetworkManager profile for that SSID to use
# public DNS servers directly instead of the ESP32's hijacked DNS, so real
# internet name resolution keeps working over the ESP32's NAT routing.
fix_ap_dns() {
    if ! command -v nmcli >/dev/null 2>&1; then
        return 0
    fi

    if ! nmcli -t -f NAME connection show | grep -Fxq "Cotton Flat Bar Quiz"; then
        log "update-quiz: no Cotton Flat Bar Quiz connection profile found yet; skipping DNS fix"
        return 0
    fi

    if nmcli connection modify "Cotton Flat Bar Quiz" \
        ipv4.ignore-auto-dns yes \
        ipv4.dns "8.8.8.8 1.1.1.1" >>"$LOG_FILE" 2>&1; then
        log "update-quiz: set public DNS (8.8.8.8, 1.1.1.1) on Cotton Flat Bar Quiz profile so Raspberry Pi Connect keeps working"
    else
        log "update-quiz: failed to update DNS settings on Cotton Flat Bar Quiz profile"
    fi

    IFACE="$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1; exit}')"
    if [ -n "$IFACE" ]; then
        ACTIVE_CONN="$(nmcli -g GENERAL.CONNECTION device show "$IFACE" 2>/dev/null)"
        if [ "$ACTIVE_CONN" = "Cotton Flat Bar Quiz" ]; then
            log "update-quiz: reapplying Cotton Flat Bar Quiz connection to pick up new DNS settings"
            nmcli connection up "Cotton Flat Bar Quiz" >>"$LOG_FILE" 2>&1 || true
        fi
    fi
}

fix_ap_dns

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

git reset --hard "origin/$BRANCH" >>"$LOG_FILE" 2>&1
git clean -fd >>"$LOG_FILE" 2>&1

if ! /usr/bin/python3 -m py_compile "$REPO_DIR/Quiz.py" >>"$LOG_FILE" 2>&1; then
    log "update-quiz: Quiz.py syntax check failed; restoring $OLD_COMMIT"
    git reset --hard "$OLD_COMMIT" >>"$LOG_FILE" 2>&1
    exit 0
fi

log "update-quiz: updated successfully to $(git rev-parse --short HEAD)"
