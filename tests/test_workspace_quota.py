import pytest

from app.core.tools import ToolError
from app.core.workspace.quota import (
    WriteQuota,
    check_content,
    check_tree,
    check_write_count,
)

SMALL = WriteQuota(max_file_bytes=10, max_files=2, max_total_bytes=15, max_writes_per_run=3)


def test_content_returns_its_size_in_utf8_bytes() -> None:
    assert check_content("app/page.tsx", "abc", SMALL) == 3
    assert check_content("app/page.tsx", "ệ", SMALL) == 3


@pytest.mark.parametrize("path", ["logo.png", ".env", "Makefile", "app/page"])
def test_disallowed_extension_is_an_error(path: str) -> None:
    with pytest.raises(ToolError) as exc_info:
        check_content(path, "x", SMALL)

    assert ".tsx" in exc_info.value.hint


@pytest.mark.parametrize(
    ("content", "problem"),
    [("a\x00b", "NUL"), ("\ud800", "UTF-8"), ("a" * 11, "limit is 10")],
)
def test_invalid_content_is_an_error(content: str, problem: str) -> None:
    with pytest.raises(ToolError) as exc_info:
        check_content("app/page.tsx", content, SMALL)

    assert problem in exc_info.value.message


def test_content_at_the_size_limit_is_allowed() -> None:
    assert check_content("app/page.tsx", "a" * 10, SMALL) == 10


def test_overwriting_a_file_does_not_count_as_a_new_file() -> None:
    check_tree({"a.ts": 5, "b.ts": 5}, "a.ts", 5, SMALL)


def test_too_many_files_is_an_error() -> None:
    with pytest.raises(ToolError, match="3 files"):
        check_tree({"a.ts": 1, "b.ts": 1}, "c.ts", 1, SMALL)


def test_too_many_bytes_is_an_error() -> None:
    with pytest.raises(ToolError, match="16 bytes"):
        check_tree({"a.ts": 10}, "b.ts", 6, SMALL)


def test_overwrite_that_shrinks_the_project_is_allowed() -> None:
    check_tree({"a.ts": 10, "b.ts": 5}, "a.ts", 1, SMALL)


def test_file_over_an_existing_directory_is_an_error() -> None:
    with pytest.raises(ToolError, match="already a directory"):
        check_tree({"app/page.tsx": 1}, "app", 1, SMALL)


def test_file_inside_an_existing_file_is_an_error() -> None:
    with pytest.raises(ToolError, match="'app' is a file"):
        check_tree({"app": 1}, "app/page.tsx", 1, SMALL)


def test_sibling_with_a_longer_name_is_not_a_conflict() -> None:
    check_tree({"app/page.tsx": 1}, "app/page.tsx.bak", 1, SMALL)


def test_write_count_below_the_limit_is_allowed() -> None:
    check_write_count(2, SMALL)


def test_write_count_at_the_limit_is_an_error() -> None:
    with pytest.raises(ToolError, match="3 file changes"):
        check_write_count(3, SMALL)
