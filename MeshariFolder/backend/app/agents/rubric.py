"""
The Mentor's review rubric — one place, written to be read and edited by the
team (docs/MENTOR_RUBRIC.md explains every choice and lists what to confirm).

The first-pass prompt named four categories and said "score 1-5", so a "3" meant
whatever the model felt like that day, and nothing tied the verdict to the
scores. This module fixes both:

  * every category has ANCHORS - what a 1, a 3 and a 5 concretely look like - so
    scores are comparable across tasks, weeks and graduates;
  * ONE rule decides the verdict, and the code enforces it (apply_rubric_rules):
    only "meets requirements" can block a task, and only below APPROVAL_BAR.
    Missing tests or thin docs are next-time comments, never a reason to bounce
    (the same philosophy as before, now stated precisely).

Change a bar or an anchor here; the prompt, the docs test and the enforcement
all read from it.
"""
from app.language import current_language

RUBRIC_VERSION = "2"

# The score at or above which a task's goal counts as met. Below it, the task
# is bounced (needs_changes). Only `correctness` can block; see VERDICT_RULE.
APPROVAL_BAR = 3

# Never show a graduate a wall of feedback: a focused list is acted on.
MAX_COMMENTS = 4

CATEGORIES = [
    {
        "key": "correctness",
        "name": "Meets requirements",
        "blocking": True,
        "asks": "Does the work do what the task asked?",
        "anchors": {
            1: "Doesn't attempt the task, or what was submitted cannot work at all.",
            2: "Attempts it, but a core part of the task's goal is missing or broken.",
            3: "The goal is substantially met; some edge cases or secondary parts are missing.",
            4: "Meets the goal, including the important edge cases.",
            5: "Meets the goal fully and thoughtfully, going beyond the brief where sensible.",
        },
    },
    {
        "key": "code_quality",
        "name": "Code quality",
        "blocking": False,
        "asks": "Is it readable and reasonably structured for someone else to maintain?",
        "anchors": {
            1: "Hard to follow: no structure, unclear names, large copy-pasted blocks.",
            3: "Readable with sensible structure; some duplication, unclear naming or long functions.",
            5: "Clear, well-structured and idiomatic; consistent style; easy to change.",
        },
    },
    {
        "key": "testing",
        "name": "Testing",
        "blocking": False,
        "asks": "Is there evidence it works?",
        "anchors": {
            1: "No verification at all where the task plainly needed some.",
            3: "Some tests, or a clear note on how it was checked by hand.",
            5: "Meaningful tests covering the key behaviour and an edge case or two.",
        },
        "scope_note": (
            "Judge testing against the task's size and what it asked for: a small "
            "exercise that didn't ask for tests shouldn't score 1 for lacking them."
        ),
    },
    {
        "key": "documentation",
        "name": "Documentation",
        "blocking": False,
        "asks": "Could someone else run it and understand what was done?",
        "anchors": {
            1: "No explanation of what it is or how to run it.",
            3: "A short README or notes: what it does and how to run it.",
            5: "Clear, usable docs, including decisions made and known limits.",
        },
    },
]

CATEGORY_KEYS = [c["key"] for c in CATEGORIES]

VERDICT_RULE = (
    f"VERDICT RULE. Use 'needs_changes' only when 'Meets requirements' scores "
    f"below {APPROVAL_BAR} - that is, the task's goal is not actually met, or the "
    "work is unusable or unsafe for its purpose. Otherwise use 'approved'. Weak "
    "code quality, missing tests or thin documentation never block a task on their "
    "own: approve, and say what to improve next time. Your verdict and your scores "
    "must agree."
)

REVIEW_STYLE = (
    "HOW TO WRITE THE REVIEW. Every comment must point at something concrete you "
    "can see in the submission (a file, a function, a behaviour, a detail in a "
    "screenshot, a line of the graduate's notes) - or state plainly that you could "
    "not verify something. When the verdict is 'needs_changes', give at most 3 "
    "comments, most important first, each saying what is wrong, why it matters and "
    "the concrete fix. When it is 'approved', give at most 2 comments on what to "
    "improve next time. Be direct and kind, the way a good senior colleague reviews "
    "a junior's work."
)

