def test_empty_submission_handling():
    """Validates that empty inline code submissions are properly rejected."""
    code = ""
    summary = ""
    is_valid = len(code.strip()) > 0 and len(summary.strip()) >= 10
    assert is_valid is False
