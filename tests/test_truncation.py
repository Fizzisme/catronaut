import pytest

from app.core.tools import truncate_head_tail

HINT = "Call Read again with offset=51."


def numbered(count: int) -> list[str]:
    return [f"line {n}\n" for n in range(1, count + 1)]


def test_text_within_the_limits_is_unchanged() -> None:
    text = "".join(numbered(200))
    assert truncate_head_tail(text, how_to_read_rest=HINT) == text


def test_too_many_lines_keeps_the_first_and_last_fifty() -> None:
    lines = numbered(300)
    result = truncate_head_tail("".join(lines), how_to_read_rest=HINT)

    omitted = sum(len(line) for line in lines[50:250])
    marker = f"... [lines 51–250 of 300 omitted ({omitted} characters). {HINT}] ...\n"
    assert result == "".join(lines[:50]) + marker + "".join(lines[250:])


def test_one_huge_line_is_cut_by_characters() -> None:
    # Like a minified bundle: one line, far over the character limit
    result = truncate_head_tail("x" * 30, how_to_read_rest=HINT, max_chars=10)

    assert result == f"xxxxx\n... [part of line 1 omitted (20 characters). {HINT}] ...\nxxxxx"


def test_a_few_long_lines_are_cut_by_characters() -> None:
    text = "a" * 8 + "\n" + "b" * 8 + "\n" + "c" * 8 + "\n"
    result = truncate_head_tail(text, how_to_read_rest=HINT, max_chars=10)

    # 5 characters from each end; the partly shown lines 1 and 3 count as shown
    assert result == f"aaaaa\n... [lines 2–2 of 3 omitted (17 characters). {HINT}] ...\ncccc\n"


def test_a_cut_without_a_way_to_read_the_rest_is_refused() -> None:
    with pytest.raises(ValueError):
        truncate_head_tail("".join(numbered(300)), how_to_read_rest="  ")
