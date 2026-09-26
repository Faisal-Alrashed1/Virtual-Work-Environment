"""
Minimal GitHub REST client — just enough context for the Mentor agent to review
real submitted work. Stage 1 only accepts public repo links (see
Project-Summary.md's "Code submission: GitHub link (public repos)"), so no token
is REQUIRED.

But each review costs three requests (repo info, file tree, README), and the
anonymous API allows 60 per hour per IP — about 20 reviews an hour, shared by
everyone testing or demoing from one network. A full `e2e_real_llm.py --full-week`
run alone uses ~45. So set GITHUB_TOKEN in backend/.env (a token with no scopes
is enough for public repos) and it is sent as a Bearer header: 5,000 per hour.
When the limit IS hit the review carries on from the task and link alone, and the
Mentor is told why (so it doesn't blame the graduate for a repo it couldn't read).

What the Mentor is shown: the repo description, the first 25 file paths, and the
first 2,000 characters of the README — NOT the code. Anything a graduate wants
judged has to be visible there (docs/TASK_BANK.md).
"""
import base64
import re

import httpx

from app.config import settings

_LINK_RE = re.compile(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


def parse_owner_repo(github_link: str) -> tuple[str, str]:
    match = _LINK_RE.search(github_link.strip())
    if not match:
        raise ValueError(f"Could not parse a GitHub owner/repo from: {github_link}")
    return match.group(1), match.group(2)


def _is_rate_limited(response) -> bool:
    """GitHub answers a rate-limited request with 403 (or 429) and either
    X-RateLimit-Remaining: 0 or a message saying so."""
    if response.status_code not in (403, 429):
        return False
    if response.headers.get("X-RateLimit-Remaining") == "0":
        return True
    try:
        return "rate limit" in str(response.json().get("message", "")).lower()
    except Exception:  # noqa: BLE001 - body wasn't JSON
        return False


def fetch_repo_context(github_link: str, max_files: int = 25) -> str:
    """
    Returns a short plain-text summary of the repo — description, top-level
    file tree, and README — enough for the Mentor to write a grounded review
    without cloning the whole thing.
    """
    owner, repo = parse_owner_repo(github_link)
    parts = [f"Repo: {owner}/{repo}"]

    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    with httpx.Client(timeout=10.0, headers=headers) as client:
        meta = client.get(f"https://api.github.com/repos/{owner}/{repo}")
        if meta.status_code != 200:
            if _is_rate_limited(meta):
                parts.append(
                    f"(GitHub's request limit was reached — status {meta.status_code} — so the repository could "
                    "not be read. This is not the graduate's fault. Set GITHUB_TOKEN in backend/.env to raise "
                    "the limit. Review based on the task and link alone.)"
                )
            else:
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
