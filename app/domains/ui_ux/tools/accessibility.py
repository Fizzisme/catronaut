"""WCAG contrast ratio checker — the first concrete `ui_ux` tool (ROADMAP M2.4)."""

import re

from pydantic import BaseModel, field_validator

from app.core.tools.base import Tool

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _expand_shorthand(hex_color: str) -> str:
    digits = hex_color[1:]
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    return digits


def _relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance (sRGB, gamma-corrected). See
    https://www.w3.org/TR/WCAG21/#dfn-relative-luminance."""
    digits = _expand_shorthand(hex_color)
    channels = []
    for i in range(0, 6, 2):
        c = int(digits[i : i + 2], 16) / 255.0
        c = c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        channels.append(c)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two hex colors, in [1, 21]. See
    https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio."""
    l1 = _relative_luminance(foreground)
    l2 = _relative_luminance(background)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class ContrastArgs(BaseModel):
    foreground: str
    background: str

    @field_validator("foreground", "background")
    @classmethod
    def _valid_hex(cls, value: str) -> str:
        # Validated here, not in run(): a malformed hex string should surface as an
        # M2.2 validation failure (eligible for the one repair turn), not a runtime
        # tool error that skips straight to M2.3's caught-exception path.
        if not _HEX_RE.match(value):
            raise ValueError("must be a hex color like #ffffff or #fff")
        return value


class CheckContrast(Tool):
    name = "check_contrast"
    description = "Check the WCAG contrast ratio between two hex colors."
    args_schema = ContrastArgs
    read_only = True
    timeout_s = 5.0

    async def run(self, args: ContrastArgs) -> str:
        ratio = wcag_contrast_ratio(args.foreground, args.background)
        return (
            f"Contrast ratio: {ratio:.2f}:1 — "
            f"WCAG AA normal text: {'PASS' if ratio >= 4.5 else 'FAIL'}, "
            f"AA large text: {'PASS' if ratio >= 3.0 else 'FAIL'}, "
            f"AAA normal text: {'PASS' if ratio >= 7.0 else 'FAIL'}"
        )
