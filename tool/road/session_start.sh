#!/usr/bin/env bash
# tool/road/session_start.sh — THE ROAD's session banner (B2-ROAD-A, 2026-09-30; the decision map CD-6 · CD-20, the cross-check K-24):
# SessionStart for Claude Code (.claude/settings.json) and Codex (.codex/hooks.json). It prints design/NEXT.md's head — the one place that
# says what's next (its first line: the last landed relay and its pull request) — the git picture and the law's pointer, as the hook's
# additional context; STATE's FOR MOHIL and KICKOFF's NEXT are frozen history from this relay on. A short, complete orientation; the
# law still asks for the full reads. Always exits 0 (a banner never blocks a session).
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
PY=$(command -v python3 || command -v python) || exit 0
"$PY" - <<'PY'
import json, pathlib, shutil, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
def read(p):
    try: return pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError: return ""
def git(*a):
    try:
        r = subprocess.run([shutil.which("git") or "git", *a], capture_output=True, timeout=5)
        return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else "(git read unavailable)"
    except (OSError, subprocess.TimeoutExpired): return "(git read unavailable)"
nxt = read("design/NEXT.md").replace("\r", "").strip() or "design/NEXT.md is absent — read AGENTS.md and ask him what's next."
picture = git("branch", "--show-current") + " · " + git("log", "-1", "--format=%h %s") + "\n" + git("status", "--short")
law = "AGENTS.md is the rulebook for every driver (CLAUDE.md adds Claude Code's lines): read it whole now. Receipts and the tree govern; memory may be stale."
def short(s, n): return s if len(s) <= n else s[:n] + " … (the rest in the file)"
for n in (2400, 1600, 900, 400):
    ctx = "== NEXT (design/NEXT.md) ==\n" + short(nxt, n) + "\n== GIT ==\n" + short(picture, 600) + "\n== LAW ==\n" + law
    payload = json.dumps({"systemMessage": short(nxt.splitlines()[0] if nxt else "", 200),
                          "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}, ensure_ascii=False)
    if len(payload.encode("utf-8")) + 1 <= 4096: break
print(payload)
PY
exit 0
