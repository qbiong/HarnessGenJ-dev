#!/usr/bin/env bash
# Deterministic git push — AI should call this instead of describing "I will push"
# Usage: ./scripts/git-push.sh [commit-message]
set -euo pipefail

COMMIT_MSG="${1:-Auto-commit: $(date '+%Y-%m-%d %H:%M')}"

cd "$(git rev-parse --show-toplevel)"

# Check for changes
if [[ -z "$(git status --porcelain)" ]]; then
    echo "No changes to commit."
    exit 0
fi

# Stage all, commit, push
git add -A
git commit -m "$COMMIT_MSG" --allow-empty
git push

echo "Push complete. HEAD: $(git rev-parse --short HEAD)"
