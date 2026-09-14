def fetch_github_submission(github_url: str, sha: str) -> dict:
    return {"url": github_url, "sha": sha, "status": "fetched"}

def generate_daily_task(day: int, difficulty: int) -> dict:
    return {"day": day, "difficulty": difficulty, "status": "generated"}
