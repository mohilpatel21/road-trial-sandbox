#!/usr/bin/env python3
"""tool/road/light.py — THE GREEN LIGHT (B2-ROAD-A · THE ROAD; the decision map CD-5 · CD-8 · CD-9, the cross-check K-2 · K-11 · K-15;
THE TRIAL's P3 and its lessons — the false green on PR #3, G9, G10). Run by .github/workflows/light.yml from MAIN's own copy when a
`ci` or `law` run completes; it runs none of the pull request's code.

It posts only when every one of these holds for the pull request's current head: open and not a draft · the newest `gate` check
green (none still running) · every `law` check from main's own law.yml (pull_request_target) green, the newest last, and no job named
`law` from the pull request's own workflows · GitHub's own merge state CLEAN. Then one comment, once per head: READ FIRST first when
the change touches the rules, the reviewer's instructions, the checks or the lock (computed here from the changed paths, never taken
from the pull request) · ✅ all checks passed with their key lines · the reviewer's verdict · what changed · decided for you · the undo
line · the models · FOR MOHIL with his one move (tap Merge) · the waiting improvements when NEXT lists any. It mentions him, then
unassigns and assigns him, so his phone rings (THE TRIAL's P3: both alerts arrive).
Environment: GH_TOKEN · REPO · OWNER (his login) · RUN_ID · RUN_HEAD_SHA · RUN_HEAD_BRANCH · RUN_NAME · PRS (the run's pull_requests JSON).
"""
import base64
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roadlib  # noqa: E402

WAIT_TRIES, WAIT_SECONDS = 12, 15
PASS_WORDS = {"full": "GREEN on the first pass", "recheck": "GREEN after one fix", "his decision": "stopped once; its findings fixed and checked by the driver — gone on by your word, not a review approval"}


def sections(body):
    """The body's `## ` sections by heading (lower-cased), and its READ FIRST text (from READ FIRST to the first heading)."""
    out, cur = {}, None
    for line in (body or "").splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1).strip().lower()
            out[cur] = []
        elif cur:
            out[cur].append(line)
    rf = ""
    if "READ FIRST" in (body or ""):
        after = body[body.index("READ FIRST"):]
        rf = after.split("\n## ", 1)[0].strip()
    return {k: "\n".join(v).strip() for k, v in out.items()}, rf


def cut(text, n=2500):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rstrip() + " …"


def run_event(gh, check):
    m = re.search(r"/actions/runs/(\d+)", check.get("details_url") or "")
    if not m:
        return None, None
    run = gh.get(f"repos/{gh.repo}/actions/runs/{m.group(1)}")
    return run.get("event"), run.get("path")


def state(gh, n, head):
    """('green', data) · ('wait', why) · ('stop', why)."""
    checks = [c for c in gh.get(f"repos/{gh.repo}/commits/{head}/check-runs?per_page=100").get("check_runs", [])
              if (c.get("app") or {}).get("slug") == "github-actions"]
    gates = sorted((c for c in checks if c["name"] == "gate"), key=lambda c: c["id"])
    laws = sorted((c for c in checks if c["name"] == "law"), key=lambda c: c["id"])
    if not gates or any(c["status"] != "completed" for c in gates):
        return "wait", "the gate is still running"
    if gates[-1]["conclusion"] != "success":
        return "stop", f"the gate reads {gates[-1]['conclusion']}"
    main_laws = []
    for c in laws:
        event, path = run_event(gh, c)
        if event == "pull_request_target" and path and path.endswith("law.yml"):
            main_laws.append(c)
        else:
            return "stop", "a job named law comes from the pull request's own workflows — no light (READ FIRST)"
    if not main_laws or any(c["status"] != "completed" for c in main_laws):
        return "wait", "law is still running"
    if main_laws[-1]["conclusion"] != "success":
        return "stop", f"law reads {main_laws[-1]['conclusion']}"
    q = gh.graphql("query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){mergeStateStatus isDraft headRefOid}}}",
                   {"o": gh.repo.split("/")[0], "r": gh.repo.split("/")[1], "n": int(n)})
    pr = (((q or {}).get("data") or {}).get("repository") or {}).get("pullRequest") or {}
    if pr.get("headRefOid") != head or pr.get("isDraft"):
        return "stop", "the pull request moved or is a draft"
    if pr.get("mergeStateStatus") != "CLEAN":
        return ("wait" if pr.get("mergeStateStatus") in ("UNKNOWN", "BLOCKED", "UNSTABLE") else "stop"), \
               f"GitHub's merge state reads {pr.get('mergeStateStatus')}"
    app = [c for c in checks if c["name"] == "app"]
    return "green", {"gate": gates[-1], "app": sorted(app, key=lambda c: c["id"])[-1] if app else None}


def key_lines(gh, data):
    app = data.get("app")
    if not app or app.get("conclusion") == "skipped":
        return "the app's tests were not needed (no app, spec or test change)"
    notes = gh.pages(f"repos/{gh.repo}/check-runs/{app['id']}/annotations")
    lines = [f"{a.get('title')}: {a.get('message')}" for a in notes if a.get("annotation_level") == "notice" and a.get("title")]
    return " · ".join(lines) or "the app job passed"


