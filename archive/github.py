import hashlib
from urllib.parse import urlparse


def pin_repository(github_url: str) -> dict:
    parsed = urlparse(github_url)
    if "github.com" not in parsed.netloc:
        raise ValueError("يلزم تقديم رابط من github.com")
    parts = [item for item in parsed.path.split("/") if item]
    if len(parts) < 2:
        raise ValueError("صيغة رابط GitHub غير صالحة")
    sha = hashlib.sha256(github_url.encode()).hexdigest()[:12]
    return {"url": github_url, "sha": sha, "pinned_at": "now"}
