import re
import httpx


PATTERN = re.compile(r"^https://github\.com/([^/]+)/([^/#]+?)(?:\.git)?/?$")


def pin_repository(url: str) -> dict:
    match = PATTERN.match(url)
    if not match: raise ValueError("يجب تقديم رابط مستودع GitHub عام صالح")
    owner, repo = match.groups()
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(f"https://api.github.com/repos/{owner}/{repo}/commits/HEAD", headers={"Accept": "application/vnd.github+json"})
    except httpx.RequestError as error:
        raise ValueError("تعذر الاتصال بـGitHub الآن؛ لم نفقد بيانات التسليم، حاول مرة أخرى") from error
    if response.status_code != 200: raise ValueError("تعذر الوصول إلى المستودع العام")
    payload = response.json()
    return {"owner": owner, "repo": repo, "sha": payload["sha"], "url": payload["html_url"]}
