#!/usr/bin/env python3
"""tool/road/guard.py — THE SMALL GUARD (B2-ROAD-A · THE ROAD, 2026-09-30; the decision map CD-2's safety basics and F.2's «a small
destructive-command guard», the cross-check K-13 · K-18, THE TRIAL's G13 and its NOTES 09:0xZ — the old wall refused harmless prose).

It judges COMMANDS, never the prose they carry: the shell text is cut into commands (quotes, escapes, heredoc bodies and comments
understood), and each command's own words are read; a `bash -c`/`sh -c`/`eval` string, a `$( … )` or a backtick body, and a heredoc
fed to a shell are judged as commands of their own. It refuses only:
  - git push that forces or deletes (--force · -f · --force-with-lease · --force-if-includes · --mirror · --delete · -d · --prune ·
    a +refspec or :refspec); git reset --hard; git clean (any);
  - rm that is recursive AND forced, unless every target lies under verify/ (the WR-24 prune door) or /tmp/;
  - merging on GitHub: gh pr merge; a write through gh api or curl to …/merge(s), …/rulesets, …/protection, …/hooks, …/dispatches,
    …/secrets, …/variables, …/keys, …/collaborators or …/actions/permissions; a graphql mutation that merges or changes protection;
  - gh workflow run except regen-ci-goldens.yml (never on main) and ci.yml; gh secret · variable · auth (but status) · repo
    delete/edit/archive/rename/transfer;
  - flutter clean; firebase deploy.
`--reviewer` (the reviewer's own hook) also refuses every git write (a read-only allow-list) and any redirection or tee outside /tmp.
A command text that cannot be parsed (an unbalanced quote) is read by a narrow fallback pattern for the same forms; an unreadable
payload is refused. Claude Code: exit 2 + the reason on stderr. Codex (`--client codex`): the JSON deny on stdout, exit 0.
Fixtures: tool/road/test_road.py (guard_*).
"""
import json
import re
import shlex
import sys

SHELLS = {"bash", "sh", "zsh", "dash"}
CACHES = {"__pycache__", ".dart_tool", "node_modules", ".pytest_cache"}
SENSITIVE = re.compile(r"/(merge|merges|rulesets?|protection|hooks|dispatches|secrets|variables|keys|collaborators)(/|$|\?)|"
                       r"/actions/permissions")
GQL_BAD = re.compile(r"\bmutation\b[\s\S]*\b(mergePullRequest|enablePullRequestAutoMerge|mergeBranch|"
                     r"(create|update|delete)(BranchProtectionRule|RepositoryRuleset))\b")
READ_ONLY_GIT = {"status", "log", "diff", "show", "rev-parse", "merge-base", "ls-files", "ls-tree", "cat-file", "grep", "blame",
                 "describe", "name-rev", "shortlog", "worktree", "fetch", "for-each-ref", "rev-list", "count-objects",
                 "check-ignore", "check-attr", "show-ref", "reflog", "remote", "config", "branch", "tag", "version", "help"}
