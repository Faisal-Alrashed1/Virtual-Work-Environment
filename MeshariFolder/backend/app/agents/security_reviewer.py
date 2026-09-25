"""
Security Reviewer agent (Stage 2 optional agent, upgraded from a
meeting-room-only persona to a real reviewer with its own structured
output — see docs/PROJECT_STATUS.md's optional-agent roster). Runs
alongside the Mentor's review during the roundtable (app/agents/
roundtable.py), grounded in real content rather than a generic opinion:
the files the graduate uploaded (read via submission_files.py) and, for
a GitHub link, the repo's dependency/config files plus a check for a
committed '.env' (via github_client.py).

Structured output (tools.SUBMIT_SECURITY_REVIEW_TOOL) rather than free
text — same reasoning as mentor.py's SUBMIT_REVIEW_TOOL. Stored as a
Review with kind=SPECIALIST_REVIEW (models.py), agent_type=
SECURITY_REVIEWER, and metrics_json records exactly which files were
read, so a verdict is never detached from what it was based on.

If nothing inspectable was submitted (only notes, or only files that
can't be read, like a zip or a screenshot), no LLM call is made: the
review is stored as verdict 'not_reviewed' with a message telling the
graduate what to upload. Asking the model anyway is what previously
produced confident "no vulnerabilities found" verdicts on code it never
saw. Runs on the small tier, same as the other roundtable specialists.
"""
from sqlalchemy.orm import Session

from app.agents.github_client import fetch_file_content, list_repo_paths, parse_owner_repo
from app.agents.llm_client import call_with_tool
from app.agents.static_checks import (
    facts_for_prompt,
    find_hardcoded_secrets,
    merge_findings,
    merge_risk_level,
    summary_prefix,
)
from app.agents.submission_files import read_submitted_files
from app.agents.tools import SUBMIT_SECURITY_REVIEW_TOOL
from app.models import AgentType, Review, ReviewKind, Task, User

SYSTEM_PROMPT = (
    "You are the Security Reviewer at Venv, examining a recent graduate's "
    "submitted work for real security concerns, not textbook advice. "
    "You're given the actual content of the files that could be read "
    "(uploaded files, and/or dependency/config files from their repo, "
    "plus a verified flag if a real .env file is committed) and the "
    "graduate's own notes. Ground every finding in something actually "
    "present in that content — a specific line, a specific package — "
    "never a generic 'you should validate input' unless you can point at "
    "where input isn't validated. Only judge content you were actually "
    "shown: you'll be told which files couldn't be read, and you must "
    "never describe those as clean or as vulnerable. In your summary, "
    "name the files you reviewed. Never repeat the actual value of a "
    "secret, key, or password you find. If nothing concerning is in the content "
    "you reviewed, say so plainly ('clear', empty findings) rather than "
    "padding the review. Severity should reflect real-world impact: a "
    "committed secret or an injection risk is 'high'; an outdated but "
    "non-exploited dependency is usually 'low' or 'medium'. "
    "Stay strictly within security: don't comment on data quality, model "
    "evaluation, project structure, or code style — those belong to your "
    "teammates — and don't restate what they said. Only state what the "
    "content actually shows: you have no vulnerability database and can't "
    "run anything, so never claim dependencies are up to date or free of "
    "known CVEs, that tests pass, or anything about files you weren't "
    "shown. When something might be a risk but the content can't confirm "
    "it, say it's worth checking rather than stating it as fact."
)

# Root-level files worth actually reading for a quick security pass — not
# exhaustive, just the common dependency/config surface across ecosystems.
_CANDIDATE_DEPENDENCY_FILES = [
    "requirements.txt",
    "Pipfile",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Gemfile",
    ".env.example",
]


def _fetch_dependency_files(owner: str, repo: str, paths: list[str]) -> list[tuple[str, str]]:
    # Only request candidates the tree says exist: each request counts
    # against GitHub's 60/hour unauthenticated limit.
    files = []
    for filename in _CANDIDATE_DEPENDENCY_FILES:
        if filename not in paths:
            continue
        content = fetch_file_content(owner, repo, filename)
        if content:
            files.append((filename, content[:3000]))
    return files


_ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")


def _has_exposed_env_file(paths: list[str]) -> bool:
    """Deterministic, code-level check (not left to the LLM to notice or
    miss) — mirrors hr.py's _active_days: compute the fact in code, let
    the LLM judge/narrate it. A real '.env' (not '.env.example'/
    '.env.sample') committed to a public repo is a concrete, checkable
    red flag, not something that needs LLM judgment to detect. Variants
    like '.env.production' / '.env.local' count too; templates don't."""
    for path in paths:
        name = path.rsplit("/", 1)[-1].lower()
        if (name == ".env" or name.startswith(".env.")) and not name.endswith(_ENV_TEMPLATE_SUFFIXES):
            return True
    return False


