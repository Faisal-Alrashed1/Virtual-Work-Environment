"""
Minimal GitHub REST client — just enough context for the agents to review
real submitted work. Works with no token for public repos, but the
unauthenticated API allows only 60 requests/hour per IP, and one review
with a GitHub link uses several (Mentor + Security/Data Reviewers) — a
handful of submissions an hour used it up in testing. Set GITHUB_TOKEN in
backend/.env (a personal access token; read-only public access is enough)
to raise that to 5,000/hour, and to let the agents read private repos the
token can see.
"""
import base64
import re

import httpx

from app.config import settings

_LINK_RE = re.compile(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


def _client() -> httpx.Client:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return httpx.Client(timeout=10.0, headers=headers)


def parse_owner_repo(github_link: str) -> tuple[str, str]:
    match = _LINK_RE.search(github_link.strip())
    if not match:
        raise ValueError(f"Could not parse a GitHub owner/repo from: {github_link}")
    return match.group(1), match.group(2)


def fetch_repo_context(github_link: str, max_files: int = 25) -> str:
    """
    Returns a short plain-text summary of the repo — description, top-level
    file tree, and README — enough for the Mentor to write a grounded review
    without cloning the whole thing.
    """
    owner, repo = parse_owner_repo(github_link)
    parts = [f"Repo: {owner}/{repo}"]

    with _client() as client:
        meta = client.get(f"https://api.github.com/repos/{owner}/{repo}")
        if meta.status_code != 200:
            parts.append(
                f"(Could not fetch repo metadata — status {meta.status_code}. "
                "Review based on the task and link alone.)"
            )
            return "\n".join(parts)

        data = meta.json()
        if data.get("description"):
            parts.append(f"Description: {data['description']}")
        default_branch = data.get("default_branch", "main")
        parts.append(f"Default branch: {default_branch}")

        tree = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}",
            params={"recursive": "1"},
        )
        if tree.status_code == 200:
            paths = [
                item["path"]
                for item in tree.json().get("tree", [])
                if item["type"] == "blob"
            ]
            parts.append(f"Files ({len(paths)} total, showing up to {max_files}):")
            parts.extend(f"  - {p}" for p in paths[:max_files])

        readme = client.get(f"https://api.github.com/repos/{owner}/{repo}/readme")
        if readme.status_code == 200:
            content = base64.b64decode(readme.json()["content"]).decode(
                "utf-8", errors="ignore"
            )
            parts.append(f"README (truncated):\n{content[:2000]}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Added for the Security Reviewer / Data Reviewer specialists (they need
# real file content, not just names, to ground a structured finding in
# what's actually in the repo). Deliberately separate from
# fetch_repo_context above rather than refactored into it — that function
# is already relied on by the Mentor's review and every existing smoke
# test; these are new, additive entry points so nothing about its
# behavior changes for the callers that already use it.
# ---------------------------------------------------------------------------

def list_repo_paths(owner: str, repo: str) -> list[str] | None:
    """Every blob (file) path in the repo's default branch — lets a
    specialist search for files of interest (e.g. '*.ipynb', a committed
    '.env') without knowing exact names ahead of time. None (not []) if
    the repo/tree couldn't be fetched — a private repo, a typo, or
    GitHub's unauthenticated rate limit (60/hour) — so callers can tell
    "GitHub didn't answer" apart from "the repo has no such files"."""
    with _client() as client:
        meta = client.get(f"https://api.github.com/repos/{owner}/{repo}")
        if meta.status_code != 200:
            return None
        default_branch = meta.json().get("default_branch", "main")

        tree = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}",
            params={"recursive": "1"},
        )
        if tree.status_code != 200:
            return None
        return [
            item["path"]
            for item in tree.json().get("tree", [])
            if item["type"] == "blob"
        ]


def fetch_file_content(owner: str, repo: str, path: str) -> str | None:
    """Raw text content of one file at the repo's default branch via the
    Contents API, or None if it doesn't exist / isn't fetchable as text
    (e.g. a binary file, or the request itself failing) — always
    best-effort, never raises, since a candidate filename not existing is
    the expected common case, not an error."""
    with _client() as client:
        resp = client.get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("encoding") != "base64" or "content" not in data:
            return None
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except (ValueError, TypeError):
            return None
