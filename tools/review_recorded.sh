#!/usr/bin/env bash
# review-recorded (K-9): the recorded verdict must be for THIS change — the files the PR changes against main (records left out),
# fingerprinted by path and blob, so an up-to-date merge from main keeps it and a later code commit voids it.
# Usage: bash tools/review_recorded.sh <base ref>        (prints the fingerprint; checks review/verdict.txt)
#        bash tools/review_recorded.sh <base ref> --print (prints only the fingerprint, for recording a verdict)
set -eu
BASE_REF="${1:-origin/main}"
MB=$(git merge-base "$BASE_REF" HEAD)
PATHS=$(git diff --name-only "$MB" HEAD -- . ':(exclude)design/NEXT.md' ':(exclude)review' | sort)
FP=$(for p in $PATHS; do printf '%s %s\n' "$p" "$(git rev-parse "HEAD:$p" 2>/dev/null || echo deleted)"; done | sha256sum | cut -c1-64)
if [ "${2:-}" = --print ]; then echo "$FP"; exit 0; fi
if [ -z "$PATHS" ]; then echo "review-recorded: records only — nothing to review"; exit 0; fi
[ -f review/verdict.txt ] || { echo "FAIL: no review/verdict.txt"; exit 1; }
read -r VERDICT VFP < review/verdict.txt
echo "change fingerprint: $FP · recorded: $VERDICT $VFP"
case "$VERDICT" in GREEN|DECISION) ;; *) echo "FAIL: the verdict is $VERDICT"; exit 1 ;; esac
[ "$FP" = "$VFP" ] || { echo "FAIL: the recorded verdict is for another change"; exit 1; }
echo "review-recorded: ok"
