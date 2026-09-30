#!/usr/bin/env python3
"""tool/road/changes.py — the gate's `changes` job (B2-ROAD-A · THE ROAD; the decision map CD-4): which jobs a change needs.

Reads `git diff --name-status --no-renames` lines on stdin («M<TAB>path», «A<TAB>path», «D<TAB>path») and prints GITHUB_OUTPUT lines:
  suite=full|readers|none — full: app code, specs, a path the tests read, or the net itself changed (roadlib.APP) — format · analyze ·
                            the whole suite · coverage · APK; readers: only a record or a lock that a test reads changed
                            (roadlib.READERS) — those tests alone; none: neither.
  tests=<a b …>           — the reader tests, when suite=readers
  walk=true|false · drivers=<a b …> — the walk recipes to run (tool/mock_walks/RECIPES.json): every added or modified driver, and
                            every recipe naming an added or modified mock; with `--all-walks` (a hand-started proof run) every recipe
  records_only=true|false — nothing but the records (roadlib.RECORDS) changed
Removals count as changes for the suite, never for the walk. Skips are decided here, never by a workflow-level path filter (a
path-filtered required check waits forever — the cross-check K-2).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roadlib  # noqa: E402

RECIPES = "tool/mock_walks/RECIPES.json"


def load_recipes(path=RECIPES):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def parse(lines):
    out = []
    for line in lines:
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        if "\t" in line:
            status, path = line.split("\t", 1)
        else:
            status, path = "M", line.strip()
        out.append((status.strip()[:1] or "M", path.strip()))
    return out


def classify(entries, recipes, all_walks=False):
    paths = [p for _, p in entries]
    live = [p for s, p in entries if s != "D"]
    full = any(roadlib.under(p, roadlib.APP) for p in paths)
    tests = [] if full else roadlib.readers_for(paths)
    suite = "full" if full else ("readers" if tests else "none")
    if all_walks:
        drivers = [r["driver"] for r in recipes]
    else:
        chosen = []
        for p in live:
            if p.startswith("tool/mock_walks/") and p.rsplit("/", 1)[-1].startswith(("walk_", "pixels_")):
                chosen.append(p.rsplit("/", 1)[-1])
            if p.startswith("mocks/"):
                chosen.extend(r["driver"] for r in recipes if p in r.get("mocks", []))
        drivers = sorted(set(chosen))
    records_only = bool(paths) and all(roadlib.is_record(p) for p in paths)
    return {"suite": suite, "tests": tests, "walk": bool(drivers), "drivers": drivers, "records_only": records_only}


def main(argv):
    c = classify(parse(sys.stdin.read().splitlines()), load_recipes(), "--all-walks" in argv)
    print(f"suite={c['suite']}")
    print(f"tests={' '.join(c['tests'])}")
    print(f"walk={'true' if c['walk'] else 'false'}")
    print(f"drivers={' '.join(c['drivers'])}")
    print(f"records_only={'true' if c['records_only'] else 'false'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main(sys.argv[1:]))
