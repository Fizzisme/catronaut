import pytest

from app.core.tools import ToolError
from app.core.workspace.paths import MAX_PATH_LENGTH, check_path


@pytest.mark.parametrize(
    "path",
    [
        "package.json",
        "app/page.tsx",
        "app/[slug]/page.tsx",
        "app/(marketing)/layout.tsx",
        "app/[...all]/page.tsx",
        "app/[[...all]]/page.tsx",
        ".env.example",
        "App/Page.tsx",
        "a" * MAX_PATH_LENGTH,
    ],
)
def test_valid_path_is_returned_unchanged(path: str) -> None:
    assert check_path(path) == path


@pytest.mark.parametrize(
    ("path", "problem"),
    [
        ("", "empty"),
        ("a" * (MAX_PATH_LENGTH + 1), "limit is 300"),
        ("app\\page.tsx", "'\\\\'"),
        ("C:/app/page.tsx", "':'"),
        ("app/pa\x00ge.tsx", "'\\x00'"),
        ("/app/page.tsx", "absolute"),
        ("app//page.tsx", "segment"),
        ("app/", "segment"),
        ("./app/page.tsx", "segment"),
        ("app/../page.tsx", "segment"),
        ("..", "segment"),
    ],
)
def test_invalid_path_is_an_error_with_a_hint(path: str, problem: str) -> None:
    with pytest.raises(ToolError) as exc_info:
        check_path(path)

    assert problem in exc_info.value.message
    assert "app/page.tsx" in exc_info.value.hint
