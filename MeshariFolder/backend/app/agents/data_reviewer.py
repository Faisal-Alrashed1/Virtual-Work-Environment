"""
Data Reviewer agent (Stage 2 optional agent, upgraded from a meeting-room-
only persona to a real reviewer with its own structured output — see
docs/PROJECT_STATUS.md's optional-agent roster). Runs alongside the
Mentor's review during the roundtable (app/agents/roundtable.py),
grounded in real content rather than a generic opinion: the files the
graduate uploaded (read via submission_files.py — notebooks reduced to
their code cells) and, for a GitHub link, the repo's notebooks plus a
check for whether any evaluation/test script is visible at all.

Structured output (tools.SUBMIT_DATA_REVIEW_TOOL) rather than free text —
same reasoning as security_reviewer.py / mentor.py. Stored as a Review
with kind=SPECIALIST_REVIEW (models.py), agent_type=DATA_REVIEWER, and
metrics_json records exactly which files were read.

If nothing inspectable was submitted, no LLM call is made: the review is
stored as verdict 'not_reviewed' with a message telling the graduate
what to upload — same reasoning as security_reviewer.py. Runs on the
small tier, same as the other roundtable specialists.
"""
import re

from sqlalchemy.orm import Session

from app.agents.github_client import fetch_file_content, list_repo_paths, parse_owner_repo
from app.agents.llm_client import call_with_tool
from app.agents.static_checks import (
    facts_for_prompt,
    find_data_leakage,
    merge_findings,
    merge_risk_level,
    summary_prefix,
)
from app.agents.submission_files import extract_notebook_code, read_submitted_files
from app.agents.tools import SUBMIT_DATA_REVIEW_TOOL
from app.models import AgentType, Review, ReviewKind, Task, User

SYSTEM_PROMPT = (
    "You are the Data Reviewer at Venv, examining a recent graduate's "
    "submitted work for real data-quality and methodology concerns, not "
    "textbook advice. You're given the actual content of the files that "
    "could be read (uploaded files, and/or notebook code cells from their "
    "repo, plus a verified flag for whether any evaluation/test file is "
    "visible in the repo structure). Ground every finding in something "
    "actually present in that content — a specific cell, a specific "
    "missing step — never a generic 'you should validate your model' "
    "unless you can point at what's missing. Only judge content you were "
    "actually shown: you'll be told which files couldn't be read, and you "
    "must never describe those as sound or as flawed. In your summary, "
    "name the files you reviewed. If nothing concerning is in the content "
    "you reviewed, say so plainly ('clear', empty findings) rather than "
    "padding the review. Severity should reflect real-world impact: "
    "genuine data leakage into a test set is 'high'; a missing docstring "
    "or a slightly informal split is usually 'low'. "
    "Stay strictly within data quality and methodology: don't comment on "
    "security (secrets, injection, auth), web/API code, project structure, "
    "or code style — those belong to your teammates — and don't restate "
    "what they said. Skip files that have nothing to do with data work "
    "rather than declaring them fine. Only state what the content actually "
    "shows: you can't run the code or see the data, so never claim a "
    "metric value, a dataset's size or balance, or anything about files "
    "you weren't shown. When something might be a problem but the content "
    "can't confirm it, say it's worth checking rather than stating it as fact."
)

_NOTEBOOK_EXTENSION = ".ipynb"
_MAX_NOTEBOOKS = 3
_EVAL_PATH_HINTS = ("eval", "test", "metric", "scor")


def _find_notebook_paths(paths: list[str]) -> list[str]:
    return [p for p in paths if p.endswith(_NOTEBOOK_EXTENSION)][:_MAX_NOTEBOOKS]


def _fetch_notebooks(owner: str, repo: str, paths: list[str]) -> list[tuple[str, str]]:
    notebooks = []
    for path in _find_notebook_paths(paths):
        content = fetch_file_content(owner, repo, path)
        if not content:
            continue
        code = extract_notebook_code(content)
        if code:
            notebooks.append((path, code[:4000]))
    return notebooks


def _has_evaluation_file(paths: list[str]) -> bool:
    """Deterministic, code-level check, same reasoning as
    security_reviewer's _has_exposed_env_file: does any repo path suggest
    an evaluation/test/metrics script? A concrete, checkable signal for
    'is evaluation methodology even visible', not something worth leaving
    to the LLM to notice or miss from a raw path listing.

    Matches whole words in the path (a word *starting* with a hint), not
    any substring — otherwise 'latest.py' or 'contest/' counted as tests."""
    for path in paths:
        words = re.split(r"[^a-z0-9]+", path.lower())
        if any(word.startswith(hint) for word in words for hint in _EVAL_PATH_HINTS):
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
            for path, code in _fetch_notebooks(owner, repo, paths):
                sections.append(f"--- {path} (from the GitHub repo, code cells only) ---\n{code}")
                reviewed.append(f"{path} (GitHub)")
                contents.append((path, code))
            if paths and not _has_evaluation_file(paths):
                sections.append(
                    "VERIFIED FACT: no file path in the repo suggests an "
                    "evaluation/test/metrics script (nothing named like eval/"
                    "test/metric/score) — evaluation methodology, if any, "
                    "isn't visible in the repo structure."
                )

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
    parts.append("Submit your data review now via the submit_data_review tool.")
    return "\n".join(parts)


def _not_reviewed_summary(task: Task, unreadable: list[str]) -> str:
    text = (
        "I couldn't do a data review of this submission: there were no "
        "notebooks, scripts, or data files I could read."
    )
    if unreadable:
        text += " I couldn't open: " + ", ".join(unreadable) + "."
        link_items = [u for u in unreadable if task.github_link and u.startswith(task.github_link)]
        if len(link_items) < len(unreadable):
            text += " Images, archives, and binary files aren't readable here."
    return text + (
        " Upload your notebook (.ipynb) or scripts directly, or link a "
        "public GitHub repo that contains them, and I'll review them."
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
    static = find_data_leakage(contents)
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
            tools=[SUBMIT_DATA_REVIEW_TOOL],
            force_tool="submit_data_review",
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
        agent_type=AgentType.DATA_REVIEWER,
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
