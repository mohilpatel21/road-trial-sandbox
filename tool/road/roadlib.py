"""tool/road/roadlib.py — THE ROAD's shared rules (B2-ROAD-A · RELAY A · THE ROAD, 2026-09-30; built to
design/THE_CLOUD_DOOR_DECISION_MAP_2026-09-30.md — CD-4 · CD-5 · CD-19 and the driver's cross-check K-2 · K-9 · K-10).

One home for the path sets every road tool reads (changes.py · review.py · law.py · light.py), and a small GitHub API reader
for law.py and light.py (standard library only — no gh, no pip). Python 3.10+.
"""
import json
import os
import urllib.request

# K-9: the records a relay writes after its review — left out of the review's fingerprint, so a records commit or an
# up-to-date merge from main keeps the verdict, and any other commit voids it.
RECORDS = ("design/NEXT.md", "design/DONE_LEDGER.md", "design/FIELD_NOTES.md", "review/")

# CD-5: READ FIRST — a change to the rules, the reviewer's instructions, the checks or the lock.
READ_FIRST = (".github/", ".claude/", ".codex/", "AGENTS.md", "CLAUDE.md", "tool/road/", "tool/githooks/",
              "tool/spec_lint.dart", "scripts/coverage_check.sh", "analysis_options.yaml", "test/flutter_test_config.dart")

# CD-4: the app job runs the whole suite whenever app code or specs change — and whenever the net itself changes (it proves
# itself once). Every path the tests read at run time is here or in READERS (the census in test_road.py keeps it so).
APP = ("lib/", "test/", "specs/", "assets/", "android/", "ios/", "integration_test/", "pubspec.yaml", "pubspec.lock",
       "analysis_options.yaml", "scripts/", "tool/spec_lint.dart", "tool/sim/", "l10n.yaml", ".github/workflows/ci.yml", "tool/road/")

# THE READERS (the 25-hour red's lesson, CD-4): a record or a lock that a test reads — a change to it runs those tests, never the
# whole suite, so no record can leave main quietly red.
READERS = {
    "design/DONE_LEDGER.md": ["test/tools/system_reliability_1_test.dart"],
    "build/STATE.md": ["test/tools/system_reliability_1_test.dart"],
    ".codex/config.toml": ["test/tools/system_reliability_1_test.dart"],
    ".claude/hooks/": ["test/tools/system_reliability_1_test.dart"],
    "build/staging/b2-system-reliability-1/": ["test/tools/system_reliability_1_test.dart"],
    "design/PRE_LAUNCH_PREP_v1.md": ["test/guards/launcher_label_test.dart"],
    "mocks/CEREMONYLAB_v7_LOCK.html": ["test/guards/ceremony_mock_extraction_test.dart"],
}


def readers_for(paths):
    """The test files that read any of the changed paths (sorted, unique)."""
    out = set()
    for p in paths:
        for key, tests in READERS.items():
            if p == key or (key.endswith("/") and p.startswith(key)):
                out.update(tests)
    return sorted(out)

# The walk job (lock relays): a mock or a walk driver changed.
WALK = ("mocks/", "tool/mock_walks/")

# CD-19 · THE SIZE CAPS (bytes and lines; «≤ 8 KB» read in the map's own decimal KB — its «27 KB» is 26,848 B) — the rulebook under 200 lines.
CAPS = {"AGENTS.md": (8000, 199), "CLAUDE.md": (3000, 60)}

FOUNDER = os.environ.get("ROAD_FOUNDER", "mohilpatel21")


def under(path: str, prefixes) -> bool:
    """True when path is one of the named files or lies under one of the named folders (a prefix ending in '/')."""
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in prefixes)


def is_record(path: str) -> bool:
    return under(path, RECORDS)


def needs_read_first(path: str) -> bool:
    return under(path, READ_FIRST)


class GitHub:
    """A tiny REST reader/writer over urllib (the runner's GITHUB_TOKEN; pagination by the Link header)."""

    def __init__(self, repo: str, token: str, api: str = "https://api.github.com"):
        self.repo, self.token, self.api = repo, token, api.rstrip("/")

    def _req(self, method: str, url: str, data=None):
        if not url.startswith("http"):
            url = f"{self.api}/{url.lstrip('/')}"
        body = None if data is None else json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "becoming-road"})
        if body is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            link = r.headers.get("Link", "")
        return (json.loads(raw) if raw else None), link

    def get(self, url: str):
        return self._req("GET", url)[0]

    def pages(self, url: str):
        """Every item of a list endpoint, page by page."""
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}per_page=100"
        out = []
        while url:
            data, link = self._req("GET", url)
            out.extend(data or [])
            url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    url = part[part.index("<") + 1:part.index(">")]
        return out

    def post(self, url: str, data):
        return self._req("POST", url, data)[0]

    def delete(self, url: str, data=None):
        return self._req("DELETE", url, data)[0]

    def graphql(self, query: str, variables: dict):
        return self._req("POST", f"{self.api}/graphql", {"query": query, "variables": variables})[0]
