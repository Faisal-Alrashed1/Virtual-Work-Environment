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
                    "'needs_changes' only when something genuinely blocks "
                    "the task's goal — minor gaps can still be 'approved'."
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
                "description": "Score all four categories: correctness, code_quality, testing, documentation.",
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
                "description": "Specific inline comments, referencing what's actually in the repo.",
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
CREATE_CAREER_PLAN_TOOL = {
    "name": "create_career_plan",
    "description": (
        "Create a practical career plan for the trainee based on their "
        "current skills, strengths, growth areas, and review history."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "current_position": {
                "type": "string",
                "description": "Short assessment of the trainee's current career position.",
            },
            "skill_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The most important skill gaps to address.",
            },
            "short_term_goals": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 3,
                "description": "Exactly three practical short-term career goals.",
            },
            "actions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete actions the trainee should take.",
            },
            "next_step": {
                "type": "string",
                "description": "The recommended next career step.",
            },
        },
        "required": [
            "current_position",
            "skill_gaps",
            "short_term_goals",
            "actions",
            "next_step",
        ],
    },
}


ANALYZE_SKILL_GAPS_TOOL = {
    "name": "analyze_skill_gaps",
    "description": (
        "Analyze the trainee's current skills and identify the most important "
        "career-related gaps to improve."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
            },
            "gaps": {
                "type": "array",
                "items": {"type": "string"},
            },
            "priorities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skill gaps ordered by what should be improved first.",
            },
            "recommendation": {
                "type": "string",
            },
        },
        "required": ["strengths", "gaps", "priorities", "recommendation"],
    },
}


PREPARE_INTERVIEW_TOOL = {
    "name": "prepare_interview",
    "description": (
        "Prepare the trainee for a job interview based on their career track, "
        "skills, strengths, and growth areas."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "focus_areas": {
                "type": "array",
                "items": {"type": "string"},
            },
            "practice_questions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "preparation_tips": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "focus_areas",
            "practice_questions",
            "preparation_tips",
        ],
    },
}


CAREER_COACH_TOOLS = [
    CREATE_CAREER_PLAN_TOOL,
    ANALYZE_SKILL_GAPS_TOOL,
    PREPARE_INTERVIEW_TOOL,
]