HONESTY = (
    "LIMITS. You can read what is provided; you cannot run the code or the tests. "
    "Never claim you ran anything or that tests pass, and never mention files you "
    "were not shown. For a GitHub repository you are shown its file list (the first "
    "25 files) and the start of its README - not the code itself. Judge what that "
    "evidence supports; if the README doesn't show something the task needed, say what "
    "evidence to add (output, a screenshot, a short note) rather than assuming it is "
    "missing from the code. If the evidence you'd need isn't visible, say so rather "
    "than guessing."
)

CALIBRATION = (
    "CALIBRATION. This is a recent graduate's early-career work. Judge it as good "
    "junior work, not as production code. Expect a little more each week."
)

RESUBMISSION = (
    "RESUBMISSIONS. If your previous feedback is shown below, this is a revision. "
    "Judge mainly whether those points were addressed. Do not raise new non-blocking "
    "issues just to keep the loop going: if the earlier blockers are fixed, approve."
)


def rubric_text() -> str:
    """The rubric as a prompt block: each category, its question and its anchors."""
    lines = ["RUBRIC. Score every category 1-5 using these anchors (2 and 4 sit between the anchors):"]
    for c in CATEGORIES:
        lines.append(f"\n{c['name']} (key: {c['key']}) - {c['asks']}")
        for score in sorted(c["anchors"]):
            lines.append(f"  {score}: {c['anchors'][score]}")
        if c.get("scope_note"):
            lines.append(f"  Note: {c['scope_note']}")
    return "\n".join(lines)


def system_prompt() -> str:
    return "\n\n".join(
        [
            "You are the Mentor at Venv, reviewing a recent graduate's submitted work: a "
            "GitHub repo, notes they wrote, images or files they attached, or any mix. "
            "You review by scoring a fixed rubric and giving specific, useful feedback.",
            rubric_text(),
            VERDICT_RULE,
            REVIEW_STYLE,
            HONESTY,
            CALIBRATION,
            RESUBMISSION,
        ]
    )


_ADJUSTMENT_NOTES = {
    "en": ("Verdict adjusted to 'needs changes': 'Meets requirements' scored {score}/5, "
           "below the approval bar of {bar}/5, so the task's goal isn't met yet."),
    "ar": ("تم تعديل القرار إلى «يحتاج تعديلات»: درجة «تحقيق المتطلبات» {score}/5، "
           "وهي أقل من حد القبول ({bar}/5)، أي أن هدف المهمة لم يتحقق بعد."),
}


def scores_by_key(categories) -> dict:
    """category key -> score, tolerant of the shapes models actually return: the
    schema's list of {key, label, score}, but also a plain {key: score} (or
    {key: {"score": n}}) mapping, and junk entries. A bad shape must never crash a
    review - at worst we can't enforce the rule for it."""
    scores: dict = {}
    if isinstance(categories, dict):
        for key, value in categories.items():
            score = value.get("score") if isinstance(value, dict) else value
            scores.setdefault(key, score)
    elif isinstance(categories, list):
        for item in categories:
            if isinstance(item, dict):
                scores.setdefault(item.get("key"), item.get("score"))
    return scores


def apply_rubric_rules(data: dict) -> tuple[dict, bool]:
    """Make the verdict agree with the scores; cap the comment list.

    Returns (data, adjusted). Only one contradiction is corrected: a model that
    says 'approved' while scoring 'meets requirements' below the bar. The reverse
    (needs_changes with decent scores) is left alone - the model may be flagging a
    real blocker its scores don't capture, and bouncing is the cautious direction.
    When we do change the verdict, the summary says so, so the graduate never sees
    a glowing review attached to a 'needs changes' with no explanation.
    """
    data = dict(data)
    comments = list(data.get("comments") or [])
    data["comments"] = comments[:MAX_COMMENTS]

    correctness = scores_by_key(data.get("categories")).get("correctness")

    if data.get("verdict") == "approved" and isinstance(correctness, int) and not isinstance(correctness, bool) and correctness < APPROVAL_BAR:
        note = _ADJUSTMENT_NOTES.get(current_language.get(), _ADJUSTMENT_NOTES["en"]).format(
            score=correctness, bar=APPROVAL_BAR
        )
        data["verdict"] = "needs_changes"
        data["summary"] = f"{data.get('summary', '').rstrip()}\n\n{note}"
        return data, True
    return data, False
