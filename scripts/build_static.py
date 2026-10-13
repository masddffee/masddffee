#!/usr/bin/env python3
"""Build the static, hand-animated SVG cards used by the profile README.

These cards only change when the copy changes, so they are generated locally
(or by the workflow when this file changes) instead of on every metrics run.
Animations are pure CSS keyframes + SMIL so they survive GitHub's image proxy:
no scripts, no external requests.

Art direction: a film title sequence — matte black, bone-white type, one racing
red, a little champagne gold, film grain instead of neon glow. Few words, set
large: every card should read at a glance.
"""
from __future__ import annotations

import math
import random

from svgkit import (
    ACCENT, BG0, BG1, DIM, DISPLAY, FONT_SLOT, GOLD, LINE, MONO, MUTED, PANEL,
    ROOT, SOFT, STEEL, TEXT, data_uri, esc, grain, grain_layer, icon,
    load_icons, measure, num, text_width, window_dots, write,
)

ASSETS = ROOT / "assets"
ICONS = load_icons()


def base_style(extra: str) -> str:
    return (
        "<style>" + FONT_SLOT +
        f"text{{font-family:{MONO}}}"
        f".dp{{font-family:{DISPLAY};font-weight:400}}"
        "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}"
        "@keyframes fadein{from{opacity:0}to{opacity:1}}"
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}"
        ".blink{animation:blink 1.1s steps(1) infinite}"
        ".pulse{animation:pulse 1.8s ease-in-out infinite}"
        + extra + "</style>"
    )


def discrete(attr: str, events: list[tuple[float, float]], cycle: float) -> str:
    """SMIL discrete animation from (time, value) events over a repeating cycle."""
    events = sorted(events)
    if not events or events[0][0] > 0:
        events.insert(0, (0.0, events[0][1] if events else 0.0))
    times, values = [], []
    for t, v in events:
        # keyTimes must be strictly increasing *after* formatting.
        k = round(min(max(t / cycle, 0.0), 1.0), 5)
        if times and k <= times[-1]:
            values[-1] = v
            continue
        times.append(k)
        values.append(v)
    return (
        f'<animate attributeName="{attr}" dur="{num(cycle)}s" repeatCount="indefinite" '
        f'calcMode="discrete" keyTimes="{";".join(f"{t:.5f}".rstrip("0").rstrip(".") or "0" for t in times)}" '
        f'values="{";".join(num(v) for v in values)}"/>'
    )


def wrap(text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines


def pill(x: float, y: float, label: str, dot: str = ACCENT) -> str:
    """Status pill: red pulse + label, used once per card."""
    w = text_width(label, 10.5, 1.4) + 32
    return (
        f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="26" rx="3" fill="{BG0}" fill-opacity=".8" stroke="{LINE}"/>'
        f'<circle class="pulse" cx="{num(x + 14)}" cy="{num(y + 13)}" r="3.2" fill="{dot}"/>'
        f'<text x="{num(x + 25)}" y="{num(y + 17)}" font-size="10.5" font-weight="700" letter-spacing="1.4" fill="{SOFT}">{esc(label)}</text>'
    )


# --------------------------------------------------------------------------- hero

def typing_track(phrases, x: float, y: float, size: float, slot: float, cid: str):
    """Type / hold / erase each phrase in turn, with one shared block cursor."""
    cw = size * 0.6
    cycle = slot * len(phrases)
    defs, body, cursor_events = [], [], []
    for i, segments in enumerate(phrases):
        length = sum(len(t) for t, _ in segments)
        start = i * slot + 0.2
        hold_end = (i + 1) * slot - 0.6
        erase = 0.32
        events = [(0.0, 0.0)]
        for k in range(length + 1):
            events.append((start + k * 0.042, k * cw))
        for k in range(length, -1, -1):
            events.append((hold_end + (length - k) * erase / length, k * cw))
        cursor_events += [(t, x + v) for t, v in events[1:]]
        defs.append(
            f'<clipPath id="{cid}{i}"><rect x="{num(x)}" y="{num(y - size)}" width="0" '
            f'height="{num(size * 1.5)}">{discrete("width", events, cycle)}</rect></clipPath>'
        )
        spans = "".join(f'<tspan class="{cls}">{esc(t)}</tspan>' for t, cls in segments)
        body.append(f'<text clip-path="url(#{cid}{i})" x="{num(x)}" y="{num(y)}" font-size="{num(size)}">{spans}</text>')
    cursor = (
        f'<rect class="blink" x="{num(x)}" y="{num(y - size * 0.82)}" width="{num(cw)}" '
        f'height="{num(size * 1.05)}" fill="{ACCENT}">{discrete("x", cursor_events, cycle)}</rect>'
    )
    return "".join(defs), "".join(body) + cursor


def globe(cx: float, cy: float, r: float) -> str:
    """Wireframe globe that spins (meridian widths follow |sin|) with a tilted orbit."""
    out = []
    period = 24.0
    samples = 36
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r * 1.6}" fill="url(#globeGlow)"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#0d0d0f" stroke="{STEEL}" stroke-opacity=".5" stroke-width="1.1"/>')
    for lat in (-60, -30, 0, 30, 60):
        rad = math.radians(lat)
        rx = r * math.cos(rad)
        out.append(
            f'<ellipse cx="{cx}" cy="{num(cy - r * math.sin(rad))}" rx="{num(rx)}" ry="{num(rx * .22)}" '
            f'fill="none" stroke="{STEEL}" stroke-opacity="{".14" if lat else ".28"}" stroke-width=".8"/>'
        )
    values = ";".join(num(r * abs(math.sin(2 * math.pi * j / samples))) for j in range(samples + 1))
    for k in range(6):
        out.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r}" fill="none" stroke="{STEEL}" '
            f'stroke-opacity=".22" stroke-width=".8"><animate attributeName="rx" dur="{period}s" '
            f'begin="{num(-period * k / 12)}s" repeatCount="indefinite" values="{values}"/></ellipse>'
        )
    nodes = [(-40, .3), (-12, 1.4), (8, 2.6), (25, 3.9), (44, 5.1), (-28, 4.4), (55, .9), (15, 5.8)]
    for i, (lat_deg, lon) in enumerate(nodes):
        lat = math.radians(lat_deg)
        xs, ops = [], []
        for j in range(samples + 1):
            a = lon + 2 * math.pi * j / samples
            xs.append(num(cx + r * math.cos(lat) * math.sin(a)))
            ops.append("1" if math.cos(a) > 0 else ".08")
        color = ACCENT if i % 3 == 0 else TEXT
        out.append(
            f'<circle cy="{num(cy - r * math.sin(lat))}" r="{2.8 if color == ACCENT else 1.9}" fill="{color}">'
            f'<animate attributeName="cx" dur="{period}s" repeatCount="indefinite" values="{";".join(xs)}"/>'
            f'<animate attributeName="opacity" dur="{period}s" repeatCount="indefinite" values="{";".join(ops)}"/>'
            "</circle>"
        )
    orbit = f"M {num(cx - r * 1.55)} {cy} a {num(r * 1.55)} {num(r * .36)} 0 1 0 {num(r * 3.1)} 0 a {num(r * 1.55)} {num(r * .36)} 0 1 0 {num(-r * 3.1)} 0"
    out.append(
        f'<g transform="rotate(-16 {cx} {cy})"><path d="{orbit}" fill="none" stroke="{GOLD}" '
        f'stroke-opacity=".45" stroke-width=".9" stroke-dasharray="1 5"/>'
    )
    for begin, color in (("0s", ACCENT), ("-6s", TEXT)):
        out.append(
            f'<circle r="3.2" fill="{color}"><animateMotion dur="12s" begin="{begin}" '
            f'repeatCount="indefinite" path="{orbit}"/></circle>'
        )
    out.append("</g>")
    return "".join(out)


