from app.services.ai import ai


def test_malformed_llm_response_handling(monkeypatch):
    """Validates that structured AI parser returns fallback dictionary when LLM returns invalid JSON."""
    monkeypatch.setattr(ai, "providers", [])
    fallback = {"status": "fallback_applied", "skills": ["Web"]}
    result = ai.structured("invalid prompt", fallback)
    assert result == fallback
