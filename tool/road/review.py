#!/usr/bin/env python3
"""tool/road/review.py — the review's record and its check (B2-ROAD-A · THE ROAD; the decision map CD-3 · CD-4, the cross-check
K-9; proven in THE TRIAL's G11, all four cases).

THIS CHANGE is the pull request's own change against main — `git diff <merge-base of the base ref and HEAD> HEAD` — with the records
left out (roadlib.RECORDS). Its FINGERPRINT is sha256 over «<path> <blob at HEAD or 'deleted'>» lines, sorted. So an up-to-date merge
from main and a records commit keep a verdict; any other commit voids it.

  python3 tool/road/review.py fingerprint [--base origin/main]
  python3 tool/road/review.py record --verdict GREEN|HALT --pass full|recheck --model <id> [--base origin/main]
        — THE REVIEWER's one write: review/VERDICT for this change (the driver commits it with review/WORDS.md, the reviewer's words
          verbatim). The driver never runs it.
  python3 tool/road/review.py decision --words "<his words, verbatim>" [--base origin/main]
        — the founder's decision after a second HALT (CD-3), recorded by the driver as HIS decision, never as a review verdict.
  python3 tool/road/review.py check [--base origin/main]
        — the gate's `review` job: records only → ok; else review/VERDICT (read from HEAD, never the working copy) must be GREEN or
          DECISION for this exact change, and review/WORDS.md present.
The honest limit: the check proves a verdict for this change exists, not who wrote it (THE TRIAL's G6 note).
"""
import datetime
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roadlib  # noqa: E402


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise SystemExit(f"review: git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def change(base: str):
    mb = git("merge-base", base, "HEAD").strip()
    paths = [p for p in git("diff", "--name-only", "--no-renames", mb, "HEAD").splitlines() if p.strip()]
    return mb, sorted(p for p in paths if not roadlib.is_record(p))


def fingerprint(base: str):
    mb, paths = change(base)
    lines = []
    for p in paths:
        blob = git("rev-parse", f"HEAD:{p}", check=False).strip() or "deleted"
        lines.append(f"{p} {blob}\n")
    return mb, paths, hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def write_verdict(fields: dict):
    os.makedirs("review", exist_ok=True)
    with open("review/VERDICT", "w", encoding="utf-8", newline="\n") as f:
        for k, v in fields.items():
            f.write(f"{k}: {v}\n")


def parse(text: str):
    out = {}
    for line in text.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            out[k.strip()] = v.strip()
    return out


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv):
    if not argv:
        print(__doc__)
        return 64
    cmd, base = argv[0], arg(argv, "--base", "origin/main")
    if cmd == "fingerprint":
        mb, paths, fp = fingerprint(base)
        print(fp)
        return 0
    if cmd == "record":
        verdict, pas, model = arg(argv, "--verdict"), arg(argv, "--pass"), arg(argv, "--model")
        if verdict not in ("GREEN", "HALT") or pas not in ("full", "recheck") or not model:
            print("review: record needs --verdict GREEN|HALT --pass full|recheck --model <id>")
            return 64
        mb, paths, fp = fingerprint(base)
        write_verdict({"verdict": verdict, "pass": pas, "fingerprint": fp, "base": mb, "head": git("rev-parse", "HEAD").strip(),
                       "paths": len(paths), "model": model, "date": now()})
        print(f"review: recorded {verdict} ({pas}) for {fp} — {len(paths)} path(s) against {mb[:7]}")
        return 0
    if cmd == "decision":
        words = arg(argv, "--words")
        if not words:
            print("review: decision needs --words \"<his words, verbatim>\"")
            return 64
        mb, paths, fp = fingerprint(base)
        write_verdict({"verdict": "DECISION", "pass": "his decision", "fingerprint": fp, "base": mb,
                       "head": git("rev-parse", "HEAD").strip(), "paths": len(paths), "decision": words, "date": now()})
        print(f"review: recorded HIS DECISION for {fp}")
        return 0
    if cmd == "check":
        mb, paths, fp = fingerprint(base)
        if not paths:
            print("review: records only — nothing to review")
            return 0
        print(f"review: this change is {len(paths)} path(s) against {mb[:7]} · fingerprint {fp}")
        raw = git("show", "HEAD:review/VERDICT", check=False)
        if not raw:
            print("review: RED — no review/VERDICT on this change (the reviewer records it; the driver never does)")
            return 1
        v = parse(raw)
        if v.get("verdict") not in ("GREEN", "DECISION"):
            print(f"review: RED — the recorded verdict is {v.get('verdict')!r}, not GREEN or his decision")
            return 1
        if v.get("fingerprint") != fp:
            print(f"review: RED — the recorded verdict is for another change ({v.get('fingerprint')}); a commit after the review moved it")
            return 1
        if v.get("verdict") == "GREEN" and not git("show", "HEAD:review/WORDS.md", check=False).strip():
            print("review: RED — review/WORDS.md (the reviewer's own words) is missing")
            return 1
        print(f"review: ok — {v.get('verdict')} ({v.get('pass')}) for this exact change")
        return 0
    print(__doc__)
    return 64


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main(sys.argv[1:]))
