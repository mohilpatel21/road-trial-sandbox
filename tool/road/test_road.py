#!/usr/bin/env python3
"""tool/road/test_road.py — THE ROAD's own fixtures (B2-ROAD-A, 2026-09-30): the gate's `road` job runs it on every pull request and
every push to main, in seconds, without Flutter. Each fixture prints one line; any failure exits 1.

  python3 tool/road/test_road.py            (from the repository root)
Groups: guard_* (the small guard — commands, never prose; THE TRIAL's two false refusals and this relay's own), changes_* (which jobs a
change needs), law_* (the pull-request check's rules), review_* (the fingerprint's four cases, THE TRIAL's G11, in a scratch git
repository), readers_* (every path the tests read is covered by roadlib.APP or roadlib.READERS), light_* (the body's sections).
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import changes  # noqa: E402
import guard  # noqa: E402
import law  # noqa: E402
import light  # noqa: E402
import roadlib  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def verdict(cmd, reviewer=False):
    try:
        guard.judge_text(cmd, reviewer)
        return "PASS"
    except guard.Refuse as r:
        return "BLOCK: " + str(r)


GUARD = [
    # (name, command, reviewer, expect PASS or BLOCK)
    ("guard_plain_push", "git push origin feature/road", False, "PASS"),
    ("guard_push_head_main", "git push origin HEAD:main", False, "PASS"),
    ("guard_force_long", "git push --force origin main", False, "BLOCK"),
    ("guard_force_after", "git push origin main --force", False, "BLOCK"),
    ("guard_force_short", "git push -f origin x", False, "BLOCK"),
    ("guard_force_cluster", "git push -uf origin x", False, "BLOCK"),
    ("guard_force_lease", "git push --force-with-lease=main:abc origin main", False, "BLOCK"),
    ("guard_plus_refspec", "git push origin +HEAD:main", False, "BLOCK"),
    ("guard_delete_refspec", "git push origin :feature", False, "BLOCK"),
    ("guard_git_C_force", "git -C /work/repo push --force", False, "BLOCK"),
    ("guard_reset_hard", "git reset --hard HEAD~1", False, "BLOCK"),
    ("guard_reset_soft", "git reset --soft HEAD~1", False, "PASS"),
    ("guard_clean", "git clean -fdx", False, "BLOCK"),
    ("guard_chain_hidden", "git status && git clean -fd", False, "BLOCK"),
    ("guard_subshell", "echo $(git reset --hard)", False, "BLOCK"),
    ("guard_backtick", "echo `git clean -fd`", False, "BLOCK"),
    ("guard_bash_c", "bash -c 'git push --force origin main'", False, "BLOCK"),
    ("guard_heredoc_shell", "bash <<'EOF'\ngit clean -fd\nEOF", False, "BLOCK"),
    ("guard_heredoc_data", "cat > notes.txt <<'EOF'\nnever run git clean or git push --force\nEOF", False, "PASS"),
    ("guard_python_heredoc_prose", "python3 - <<'PY'\ns = 'rm -rf / and git reset --hard are refused'\nprint(s)\nPY", False, "PASS"),
    ("guard_commit_message_prose", "git commit -m \"the guard refuses git clean and gh pr merge\"", False, "PASS"),
    ("guard_echo_prose", "echo \"git push --force is refused\"", False, "PASS"),
    ("guard_grep_prose", "grep -n \"rm -rf\" tool/road/guard.py", False, "PASS"),
    ("guard_comment", "ls  # git clean -fdx would be refused", False, "PASS"),
    ("guard_trial_body", "gh pr create --draft --title x --body \"example: rm -rf / (a string, not a command)\"", False, "PASS"),
    ("guard_unbalanced_prose", "echo \"it's", False, "PASS"),
    ("guard_unbalanced_danger", "echo \"x && git clean -fd", False, "BLOCK"),
    ("guard_rm_r_verify", "rm -r verify/b2-road-a/scratch", False, "PASS"),
    ("guard_rm_rf_verify", "rm -rf verify/b2-road-a/scratch", False, "PASS"),
    ("guard_rm_rf_tmp", "rm -rf /tmp/review_x", False, "PASS"),
    ("guard_rm_rf_cache", "rm -rf tool/road/__pycache__", False, "PASS"),
    ("guard_rm_rf_lib", "rm -rf lib", False, "BLOCK"),
    ("guard_rm_rf_root", "rm -rf /", False, "BLOCK"),
    ("guard_rm_rf_climb", "rm -rf verify/../lib", False, "BLOCK"),
    ("guard_rm_preserve_root", "rm --preserve-root -f notes.txt", False, "PASS"),
    ("guard_xargs_rm", "ls | xargs rm -rf", False, "BLOCK"),
    ("guard_xargs_rm_named", "find . -name x | xargs rm -rf build", False, "BLOCK"),
    ("guard_pr_merge", "gh pr merge 12 --squash", False, "BLOCK"),
    ("guard_pr_view", "gh pr view 12 --json state", False, "PASS"),
    ("guard_api_merge", "gh api -X PUT repos/o/r/pulls/12/merge", False, "BLOCK"),
    ("guard_api_ruleset_post", "gh api repos/o/r/rulesets -f name=x", False, "BLOCK"),
    ("guard_api_ruleset_get", "gh api repos/o/r/rulesets", False, "PASS"),
    ("guard_api_runs", "gh api repos/o/r/actions/runs?head_sha=abc", False, "PASS"),
    ("guard_api_hooks", "gh api --method POST repos/o/r/hooks --input hook.json", False, "BLOCK"),
    ("guard_gql_merge", "gh api graphql -f query='mutation { mergePullRequest(input:{pullRequestId:\"x\"}) { clientMutationId } }'", False, "BLOCK"),
    ("guard_gql_read", "gh api graphql -f query='query { viewer { login } }'", False, "PASS"),
    # B2-ROAD-A's plan pass (its readings): gh's -R before the action, -XPUT attached, a recursive rm unforced
    ("guard_pr_merge_repo", "gh pr -R o/r merge 12", False, "BLOCK"),
    ("guard_pr_merge_repo_long", "gh pr --repo o/r merge 12 --squash", False, "BLOCK"),
    ("guard_pr_list_search", "gh pr list --search merge", False, "PASS"),
    ("guard_api_merge_attached", "gh api -XPUT repos/o/r/pulls/12/merge", False, "BLOCK"),
    ("guard_workflow_repo_regen_main", "gh workflow -R o/r run regen-ci-goldens.yml -f branch=main", False, "BLOCK"),
    ("guard_rm_r_lib", "rm -r lib/ui", False, "BLOCK"),
    ("guard_rm_r_tmp", "rm -r /tmp/review_x", False, "PASS"),
    ("guard_xargs_rm_r", "ls | xargs rm -r", False, "BLOCK"),
    ("guard_curl_merge", "curl -X PUT -H 'Authorization: token t' https://api.github.com/repos/o/r/pulls/1/merge", False, "BLOCK"),
    ("guard_curl_read", "curl -s https://api.github.com/repos/o/r/pulls/1", False, "PASS"),
    ("guard_regen_branch", "gh workflow run regen-ci-goldens.yml -f branch=b2-r53-lock", False, "PASS"),
    ("guard_regen_main", "gh workflow run regen-ci-goldens.yml -f branch=main", False, "BLOCK"),
    ("guard_ci_dispatch", "gh workflow run ci.yml -f walks=all", False, "PASS"),
    ("guard_ios_dispatch", "gh workflow run ios.yml", False, "BLOCK"),
    ("guard_secret", "gh secret set KEY < key.txt", False, "BLOCK"),
    ("guard_auth_status", "gh auth status", False, "PASS"),
    ("guard_auth_token", "gh auth token", False, "BLOCK"),
    ("guard_repo_edit", "gh repo edit --visibility public", False, "BLOCK"),
    ("guard_flutter_clean", "flutter clean", False, "BLOCK"),
    ("guard_flutter_test", "CI=true flutter test test/gates", False, "PASS"),
    ("guard_firebase_deploy", "firebase deploy --only firestore:rules", False, "BLOCK"),
    ("guard_env_wrapper", "env GIT_TRACE=1 git push --force", False, "BLOCK"),
    ("guard_timeout_wrapper", "timeout 30 git clean -n", False, "BLOCK"),
    ("guard_redirect_ok", "git log --oneline > /tmp/log.txt 2>&1", False, "PASS"),
    ("guard_reviewer_reads", "git diff --stat abc def && git log -3", True, "PASS"),
    ("guard_reviewer_worktree", "git worktree add /tmp/review_b2 HEAD", True, "PASS"),
    ("guard_reviewer_record", "python3 tool/road/review.py record --verdict GREEN --pass full --model claude-opus-5-5", True, "PASS"),
    ("guard_reviewer_commit", "git commit -m x", True, "BLOCK"),
    ("guard_reviewer_redirect", "echo x > lib/a.dart", True, "BLOCK"),
    ("guard_reviewer_redirect_tmp", "flutter analyze > /tmp/analyze.txt 2>&1", True, "PASS"),
    ("guard_reviewer_input", "wc -l < lib/main.dart", True, "PASS"),
    ("guard_reviewer_tee", "flutter test | tee test_out.txt", True, "BLOCK"),
    # B2-ROAD-A's plan pass (its finding 1): the reviewer's git in its listing forms only; its worktree under /tmp
    ("guard_reviewer_branch_create", "git branch review-scratch", True, "BLOCK"),
    ("guard_reviewer_branch_list", "git branch -a --contains abc123", True, "PASS"),
    ("guard_reviewer_tag_create", "git tag v9", True, "BLOCK"),
    ("guard_reviewer_tag_list", "git tag -l 'v*'", True, "PASS"),
    ("guard_reviewer_remote_add", "git remote add up https://example.invalid/r.git", True, "BLOCK"),
    ("guard_reviewer_remote_v", "git remote -v", True, "PASS"),
    ("guard_reviewer_reflog_expire", "git reflog expire --expire=now --all", True, "BLOCK"),
    ("guard_reviewer_worktree_remove_repo", "git worktree remove D:/development/becoming", True, "BLOCK"),
    ("guard_reviewer_worktree_remove_tmp", "git worktree remove --force /tmp/review_b2", True, "PASS"),
    ("guard_reviewer_worktree_branch", "git worktree add -b scratch /tmp/review_b2 HEAD", True, "BLOCK"),
    ("guard_reviewer_fetch", "git fetch origin", True, "PASS"),
]


def test_guard():
    for name, cmd, reviewer, want in GUARD:
        got = verdict(cmd, reviewer)
        check(name, got.startswith(want), f"{cmd!r} → {got}")
    # the hook's payload forms, through guard.py's own entry (B2-ROAD-A's plan pass, a reading: the old fixture asserted none of them):
    # Claude's string and a list command judged; an unreadable payload refused; Codex answered with the JSON deny and exit 0
    gp = os.path.join(HERE, "guard.py")
    def hook(payload, *extra):
        r = subprocess.run([sys.executable, "-B", gp, *extra], input=payload.encode("utf-8"), capture_output=True)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    rc, _, err = hook(json.dumps({"tool_input": {"command": "gh pr merge 5 --squash"}}))
    check("guard_payload_string_blocked", rc == 2 and "BLOCKED by THE SMALL GUARD" in err, f"rc {rc} · {err[:80]}")
    rc, _, err = hook(json.dumps({"tool_input": {"command": ["git", "push", "--force", "origin", "main"]}}))
    check("guard_payload_list_blocked", rc == 2 and "BLOCKED" in err, f"rc {rc} · {err[:80]}")
    rc, _, err = hook(json.dumps({"tool_input": {"command": "git status"}}))
    check("guard_payload_string_passes", rc == 0 and not err, f"rc {rc} · {err[:80]}")
    rc, _, err = hook("not json at all")
    check("guard_payload_unreadable_refused", rc == 2 and "could not be read" in err, f"rc {rc} · {err[:80]}")
    rc, out, _ = hook(json.dumps({"tool_input": {"command": "gh pr merge 5"}}), "--client", "codex")
    check("guard_payload_codex_deny", rc == 0 and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny", f"rc {rc} · {out[:80]}")


def test_changes():
    recipes = [{"driver": "walk_editlab_d1.js", "mocks": ["mocks/EDITLAB_D1_v4_LOCK.html"]}]
    c = changes.classify(changes.parse(["M\tdesign/NEXT.md", "M\tdesign/FIELD_NOTES.md"]), recipes)
    check("changes_records_only", c["records_only"] and c["suite"] == "none" and not c["walk"], str(c))
    c = changes.classify(changes.parse(["M\tspecs/system_testing.md"]), recipes)
    check("changes_spec_runs_the_suite", c["suite"] == "full", str(c))
    c = changes.classify(changes.parse(["M\tdesign/DONE_LEDGER.md"]), recipes)
    check("changes_ledger_runs_its_readers", c["suite"] == "readers" and c["tests"] == ["test/tools/system_reliability_1_test.dart"], str(c))
    c = changes.classify(changes.parse(["M\t.github/workflows/ci.yml"]), recipes)
    check("changes_the_net_proves_itself", c["suite"] == "full", str(c))
    c = changes.classify(changes.parse(["M\tmocks/EDITLAB_D1_v4_LOCK.html"]), recipes)
    check("changes_mock_runs_its_walk", c["walk"] and c["drivers"] == ["walk_editlab_d1.js"], str(c))
    c = changes.classify(changes.parse(["A\ttool/mock_walks/walk_themelab.js", "A\tmocks/THEMELAB_LOCK.html"]), recipes)
    check("changes_new_driver_walks", c["drivers"] == ["walk_themelab.js"], str(c))
    c = changes.classify(changes.parse(["D\tmocks/EDITLAB_D1_v4_LOCK.html"]), recipes)
    check("changes_removal_never_walks", not c["walk"], str(c))
    c = changes.classify(changes.parse(["M\tdesign/B2_SOME_STUDY.md"]), recipes)
    check("changes_study_no_suite", c["suite"] == "none" and not c["records_only"], str(c))
    c = changes.classify([], recipes, all_walks=True)
    check("changes_all_walks", c["drivers"] == ["walk_editlab_d1.js"], str(c))


def f(name, status="modified", patch=""):
    return {"filename": name, "status": status, "patch": patch}


def red(rules, which):
    return [r for r, ok, _ in rules if not ok] == which


def test_law():
    good = "## What changed\nx\n## Decided for you\ny\n## FOR MOHIL\nz\n## Models\ndriver: a · reviewer: b\n"
    r = law.judge([f("lib/a.dart")], good, False, [], {})
    check("law_green_code", red(r, []), str(r))
    r = law.judge([f("lib/a.dart")], "## What changed\nx", False, [], {})
    check("law_body_missing", red(r, ["L1"]), str(r))
    r = law.judge([f("lib/a.dart")], "", True, [], {})
    check("law_draft_body_waits", red(r, []), str(r))
    r = law.judge([f(".github/workflows/ci.yml")], good, False, [], {})
    check("law_read_first_needed", red(r, ["L2"]), str(r))
    r = law.judge([f(".github/workflows/ci.yml")], "READ FIRST — the checks change.\n" + good, False, [], {})
    check("law_read_first_given", red(r, []), str(r))
    r = law.judge([f("test/a_test.dart", "removed")], good, False, [], {})
    check("law_test_removed_unnamed", red(r, ["L3"]), str(r))
    r = law.judge([f("test/a_test.dart", "removed")], "READ FIRST — a_test.dart retires: its spec clause moved.\n" + good, False, [], {})
    check("law_test_removed_named", red(r, []), str(r))
    r = law.judge([f("test/b_test.dart", patch="@@\n+  test('x', () {}, skip: 'waits for B4');")], good, False, [], {})
    check("law_skip_unnamed", red(r, ["L3"]), str(r))
    r = law.judge([f("test/c_test.dart", patch="@@\n-  test('x', () {});\n-  test('y', () {});\n+  test('z', () {});")], good, False, [], {})
    check("law_case_removed", red(r, ["L3"]), str(r))
    r = law.judge([f("design/S31_LINT_BASELINE.txt", patch="@@\n+specs/x.md · L1 · abc")], good, False, [], {})
    check("law_baseline_grows", red(r, ["L4"]), str(r))
    r = law.judge([f("design/S31_LINT_BASELINE.txt", patch="@@\n-specs/x.md · L1 · abc")], good, False, [], {})
    check("law_baseline_shrinks", red(r, []), str(r))
    r = law.judge([f("test/ui/goldens/ci/a.png")], good, False, [("Claude", ["test/ui/goldens/ci/a.png"])], {})
    check("law_goldens_by_hand", red(r, ["L5"]), str(r))
    r = law.judge([f("test/ui/goldens/ci/a.png")], good, False, [("regen-ci-goldens", ["test/ui/goldens/ci/a.png"])], {})
    check("law_goldens_by_regen", red(r, []), str(r))
    r = law.judge([f("specs/a.md"), f("lib/a.dart")], good, False, [], {})
    check("law_specs_beside_lib", red(r, ["L6"]), str(r))
    r = law.judge([f("AGENTS.md")], "READ FIRST — the rulebook.\n" + good, False, [], {"AGENTS.md": (9000, 120)})
    check("law_size_cap", red(r, ["L7"]), str(r))
    r = law.judge([f(".github/workflows/x.yml", patch="@@\n+on:\n+  issue_comment:")], "READ FIRST\n" + good, False, [], {})
    check("law_comment_trigger", red(r, ["L8"]), str(r))
    r = law.judge([f("build/seals/x.json", "added")], good, False, [], {})
    check("law_old_seal_written", red(r, ["L9"]), str(r))
    r = law.judge([f("build/staging/b2-x/a.md", "removed")], good, False, [], {})
    check("law_old_staging_removed", red(r, []), str(r))


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def test_review():
    import review
    with tempfile.TemporaryDirectory() as d:
        git(d, "init", "-q", "-b", "main")
        git(d, "config", "user.email", "t@example.invalid"); git(d, "config", "user.name", "t")
        git(d, "config", "core.autocrlf", "false")
        pathlib.Path(d, "lib").mkdir(); pathlib.Path(d, "design").mkdir()
        pathlib.Path(d, "lib/a.dart").write_text("a\n"); pathlib.Path(d, "design/NEXT.md").write_text("n\n")
        git(d, "add", "-A"); git(d, "commit", "-qm", "base")
        git(d, "checkout", "-qb", "relay")
        pathlib.Path(d, "lib/a.dart").write_text("a2\n"); git(d, "commit", "-qam", "change")
        cwd = os.getcwd()
        os.chdir(d)
        try:
            _, _, fp1 = review.fingerprint("main")
            pathlib.Path(d, "design/NEXT.md").write_text("n2\n"); git(d, "commit", "-qam", "records")
            _, _, fp2 = review.fingerprint("main")
            check("review_records_keep", fp1 == fp2)
            git(d, "checkout", "-q", "main"); pathlib.Path(d, "lib/b.dart").write_text("b\n"); git(d, "add", "-A"); git(d, "commit", "-qm", "main moves")
            git(d, "checkout", "-q", "relay"); git(d, "merge", "-q", "--no-edit", "main")
            _, _, fp3 = review.fingerprint("main")
            check("review_up_to_date_keeps", fp1 == fp3)
            pathlib.Path(d, "lib/a.dart").write_text("a3\n"); git(d, "commit", "-qam", "code after review")
            _, _, fp4 = review.fingerprint("main")
            check("review_code_voids", fp4 != fp1)
            rc = review.main(["record", "--verdict", "GREEN", "--pass", "full", "--model", "m", "--base", "main"])
            pathlib.Path(d, "review/WORDS.md").write_text("words\nVERDICT: GREEN\n")
            git(d, "add", "-A"); git(d, "commit", "-qm", "the review")
            check("review_check_green", rc == 0 and review.main(["check", "--base", "main"]) == 0)
            pathlib.Path(d, "lib/a.dart").write_text("a4\n"); git(d, "commit", "-qam", "late code")
            check("review_check_voided", review.main(["check", "--base", "main"]) == 1)
        finally:
            os.chdir(cwd)


def test_readers():
    root = pathlib.Path("test")
    if not root.is_dir():
        print("skip readers_census — no test/ here")
        return
    lit = re.compile(r"""['"]((?:design|build|mocks|\.claude|\.codex|integration_test|tool|scripts|archive|specs|assets|android|ios)/[^'"$\s]*)['"]""")
    # written inside a test's own temporary fixture (test/tools/system_reliability_1_fixture.dart's temp root), never read from the tree
    fixture_only = {"build/NOTES_FOR_MOHIL.md", "design/KICKOFF.md"}
    uncovered = set()
    for p in root.rglob("*.dart"):
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lstrip().startswith("//"):
                continue
            for m in lit.finditer(line):
                path = m.group(1)
                if path in fixture_only:
                    continue
                if not (roadlib.under(path, roadlib.APP) or any(path == k or path.startswith(k) or k.startswith(path)
                                                               for k in roadlib.READERS)):
                    uncovered.add(f"{path} ({p.as_posix()})")
    check("readers_census", not uncovered, "; ".join(sorted(uncovered)[:8]))


def test_light():
    body = "READ FIRST — the checks change.\n\n## What changed\nThe gate.\n## Decided for you\n- one\n## FOR MOHIL\nall good\n## Models\ndriver: x · reviewer: y\n"
    secs, rf = light.sections(body)
    check("light_sections", secs.get("what changed") == "The gate." and rf.startswith("READ FIRST"), str(secs))
    check("light_waiting", light.waiting_count("# NEXT\n## Waiting\n- a\n- b\n## Health\n- x\n") == 2)
    check("light_waiting_none", light.waiting_count("## Waiting\n- (none)\n") == 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    for t in (test_guard, test_changes, test_law, test_review, test_readers, test_light):
        t()
    print(f"road self-test: {len(FAILS)} failure(s)" + (": " + ", ".join(FAILS) if FAILS else " — all green"))
    sys.exit(1 if FAILS else 0)
