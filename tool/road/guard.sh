#!/usr/bin/env bash
# tool/road/guard.sh — THE SMALL GUARD's launcher (B2-ROAD-A, 2026-09-30): PreToolUse on Bash for Claude Code (.claude/settings.json),
# for Codex (.codex/hooks.json, `--client codex`) and for the reviewer (`--reviewer`, its own hook in .claude/agents/reviewer.md). The
# program is tool/road/guard.py beside it; the payload passes on stdin. No python → refused (a guard that cannot judge never passes).
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "BLOCKED by THE SMALL GUARD: no python to judge the command. Nothing ran." >&2
  exit 2
fi
exec "$PY" "$(dirname "$0")/guard.py" "$@"
