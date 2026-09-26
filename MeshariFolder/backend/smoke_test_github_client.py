"""
Smoke test for the Mentor's evidence source: agents/github_client.py.

Every review depends on this function and nothing tested it. It matters more than it
looks: the Mentor sees a repository ONLY through it (the description, the first 25 file
paths and the first 2,000 characters of the README - not the code), it costs three
GitHub requests per review against an anonymous limit of 60/hour/IP, and when GitHub
refuses, the Mentor must be told why so it doesn't blame the graduate.

GitHub is faked; nothing here touches the network.

Run: python smoke_test_github_client.py
"""
import base64
import os
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used")

from app.agents import github_client  # noqa: E402
from app.agents.github_client import fetch_repo_context, parse_owner_repo  # noqa: E402


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


# ---- parsing ------------------------------------------------------------------------
check("parses a normal link", parse_owner_repo("https://github.com/psf/requests") == ("psf", "requests"))
check("...with a trailing slash", parse_owner_repo("https://github.com/psf/requests/") == ("psf", "requests"))
check("...with .git", parse_owner_repo("https://github.com/psf/requests.git") == ("psf", "requests"))
check("...with surrounding whitespace", parse_owner_repo("  https://github.com/psf/requests \n") == ("psf", "requests"))
try:
    parse_owner_repo("https://example.com/nothing")
    raised = False
except ValueError:
    raised = True
check("a non-GitHub link is rejected with ValueError", raised)


# ---- a fake GitHub -------------------------------------------------------------------
class Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeClient:
    """Stands in for httpx.Client; records how it was constructed and every URL asked for."""

    routes: dict = {}
    made: list = []

    def __init__(self, timeout=None, headers=None):
        self.headers, self.urls = headers or {}, []
        FakeClient.made.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        self.urls.append(url)
        for suffix, resp in FakeClient.routes.items():
            if url.endswith(suffix):
                return resp
        return Resp(404, {})


def readme(text, raw=None):
    return Resp(200, {"content": base64.b64encode(raw if raw is not None else text.encode()).decode()})


def files(n, dirs=0):
    return Resp(200, {"tree": [{"type": "blob", "path": f"src/file{i}.py"} for i in range(n)] + [{"type": "tree", "path": f"dir{i}"} for i in range(dirs)]})


def fetch(routes, token="", link="https://github.com/acme/roomsync"):
    FakeClient.routes, FakeClient.made = routes, []
    with patch("app.agents.github_client.httpx.Client", FakeClient), patch.object(github_client.settings, "github_token", token):
        text = fetch_repo_context(link)
    return text, FakeClient.made[0]


REPO = Resp(200, {"description": "Team booking API", "default_branch": "main"})
OK_ROUTES = {"/repos/acme/roomsync": REPO, "/git/trees/main": files(3), "/readme": readme("# RoomSync\nRun it with make run.")}

# ---- what the Mentor is shown ------------------------------------------------------------
text, client = fetch(OK_ROUTES)
check("the Mentor is shown the repo name and description", "Repo: acme/roomsync" in text and "Description: Team booking API" in text)
check("...the default branch", "Default branch: main" in text)
check("...the file list", "src/file0.py" in text and "Files (3 total, showing up to 25):" in text)
check("...and the README", "README (truncated):" in text and "Run it with make run." in text)
check("a review costs exactly THREE GitHub requests (repo, tree, README) - the quota maths depends on it", len(client.urls) == 3)

text, _ = fetch({**OK_ROUTES, "/git/trees/main": files(40, dirs=5)})
shown = [line for line in text.splitlines() if line.startswith("  - ")]
check("only the first 25 files are listed of 40", len(shown) == 25 and "(40 total, showing up to 25)" in text)
check("directories are not counted as files", "40 total" in text)
text, _ = fetch({**OK_ROUTES, "/readme": readme("x" * 5000)})
check("a long README is cut to 2,000 characters", text.count("x") == 2000)
text, _ = fetch({**OK_ROUTES, "/readme": readme("", raw=b"caf\xe9 \xff\xfe ok")})
check("a README that isn't valid UTF-8 doesn't crash the review", "README (truncated):" in text and "ok" in text)

# ---- authentication -----------------------------------------------------------------------
_, client = fetch(OK_ROUTES, token="")
check("no GITHUB_TOKEN: no Authorization header is sent", "Authorization" not in client.headers)
text, client = fetch(OK_ROUTES, token="ghp_secret123")
check("with GITHUB_TOKEN: it is sent as a Bearer header", client.headers.get("Authorization") == "Bearer ghp_secret123")
check("...and the token never leaks into what the Mentor sees", "ghp_secret123" not in text)
check("...the API media type is still requested", client.headers.get("Accept") == "application/vnd.github+json")

# ---- when GitHub says no ---------------------------------------------------------------------
text, client = fetch({"/repos/acme/roomsync": Resp(403, {"message": "API rate limit exceeded for 1.2.3.4."}, {"X-RateLimit-Remaining": "0"})})
check("rate-limited (403 + remaining 0): the Mentor is told it is GitHub's limit", "request limit was reached" in text and "not the graduate's fault" in text)
check("...and how to fix it", "GITHUB_TOKEN" in text)
check("...it stops after one request (doesn't burn more quota)", len(client.urls) == 1)
text, _ = fetch({"/repos/acme/roomsync": Resp(429, {"message": "Too Many Requests"}, {"X-RateLimit-Remaining": "0"})})
check("429 is recognised as rate limiting too", "request limit was reached" in text)
text, _ = fetch({"/repos/acme/roomsync": Resp(403, {"message": "Secondary rate limit hit"}, {})})
check("...and a 403 whose message says 'rate limit' even without the header", "request limit was reached" in text)
text, _ = fetch({"/repos/acme/roomsync": Resp(403, {"message": "Repository access blocked"}, {})})
check("a 403 that is NOT rate limiting is reported as a plain fetch failure", "Could not fetch repo metadata — status 403" in text and "request limit" not in text)
text, _ = fetch({"/repos/acme/roomsync": Resp(403, ValueError("not json"), {})})
check("a 403 with a non-JSON body doesn't crash", "Could not fetch repo metadata — status 403" in text)
text, _ = fetch({"/repos/acme/roomsync": Resp(404, {"message": "Not Found"})})
check("a missing/private repo is a plain failure with the status, and the review carries on", "status 404" in text and "task and link alone" in text)

# ---- partial failures never sink the review ------------------------------------------------------
text, _ = fetch({**OK_ROUTES, "/git/trees/main": Resp(500, {})})
check("the file tree failing still returns the README", "README (truncated):" in text and "Files (" not in text)
text, _ = fetch({"/repos/acme/roomsync": REPO, "/git/trees/main": files(2)})
check("a repo with no README still returns the file list", "Files (2 total" in text and "README" not in text)
text, _ = fetch({"/repos/acme/roomsync": Resp(200, {"default_branch": "develop"}), "/git/trees/develop": files(1), "/readme": readme("hi")})
check("a non-'main' default branch is followed, and a missing description is fine", "Default branch: develop" in text and "Description:" not in text and "src/file0.py" in text)

print("\nAll GitHub-client smoke checks passed.")