def hero() -> str:
    W, H = 980, 400
    phrases = [
        [("shipping ", "p"), ("Zonr", "k"), (" — an AI goal planner", "p")],
        [("guarding vision-AI with ", "p"), ("LensGuard", "k")],
        [("building ", "p"), ("agent skills", "k"), (" for Play review", "p")],
        [("turning ", "p"), ("ML prototypes", "k"), (" into products", "p")],
    ]
    type_defs, type_body = typing_track(phrases, 128, 326, 15, 5.0, "tp")
    title_size = 150
    title_w = measure("AY-MR", title_size, "Anton", spacing=4)
    style = base_style(
        "@keyframes leak{0%,100%{opacity:.35;transform:translateX(0)}50%{opacity:.8;transform:translateX(50px)}}"
        ".leak{animation:leak 10s ease-in-out infinite}"
        "@keyframes intro{0%{opacity:0;transform:translateY(12px)}35%{opacity:1}42%{opacity:.25}"
        "50%{opacity:1}100%{opacity:1;transform:translateY(0)}}"
        ".intro{opacity:0;animation:intro 1.1s .5s ease-out forwards}"
        ".intro0{opacity:0;animation:fadein 1s .2s ease-out forwards}"
        ".intro2{opacity:0;animation:fadein 1s 1.5s ease-out forwards}"
        "@keyframes ghost{0%,86%,100%{opacity:0;transform:translate(0,0)}"
        "87%{opacity:.85;transform:translate(-6px,1px);clip-path:inset(10% 0 58% 0)}"
        "89%{transform:translate(5px,-1px);clip-path:inset(60% 0 8% 0)}"
        "91%{transform:translate(-3px,0);clip-path:inset(32% 0 40% 0)}"
        "93%{opacity:.85;transform:translate(4px,1px);clip-path:inset(0 0 76% 0)}"
        "94%{opacity:0}}"
        ".ghost{animation:ghost 8s 2.6s infinite steps(1)}"
        f".p{{fill:{SOFT}}}.k{{fill:{TEXT};font-weight:700}}"
        "@keyframes bar{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        ".ubar{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:bar 1s 1.2s cubic-bezier(.2,.9,.2,1) forwards}"
        "@keyframes rise{from{opacity:0;transform:scale(.92)}to{opacity:1;transform:scale(1)}}"
        ".globe{opacity:0;transform-origin:790px 205px;animation:rise 1.6s .3s cubic-bezier(.2,.8,.2,1) forwards}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">AY-MR — AI product engineer</title>
<desc id="d">Cinematic title card: AY-MR, AI product engineer in Taiwan, building Zonr, LensGuard and agent tooling.</desc>
{style}
<defs>
<clipPath id="frame"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20"/></clipPath>
<radialGradient id="warm" cx="8%" cy="95%" r="65%"><stop offset="0" stop-color="#3a120d" stop-opacity=".75"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<radialGradient id="cool" cx="80%" cy="52%" r="48%"><stop offset="0" stop-color="#1a1d22" stop-opacity=".9"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<radialGradient id="globeGlow"><stop offset="0" stop-color="{STEEL}" stop-opacity=".09"/><stop offset="1" stop-color="{STEEL}" stop-opacity="0"/></radialGradient>
<radialGradient id="vig" cx="50%" cy="50%" r="75%"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".7"/></radialGradient>
<linearGradient id="leakG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff6a3d" stop-opacity=".16"/><stop offset=".5" stop-color="#ff6a3d" stop-opacity="0"/></linearGradient>
<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="170" y2="0">
<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
<animateTransform attributeName="gradientTransform" type="translate" values="-220 0;-220 0;{num(title_w + 260)} 0" keyTimes="0;.55;1" dur="6.5s" begin="1.8s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="border" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".9"/><stop offset=".3" stop-color="{LINE}"/><stop offset="1" stop-color="{LINE}"/>
<animateTransform attributeName="gradientTransform" type="rotate" from="0 .5 .5" to="360 .5 .5" dur="14s" repeatCount="indefinite"/></linearGradient>
{grain()}
{type_defs}
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect width="{W}" height="{H}" fill="url(#warm)"/>
<rect width="{W}" height="{H}" fill="url(#cool)"/>
<g class="globe">{globe(790, 205, 118)}</g>

<rect x="0" y="0" width="{W}" height="36" fill="#000" fill-opacity=".45"/>
<path d="M0 36.5H{W}" stroke="{LINE}"/>
{window_dots(18)}
<text x="{W - 24}" y="22.5" text-anchor="end" font-size="10.5" font-weight="700" letter-spacing="1.5" fill="{ACCENT}"><tspan class="blink">●</tspan> REC</text>

<text class="intro0" x="46" y="112" font-size="12" letter-spacing="3.2" fill="{MUTED}">AI PRODUCT ENGINEER · TAIWAN</text>
<g class="intro">
<text class="dp ghost" x="40" y="270" font-size="{title_size}" letter-spacing="4" fill="{ACCENT}">AY-MR</text>
<text class="dp" x="40" y="270" font-size="{title_size}" letter-spacing="4" fill="{TEXT}">AY-MR</text>
<text class="dp" x="40" y="270" font-size="{title_size}" letter-spacing="4" fill="url(#shine)" opacity=".55">AY-MR</text>
</g>
<rect class="ubar" x="46" y="288" width="72" height="4" fill="{ACCENT}"/>
<g class="intro2">
<text x="46" y="326" font-size="15" fill="{ACCENT}" font-weight="700">$ <tspan fill="{STEEL}">./now</tspan></text>
{type_body}
</g>

<rect class="leak" x="-80" y="0" width="560" height="{H}" fill="url(#leakG)"/>
{grain_layer(W, H, moving=True)}
<rect width="{W}" height="{H}" fill="url(#vig)"/>
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="none" stroke="url(#border)" stroke-width="1.4"/>
</svg>'''


# ------------------------------------------------------------------------ buttons

def rect_perimeter(w: float, h: float, r: float) -> float:
    return 2 * (w + h) - (8 - 2 * math.pi) * r


def button(label: str, glyph: str) -> str:
    W, H, R = 232, 56, 10
    per = rect_perimeter(W - 2, H - 2, R)
    style = base_style(
        f"@keyframes run{{from{{stroke-dashoffset:0}}to{{stroke-dashoffset:-{num(per)}}}}}"
        ".run{animation:run 4.2s linear infinite}"
        "@keyframes nudge{0%,60%,100%{transform:translateX(0)}75%{transform:translateX(4px)}}"
        ".arr{animation:nudge 2.4s ease-in-out infinite}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">
{style}
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{R}" fill="{PANEL}" stroke="{LINE}"/>
<rect class="run" x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{R}" fill="none" stroke="{ACCENT}" stroke-width="1.4" stroke-linecap="round" stroke-dasharray="38 {num(per - 38)}"/>
<g transform="translate(20 16)">{glyph}</g>
<text x="58" y="36" class="dp" font-size="20" letter-spacing="1.6" fill="{TEXT}">{esc(label)}</text>
<g class="arr"><text x="{W - 20}" y="34" text-anchor="end" font-size="15" font-weight="700" fill="{ACCENT}">-&gt;</text></g>
</svg>'''


def glyph_lens(color: str) -> str:
    return (
        f'<circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="12" cy="12" r="5.5" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="12" cy="12" r="1.8" fill="{ACCENT}"/>'
    )


def glyph_orbit(color: str) -> str:
    return (
        f'<circle cx="12" cy="12" r="4.5" fill="{color}"/>'
        f'<ellipse cx="12" cy="12" rx="11" ry="4.5" fill="none" stroke="{color}" stroke-width="1.3" transform="rotate(-25 12 12)"/>'
        f'<circle cx="21.5" cy="7.6" r="2" fill="{ACCENT}"><animate attributeName="opacity" values="1;.2;1" dur="1.6s" repeatCount="indefinite"/></circle>'
    )


def glyph_image(uri: str, rx: float = 12) -> str:
    return (
        f'<clipPath id="ic"><rect width="24" height="24" rx="{rx}"/></clipPath>'
        f'<image href="{uri}" width="24" height="24" clip-path="url(#ic)"/>'
    )


def buttons() -> dict[str, str]:
    planet = data_uri(ASSETS / "brand" / "zonr-planet.jpg", "image/jpeg")
    return {
        "btn-zonr.svg": button("ZONR.PRO", glyph_image(planet)),
        "btn-lensguard.svg": button("LENSGUARD", glyph_lens(TEXT)),
        "btn-email.svg": button("EMAIL", icon(ICONS, "gmail", 0, 0, 24, TEXT)),
        "btn-orbit.svg": button("JOIN ORBIT", glyph_orbit(TEXT)),
    }


# ----------------------------------------------------------------------- headers

def header(index: str, title: str) -> str:
    """Section slate: its own dark panel so it reads on light and dark GitHub themes."""
    W, H = 980, 72
    style = base_style(
        "@keyframes sweep{from{transform:translateX(-160px)}to{transform:translateX(1000px)}}"
        ".sw{animation:sweep 6s cubic-bezier(.6,0,.4,1) infinite}"
    )
    tw = measure(title, 34, "Anton", spacing=2)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">
{style}
<defs><linearGradient id="s" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/><stop offset=".5" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient>
<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="12"/></clipPath>{grain()}</defs>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<text x="26" y="45" font-size="13" font-weight="700" fill="{ACCENT}">{esc(index)}</text>
<rect x="56" y="22" width="1" height="28" fill="{LINE}"/>
<text x="74" y="49" class="dp" font-size="34" letter-spacing="2" fill="{TEXT}">{esc(title)}</text>
<rect class="blink" x="{num(82 + tw)}" y="26" width="12" height="23" fill="{ACCENT}"/>
<rect class="sw" x="0" y="{H - 3}" width="160" height="3" fill="url(#s)"/>
{grain_layer(W, H)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="12" fill="none" stroke="{LINE}"/>
</svg>'''


HEADERS = {
    "h-work.svg": ("01", "SELECTED WORK"),
    "h-journey.svg": ("02", "THE JOURNEY"),
    "h-stack.svg": ("03", "TECH STACK"),
    "h-activity.svg": ("04", "ENGINEERING ACTIVITY"),
    "h-orbit.svg": ("05", "THE ORBIT"),
}


# ------------------------------------------------------------------------- cards

def card_shell(W: float, H: float, accent: str, body: str, extra_style: str = "", extra_defs: str = "", label: str = "") -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">
{base_style(extra_style)}
<defs>
<radialGradient id="glow" cx="78%" cy="40%" r="55%"><stop offset="0" stop-color="{accent}" stop-opacity=".09"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{accent}" stop-opacity=".55"/><stop offset=".35" stop-color="{LINE}"/><stop offset="1" stop-color="{LINE}"/></linearGradient>
<clipPath id="cardclip"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>
{grain()}
{extra_defs}
</defs>
<g clip-path="url(#cardclip)">
<rect width="{W}" height="{H}" fill="{PANEL}"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>
{body}
{grain_layer(W, H)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="url(#edge)" stroke-width="1.2"/>
</svg>'''


def sparkle(x: float, y: float, s: float, color: str, delay: float) -> str:
    d = f"M0 {-s} C {s * .15} {-s * .15} {s * .15} {-s * .15} {s} 0 C {s * .15} {s * .15} {s * .15} {s * .15} 0 {s} C {-s * .15} {s * .15} {-s * .15} {s * .15} {-s} 0 C {-s * .15} {-s * .15} {-s * .15} {-s * .15} 0 {-s} Z"
    return f'<g transform="translate({num(x)} {num(y)})"><path class="tw" style="animation-delay:{delay}s" d="{d}" fill="{color}"/></g>'


def card_zonr() -> str:
    """Wide feature card: the shipped product gets the most room."""
    W, H = 980, 320
    uri = data_uri(ASSETS / "brand" / "zonr-planet.jpg", "image/jpeg")
    cx, cy, r = 742, 160, 112
    back = f"M {cx - 172} {cy + 12} A 172 40 0 0 1 {cx + 172} {cy - 12}"
    front = f"M {cx + 172} {cy - 12} A 172 40 0 0 1 {cx - 172} {cy + 12}"
    lines = wrap("Turns a stalled, deadline-driven goal into today's next step.", 38)
    tagline = "".join(
        f'<text x="48" y="{196 + i * 26}" font-size="17" fill="{SOFT}">{esc(t)}</text>' for i, t in enumerate(lines)
    )
    body = f'''
<g transform="rotate(-12 {cx} {cy})"><path d="{back}" fill="none" stroke="{GOLD}" stroke-opacity=".35" stroke-width="1" stroke-dasharray="2 5"/></g>
<circle cx="{cx}" cy="{cy}" r="{r + 22}" fill="url(#halo)"/>
<g class="drift"><clipPath id="pl"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>
<image href="{uri}" x="{num(cx - r * 1.19)}" y="{num(cy - r * 1.2)}" width="{num(r * 2.55)}" height="{num(r * 2.55)}" clip-path="url(#pl)"/>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#terminator)"/>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GOLD}" stroke-opacity=".22"/></g>
<g transform="rotate(-12 {cx} {cy})"><path d="{front}" fill="none" stroke="{GOLD}" stroke-width="1.4" stroke-opacity=".85"/>
<circle r="4.5" fill="{TEXT}"><animateMotion dur="6s" repeatCount="indefinite" path="{front}"/>
<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.12;.88;1" dur="6s" repeatCount="indefinite"/></circle></g>
{sparkle(cx - 150, cy - 96, 7, GOLD, 0)}{sparkle(cx + 138, cy - 104, 5, TEXT, 1)}{sparkle(cx + 160, cy + 92, 6, GOLD, 2)}
<text x="48" y="62" font-size="11.5" font-weight="700" letter-spacing="2.4" fill="{GOLD}">01 <tspan fill="{DIM}">—</tspan> <tspan fill="{MUTED}">SHIPPED APP</tspan></text>
<text class="dp" x="44" y="150" font-size="84" letter-spacing="2" fill="{TEXT}">ZONR</text>
{tagline}
<text x="48" y="{196 + len(lines) * 26 + 10}" font-size="13" fill="{GOLD}">WorldSkills BeChangeMaker 2026 — Global Top 15</text>
{pill(48, 270, "LIVE ON iOS + ANDROID")}
<text x="{num(48 + text_width("LIVE ON iOS + ANDROID", 10.5, 1.4) + 52)}" y="288" font-size="14" font-weight="700" fill="{ACCENT}">zonr.pro -&gt;</text>
'''
    return card_shell(
        W, H, GOLD, body, label="Zonr — turns a stalled, deadline-driven goal into today's next step. Live on iOS and Android.",
        extra_defs=(
            f'<radialGradient id="halo"><stop offset=".78" stop-color="{GOLD}" stop-opacity=".12"/><stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="terminator" cx="30%" cy="28%" r="85%"><stop offset=".45" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>'
        ),
        extra_style=(
            "@keyframes tw{0%,100%{transform:scale(.4);opacity:.2}50%{transform:scale(1);opacity:.9}}"
            ".tw{transform-box:fill-box;transform-origin:center;animation:tw 3.6s ease-in-out infinite}"
            "@keyframes drift{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}"
            ".drift{animation:drift 7s ease-in-out infinite}"
        ),
    )


def half_card(index: str, kind: str, title: str, tagline: str, status: str, accent: str, art: str,
              extra_style: str = "", extra_defs: str = "") -> str:
    W, H = 480, 270
    size = min(46.0, 46.0 * 262 / measure(title, 46, "Anton", spacing=1))  # keep clear of the art
    lines = "".join(
        f'<text x="30" y="{144 + i * 22}" font-size="14" fill="{SOFT}">{esc(t)}</text>'
        for i, t in enumerate(wrap(tagline, 28))
    )
    body = f'''{art}
<text x="30" y="50" font-size="11" font-weight="700" letter-spacing="2.2" fill="{accent}">{esc(index)} <tspan fill="{DIM}">—</tspan> <tspan fill="{MUTED}">{esc(kind)}</tspan></text>
<text class="dp" x="28" y="110" font-size="{num(size)}" letter-spacing="1" fill="{TEXT}">{esc(title)}</text>
{lines}
{pill(30, 222, status)}
<text x="{W - 28}" y="240" text-anchor="end" font-size="14" font-weight="700" fill="{ACCENT}">open -&gt;</text>
'''
    return card_shell(W, H, accent, body, extra_style, extra_defs, label=f"{title} — {tagline}")


def card_lensguard() -> str:
    cx, cy = 384, 112
    blades = "".join(
        f'<path d="M {cx} {cy} L {num(cx + 42 * math.cos(math.radians(a)))} {num(cy + 42 * math.sin(math.radians(a)))} '
        f'L {num(cx + 42 * math.cos(math.radians(a + 60)))} {num(cy + 42 * math.sin(math.radians(a + 60)))} Z" '
        f'fill="{TEXT}" fill-opacity="{.03 + (i % 2) * .04:.2f}" stroke="{STEEL}" stroke-opacity=".45" stroke-width=".8"/>'
        for i, a in enumerate(range(0, 360, 60))
    )
    art = f'''
<circle cx="{cx}" cy="{cy}" r="70" fill="none" stroke="{STEEL}" stroke-opacity=".18" stroke-dasharray="2 4"/>
<circle cx="{cx}" cy="{cy}" r="57" fill="#0c0c0e" stroke="{STEEL}" stroke-opacity=".6" stroke-width="1.4"/>
<g class="iris">{blades}</g>
<circle cx="{cx}" cy="{cy}" r="15" fill="#050506" stroke="{STEEL}" stroke-width="1.1"/>
<circle cx="{cx}" cy="{cy}" r="4.5" fill="{ACCENT}" class="pulse"/>
<circle cx="{cx - 6}" cy="{cy - 6}" r="2.8" fill="#fff" fill-opacity=".55"/>
<g class="sweep"><path d="M {cx} {cy} L {cx + 57} {cy} A 57 57 0 0 0 {num(cx + 57 * math.cos(math.radians(-38)))} {num(cy + 57 * math.sin(math.radians(-38)))} Z" fill="url(#beam)"/></g>
<g class="stamp"><rect x="{cx - 52}" y="{cy + 78}" width="104" height="26" rx="2" fill="{ACCENT}"/>
<text x="{cx}" y="{cy + 97}" text-anchor="middle" class="dp" font-size="16" letter-spacing="4" fill="{TEXT}">BLOCKED</text></g>
'''
    return half_card(
        "02", "OPEN SOURCE", "LENSGUARD",
        "Blocks prompt injections hidden in what vision-AI assistants see.",
        "TEAM BUILD", ACCENT, art,
        extra_defs=f'<linearGradient id="beam" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/><stop offset="1" stop-color="{ACCENT}" stop-opacity=".35"/></linearGradient>',
        extra_style=(
            "@keyframes spin{to{transform:rotate(360deg)}}"
            f".iris{{transform-origin:{cx}px {cy}px;animation:spin 22s linear infinite}}"
            f".sweep{{transform-origin:{cx}px {cy}px;animation:spin 3.4s linear infinite}}"
            "@keyframes stamp{0%,40%{opacity:0;transform:scale(1.7) rotate(-6deg)}48%{opacity:1;transform:scale(.94) rotate(-6deg)}"
            "54%,90%{opacity:1;transform:scale(1) rotate(-6deg)}100%{opacity:0;transform:scale(1) rotate(-6deg)}}"
            ".stamp{transform-box:fill-box;transform-origin:center;animation:stamp 4.4s ease-out infinite}"
        ),
    )


def card_preflight() -> str:
    x0, y0, w, h = 326, 46, 128, 140
    rows = []
    for i, bar in enumerate((70, 52, 62, 44, 58)):
        y = y0 + 38 + i * 21
        d = 0.35 + i * 0.45
        rows.append(
            f'<rect x="{x0 + 14}" y="{y - 10}" width="13" height="13" rx="2" fill="none" stroke="{STEEL}" stroke-opacity=".5"/>'
            f'<path class="tick" style="animation-delay:{d:.2f}s" d="M {x0 + 17} {y - 3.5} l 3 3 l 5.5 -6" fill="none" stroke="{TEXT}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" pathLength="1"/>'
            f'<rect x="{x0 + 36}" y="{y - 5}" width="{bar}" height="4" rx="2" fill="{STEEL}" fill-opacity=".28"/>'
        )
    art = f'''
<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="6" fill="#0c0c0e" stroke="{LINE}"/>
<rect x="{x0}" y="{y0}" width="{w}" height="20" rx="6" fill="#1a1a1d"/>
{"".join(f'<circle cx="{x0 + 12 + k * 9}" cy="{y0 + 10}" r="2.4" fill="#3a3a3f"/>' for k in range(3))}
{icon(ICONS, "android", x0 + w - 22, y0 + 4, 12, STEEL)}
{"".join(rows)}
<g class="ready"><rect x="{x0 + 16}" y="{y0 + 54}" width="102" height="32" rx="2" fill="{BG0}" fill-opacity=".6" stroke="{ACCENT}" stroke-width="2.2"/>
<text x="{x0 + 67}" y="{y0 + 77}" text-anchor="middle" class="dp" font-size="18" letter-spacing="3" fill="{ACCENT}">APPROVED</text></g>
'''
    return half_card(
        "03", "AGENT SKILL", "PLAY PREFLIGHT",
        "Catches Google Play review blockers before you hit submit.",
        "OPEN SOURCE", STEEL, art,
        extra_style=(
            "@keyframes tick{0%{stroke-dashoffset:1}12%,88%{stroke-dashoffset:0}100%{stroke-dashoffset:1}}"
            ".tick{stroke-dasharray:1;stroke-dashoffset:1;animation:tick 5s ease-out infinite}"
            "@keyframes ready{0%,52%{opacity:0;transform:scale(1.6) rotate(-8deg)}60%{opacity:1;transform:scale(.95) rotate(-8deg)}66%,88%{opacity:1;transform:scale(1) rotate(-8deg)}100%{opacity:0;transform:scale(1) rotate(-8deg)}}"
            ".ready{transform-box:fill-box;transform-origin:center;animation:ready 5s ease-out infinite}"
        ),
    )


# -------------------------------------------------------------------- store pills

def store_badge(label: str, glyph: str) -> str:
    W, H = 190, 52
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">
{base_style("")}
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="8" fill="#000" stroke="{LINE}"/>
<rect x="1" y="{H - 3}" width="{W - 2}" height="2" fill="{ACCENT}" fill-opacity=".8"/>
<g transform="translate(18 14)">{glyph}</g>
<text x="56" y="34" class="dp" font-size="19" letter-spacing="1.4" fill="{TEXT}">{esc(label)}</text>
</svg>'''


def store_badges() -> dict[str, str]:
    planet = data_uri(ASSETS / "brand" / "zonr-planet.jpg", "image/jpeg")
    return {
        "store-web.svg": store_badge("ZONR.PRO", glyph_image(planet)),
        "store-ios.svg": store_badge("APP STORE", icon(ICONS, "apple", 0, 0, 24, TEXT)),
        "store-play.svg": store_badge("GOOGLE PLAY", icon(ICONS, "googleplay", 0, 0, 24, TEXT)),
    }


# ------------------------------------------------------------------------ journey

JOURNEY = [  # (stamp, title, line) — only publicly verifiable milestones
    ("ORIGINS", "ML SNAKE", "a DQN agent learns Snake"),
    ("2026", "ZONR SHIPS", "live on iOS + Google Play"),
    ("2026", "GLOBAL TOP 15", "WorldSkills BeChangeMaker"),
    ("2026.06", "PLAY PREFLIGHT", "open-source agent skill"),
    ("2026.09", "LENSGUARD", "vision-AI safety, team build"),
    ("NEXT", "NEXT FRAME", "rendering…"),
]


def journey() -> str:
    W, H = 980, 210
    fw, gap = 300, 14
    strip_w = len(JOURNEY) * (fw + gap)
    top, bottom = 14, 196
    frame_h = bottom - top - 44
    frames = []
    for copy in range(2):  # two copies make the scroll seamless
        for i, (stamp, title, line) in enumerate(JOURNEY):
            x = copy * strip_w + i * (fw + gap) + 7
            hot = stamp == "NEXT"
            frames.append(
                f'<g transform="translate({x} {top + 22})">'
                f'<rect width="{fw}" height="{frame_h}" rx="3" fill="#141416" stroke="{ACCENT if hot else LINE}" stroke-opacity="{.7 if hot else 1}"/>'
                f'<rect width="{fw}" height="{frame_h}" rx="3" fill="url(#frameVig)"/>'
                f'<text x="20" y="34" font-size="11.5" font-weight="700" letter-spacing="2" fill="{ACCENT}">{esc(stamp)}</text>'
                f'<text x="18" y="84" class="dp" font-size="36" letter-spacing="1.2" fill="{TEXT}">{esc(title)}</text>'
                f'<text x="20" y="114" font-size="13" fill="{MUTED}">{esc(line)}</text>'
                "</g>"
            )
    holes = []
    for copy in range(2):
        for k in range(int(strip_w / 24) + 1):
            x = copy * strip_w + k * 24 + 6
            holes.append(f'<rect x="{x}" y="{top + 6}" width="12" height="9" rx="2" fill="{BG0}"/>')
            holes.append(f'<rect x="{x}" y="{bottom - 15}" width="12" height="9" rx="2" fill="{BG0}"/>')
    style = base_style(
        f"@keyframes reel{{from{{transform:translateX(0)}}to{{transform:translateX(-{strip_w}px)}}}}"
        ".reel{animation:reel 80s linear infinite}"
        "@keyframes flicker{0%,100%{opacity:0}7%{opacity:.05}9%{opacity:0}53%{opacity:.03}55%{opacity:0}}"
        ".flk{animation:flicker 2.2s steps(1) infinite}"
    )
    alt = " / ".join(f"{s} {t}: {a}" for s, t, a in JOURNEY)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Journey film strip — {esc(alt)}">
{style}
<defs>
<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>
<radialGradient id="frameVig" cx="40%" cy="35%" r="80%"><stop offset=".5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".45"/></radialGradient>
<linearGradient id="edgeFade" x1="0" x2="1"><stop offset="0" stop-color="{BG0}"/><stop offset=".08" stop-color="{BG0}" stop-opacity="0"/><stop offset=".92" stop-color="{BG0}" stop-opacity="0"/><stop offset="1" stop-color="{BG0}"/></linearGradient>
{grain()}
</defs>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect x="0" y="{top}" width="{W}" height="{bottom - top}" fill="#1b1b1e"/>
<g class="reel">{"".join(holes)}{"".join(frames)}</g>
<rect x="0" y="{top}" width="{W}" height="{bottom - top}" fill="#fff" class="flk"/>
<rect width="{W}" height="{H}" fill="url(#edgeFade)"/>
{grain_layer(W, H, moving=True)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="{LINE}"/>
</svg>'''


# ------------------------------------------------------------------------- stack

STACK = [
    ("AI / ML", [("python", "Python"), ("pytorch", "PyTorch"), ("tensorflow", "TensorFlow"), ("opencv", "OpenCV"), ("nvidia", "NVIDIA")]),
    ("PRODUCT", [("typescript", "TypeScript"), ("react", "React"), ("nextdotjs", "Next.js"), ("nodedotjs", "Node.js"), ("fastapi", "FastAPI")]),
    ("SYSTEMS", [("rust", "Rust"), ("cplusplus", "C++"), ("sqlite", "SQLite"), ("docker", "Docker"), ("cloudflare", "Cloudflare")]),
]


def stack() -> str:
    W = 980
    tile, gap, x0 = 112, 22, 290
    row_h = 132
    H = 28 + row_h * len(STACK)
    rows, n = [], 0
    for r, (name, items) in enumerate(STACK):
        y = 20 + r * row_h
        rows.append(
            f'<text x="36" y="{y + 66}" class="dp" font-size="30" letter-spacing="2" fill="{TEXT}">{esc(name)}</text>'
            f'<rect x="38" y="{y + 80}" width="28" height="3" fill="{ACCENT}"/>'
        )
        for c, (slug, label) in enumerate(items):
            x = x0 + c * (tile + gap)
            delay = (c + r * 2) * 0.22
            rows.append(
                f'<g><rect x="{x}" y="{y + 4}" width="{tile}" height="{tile}" rx="10" fill="{PANEL}" stroke="{LINE}"/>'
                f'<rect class="lit" style="animation-delay:{delay:.2f}s" x="{x}" y="{y + 4}" width="{tile}" height="{tile}" rx="10" fill="{ACCENT}" fill-opacity=".05" stroke="{ACCENT}" stroke-width="1.2"/>'
                f'{icon(ICONS, slug, x + tile / 2 - 17, y + 24, 34, TEXT, " fill-opacity=\".9\"")}'
                f'<text x="{x + tile / 2}" y="{y + 94}" text-anchor="middle" font-size="12" fill="{MUTED}">{esc(label)}</text></g>'
            )
            n += 1
    style = base_style(
        "@keyframes lit{0%,100%{opacity:0}12%{opacity:1}30%{opacity:0}}"
        ".lit{opacity:0;animation:lit 5.5s ease-in-out infinite}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Tech stack: {n} tools across AI/ML, product and systems">
{style}
<defs>{grain()}<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath></defs>
<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="{BG1}"/>
{"".join(rows)}
{grain_layer(W, H)}</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="{LINE}"/>
</svg>'''


# ----------------------------------------------------------------------- decrypt

ABOUT = [
    ("ROLE", "AI product engineer · Taiwan"),
    ("BUILDING", "Zonr — live on iOS + Android"),
    ("RESEARCH", "LensGuard — safe vision-AI actions"),
    ("CONTACT", "houbaian54@gmail.com"),
]


def decrypt() -> str:
    """Scramble -> decrypt -> unlock, then re-encrypt and loop.

    Driven by one SMIL master clock (`clk`) because the README shows this inside
    a <details> panel: GitHub strips loading="lazy", so the image starts with the
    page and a one-shot animation would be over before anyone clicks.
    """
    W = 980
    row_h = 40
    H = 104 + len(ABOUT) * row_h + 14
    cycle = 12.0
    rng = random.Random(3)
    noise = "ABCDEF0123456789#$%&*+=<>/\\[]{}?!"
    frames = 7
    step = 0.06
    hide_at = cycle - 0.7  # re-encrypt shortly before the loop restarts

    def at(t: float) -> str:
        return f"clk.begin+{t:.2f}s"

    def show(t: float, until: float) -> str:
        return f'<set attributeName="opacity" to="1" begin="{at(t)}" dur="{until - t:.2f}s"/>'

    body = []
    for i, (key, value) in enumerate(ABOUT):
        y = 124 + i * row_h
        start = 1.2 + i * 0.32
        body.append(
            f'<text x="48" y="{y}" opacity="0" font-size="12.5" font-weight="700" letter-spacing="2.4" fill="{MUTED}">{key}'
            f'{show(start - .2, hide_at)}</text>'
        )
        for f in range(frames):
            garbage = "".join(" " if ch == " " else rng.choice(noise) for ch in value)
            t = start + f * step
            body.append(f'<text opacity="0" x="210" y="{y}" font-size="18" fill="{DIM}">{esc(garbage)}{show(t, t + step)}</text>')
        reveal = start + frames * step
        body.append(f'<text opacity="0" x="210" y="{y}" font-size="18" fill="{TEXT}">{esc(value)}{show(reveal, hide_at)}</text>')
        garbage = "".join(" " if ch == " " else rng.choice(noise) for ch in value)
        body.append(
            f'<text opacity="0" x="210" y="{y}" font-size="18" fill="{ACCENT}" fill-opacity=".85">{esc(garbage)}{show(hide_at, hide_at + .35)}</text>'
        )
    bar_w = 440
    done = 1.2 + len(ABOUT) * 0.32 + frames * step
    lx, ly = 850, H / 2 + 4
    gw = measure("ACCESS GRANTED", 16, "Anton", spacing=2.4) + 26
    unlocked = f'begin="{at(done)}" dur="{hide_at - done:.2f}s"'
    k1, k2 = 1 / cycle, hide_at / cycle
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Decrypted profile: {esc(" / ".join(v for _, v in ABOUT))}">
{base_style("")}
<defs><clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>
<linearGradient id="wg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{TEXT}" stop-opacity="0"/><stop offset="1" stop-color="{TEXT}" stop-opacity=".08"/></linearGradient>
<radialGradient id="warm" cx="85%" cy="50%" r="45%"><stop offset="0" stop-color="#2e0f0b" stop-opacity=".7"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
{grain()}</defs>
<rect width="0" height="0"><animate id="clk" attributeName="x" from="0" to="0" begin="0s;clk.end" dur="{cycle}s"/></rect>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect width="{W}" height="{H}" fill="url(#warm)"/>
<text x="48" y="52" font-size="14" fill="{MUTED}"><tspan fill="{ACCENT}" font-weight="700">$</tspan> decrypt ./about.enc</text>
<rect x="48" y="68" width="{bar_w}" height="3" fill="{LINE}"/>
<rect x="48" y="68" width="0" height="3" fill="{ACCENT}">
<animate attributeName="width" values="0;{bar_w};{bar_w};0" keyTimes="0;{k1:.4f};{k2:.4f};1" begin="{at(.15)}" dur="{cycle - .15:.2f}s" calcMode="spline" keySplines=".3 .7 .2 1;0 0 1 1;.4 0 1 1"/></rect>
<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -13;0 -13;0 0" keyTimes="0;.06;.94;1" {unlocked}/>
<path d="M {lx - 20} {ly - 6} v -18 a 20 20 0 0 1 40 0 v 18" fill="none" stroke="{STEEL}" stroke-width="6" stroke-linecap="round"><set attributeName="stroke" to="{ACCENT}" {unlocked}/></path></g>
<rect x="{lx - 34}" y="{ly - 8}" width="68" height="54" rx="7" fill="#141416" stroke="{STEEL}" stroke-width="2.4"><set attributeName="stroke" to="{ACCENT}" {unlocked}/></rect>
<circle cx="{lx}" cy="{ly + 13}" r="6" fill="{TEXT}"/><rect x="{lx - 2.5}" y="{ly + 15}" width="5" height="14" rx="2.5" fill="{TEXT}"/>
<g opacity="0">{show(done + .2, hide_at)}<rect x="{num(lx - gw / 2)}" y="{ly + 62}" width="{num(gw)}" height="28" rx="2" fill="{ACCENT}"/>
<text x="{lx}" y="{ly + 82}" text-anchor="middle" class="dp" font-size="16" letter-spacing="2.4" fill="{TEXT}">ACCESS GRANTED</text></g>
{"".join(body)}
<rect x="0" y="-30" width="{W}" height="30" fill="url(#wg)"><animateTransform attributeName="transform" type="translate" from="0 0" to="0 {H + 30}" begin="{at(done)}" dur="1.4s"/></rect>
{grain_layer(W, H)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="{LINE}"/>
</svg>'''


# ------------------------------------------------------------------------ footer

def footer() -> str:
    W, H = 980, 130
    line = "build -> measure -> ship -> learn"
    lw = text_width(line, 15)
    style = base_style(
        "@keyframes flow{from{transform:translateX(-100%)}to{transform:translateX(100%)}}"
        ".flow{animation:flow 5s cubic-bezier(.6,0,.4,1) infinite}"
        "@keyframes fin{0%,100%{opacity:.8}50%{opacity:1}}"
        ".fin{animation:fin 4s ease-in-out infinite}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Fin — {esc(line)}">
{style}
<defs><linearGradient id="f" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/><stop offset=".5" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient>
<radialGradient id="warm" cx="50%" cy="120%" r="70%"><stop offset="0" stop-color="#3a120d" stop-opacity=".7"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>
<clipPath id="ty"><rect x="{num(W / 2 - lw / 2)}" y="84" width="0" height="26"><animate attributeName="width" values="0;{num(lw)};{num(lw)};0" keyTimes="0;.35;.85;1" dur="7s" repeatCount="indefinite" calcMode="spline" keySplines=".4 0 .6 1;0 0 1 1;.4 0 .6 1"/></rect></clipPath>{grain()}</defs>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect width="{W}" height="{H}" fill="url(#warm)"/>
<g class="flow"><rect x="0" y="0" width="{W}" height="3" fill="url(#f)"/></g>
<text class="dp fin" x="{W / 2}" y="74" text-anchor="middle" font-size="42" letter-spacing="12" fill="{TEXT}">FIN.</text>
<text x="{W / 2}" y="103" text-anchor="middle" font-size="15" font-weight="700" fill="{SOFT}" clip-path="url(#ty)">{esc(line)}</text>
{grain_layer(W, H)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="{LINE}"/>
</svg>'''


def all_cards() -> dict[str, str]:
    out = {
        "hero.svg": hero(),
        "journey.svg": journey(),
        "stack.svg": stack(),
        "decrypt.svg": decrypt(),
        "footer.svg": footer(),
        "card-zonr.svg": card_zonr(),
        "card-lensguard.svg": card_lensguard(),
        "card-preflight.svg": card_preflight(),
    }
    out.update(buttons())
    out.update(store_badges())
    for name, args in HEADERS.items():
        out[name] = header(*args)
    return out


def main() -> None:
    cards = ASSETS / "cards"
    built = all_cards()
    for stale in cards.glob("*.svg"):  # drop cards that are no longer generated
        if stale.name not in built:
            stale.unlink()
            print(f"removed {stale.relative_to(ROOT)}")
    for name, svg in built.items():
        target = cards / name
        write(target, svg)
        print(f"built {target.relative_to(ROOT)} ({target.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