def _gather_content(task: Task) -> tuple[list[str], list[str], list[str], list[tuple[str, str]]]:
    """Returns (prompt sections, files actually read, files that couldn't
    be read, (filename, text) of everything read — for static_checks).
    The second list is what decides whether a review happens at all —
    see review_task."""
    sections: list[str] = []
    reviewed: list[str] = []
    unreadable: list[str] = []
    contents: list[tuple[str, str]] = []

    if task.github_link:
        try:
            owner, repo = parse_owner_repo(task.github_link)
        except ValueError:
            owner = repo = None

        paths = list_repo_paths(owner, repo) if owner and repo else None
        if not (owner and repo):
            unreadable.append(f"{task.github_link} (not a recognizable GitHub repo URL)")
        elif paths is None:
            unreadable.append(
                f"{task.github_link} (GitHub didn't respond — the repo may be "
                "private, or GitHub's hourly request limit was reached)"
            )
        else:
            for filename, content in _fetch_dependency_files(owner, repo, paths):
                sections.append(f"--- {filename} (from the GitHub repo) ---\n{content}")
                reviewed.append(f"{filename} (GitHub)")
                contents.append((filename, content))
            if _has_exposed_env_file(paths):
                sections.append(
                    "VERIFIED FACT: a real '.env' file (not '.env.example') is "
                    "committed to this repo's default branch — treat this as a "
                    "committed-secrets concern unless you have reason to believe "
                    "it's a harmless placeholder."
                )
                reviewed.append(".env (GitHub, presence check)")

    files, unreadable_uploads = read_submitted_files(task)
    for filename, text in files:
        sections.append(f"--- {filename} (uploaded) ---\n{text}")
        reviewed.append(filename)
        contents.append((filename, text))
    unreadable.extend(unreadable_uploads)

    return sections, reviewed, unreadable, contents


def _build_prompt(
    task: Task,
    sections: list[str],
    unreadable: list[str],
    discussion_so_far: str | None,
) -> str:
    parts = [f"Task: {task.title}\n{task.description}\n", *sections]
    if unreadable:
        parts.append(
            "Could NOT be read (do not comment on their contents): "
            + ", ".join(unreadable)
        )
    if task.submission_text:
        parts.append(f"Graduate's own notes on this submission:\n{task.submission_text}\n")
    if discussion_so_far:
        parts.append(
            "--- Team discussion so far (Mentor's review and any earlier "
            f"specialist turns) ---\n{discussion_so_far}\n\nGround your "
            "review in the actual content above; only reference the "
            "discussion where it's genuinely relevant to note agreement, "
            "disagreement, or something it missed."
        )
    parts.append("Submit your security review now via the submit_security_review tool.")
    return "\n".join(parts)


def _not_reviewed_summary(task: Task, unreadable: list[str]) -> str:
    text = (
        "I couldn't do a security review of this submission: there was no "
        "code or config content I could read."
    )
    if unreadable:
        text += " I couldn't open: " + ", ".join(unreadable) + "."
        link_items = [u for u in unreadable if task.github_link and u.startswith(task.github_link)]
        if len(link_items) < len(unreadable):
            text += " Images, archives, and binary files aren't readable here."
    return text + (
        " Upload the source files directly (e.g. .py, .js, requirements.txt) "
        "or link a public GitHub repo, and I'll review them."
    )


def review_task(
    db: Session, task: Task, user: User, discussion_so_far: str | None = None
) -> Review:
    """Always produces a structured Review. When there's readable content,
    the LLM reviews it; when there isn't, a 'not_reviewed' Review is
    stored without an LLM call. discussion_so_far (optional) keeps this
    specialist part of the roundtable's actual conversation. Caller
    (roundtable.py) posts the thread message from the returned review's
    content and treats this call as best-effort."""
    sections, reviewed, unreadable, contents = _gather_content(task)
    static = find_hardcoded_secrets(contents)
    if static:
        sections.append(facts_for_prompt(static))

    if not reviewed:
        verdict, risk_level, findings = "not_reviewed", None, []
        summary = _not_reviewed_summary(task, unreadable)
    else:
        result = call_with_tool(
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _build_prompt(task, sections, unreadable, discussion_so_far),
                }
            ],
            tools=[SUBMIT_SECURITY_REVIEW_TOOL],
            force_tool="submit_security_review",
            tier="small",
            max_tokens=1200,
        )
        data = result["input"]
        # Rule-based findings are verified, so they always make it into the
        # stored review and the thread message, whatever the model returned.
        findings = merge_findings(static, data["findings"], [name for name, _ in contents])
        risk_level = merge_risk_level(data["risk_level"], static)
        verdict = "concerns_found" if findings else data["verdict"]
        summary = summary_prefix(static) + data["summary"]

    review = Review(
        user_id=user.id,
        task_id=task.id,
        week_id=task.week_id,
        agent_type=AgentType.SECURITY_REVIEWER,
        kind=ReviewKind.SPECIALIST_REVIEW,
        content=summary,
        metrics_json={
            "verdict": verdict,
            "risk_level": risk_level,
            "findings": findings,
            "reviewed_files": reviewed,
            "unreadable_files": unreadable,
        },
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