FALLBACK = [
    (re.compile(r"\bgit\s+push\b[^\n;&|]*\s(--force\b|--force-with-lease\b|-f\b|--mirror\b|--delete\b)"), "a forced or deleting git push"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
    (re.compile(r"\bgit\s+clean\b"), "git clean"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "gh pr merge"),
    (re.compile(r"\brm\s+-\w*(r\w*f|f\w*r)"), "a recursive forced rm"),
    (re.compile(r"\bflutter\s+clean\b"), "flutter clean"),
    (re.compile(r"\bfirebase\s+deploy\b"), "firebase deploy"),
]


class Refuse(Exception):
    pass


def cut_heredocs(text):
    """Remove heredoc bodies from the text; return (command text with unquoted newlines as ';', [(owner command, body)])."""
    out, bodies, pending = [], [], []
    i, n, quote = 0, len(text), None
    line_start = 0
    while i < n:
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = None
            out.append(c); i += 1; continue
        if c == "\\" and i + 1 < n:
            out.append(text[i:i + 2]); i += 2; continue
        if quote == '"':
            if c == '"':
                quote = None
            out.append(c); i += 1; continue
        if c in "'\"":
            quote = c; out.append(c); i += 1; continue
        if c == "#" and (i == 0 or text[i - 1] in " \t\n;&|("):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text.startswith("<<", i) and not text.startswith("<<<", i):
            m = re.match(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", text[i:])
            if m:
                owner = "".join(out)[line_start:]
                pending.append((m.group(2), text.startswith("<<-", i), owner))
                i += m.end(); continue
        if c == "\n":
            out.append(" ; "); i += 1
            line_start = len("".join(out))
            while pending:
                delim, dash, owner = pending.pop(0)
                body = []
                while i < n:
                    j = text.find("\n", i)
                    line = text[i:] if j < 0 else text[i:j]
                    i = n if j < 0 else j + 1
                    if (line.lstrip("\t") if dash else line) == delim:
                        break
                    body.append(line)
                bodies.append((owner, "\n".join(body)))
            continue
        out.append(c); i += 1
    return "".join(out), bodies


def substitutions(text):
    """The bodies of $( … ) and backticks outside single quotes (balanced parentheses)."""
    found, i, n, quote = [], 0, len(text), None
    while i < n:
        c = text[i]
        if quote == "'":
            quote = None if c == "'" else quote; i += 1; continue
        if c == "\\":
            i += 2; continue
        if c == "'" and quote is None:
            quote = "'"; i += 1; continue
        if text.startswith("$(", i) and not text.startswith("$((", i):
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0); j += 1
            found.append(text[i + 2:j - 1]); i = j; continue
        if c == "`":
            j = text.find("`", i + 1)
            if j < 0:
                break
            found.append(text[i + 1:j]); i = j + 1; continue
        i += 1
    return found


OUT_OPS = {">", ">>", ">|", "&>", "&>>", ">&"}


def split_argvs(text):
    """The simple commands of a text: [(argv, output-redirection targets)] — operators split them; a redirection's target never
    joins the argv (an input's is dropped, an output's is kept for the reviewer's check)."""
    lex = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    lex.commenters = ""
    argvs, cur, outs, pending = [], [], [], None
    for tok in lex:
        if pending is not None:
            if pending in OUT_OPS:
                outs.append(tok)
            pending = None
            continue
        if tok and set(tok) <= set(";&|()"):
            if cur:
                argvs.append((cur, outs))
            cur, outs = [], []
            continue
        if tok and set(tok) <= set("<>&|"):
            pending = tok
            continue
        cur.append(tok)
    if cur:
        argvs.append((cur, outs))
    return argvs


def strip_wrappers(argv, seen=None):
    """The command under its wrappers (VAR=value · sudo · command · env · timeout · xargs …); `seen` collects the wrappers met."""
    while argv and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", argv[0]):
        argv = argv[1:]
    while argv and argv[0] in ("sudo", "command", "builtin", "exec", "nohup", "time", "nice", "env", "timeout", "xargs", "stdbuf"):
        w, argv = argv[0], argv[1:]
        if seen is not None:
            seen.add(w)
        while argv and (argv[0].startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", argv[0])):
            opt, argv = argv[0], argv[1:]
            if w in ("nice", "timeout", "stdbuf") and opt in ("-n", "-s", "-k", "-i", "-o", "-e") and argv:
                argv = argv[1:]
        if w == "timeout" and argv and re.match(r"^\d+(\.\d+)?[smhd]?$", argv[0]):
            argv = argv[1:]
    return argv


def flags(args):
    return [a for a in args if a.startswith("-")]


def judge_git(args, reviewer):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-C", "-c") else 1
    if i >= len(args):
        return
    sub, rest = args[i], args[i + 1:]
    if reviewer:
        if sub not in READ_ONLY_GIT:
            raise Refuse(f"git {sub} — the reviewer reads; its one write is tool/road/review.py record")
        if sub == "branch" and any(f in rest for f in ("-d", "-D", "-m", "-M", "-c", "-C", "--delete", "--move")):
            raise Refuse("git branch changes — the reviewer reads")
        if sub == "config" and not any(f in rest for f in ("--get", "--list", "-l", "--get-all", "--get-regexp")):
            raise Refuse("git config write — the reviewer reads")
    if sub == "push":
        for a in rest:
            if a in ("--force", "--force-with-lease", "--force-if-includes", "--mirror", "--delete", "--prune") or \
               a.startswith("--force-with-lease=") or (re.match(r"^-[a-zA-Z]+$", a) and ("f" in a or "d" in a)):
                raise Refuse(f"git push {a} — a push that forces or deletes rewrites history")
            if not a.startswith("-") and (a.startswith("+") or a.startswith(":")):
                raise Refuse(f"git push {a} — a +refspec forces and a :refspec deletes")
    if sub == "reset" and "--hard" in rest:
        raise Refuse("git reset --hard — founder-run only")
    if sub == "clean":
        raise Refuse("git clean — it wipes untracked work (verify/ among it); founder-run only")


def judge_gh(args):
    if not args:
        return
    sub, act = args[0], (args[1] if len(args) > 1 else "")
    if sub == "pr" and act == "merge":
        raise Refuse("gh pr merge — the AI never merges; he taps Merge")
    if sub == "api":
        method, fields, ep, body = None, False, "", ""
        k = 1
        while k < len(args):
            a = args[k]
            if a in ("-X", "--method") and k + 1 < len(args):
                method = args[k + 1].upper(); k += 2; continue
            if a.startswith("--method="):
                method = a.split("=", 1)[1].upper(); k += 1; continue
            if a in ("-f", "-F", "--field", "--raw-field", "--input") and k + 1 < len(args):
                fields = True; body += " " + args[k + 1]; k += 2; continue
            if not a.startswith("-") and not ep:
                ep = a
            k += 1
        method = method or ("POST" if fields else "GET")
        if ep == "graphql":
            if GQL_BAD.search(body):
                raise Refuse("a graphql mutation that merges or changes protection")
        elif method != "GET" and SENSITIVE.search("/" + ep.lstrip("/")):
            raise Refuse(f"gh api {method} {ep} — merging, the lock, hooks, dispatches and secrets are never the AI's")
    if sub == "workflow" and act == "run":
        target = args[2] if len(args) > 2 else ""
        if target in ("regen-ci-goldens.yml", "regen-ci-goldens"):
            joined = " ".join(args)
            if re.search(r"branch=(main|master|refs/heads/main)\b", joined):
                raise Refuse("regen-ci-goldens on main — the pictures regenerate on a relay's own branch")
            return
        if target in ("ci.yml", "ci"):
            return
        raise Refuse(f"gh workflow run {target} — only regen-ci-goldens.yml and ci.yml are the driver's; ask him for the others")
    if sub in ("secret", "variable"):
        raise Refuse(f"gh {sub} — secrets and settings are never the AI's")
    if sub == "auth" and act not in ("status", ""):
        raise Refuse(f"gh auth {act} — his accounts are never the AI's")
    if sub == "repo" and act in ("delete", "edit", "archive", "unarchive", "rename", "transfer"):
        raise Refuse(f"gh repo {act} — the repository's settings are his")


def judge_curl(args):
    url = next((a for a in args if "api.github.com" in a), "")
    if not url:
        return
    method = None
    for k, a in enumerate(args):
        if a in ("-X", "--request") and k + 1 < len(args):
            method = args[k + 1].upper()
        elif a.startswith("-X") and len(a) > 2:
            method = a[2:].upper()
    if method is None and any(a in ("-d", "--data", "--data-raw", "--data-binary", "--json", "-F", "--form") for a in args):
        method = "POST"
    if (method or "GET") != "GET" and SENSITIVE.search(url.split("api.github.com", 1)[1]):
        raise Refuse(f"curl {method} to {url} — merging, the lock, hooks, dispatches and secrets are never the AI's")


def outside_tmp(path):
    return not (path.startswith("/tmp/") or path in ("/dev/null", "/dev/stderr", "/dev/stdout") or path.startswith("&"))


def judge_argv(argv, redirs, reviewer, depth):
    seen = set()
    argv = strip_wrappers(list(argv), seen)
    if not argv:
        return
    w = argv[0].rsplit("/", 1)[-1]
    if reviewer:
        bad = [r for r in redirs if outside_tmp(r) and not re.match(r"^(\d|-)$", r)]
        if bad:
            raise Refuse(f"a write to {bad[0]} — the reviewer writes nowhere but /tmp and its record")
        if w == "tee" and any(outside_tmp(a) for a in argv[1:] if not a.startswith("-")):
            raise Refuse("tee outside /tmp — the reviewer writes nowhere but /tmp and its record")
    if w in SHELLS:
        if "-c" in argv:
            k = argv.index("-c")
            if k + 1 < len(argv):
                judge_text(argv[k + 1], reviewer, depth + 1)
        return
    if w == "eval":
        judge_text(" ".join(argv[1:]), reviewer, depth + 1)
        return
    if w == "git":
        judge_git(argv[1:], reviewer)
    elif w == "gh":
        judge_gh(argv[1:])
    elif w in ("curl", "wget", "http", "https"):
        judge_curl(argv[1:])
    elif w == "rm":
        short = "".join(a[1:] for a in argv[1:] if a.startswith("-") and not a.startswith("--"))
        longs = [a for a in argv[1:] if a.startswith("--")]
        recursive = "r" in short or "R" in short or "--recursive" in longs
        force = "f" in short or "--force" in longs
        if recursive and force and "xargs" in seen:
            raise Refuse("xargs rm -rf — a forced recursive delete of targets read from a pipe")
        if recursive and force:
            for t in (a for a in argv[1:] if not a.startswith("-")):
                tn = t.replace("\\", "/").rstrip("/")
                last = tn.rsplit("/", 1)[-1]
                safe = ".." not in tn and (tn.startswith("verify/") or "/verify/" in tn or tn.startswith("/tmp/")
                                            or "/temp/" in tn.lower() + "/" or last in CACHES)
                if not safe:
                    raise Refuse(f"rm -rf {t} — a forced recursive delete outside verify/, a temp folder or a cache "
                                 f"(the prune door: rm -r verify/<path>)")
    elif w == "flutter" and len(argv) > 1 and argv[1] == "clean":
        raise Refuse("flutter clean — founder-run only")
    elif w == "firebase" and "deploy" in argv[1:]:
        raise Refuse("firebase deploy — prod actions are founder-run only")


def judge_text(text, reviewer=False, depth=0):
    if depth > 6:
        raise Refuse("commands nested too deep to read")
    for sub in substitutions(text):
        judge_text(sub, reviewer, depth + 1)
    cmd, bodies = cut_heredocs(text)
    try:
        argvs = split_argvs(cmd)
    except ValueError:
        for pat, what in FALLBACK:
            if pat.search(text):
                raise Refuse(f"{what} (read by the fallback pattern — the text did not parse)")
        return
    for argv, redirs in argvs:
        judge_argv(argv, redirs, reviewer, depth)
    for owner, body in bodies:
        try:
            owner_argv = strip_wrappers(split_argvs(owner)[-1][0]) if owner.strip() else []
        except (ValueError, IndexError):
            owner_argv = []
        if owner_argv and owner_argv[0].rsplit("/", 1)[-1] in SHELLS and "-c" not in owner_argv:
            judge_text(body, reviewer, depth + 1)


def main(argv):
    client = "codex" if "--client" in argv and argv[argv.index("--client") + 1:argv.index("--client") + 2] == ["codex"] else "claude"
    reviewer = "--reviewer" in argv
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        cmd = payload.get("tool_input", {}).get("command", "")
        if isinstance(cmd, list):
            cmd = " ".join(shlex.quote(str(c)) for c in cmd)
        cmd = str(cmd or "")
        reason = None
        judge_text(cmd, reviewer)
    except Refuse as r:
        reason = str(r)
    except Exception as e:  # an unreadable payload is never a pass
        reason = f"the payload could not be read ({type(e).__name__})"
    if reason is None:
        return 0
    msg = f"BLOCKED by THE SMALL GUARD (tool/road/guard.py): {reason}. Nothing ran."
    if client == "codex":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": msg}}))
        return 0
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main(sys.argv[1:]))
