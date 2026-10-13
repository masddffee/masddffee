"""Shared helpers for the hand-built SVG cards in this profile.

Everything here is standard library only, so the GitHub Actions workflows can run
without installing anything. When fontTools is available the embedded font is
subset to the glyphs a card actually uses; otherwise the full Latin subset is
embedded so the card still renders with the same typeface.
"""
from __future__ import annotations

import base64
import html
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
FONT_FILES = {
    400: "jetbrains-mono-latin-400.woff2",
    700: "jetbrains-mono-latin-700.woff2",
    800: "jetbrains-mono-latin-800.woff2",
}
FONT_SLOT = "/*FONTS*/"

MONO = "JBM, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
CJK = "'PingFang TC', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif"
CHAR_W = 0.6  # JetBrains Mono advance width, in em.

# Palette shared by every card so the README reads as one system.
BG0 = "#05070d"
BG1 = "#0a0f1a"
PANEL = "#0b111c"
LINE = "#1c2636"
TEXT = "#e6edf3"
MUTED = "#8b98a9"
DIM = "#4b5768"
MINT = "#3dfc9c"
CYAN = "#38bdf8"
PINK = "#f472b6"
VIOLET = "#a78bfa"
AMBER = "#fbbf24"
RED = "#ff5f56"


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def text_width(text: str, size: float, spacing: float = 0.0) -> float:
    """Width of a monospace run, used to size chips, clips and marquees."""
    return len(text) * (size * CHAR_W + spacing)


def num(value: float) -> str:
    """Compact number formatting for coordinates."""
    out = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if out == "-0" else out


_TEXT_RE = re.compile(r"<text\b[^>]*>(.*?)</text>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def used_text(svg: str) -> str:
    chars: set[str] = set()
    for match in _TEXT_RE.finditer(svg):
        chars.update(html.unescape(_TAG_RE.sub("", match.group(1))))
    return "".join(sorted(chars))


def font_faces(text: str, weights) -> str:
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
    except ImportError:  # Full Latin subset fallback.
        subset = None

    rules = []
    for weight in sorted(set(weights)):
        raw = (FONT_DIR / FONT_FILES[weight]).read_bytes()
        if subset is not None and text:
            font = TTFont(io.BytesIO(raw), recalcTimestamp=False)
            options = subset.Options()
            options.flavor = "woff2"
            options.layout_features = ["calt", "liga", "kern"]
            subsetter = subset.Subsetter(options)
            subsetter.populate(text=text)
            subsetter.subset(font)
            buffer = io.BytesIO()
            font.flavor = "woff2"
            font.save(buffer)
            raw = buffer.getvalue()
        data = base64.b64encode(raw).decode("ascii")
        rules.append(
            f"@font-face{{font-family:JBM;font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
        )
    return "".join(rules)


_WEIGHT_RE = re.compile(r"font-weight(?:=\"|:)(\d{3})")


def finalize(svg: str) -> str:
    """Replace the font slot with @font-face rules subset to the card's text."""
    weights = {400} | {int(w) for w in _WEIGHT_RE.findall(svg) if int(w) in FONT_FILES}
    return svg.replace(FONT_SLOT, font_faces(used_text(svg), weights), 1)


def data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def load_icons() -> dict:
    return json.loads((ROOT / "data" / "icons.json").read_text(encoding="utf-8"))["icons"]


def icon(icons: dict, slug: str, x: float, y: float, size: float, fill: str, extra: str = "") -> str:
    """Place a 24×24 Simple Icons path at (x, y) scaled to `size`."""
    scale = size / 24
    return (
        f'<path transform="translate({num(x)} {num(y)}) scale({num(scale)})" '
        f'fill="{fill}" d="{icons[slug]["path"]}"{extra}/>'
    )


def write(path: Path, svg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(finalize(svg), encoding="utf-8")
