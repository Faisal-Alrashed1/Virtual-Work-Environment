import pytest
from app.services.github import pin_repository


def test_invalid_github_link_handling():
    """Validates that non-github URLs or malformed github links throw ValueError."""
    with pytest.raises(ValueError, match="يلزم تقديم رابط من github.com"):
        pin_repository("https://gitlab.com/user/project")

    with pytest.raises(ValueError, match="صيغة رابط GitHub غير صالحة"):
        pin_repository("https://github.com/")
