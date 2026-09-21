from types import SimpleNamespace

from app.agents import coach


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
        lambda **kwargs: SimpleNamespace(text="Test coach response"),
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
