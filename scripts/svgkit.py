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
    ("JBM", 400): "jetbrains-mono-latin-400.woff2",
    ("JBM", 700): "jetbrains-mono-latin-700.woff2",
    ("JBM", 800): "jetbrains-mono-latin-800.woff2",
    ("Anton", 400): "anton-latin-400.woff2",
}
FONT_SLOT = "/*FONTS*/"

MONO = "JBM, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
DISPLAY = "Anton, Impact, 'Arial Narrow', sans-serif"
CJK = "'PingFang TC', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif"
CHAR_W = 0.6  # JetBrains Mono advance width, in em.
ANTON_W = 0.46  # Average Anton caps advance, in em (only used for rough layout).

# Noir palette: matte black, bone white, one racing red and a little champagne.
# Every card draws from these so the README reads as one film, not a dashboard.
BG0 = "#0a0a0b"
BG1 = "#0f0f11"
PANEL = "#121214"
LINE = "#26262a"
TEXT = "#ece6da"   # bone
MUTED = "#9a948a"
DIM = "#5c5852"
ASH = "#77726b"
STEEL = "#aab0b8"
ACCENT = "#e5322d"  # racing red
ACCENT_DEEP = "#7c1813"
GOLD = "#c9a45c"
SOFT = "#c9c3b8"  # secondary bone for long copy


def grain(fid: str = "grain", strength: float = 0.085) -> str:
    """Film grain: monochrome fractal noise turned into a faint alpha speckle."""
    return (
        f'<filter id="{fid}" x="0" y="0" width="100%" height="100%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7" stitchTiles="stitch"/>'
        f'<feColorMatrix values="0 0 0 0 .93 0 0 0 0 .9 0 0 0 0 .85 {strength * 1.8:.3f} 0 0 0 -{strength * .55:.3f}"/>'
        "</filter>"
    )


def grain_layer(w: float, h: float, fid: str = "grain", moving: bool = False) -> str:
    jitter = (
        '<animateTransform attributeName="transform" type="translate" calcMode="discrete" dur=".6s" '
        'repeatCount="indefinite" values="0 0;-9 5;6 -4;-4 -8;8 6;-7 -2"/>'
        if moving else ""
    )
    return f'<rect x="-20" y="-20" width="{w + 40}" height="{h + 40}" filter="url(#{fid})">{jitter}</rect>'


def window_dots(y: float = 20) -> str:
    return "".join(f'<circle cx="{24 + i * 17}" cy="{y}" r="4.5" fill="#2e2e33"/>' for i in range(3))


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


def font_faces(text: str, faces) -> str:
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
    except ImportError:  # Full Latin subset fallback.
        subset = None

    rules = []
    for family, weight in sorted(set(faces)):
        raw = (FONT_DIR / FONT_FILES[(family, weight)]).read_bytes()
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
            f"@font-face{{font-family:{family};font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
        )
    return "".join(rules)


_WEIGHT_RE = re.compile(r"font-weight(?:=\"|:)(\d{3})")


_DISPLAY_RE = re.compile(r'class="[^"]*\bdp\b')


def finalize(svg: str) -> str:
    """Replace the font slot with @font-face rules subset to the card's text."""
    faces = {("JBM", 400)} | {("JBM", int(w)) for w in _WEIGHT_RE.findall(svg) if ("JBM", int(w)) in FONT_FILES}
    if _DISPLAY_RE.search(svg):
        faces.add(("Anton", 400))
    return svg.replace(FONT_SLOT, font_faces(used_text(svg), faces), 1)


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


_ADVANCES: dict[tuple[str, int], tuple[dict[str, float], float]] = {}


def measure(text: str, size: float, family: str = "JBM", weight: int = 400, spacing: float = 0.0) -> float:
    """Rendered width of `text`; exact when fontTools is installed, estimated otherwise."""
    if family == "JBM":
        return text_width(text, size, spacing)
    key = (family, weight)
    if key not in _ADVANCES:
        try:
            from fontTools.ttLib import TTFont

            font = TTFont(io.BytesIO((FONT_DIR / FONT_FILES[key]).read_bytes()))
            cmap, hmtx = font.getBestCmap(), font["hmtx"].metrics
            upem = font["head"].unitsPerEm
            _ADVANCES[key] = ({chr(c): hmtx[g][0] / upem for c, g in cmap.items()}, upem)
        except Exception:
            _ADVANCES[key] = ({}, 1000)
    advances, _ = _ADVANCES[key]
    return sum(advances.get(ch, ANTON_W) * size + spacing for ch in text)