def content(gh, path, ref):
    try:
        got = gh.get(f"repos/{gh.repo}/contents/{path}?ref={ref}")
        return base64.b64decode(got.get("content", "")).decode("utf-8", "replace")
    except Exception:
        return ""


def compose(owner, pr, head, files, verdict, keys, waiting):
    secs, rf_text = sections(pr.get("body"))
    rf_paths = [f["filename"] for f in files if roadlib.needs_read_first(f["filename"])]
    parts = []
    if rf_paths or rf_text:
        why = cut(rf_text, 1500) if rf_text else "(the body gives no READ FIRST paragraph)"
        parts.append("> **READ FIRST** — this change touches " + (", ".join(rf_paths[:8]) + (" …" if len(rf_paths) > 8 else "")
                     if rf_paths else "a test") + ".\n> " + why.replace("\n", "\n> "))
    parts.append(f"@{owner} ✅ **Ready for your tap** — {pr.get('title')}")
    parts.append(f"**All checks passed** on `{head[:7]}`: {keys}.")
    if verdict is None:
        parts.append("**Reviewer:** not needed — records only.")
    else:
        parts.append(f"**Reviewer:** {PASS_WORDS.get(verdict.get('pass'), verdict.get('verdict'))}"
                     + (f" ({verdict.get('model')})" if verdict.get("model") else "") + ".")
    parts.append("**What changed:**\n" + cut(secs.get("what changed", "(missing)")))
    parts.append("**Decided for you:**\n" + cut(secs.get("decided for you", "(missing)")))
    parts.append(f"**Undo:** tell the driver «undo #{pr.get('number')}» — it opens a pull request that reverses this one, through the same checks.")
    parts.append("**Models:** " + cut(secs.get("models", "(missing)"), 300))
    fm = cut(secs.get("for mohil", ""), 2500)
    parts.append("**FOR MOHIL**\n" + (fm + "\n" if fm else "") + f"What you do now: tap **Merge** on this pull request → {pr.get('html_url')}")
    if waiting:
        parts.append(f"{waiting} improvement{'s' if waiting != 1 else ''} waiting — say «look».")
    parts.append(f"<sub>light {head[:7]}</sub>")
    return "\n\n".join(parts)


def waiting_count(next_md):
    m = re.search(r"^## Waiting\b.*?$(.*?)(?=^## |\Z)", next_md or "", re.M | re.S)
    if not m:
        return 0
    return sum(1 for l in m.group(1).splitlines() if l.startswith("- ") and "(none)" not in l)


def main():
    gh = roadlib.GitHub(os.environ["REPO"], os.environ["GH_TOKEN"])
    owner = os.environ.get("OWNER") or roadlib.FOUNDER
    head_sha = os.environ["RUN_HEAD_SHA"]
    prs = json.loads(os.environ.get("PRS") or "[]")
    n = prs[0]["number"] if prs else None
    if n is None:
        found = gh.get(f"repos/{gh.repo}/pulls?state=open&head={owner}:{os.environ.get('RUN_HEAD_BRANCH', '')}")
        n = found[0]["number"] if found else None
    if n is None:
        print("light: no open pull request for this run")
        return 0
    for attempt in range(WAIT_TRIES):
        pr = gh.get(f"repos/{gh.repo}/pulls/{n}")
        if pr.get("state") != "open" or pr.get("draft"):
            print(f"light: #{n} is {'a draft' if pr.get('draft') else pr.get('state')} — no light")
            return 0
        head = pr["head"]["sha"]
        if head != head_sha:
            print(f"light: #{n} moved on ({head[:7]}) — this run's head {head_sha[:7]} is stale")
            return 0
        verdict_state, data = state(gh, n, head)
        if verdict_state == "green":
            break
        print(f"light: #{n} {verdict_state} — {data}")
        if verdict_state == "stop":
            return 0
        time.sleep(WAIT_SECONDS)
    else:
        print("light: still waiting after the bound — the next completed run lights it")
        return 0
    comments = gh.pages(f"repos/{gh.repo}/issues/{n}/comments")
    if any(f"light {head[:7]}" in (c.get("body") or "") for c in comments):
        print(f"light: #{n} already lit for {head[:7]}")
        return 0
    files = gh.pages(f"repos/{gh.repo}/pulls/{n}/files")
    change = [f for f in files if not roadlib.is_record(f["filename"])]
    verdict = None
    if change:
        raw = content(gh, "review/VERDICT", head)
        verdict = {k.strip(): v.strip() for k, v in (l.split(": ", 1) for l in raw.splitlines() if ": " in l)} or {"verdict": "?"}
    body = compose(owner, pr, head, files, verdict, key_lines(gh, data), waiting_count(content(gh, "design/NEXT.md", head)))
    gh.post(f"repos/{gh.repo}/issues/{n}/comments", {"body": body})
    try:
        gh.delete(f"repos/{gh.repo}/issues/{n}/assignees", {"assignees": [owner]})
    except Exception:
        pass
    gh.post(f"repos/{gh.repo}/issues/{n}/assignees", {"assignees": [owner]})
    print(f"light: #{n} lit at {head[:7]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main())
