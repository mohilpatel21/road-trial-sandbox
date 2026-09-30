#!/usr/bin/env python3
"""tool/road/law.py — THE PULL-REQUEST CHECK, `law` (B2-ROAD-A · THE ROAD; the decision map CD-4 · CD-5 · CD-19, the cross-check
K-2 · K-10; proven in THE TRIAL's G7 · G9). Run by .github/workflows/law.yml from MAIN's own checkout (pull_request_target): it reads
the pull request's files, commits and body through the API and the environment, and never runs the pull request's code — so a pull
request cannot reshape the check that judges it.

The rules (each prints ok or RED with a plain reason; any RED fails):
  L1 THE REPORT — a ready pull request's body carries `## What changed`, `## Decided for you`, `## FOR MOHIL` and `## Models`.
  L2 READ FIRST — a change to the rules, the reviewer's instructions, the checks or the lock (roadlib.READ_FIRST) says READ FIRST.
  L3 NO TEST LOST — a test file removed, a test case removed, or a skip added is named in the body beside READ FIRST (BC-7 · K-10).
  L4 THE BASELINE ONLY SHRINKS — design/S31_LINT_BASELINE.txt gains no line.
  L5 PICTURES ONLY FROM REGEN — every commit that touches goldens/ci/ is the regen-ci-goldens workflow's own.
  L6 NO SPECS BESIDE LIB — specs/ and lib/ never change in one pull request.
  L7 THE SIZE CAPS — AGENTS.md ≤ 8,000 bytes and ≤ 199 lines; CLAUDE.md ≤ 3,000 bytes and ≤ 60 lines (roadlib.CAPS).
  L8 NO COMMENT TRIGGERS — no workflow gains an issue_comment, pull_request_review_comment or discussion_comment trigger.
  L9 THE OLD PATH'S FILES — nothing is added to or changed in build/seals/ or build/staging/ (removals are lawful).
Environment: GH_TOKEN · REPO · PR · HEAD_SHA · DRAFT («true»/«false») · BODY. Exit 0 green · 1 red · 2 a read failure.
"""
import base64
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roadlib  # noqa: E402

SECTIONS = ("## What changed", "## Decided for you", "## FOR MOHIL", "## Models")
TEST_CASE = re.compile(r"^\s*(test|testWidgets|goldenTest|group)\s*\(")
SKIP = re.compile(r"\bskip\s*:|@Skip\b|markTestSkipped\s*\(")
COMMENT_TRIGGER = re.compile(r"\b(issue_comment|pull_request_review_comment|discussion_comment)\b")


def added(patch):
    return [l[1:] for l in (patch or "").splitlines() if l.startswith("+") and not l.startswith("+++")]


def removed(patch):
    return [l[1:] for l in (patch or "").splitlines() if l.startswith("-") and not l.startswith("---")]


