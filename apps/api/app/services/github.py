import re
import httpx


PATTERN = re.compile(r"^https://github\.com/([^/]+)/([^/#]+?)(?:\.git)?(?:/pull/(\d+))?/?$")


def pin_repository(url: str) -> dict:
    match = PATTERN.match(url)
    if not match: raise ValueError("يجب تقديم رابط مستودع GitHub عام صالح")
    owner, repo, pull_number = match.groups()
    endpoint = f"pulls/{pull_number}" if pull_number else "commits/HEAD"
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(f"https://api.github.com/repos/{owner}/{repo}/{endpoint}", headers={"Accept": "application/vnd.github+json"})
    except httpx.RequestError as error:
        raise ValueError("تعذر الاتصال بـGitHub الآن؛ لم نفقد بيانات التسليم، حاول مرة أخرى") from error
    if response.status_code != 200: raise ValueError("تعذر الوصول إلى المستودع العام")
    payload = response.json()
    sha = payload["head"]["sha"] if pull_number else payload["sha"]
    return {"owner": owner, "repo": repo, "sha": sha, "url": payload["html_url"], "pull_number": pull_number}
