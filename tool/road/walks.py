#!/usr/bin/env python3
"""tool/road/walks.py — the gate's `walk` job (B2-ROAD-A · THE ROAD; the decision map CD-4 «the walk job for lock relays», THE TRIAL's
G12 · C3): runs the walk recipes the `changes` job chose, each under its bound, and reads each recipe's expected lines whole.

  python3 tool/road/walks.py <driver> [<driver> …]

A recipe (tool/mock_walks/RECIPES.json) names its driver, the mocks it reads, the command (run from the repository root), the lines
its output must carry — each read as a whole line —, its bound in seconds, and where it was proven. A changed driver without a recipe
is RED: the lock relay that boards a driver adds its recipe. The environment gives the rig: CHROME and CHROME_PATH (a Chrome), NODE_PATH
(jsdom 30.0.1 · puppeteer-core 25.4.0). Exit 0 when every recipe is green, 1 otherwise.
"""
import json
import os
import subprocess
import sys
import time

RECIPES = "tool/mock_walks/RECIPES.json"


def run(recipe):
    missing_mocks = [m for m in recipe.get("mocks", []) if not os.path.isfile(m)]
    if missing_mocks:
        return False, f"a mock it reads is absent: {', '.join(missing_mocks)}"
    t0 = time.time()
    try:
        p = subprocess.run(recipe["cmd"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=recipe.get("bound", 600), env=os.environ.copy())
    except subprocess.TimeoutExpired:
        return False, f"over its bound of {recipe.get('bound', 600)} s"
    lines = [l.strip() for l in p.stdout.splitlines()]
    missing = [e for e in recipe["expect"] if e.strip() not in lines]
    took = f"{time.time() - t0:.0f} s"
    tail = " | ".join(l for l in lines[-3:] if l)
    if p.returncode != recipe.get("rc", 0):
        return False, f"exit {p.returncode} in {took} — {tail or p.stderr.strip()[-300:]}"
    if missing:
        return False, f"{took} — its expected line is missing: «{missing[0]}» (last lines: {tail})"
    return True, f"{took} — " + " · ".join(f"«{e}»" for e in recipe["expect"])


def main(argv):
    names = [n for a in argv for n in a.split() if n]
    with open(RECIPES, encoding="utf-8") as f:
        recipes = {r["driver"]: r for r in json.load(f)}
    reds = 0
    for n in names:
        r = recipes.get(n)
        if r is None:
            print(f"walk {n}: RED — no recipe in {RECIPES} (the relay that boards or changes a driver adds its recipe)")
            reds += 1
            continue
        ok, msg = run(r)
        print(f"walk {n}: {'green' if ok else 'RED'} — {msg}")
        reds += 0 if ok else 1
    print(f"walks: {len(names)} run · {reds} red")
    return 0 if reds == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main(sys.argv[1:]))