def judge(files, body, draft, commit_files, sizes):
    """files: [{filename, status, patch}] · commit_files: [(author name, [paths])] · sizes: {path: (bytes, lines)} at head.
    Returns [(rule, ok, message)]."""
    body = body or ""
    names = [f["filename"] for f in files]
    has_rf = "READ FIRST" in body
    out = []
    if draft:
        out.append(("L1", True, "a draft — the report is checked when it turns ready"))
    else:
        missing = [s for s in SECTIONS if s.lower() not in body.lower()]
        out.append(("L1", not missing, "the report's sections are present" if not missing else
                    "the body (the report) lacks " + ", ".join(f"«{m}»" for m in missing)))
    rf_paths = [n for n in names if roadlib.needs_read_first(n)]
    out.append(("L2", (not rf_paths) or has_rf, "no READ FIRST needed" if not rf_paths else
                ("READ FIRST present for " + ", ".join(rf_paths[:6]) if has_rf else
                 "this change touches the rules or the checks (" + ", ".join(rf_paths[:6]) + ") — the body must say READ FIRST")))
    lost = []
    for f in files:
        n = f["filename"]
        if not (n.startswith("test/") and n.endswith(".dart")):
            continue
        cases_gone = sum(1 for l in removed(f.get("patch")) if TEST_CASE.match(l)) - sum(1 for l in added(f.get("patch")) if TEST_CASE.match(l))
        if f.get("status") == "removed" or cases_gone > 0 or any(SKIP.search(l) for l in added(f.get("patch"))):
            lost.append(n)
    unnamed = [n for n in lost if not has_rf or n.split("/")[-1] not in body]
    out.append(("L3", not unnamed, "no test removed or skipped" if not lost else
                ("each removed or skipped test is named beside READ FIRST" if not unnamed else
                 "a test is removed or skipped without READ FIRST naming it: " + ", ".join(unnamed))))
    base_f = next((f for f in files if f["filename"] == "design/S31_LINT_BASELINE.txt"), None)
    grew = base_f is not None and bool(added(base_f.get("patch")))
    out.append(("L4", not grew, "the lint baseline did not grow" if not grew else
                "design/S31_LINT_BASELINE.txt gained a line — the baseline only shrinks"))
    bad = [a for a, paths in commit_files if any("/goldens/ci/" in p for p in paths) and a != "regen-ci-goldens"]
    out.append(("L5", not bad, "no picture moved outside regen-ci-goldens" if not bad else
                "goldens/ci/ changed in a commit by «" + ", ".join(sorted(set(bad))) + "» — pictures change only by the regen-ci-goldens workflow"))
    both = any(n.startswith("specs/") for n in names) and any(n.startswith("lib/") for n in names)
    out.append(("L6", not both, "specs and code are apart" if not both else "specs/ and lib/ change in one pull request — a spec door and a build are separate relays"))
    over = []
    for path, (cap_b, cap_l) in roadlib.CAPS.items():
        if path in sizes:
            b, l = sizes[path]
            if b > cap_b or l > cap_l:
                over.append(f"{path} {b} B / {l} lines (cap {cap_b} B / {cap_l} lines)")
    out.append(("L7", not over, "the rulebook within its caps" if not over else "over the size cap: " + "; ".join(over)))
    trig = [f["filename"] for f in files if f["filename"].startswith(".github/workflows/")
            and any(COMMENT_TRIGGER.search(l) for l in added(f.get("patch")))]
    out.append(("L8", not trig, "no workflow triggers on comments" if not trig else "a workflow gains a comment trigger: " + ", ".join(trig)))
    old = [f["filename"] for f in files if f["filename"].startswith(("build/seals/", "build/staging/")) and f.get("status") != "removed"]
    out.append(("L9", not old, "the old path's seals and staging untouched" if not old else
                "the old path's files are written on the road: " + ", ".join(old[:6])))
    return out


def main():
    try:
        gh = roadlib.GitHub(os.environ["REPO"], os.environ["GH_TOKEN"])
        pr, head = os.environ["PR"], os.environ["HEAD_SHA"]
        draft = os.environ.get("DRAFT", "false") == "true"
        body = os.environ.get("BODY", "")
        files = gh.pages(f"repos/{gh.repo}/pulls/{pr}/files")
        commit_files = []
        if any("/goldens/ci/" in f["filename"] for f in files):
            for c in gh.pages(f"repos/{gh.repo}/pulls/{pr}/commits"):
                detail = gh.get(f"repos/{gh.repo}/commits/{c['sha']}")
                commit_files.append(((c.get("commit") or {}).get("author", {}).get("name", "?"),
                                     [x["filename"] for x in detail.get("files") or []]))
        sizes = {}
        for path in roadlib.CAPS:
            if any(f["filename"] == path for f in files):
                got = gh.get(f"repos/{gh.repo}/contents/{path}?ref={head}")
                raw = base64.b64decode(got.get("content", "")) if got else b""
                sizes[path] = (len(raw), raw.count(b"\n"))
    except Exception as e:  # a read failure is never a pass
        print(f"law: could not read the pull request ({e!r}) — not a pass")
        return 2
    verdicts = judge(files, body, draft, commit_files, sizes)
    for rule, ok, msg in verdicts:
        print(f"{rule} {'ok ' if ok else 'RED'} — {msg}")
    reds = [r for r, ok, _ in verdicts if not ok]
    print("law: GREEN" if not reds else f"law: RED ({', '.join(reds)})")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as s:
            s.write("\n".join(f"- {r} {'ok' if ok else '**RED**'} — {m}" for r, ok, m in verdicts) + "\n")
    return 0 if not reds else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main())
