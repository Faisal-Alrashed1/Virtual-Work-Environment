"""
Tool schemas the agents call through (Anthropic tool-use format:
name + description + JSON-schema input_schema). Kept separate from the
agent modules so the shape of each tool is easy to find and review in one
place — it's effectively the contract each agent's LLM calls have to fill.
"""

CREATE_PROJECT_TOOL = {
    "name": "create_project",
    "description": (
        "Introduce the graduate to the main project they'll be working on "
        "throughout their time at Venv, calibrated to their CV/skills. "
        "Called once per graduate, at their very first task."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short project name."},
            "description": {
                "type": "string",
                "description": "What the project is and roughly what it'll involve, in a few sentences.",
            },
        },
        "required": ["title", "description"],
    },
}

PLAN_WEEK_TOOL = {
    "name": "plan_week",
    "description": (
        "Plan this week's work within the project: one 'big task' broken "
        "into exactly 5 subtasks the graduate will complete one at a time, "
        "one per workday. Each subtask should be a clear, scoped, testable "
        "deliverable that builds toward the big task."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "big_task_title": {"type": "string"},
            "big_task_description": {
                "type": "string",
                "description": "What this week is building toward, and why, in a sentence or two.",
            },
            "subtasks": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["title", "description"],
                },
                "description": "Exactly 5 subtasks, in the order the graduate should complete them.",
            },
        },
        "required": ["big_task_title", "big_task_description", "subtasks"],
    },
}

POST_MESSAGE_TOOL = {
    "name": "post_message",
    "description": "Post a plain-text message in the task's comment thread.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The message to post."},
        },
        "required": ["content"],
    },
}

# Rubric keys match frontend/src/lib/reviews.ts's proposed shape exactly —
# see docs/PROJECT_STATUS.md: that shape was flagged as "not an agreed
# contract yet". This is that contract's first real implementation.
SUBMIT_REVIEW_TOOL = {
    "name": "submit_review",
    "description": "Submit a structured code review for a submitted task.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["approved", "needs_changes"],
                "description": (
                    "'needs_changes' only when 'Meets requirements' scores below 3 "
                    "(the task's goal isn't met). Weak tests/docs/code quality alone "
                    "never block: approve and note them. Must agree with the scores."
                ),
            },
            "summary": {
                "type": "string",
                "description": "2-4 sentence overall review, specific to what was submitted.",
            },
            "categories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "enum": [
                                "correctness",
                                "code_quality",
                                "testing",
                                "documentation",
                            ],
                        },
                        "label": {"type": "string"},
                        "score": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                        },
                    },
                    "required": ["key", "label", "score"],
                },
                "minItems": 4,
                "maxItems": 4,
                "description": "Score all four categories exactly once: correctness, code_quality, testing, documentation.",
            },
            "comments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Must match one of the categories[].key values above.",
                        },
                        "content": {"type": "string"},
                    },
                    "required": ["category", "content"],
                },
                "maxItems": 4,
                "description": (
                    "Specific comments, each pointing at something concrete in the "
                    "submission. At most 3 when needs_changes, at most 2 when approved."
                ),
            },
        },
        "required": ["verdict", "summary", "categories", "comments"],
    },
}

UPDATE_EMPLOYEE_FILE_TOOL = {
    "name": "update_employee_file",
    "description": (
        "Update the graduate's shared Employee File after reviewing their "
        "Mentor review history. This is the one record Manager, Mentor, "
        "and HR all read from."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skills actually demonstrated in reviewed work so far.",
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific, evidence-based strengths — not generic praise.",
            },
            "growth_areas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Actionable growth areas (e.g. 'add tests alongside a feature'), not vague ones.",
            },
            "summary": {
                "type": "string",
                "description": "2-4 sentence overall narrative of progress so far.",
            },
        },
        "required": ["skills", "strengths", "growth_areas", "summary"],
    },
}

WEEK_PROGRESS_TOOL = {
    "name": "submit_week_progress",
    "description": (
        "Submit the Manager's end-of-week progress review, based on the "
        "Mentor's reviews of each of this week's subtasks."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-4 sentence overall progress summary for the week.",
            },
            "subtasks_completed": {
                "type": "integer",
                "description": "How many of this week's subtasks reached an approved review.",
            },
            "subtasks_needed_changes": {
                "type": "integer",
                "description": "How many subtasks needed at least one round of changes before approval.",
            },
        },
        "required": ["summary", "subtasks_completed", "subtasks_needed_changes"],
    },
}

# The attended/absent/late counts are computed in code from timestamps
# already on Task/TaskMessage (see hr.py's _active_days) — the model only
# writes the narrative and rating on top of numbers it's handed, so the
# evaluation itself isn't left to the LLM to invent.
BEHAVIORAL_REVIEW_TOOL = {
    "name": "submit_behavioral_review",
    "description": (
        "Write this week's behavioral evaluation — attendance, "
        "consistency, and absence — based on the attendance/lateness "
        "figures provided in the prompt."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-4 sentence behavioral summary for the week, referencing the actual figures given.",
            },
            "consistency_rating": {
                "type": "string",
                "enum": ["strong", "adequate", "needs_improvement"],
            },
        },
        "required": ["summary", "consistency_rating"],
    },
}

CAREER_CHECKIN_TOOL = {
    "name": "submit_career_checkin",
    "description": (
        "Write this graduate's career check-in — how their work so far "
        "would read to an employer, and what to focus on next to "
        "strengthen that — based on their Employee File and CV."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "2-4 sentence honest assessment of how hireable their "
                    "work-to-date makes them look, grounded in specifics "
                    "from the Employee File — not generic encouragement."
                ),
            },
            "resume_highlights": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "2-4 concrete bullets they could actually put on a "
                    "resume or LinkedIn, phrased the way a real resume "
                    "bullet reads (action verb + what + impact) — not "
                    "restated task titles."
                ),
            },
            "suggested_focus": {
                "type": "string",
                "description": "The one thing most worth focusing on next to strengthen their story for employers.",
            },
        },
        "required": ["summary", "resume_highlights", "suggested_focus"],
    },
}
