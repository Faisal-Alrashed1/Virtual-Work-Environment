from types import SimpleNamespace

from app.agents import coach
from app.agents.llm_client import ToolCall


def test_build_career_profile_with_data():
    user = SimpleNamespace(
        track=SimpleNamespace(value="data_science"),
        employee_file=SimpleNamespace(
            skills_json=["Python", "SQL"],
            strengths_json=["Problem solving"],
            growth_areas_json=["Interview skills"],
        ),
    )

    result = coach.build_career_profile(user)

    assert "data_science" in result
    assert "Python" in result
    assert "Problem solving" in result
    assert "Interview skills" in result


def test_build_career_profile_without_data():
    user = SimpleNamespace(
        track=None,
        employee_file=None,
    )

    result = coach.build_career_profile(user)

    assert result == "No career profile information is available yet."


def test_generate_reply(monkeypatch):
    monkeypatch.setattr(
        coach,
        "build_context",
        lambda db, user: "Test career context",
    )

    monkeypatch.setattr(
        coach,
        "call_agentic",
        lambda **kwargs: SimpleNamespace(
            text="Test coach response",
            tool_calls=[],
        ),
    )

    result = coach.generate_reply(
        db=object(),
        user=SimpleNamespace(),
        messages=[{"role": "user", "content": "Help me"}],
    )

    assert result == "Test coach response"


def test_generate_career_plan(monkeypatch):
    monkeypatch.setattr(
        coach,
        "build_context",
        lambda db, user: "Test career context",
    )

    monkeypatch.setattr(
        coach,
        "call_agentic",
        lambda **kwargs: SimpleNamespace(text="Test career plan"),
    )

    result = coach.generate_career_plan(
        db=object(),
        user=SimpleNamespace(),
    )

    assert result == "Test career plan"


def test_create_career_plan_tool(monkeypatch):
    monkeypatch.setattr(
        coach,
        "build_context",
        lambda db, user: "Test career context",
    )

    monkeypatch.setattr(
        coach,
        "call_agentic",
        lambda **kwargs: SimpleNamespace(
            text=None,
            tool_calls=[
                ToolCall(
                    name="create_career_plan",
                    input={
                        "current_position": "Junior developer",
                        "skill_gaps": ["Testing", "Deployment"],
                        "short_term_goals": [
                            "Build one project",
                            "Improve testing",
                            "Practice interviews",
                        ],
                        "actions": [
                            "Write tests",
                            "Deploy a project",
                        ],
                        "next_step": "Apply for junior developer roles",
                    },
                )
            ],
        ),
    )

    result = coach.generate_reply(
        db=object(),
        user=SimpleNamespace(),
        messages=[{"role": "user", "content": "Create a career plan"}],
    )

    assert "Junior developer" in result
    assert "Testing" in result
    assert "Apply for junior developer roles" in result


def test_analyze_skill_gaps_tool(monkeypatch):
    monkeypatch.setattr(
        coach,
        "build_context",
        lambda db, user: "Test career context",
    )

    monkeypatch.setattr(
        coach,
        "call_agentic",
        lambda **kwargs: SimpleNamespace(
            text=None,
            tool_calls=[
                ToolCall(
                    name="analyze_skill_gaps",
                    input={
                        "strengths": ["Python"],
                        "gaps": ["Testing"],
                        "priorities": ["Testing first"],
                        "recommendation": "Practice automated testing.",
                    },
                )
            ],
        ),
    )

    result = coach.generate_reply(
        db=object(),
        user=SimpleNamespace(),
        messages=[{"role": "user", "content": "Analyze my skills"}],
    )

    assert "Python" in result
    assert "Testing" in result
    assert "Practice automated testing." in result


def test_prepare_interview_tool(monkeypatch):
    monkeypatch.setattr(
        coach,
        "build_context",
        lambda db, user: "Test career context",
    )

    monkeypatch.setattr(
        coach,
        "call_agentic",
        lambda **kwargs: SimpleNamespace(
            text=None,
            tool_calls=[
                ToolCall(
                    name="prepare_interview",
                    input={
                        "focus_areas": ["Python", "APIs"],
                        "practice_questions": [
                            "Explain REST APIs.",
                            "What is dependency injection?",
                        ],
                        "preparation_tips": [
                            "Practice concise answers.",
                            "Review your projects.",
                        ],
                    },
                )
            ],
        ),
    )

    result = coach.generate_reply(
        db=object(),
        user=SimpleNamespace(),
        messages=[{"role": "user", "content": "Prepare me for an interview"}],
    )

    assert "Python" in result
    assert "Explain REST APIs." in result
    assert "Review your projects." in result

def test_review_resume_tool(monkeypatch):
    monkeypatch.setattr(
        coach,
        "build_context",
        lambda db, user: "Test career context",
    )

    monkeypatch.setattr(
        coach,
        "call_agentic",
        lambda **kwargs: SimpleNamespace(
            text=None,
            tool_calls=[
                ToolCall(
                    name="review_resume",
                    input={
                        "strengths": ["Python projects"],
                        "weak_sections": ["Professional summary"],
                        "missing_skills": ["Testing"],
                        "improvements": ["Add measurable achievements"],
                        "suggested_summary": "Junior developer focused on Python and APIs.",
                    },
                )
            ],
        ),
    )

    result = coach.generate_reply(
        db=object(),
        user=SimpleNamespace(),
        messages=[{"role": "user", "content": "Review my resume"}],
    )

    assert "Python projects" in result
    assert "Professional summary" in result
    assert "Add measurable achievements" in result


def test_build_portfolio_plan_tool(monkeypatch):
    monkeypatch.setattr(
        coach,
        "build_context",
        lambda db, user: "Test career context",
    )

    monkeypatch.setattr(
        coach,
        "call_agentic",
        lambda **kwargs: SimpleNamespace(
            text=None,
            tool_calls=[
                ToolCall(
                    name="build_portfolio_plan",
                    input={
                        "projects_to_showcase": ["FastAPI project"],
                        "skills_to_highlight": ["Python", "APIs"],
                        "missing_project_types": ["Deployed application"],
                        "portfolio_actions": ["Add README", "Deploy project"],
                    },
                )
            ],
        ),
    )

    result = coach.generate_reply(
        db=object(),
        user=SimpleNamespace(),
        messages=[{"role": "user", "content": "Help me improve my portfolio"}],
    )

    assert "FastAPI project" in result
    assert "Python" in result
    assert "Deploy project" in result
