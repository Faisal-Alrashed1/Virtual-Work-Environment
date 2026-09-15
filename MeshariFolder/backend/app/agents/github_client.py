"""
Minimal, unauthenticated GitHub REST client — just enough context for the
Mentor agent to review real submitted work. Stage 1 only accepts public
repo links (see Project-Summary.md's "Code submission: GitHub link (public
repos)"), so no token is needed. The public API is rate-limited to 60
unauthenticated requests/hour per IP, which is fine at bootcamp scale; if
that ever becomes a problem, pass a token via a new GITHUB_TOKEN setting
and add it as a Bearer header below — nothing else here would need to change.
"""
import base64
import re

import httpx

_LINK_RE = re.compile(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


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

    with httpx.Client(
        timeout=10.0, headers={"Accept": "application/vnd.github+json"}
    ) as client:
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
