#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/d/CottonFlatBarQuiz"
BRANCH="main"

cd "$REPO_DIR"

# Make sure this is actually a git repo; if not, nothing to update.
if [ ! -d .git ]; then
    echo "update-quiz: $REPO_DIR is not a git repository, skipping update" >&2
    exit 0
fi

echo "update-quiz: fetching latest changes from origin/$BRANCH"
git fetch origin "$BRANCH"

# Reset any local changes and fast-forward to the latest commit on the branch,
# so the Pi always runs exactly what's in GitHub.
git reset --hard "origin/$BRANCH"
git clean -fd

echo "update-quiz: now at $(git rev-parse --short HEAD)"
