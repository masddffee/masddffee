#!/usr/bin/env python3
"""Build the static, hand-animated SVG cards used by the profile README.

These cards only change when the copy changes, so they are generated locally
(or by the workflow when this file changes) instead of on every metrics run.
Animations are pure CSS keyframes + SMIL so they survive GitHub's image proxy:
no scripts, no external requests.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from svgkit import (
    AMBER, BG0, BG1, CJK, CYAN, DIM, FONT_SLOT, LINE, MINT, MONO, MUTED, PANEL,
    PINK, RED, ROOT, TEXT, VIOLET, data_uri, esc, icon, load_icons, num,
    text_width, write,
)

ASSETS = ROOT / "assets"
ICONS = load_icons()
REPO = "https://github.com/masddffee/masddffee"


def base_style(extra: str) -> str:
    return (
        "<style>" + FONT_SLOT +
        f"text{{font-family:{MONO}}}"
        ".cjk{font-family:" + CJK + "}"
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
        f'height="{num(size * 1.05)}" fill="{MINT}">{discrete("x", cursor_events, cycle)}</rect>'
    )
    return "".join(defs), "".join(body) + cursor


def globe(cx: float, cy: float, r: float) -> str:
    out = []
    period = 18.0
    samples = 36
    # Latitude rings (static) and the sphere outline.
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r * 1.55}" fill="url(#globeGlow)"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#06111c" fill-opacity=".55" stroke="{CYAN}" stroke-opacity=".55" stroke-width="1.2"/>')
    for lat in (-60, -30, 0, 30, 60):
        rad = math.radians(lat)
        rx = r * math.cos(rad)
        out.append(
            f'<ellipse cx="{cx}" cy="{num(cy - r * math.sin(rad))}" rx="{num(rx)}" ry="{num(rx * .22)}" '
            f'fill="none" stroke="{CYAN}" stroke-opacity="{".32" if lat else ".5"}" stroke-width=".8"/>'
        )
    # Meridians: great circles whose apparent width follows |sin| as the globe spins.
    values = ";".join(num(r * abs(math.sin(2 * math.pi * j / samples))) for j in range(samples + 1))
    for k in range(6):
        begin = -period * k / 12
        out.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r}" fill="none" stroke="{CYAN}" '
            f'stroke-opacity=".4" stroke-width=".8"><animate attributeName="rx" dur="{period}s" '
            f'begin="{num(begin)}s" repeatCount="indefinite" values="{values}"/></ellipse>'
        )
    # Data nodes riding on the surface; dim when they pass behind the globe.
    rng = random.Random(11)
    nodes = []
    for _ in range(12):
        lat = math.radians(rng.uniform(-58, 62))
        lon = rng.uniform(0, 2 * math.pi)
        xs, ops = [], []
        for j in range(samples + 1):
            a = lon + 2 * math.pi * j / samples
            xs.append(num(cx + r * math.cos(lat) * math.sin(a)))
            ops.append("1" if math.cos(a) > 0 else ".12")
        y = cy - r * math.sin(lat)
        color = rng.choice([MINT, MINT, CYAN, PINK])
        nodes.append((xs, ops, y, color))
        out.append(
            f'<circle cy="{num(y)}" r="2.6" fill="{color}" filter="url(#glow)">'
            f'<animate attributeName="cx" dur="{period}s" repeatCount="indefinite" values="{";".join(xs)}"/>'
            f'<animate attributeName="opacity" dur="{period}s" repeatCount="indefinite" values="{";".join(ops)}"/>'
            "</circle>"
        )
    # Tilted orbit with two satellites.
    orbit = f"M {num(cx - r * 1.5)} {cy} a {num(r * 1.5)} {num(r * .36)} 0 1 0 {num(r * 3)} 0 a {num(r * 1.5)} {num(r * .36)} 0 1 0 {num(-r * 3)} 0"
    out.append(
        f'<g transform="rotate(-16 {cx} {cy})"><path d="{orbit}" fill="none" stroke="{PINK}" '
        f'stroke-opacity=".45" stroke-width="1" stroke-dasharray="2 5"/>'
    )
    for begin, color in (("0s", PINK), ("-4.5s", MINT)):
        out.append(
            f'<circle r="3.4" fill="{color}" filter="url(#glow)"><animateMotion dur="9s" begin="{begin}" '
            f'repeatCount="indefinite" path="{orbit}"/></circle>'
        )
    out.append("</g>")
    return "".join(out)


def hero() -> str:
    W, H = 980, 400
    rng = random.Random(7)
    glyphs = "01ABCDEF0123456789<>/{}[]=+*#$%&"

    rain = []
    for i in range(17):
        x = 604 + i * 22
        n = rng.randint(10, 20)
        dur = rng.uniform(6, 12)
        spans = "".join(
            f'<tspan x="{x}" dy="15"{" class=\"hd\"" if j == n - 1 else ""}>{esc(rng.choice(glyphs))}</tspan>'
            for j in range(n)
        )
        rain.append(
            f'<text class="rain" y="{-n * 15}" font-size="12" '
            f'style="animation-duration:{dur:.2f}s;animation-delay:{-rng.uniform(0, dur):.2f}s">{spans}</text>'
        )

    boot = [
        ("booting ", "ay-mr.os", " v2026.10"),
        ("loading modules: ", "vision · llm · agents · mobile", ""),
        ("linking ", "zonr.pro · lensguard · play-preflight", ""),
        ("status: ", "shipping", " -> all systems nominal"),
    ]
    boot_defs, boot_lines = [], []
    for i, (a, b, c) in enumerate(boot):
        y = 76 + i * 17
        width = text_width("[ OK ] " + a + b + c, 11)
        begin = 0.25 + i * 0.32
        boot_defs.append(
            f'<clipPath id="boot{i}"><rect x="44" y="{y - 12}" width="0" height="16">'
            f'<animate attributeName="width" from="0" to="{num(width + 4)}" begin="{begin:.2f}s" '
            f'dur=".3s" fill="freeze"/></rect></clipPath>'
        )
        boot_lines.append(
            f'<text clip-path="url(#boot{i})" x="44" y="{y}" font-size="11" fill="{MUTED}">'
            f'<tspan fill="{MINT}">[ OK ]</tspan> {esc(a)}<tspan fill="{TEXT}">{esc(b)}</tspan>{esc(c)}</text>'
        )

    phrases = [
        [("shipping ", "p"), ("Zonr", "k"), (" -> AI goal planner, iOS + Android", "p")],
        [("guarding vision-AI agents with ", "p"), ("LensGuard", "k")],
        [("building ", "p"), ("agent skills", "k"), (" that catch review blockers", "p")],
        [("turning ", "p"), ("ML prototypes", "k"), (" into products people use", "p")],
    ]
    type_defs, type_body = typing_track(phrases, 128, 318, 14, 5.0, "tp")

    ticker = "AI PRODUCTS // FULL-STACK SYSTEMS // AGENT TOOLING // COMPUTER VISION // EDGE ML // SHIP > DEMO // "
    tick_w = text_width(ticker, 10.5, 2.2)

    style = base_style(
        f".rain{{fill:{MINT};opacity:.16;animation:rain linear infinite}}"
        ".rain .hd{fill:#eafff4;opacity:1}"
        "@keyframes rain{from{transform:translateY(0)}to{transform:translateY(760px)}}"
        "@keyframes scan{from{transform:translateY(-120px)}to{transform:translateY(420px)}}"
        ".scan{animation:scan 6.5s linear infinite}"
        "@keyframes tick{from{transform:translateX(0)}to{transform:translateX(-" + num(tick_w) + "px)}}"
        ".tick{animation:tick 38s linear infinite}"
        "@keyframes intro{0%{opacity:0;transform:translateY(8px)}"
        "30%{opacity:1}38%{opacity:.15}46%{opacity:1}60%{opacity:.4}"
        "100%{opacity:1;transform:translateY(0)}}"
        ".intro{opacity:0;animation:intro .9s 1.45s ease-out forwards}"
        ".intro2{opacity:0;animation:fadein .8s 2.1s ease-out forwards}"
        "@keyframes glc{0%,84%,100%{opacity:0;transform:translate(0,0)}"
        "85%{opacity:.9;transform:translate(-5px,1px);clip-path:inset(8% 0 58% 0)}"
        "87%{transform:translate(4px,-1px);clip-path:inset(62% 0 6% 0)}"
        "89%{transform:translate(-3px,0);clip-path:inset(34% 0 38% 0)}"
        "91%{transform:translate(6px,2px);clip-path:inset(0 0 78% 0)}"
        "93%{opacity:.9;transform:translate(-2px,0);clip-path:inset(72% 0 0 0)}"
        "94%{opacity:0}}"
        "@keyframes glm{0%,84%,100%{opacity:0;transform:translate(0,0)}"
        "85%{opacity:.9;transform:translate(5px,-1px);clip-path:inset(50% 0 20% 0)}"
        "87%{transform:translate(-4px,1px);clip-path:inset(12% 0 64% 0)}"
        "89%{transform:translate(3px,0);clip-path:inset(70% 0 4% 0)}"
        "91%{transform:translate(-6px,-1px);clip-path:inset(28% 0 50% 0)}"
        "93%{opacity:.9;transform:translate(2px,0);clip-path:inset(0 0 66% 0)}"
        "94%{opacity:0}}"
        "@keyframes skew{0%,84%,95%,100%{transform:none}86%{transform:skewX(-9deg)}"
        "88%{transform:skewX(6deg)}90%{transform:none}92%{transform:skewX(-4deg)}}"
        ".gc{fill:#22d3ee;animation:glc 5.5s 3s infinite steps(1)}"
        ".gm{fill:#f472b6;animation:glm 5.5s 3s infinite steps(1)}"
        ".gt{animation:skew 5.5s 3s infinite steps(1);transform-box:fill-box;transform-origin:center}"
        f".p{{fill:#cdeee0}}.k{{fill:{MINT};font-weight:700}}"
        "@keyframes callout{0%{opacity:0}100%{opacity:1}}"
        ".co{opacity:0;animation:callout .5s ease-out forwards}"
        "@keyframes bar{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        ".ubar{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:bar .9s 2s cubic-bezier(.2,.9,.2,1) forwards}"
        "@keyframes eq{0%,100%{transform:scaleY(.25)}50%{transform:scaleY(1)}}"
        ".eq{transform-box:fill-box;transform-origin:bottom;animation:eq 1.2s ease-in-out infinite}"
    )

    gx, gy, gr = 802, 212, 108
    callouts = [
        ("VISION", gx - 168, 118, gx - 76, 152, 2.6),
        ("LLM", gx + 128, 104, gx + 62, 150, 2.85),
        ("AGENTS", gx + 132, 300, gx + 70, 262, 3.1),
        ("MOBILE", gx - 172, 306, gx - 80, 272, 3.35),
    ]
    co = []
    for label, lx, ly, px, py, delay in callouts:
        w = text_width(label, 9.5, 1.5) + 14
        bx = lx if lx < gx else lx - w + 40
        co.append(
            f'<g class="co" style="animation-delay:{delay}s">'
            f'<path d="M {num(px)} {num(py)} L {num(bx + w / 2)} {num(ly + 9)}" stroke="{CYAN}" stroke-opacity=".5" stroke-width=".8" fill="none"/>'
            f'<circle cx="{num(px)}" cy="{num(py)}" r="2.2" fill="{CYAN}"/>'
            f'<rect x="{num(bx)}" y="{ly}" width="{num(w)}" height="18" rx="3" fill="{BG0}" fill-opacity=".85" stroke="{CYAN}" stroke-opacity=".55"/>'
            f'<text x="{num(bx + w / 2)}" y="{ly + 12.5}" text-anchor="middle" font-size="9.5" letter-spacing="1.5" fill="{CYAN}" font-weight="700">{label}</text></g>'
        )

    brackets = []
    for (x, y, dx, dy) in ((650, 62, 1, 1), (954, 62, -1, 1), (650, 352, 1, -1), (954, 352, -1, -1)):
        brackets.append(f'<path d="M {x} {y + dy * 16} V {y} H {x + dx * 16}" stroke="{CYAN}" stroke-opacity=".6" fill="none" stroke-width="1.4"/>')

    eq = "".join(
        f'<rect class="eq" x="{896 + i * 6}" y="320" width="3.5" height="18" fill="{MINT}" fill-opacity=".75" style="animation-delay:{-i * .17:.2f}s"/>'
        for i in range(8)
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">AY-MR — AI product engineer</title>
<desc id="d">Animated terminal-style banner: AI product engineer building Zonr, LensGuard and agent tooling, Taiwan.</desc>
{style}
<defs>
<clipPath id="frame"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20"/></clipPath>
<radialGradient id="bgA" cx="12%" cy="0%" r="70%"><stop offset="0" stop-color="#1b1446" stop-opacity=".9"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<radialGradient id="bgB" cx="85%" cy="55%" r="55%"><stop offset="0" stop-color="#062a2a" stop-opacity=".9"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<radialGradient id="globeGlow"><stop offset="0" stop-color="{CYAN}" stop-opacity=".22"/><stop offset=".6" stop-color="{CYAN}" stop-opacity=".05"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>
<radialGradient id="vig" cx="50%" cy="50%" r="75%"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>
<linearGradient id="title" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#d9fff0"/><stop offset="1" stop-color="{MINT}"/></linearGradient>
<linearGradient id="accent" x1="0" x2="1"><stop offset="0" stop-color="{MINT}"/><stop offset=".5" stop-color="{CYAN}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>
<linearGradient id="border" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{MINT}"/><stop offset=".35" stop-color="{LINE}"/><stop offset=".65" stop-color="{LINE}"/><stop offset="1" stop-color="{PINK}"/>
<animateTransform attributeName="gradientTransform" type="rotate" from="0 .5 .5" to="360 .5 .5" dur="10s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="scanG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{MINT}" stop-opacity="0"/><stop offset=".5" stop-color="{MINT}" stop-opacity=".07"/><stop offset="1" stop-color="{MINT}" stop-opacity="0"/></linearGradient>
<linearGradient id="rainFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".25" stop-color="#fff"/><stop offset=".8" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<mask id="rainMask"><rect x="590" y="40" width="390" height="320" fill="url(#rainFade)"/></mask>
<pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#fff" stroke-opacity=".035"/></pattern>
<pattern id="lines" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" fill-opacity=".28"/></pattern>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="soft" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="9"/></filter>
{"".join(boot_defs)}{type_defs}
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect width="{W}" height="{H}" fill="url(#bgA)"/>
<rect width="{W}" height="{H}" fill="url(#bgB)"/>
<rect width="{W}" height="{H}" fill="url(#grid)"/>
<g mask="url(#rainMask)">{"".join(rain)}</g>
{globe(gx, gy, gr)}
{"".join(brackets)}
<text x="664" y="80" font-size="9" letter-spacing="1.6" fill="{CYAN}" fill-opacity=".8">NEURAL.MAP // LIVE</text>
<text x="940" y="80" text-anchor="end" font-size="9" letter-spacing="1.4" fill="{MINT}"><tspan class="pulse">●</tspan> NOMINAL</text>
<text x="664" y="344" font-size="9" letter-spacing="1.2" fill="{MUTED}">LAT 23.69N  LON 120.96E  //  UTC+8</text>
{eq}
{"".join(co)}

<rect x="0" y="0" width="{W}" height="40" fill="#000" fill-opacity=".35"/>
<path d="M0 40.5H{W}" stroke="{LINE}"/>
<circle cx="26" cy="20" r="5.5" fill="{RED}"/><circle cx="45" cy="20" r="5.5" fill="#ffbd2e"/><circle cx="64" cy="20" r="5.5" fill="#27c93f"/>
<text x="{W / 2}" y="24.5" text-anchor="middle" font-size="11.5" fill="{MUTED}">ay-mr@taiwan: <tspan fill="{TEXT}">~/profile</tspan> — zsh — 980×400</text>
<text x="{W - 24}" y="24.5" text-anchor="end" font-size="10.5" font-weight="700" letter-spacing="1.5" fill="{RED}"><tspan class="blink">●</tspan> REC</text>

{"".join(boot_lines)}

<g class="intro">
<text x="40" y="226" font-size="98" font-weight="800" letter-spacing="3" fill="{MINT}" opacity=".35" filter="url(#soft)">AY-MR</text>
<g class="gt"><text x="40" y="226" font-size="98" font-weight="800" letter-spacing="3" fill="url(#title)">AY-MR</text></g>
<text class="gc" x="40" y="226" font-size="98" font-weight="800" letter-spacing="3">AY-MR</text>
<text class="gm" x="40" y="226" font-size="98" font-weight="800" letter-spacing="3">AY-MR</text>
</g>
<rect class="ubar" x="44" y="244" width="150" height="4" rx="2" fill="url(#accent)"/>
<g class="intro2">
<text x="44" y="276" font-size="16.5" fill="#c9d4e3">AI product engineer <tspan fill="{DIM}">·</tspan> full-stack <tspan fill="{DIM}">·</tspan> applied ML <tspan fill="{DIM}">·</tspan> agents</text>
<text x="44" y="318" font-size="14" fill="{MINT}" font-weight="700">$ <tspan fill="{CYAN}">./now</tspan></text>
{type_body}
</g>

<path d="M0 362.5H{W}" stroke="{LINE}"/>
<rect x="0" y="363" width="{W}" height="{H - 363}" fill="#000" fill-opacity=".3"/>
<g class="tick"><text x="24" y="385.5" font-size="10.5" letter-spacing="2.2" fill="{DIM}">{esc(ticker * 4)}</text></g>

<rect class="scan" x="0" y="0" width="{W}" height="110" fill="url(#scanG)"/>
<rect width="{W}" height="{H}" fill="url(#lines)"/>
<rect width="{W}" height="{H}" fill="url(#vig)"/>
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="none" stroke="url(#border)" stroke-width="1.6"/>
</svg>'''
    return svg


# ------------------------------------------------------------------------ buttons

def rect_perimeter(w: float, h: float, r: float) -> float:
    return 2 * (w + h) - (8 - 2 * math.pi) * r


def button(label: str, sub: str, accent: str, glyph: str) -> str:
    W, H, R = 232, 56, 12
    per = rect_perimeter(W - 2, H - 2, R)
    style = base_style(
        f"@keyframes run{{from{{stroke-dashoffset:0}}to{{stroke-dashoffset:-{num(per)}}}}}"
        ".run{animation:run 3.6s linear infinite}"
        "@keyframes nudge{0%,60%,100%{transform:translateX(0)}75%{transform:translateX(4px)}}"
        ".arr{animation:nudge 2.4s ease-in-out infinite}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)} — {esc(sub)}">
{style}
<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{accent}" stop-opacity=".16"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient></defs>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{R}" fill="{PANEL}" stroke="{LINE}"/>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{R}" fill="url(#g)"/>
<rect class="run" x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{R}" fill="none" stroke="{accent}" stroke-width="1.6" stroke-linecap="round" stroke-dasharray="46 {num(per - 46)}"/>
<rect x="12" y="12" width="32" height="32" rx="8" fill="{accent}" fill-opacity=".12" stroke="{accent}" stroke-opacity=".45"/>
<g transform="translate(16 16)">{glyph}</g>
<text x="56" y="25" font-size="13" font-weight="800" letter-spacing="1.2" fill="{TEXT}">{esc(label)}</text>
<text x="56" y="41" font-size="10" fill="{MUTED}">{esc(sub)}</text>
<g class="arr"><text x="{W - 18}" y="33" text-anchor="end" font-size="15" font-weight="700" fill="{accent}">-&gt;</text></g>
</svg>'''


def glyph_lens(color: str) -> str:
    return (
        f'<circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="1.6"/>'
        f'<circle cx="12" cy="12" r="5.5" fill="none" stroke="{color}" stroke-width="1.6"/>'
        f'<circle cx="12" cy="12" r="1.8" fill="{color}"/>'
        f'<path d="M12 2 L15 8 M22 12 L16 15 M12 22 L9 16 M2 12 L8 9" stroke="{color}" stroke-width="1.2"/>'
    )


def glyph_orbit(color: str) -> str:
    return (
        f'<circle cx="12" cy="12" r="4.5" fill="{color}"/>'
        f'<ellipse cx="12" cy="12" rx="11" ry="4.5" fill="none" stroke="{color}" stroke-width="1.4" transform="rotate(-25 12 12)"/>'
        f'<circle cx="21.5" cy="7.6" r="2" fill="{color}"><animate attributeName="opacity" values="1;.2;1" dur="1.6s" repeatCount="indefinite"/></circle>'
    )


def glyph_image(uri: str) -> str:
    return (
        '<clipPath id="ic"><rect width="24" height="24" rx="6"/></clipPath>'
        f'<image href="{uri}" width="24" height="24" clip-path="url(#ic)"/>'
    )


def buttons() -> dict[str, str]:
    zonr = data_uri(ASSETS / "brand" / "zonr-icon.jpg", "image/jpeg")
    return {
        "btn-zonr.svg": button("ZONR.PRO", "official site + app", PINK, glyph_image(zonr)),
        "btn-lensguard.svg": button("LENSGUARD", "open-source vision AI", CYAN, glyph_lens(CYAN)),
        "btn-email.svg": button("EMAIL", "houbaian54@gmail.com", AMBER, icon(ICONS, "gmail", 0, 0, 24, AMBER)),
        "btn-orbit.svg": button("JOIN ORBIT", "drop your avatar here", MINT, glyph_orbit(MINT)),
    }


# ----------------------------------------------------------------------- headers

def header(index: str, title: str, command: str, accent: str) -> str:
    W, H = 980, 64
    style = base_style(
        "@keyframes sweep{from{transform:translateX(-160px)}to{transform:translateX(1000px)}}"
        ".sw{animation:sweep 5s cubic-bezier(.6,0,.4,1) infinite}"
    )
    tw = text_width(title, 24, 1)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">
{style}
<defs><linearGradient id="s" x1="0" x2="1"><stop offset="0" stop-color="{accent}" stop-opacity="0"/><stop offset=".5" stop-color="{accent}"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient></defs>
<text x="4" y="36" font-size="13" font-weight="700" fill="{accent}">//{esc(index)}</text>
<text x="44" y="37" font-size="24" font-weight="800" letter-spacing="1" fill="{TEXT}">{esc(title)}</text>
<rect class="blink" x="{num(50 + tw)}" y="19" width="12" height="22" fill="{accent}" fill-opacity=".85"/>
<text x="{W - 4}" y="36" text-anchor="end" font-size="12.5" fill="{DIM}"><tspan fill="{accent}">$</tspan> {esc(command)}</text>
<rect x="4" y="52" width="{W - 8}" height="1" fill="{LINE}"/>
<rect class="sw" x="0" y="51" width="160" height="3" rx="1.5" fill="url(#s)"/>
</svg>'''


HEADERS = {
    "h-work.svg": ("01", "SELECTED WORK", "ls ~/projects --featured", MINT),
    "h-stack.svg": ("02", "TECH STACK", "cat ~/.stack.yml", CYAN),
    "h-activity.svg": ("03", "ENGINEERING ACTIVITY", "git log --since=1y | viz", MINT),
    "h-orbit.svg": ("04", "THE ORBIT", "./orbit --summon", PINK),
}


# ------------------------------------------------------------------------- cards

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


def card(
    *, index: str, kind: str, title: str, title_cjk: str, status: str, accent: str,
    tagline: str, meta: str, chips: list[str], art: str, extra_style: str = "", extra_defs: str = "",
    meta_svg: str = "",
) -> str:
    W, H = 480, 280
    style = base_style(extra_style)
    wrapped = wrap(tagline, 37)
    lines = "".join(
        f'<text x="26" y="{116 + i * 18}" font-size="12.5" fill="{MUTED}">{esc(line)}</text>'
        for i, line in enumerate(wrapped)
    )
    meta_y = 116 + max(len(wrapped), 3) * 18 + 8
    chip_svg, cx = [], 26.0
    for chip in chips:
        w = text_width(chip, 10.5) + 18
        chip_svg.append(
            f'<rect x="{num(cx)}" y="232" width="{num(w)}" height="24" rx="12" fill="{accent}" fill-opacity=".08" stroke="{accent}" stroke-opacity=".35"/>'
            f'<text x="{num(cx + w / 2)}" y="248" text-anchor="middle" font-size="10.5" fill="{TEXT}" fill-opacity=".85">{esc(chip)}</text>'
        )
        cx += w + 8
    sw = text_width(status, 9.5, 1.2) + 30
    cjk = f'<tspan class="cjk" font-size="20" font-weight="700" fill="{accent}" dx="10">{esc(title_cjk)}</tspan>' if title_cjk else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)} — {esc(tagline)}">
{style}
<defs>
<radialGradient id="glow" cx="82%" cy="30%" r="60%"><stop offset="0" stop-color="{accent}" stop-opacity=".2"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{accent}" stop-opacity=".75"/><stop offset=".4" stop-color="{LINE}"/><stop offset="1" stop-color="{LINE}"/></linearGradient>
<pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".8" fill="#fff" fill-opacity=".05"/></pattern>
<clipPath id="cardclip"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16"/></clipPath>
<filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
{extra_defs}
</defs>
<g clip-path="url(#cardclip)">
<rect width="{W}" height="{H}" fill="{PANEL}"/>
<rect width="{W}" height="{H}" fill="url(#dots)"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>
{art}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="none" stroke="url(#edge)" stroke-width="1.4"/>
<text x="26" y="38" font-size="11" font-weight="700" letter-spacing="1.2" fill="{accent}">{esc(index)} <tspan fill="{DIM}">/ {esc(kind)}</tspan></text>
<rect x="{num(W - 22 - sw)}" y="22" width="{num(sw)}" height="22" rx="11" fill="{BG0}" fill-opacity=".7" stroke="{accent}" stroke-opacity=".5"/>
<circle class="pulse" cx="{num(W - 22 - sw + 13)}" cy="33" r="3.2" fill="{accent}"/>
<text x="{num(W - 22 - sw + 22)}" y="36.5" font-size="9.5" font-weight="700" letter-spacing="1.2" fill="{accent}">{esc(status)}</text>
<text x="26" y="86" font-size="30" font-weight="800" fill="{TEXT}">{esc(title)}{cjk}</text>
{lines}
<text x="26" y="{meta_y}" font-size="11" fill="{accent}">&gt; <tspan fill="{TEXT}" fill-opacity=".8">{meta_svg or esc(meta)}</tspan></text>
{"".join(chip_svg)}
<text x="{W - 24}" y="249" text-anchor="end" font-size="13" font-weight="700" fill="{accent}">open -&gt;</text>
</svg>'''


def sparkle(x: float, y: float, s: float, color: str, delay: float) -> str:
    d = f"M0 {-s} C {s * .15} {-s * .15} {s * .15} {-s * .15} {s} 0 C {s * .15} {s * .15} {s * .15} {s * .15} 0 {s} C {-s * .15} {s * .15} {-s * .15} {s * .15} {-s} 0 C {-s * .15} {-s * .15} {-s * .15} {-s * .15} 0 {-s} Z"
    return (
        f'<g transform="translate({num(x)} {num(y)})"><path class="tw" style="animation-delay:{delay}s" d="{d}" fill="{color}"/></g>'
    )


def card_zonr() -> str:
    uri = data_uri(ASSETS / "brand" / "zonr-icon.jpg", "image/jpeg")
    cx, cy = 398, 126
    back = f"M {cx - 74} {cy + 6} A 74 22 0 0 1 {cx + 74} {cy - 6}"
    front = f"M {cx + 74} {cy - 6} A 74 22 0 0 1 {cx - 74} {cy + 6}"
    art = f'''
<g transform="rotate(-10 {cx} {cy})"><path d="{back}" fill="none" stroke="{PINK}" stroke-opacity=".45" stroke-width="1.6" stroke-dasharray="3 5"/></g>
<rect x="{cx - 54}" y="{cy - 54}" width="108" height="108" rx="26" fill="{PINK}" fill-opacity=".25" filter="url(#gl)"/>
<g class="bob"><clipPath id="icon"><rect x="{cx - 52}" y="{cy - 52}" width="104" height="104" rx="25"/></clipPath>
<image href="{uri}" x="{cx - 52}" y="{cy - 52}" width="104" height="104" clip-path="url(#icon)"/>
<rect x="{cx - 52}" y="{cy - 52}" width="104" height="104" rx="25" fill="none" stroke="#fff" stroke-opacity=".25"/></g>
<g transform="rotate(-10 {cx} {cy})"><path id="fr" d="{front}" fill="none" stroke="{PINK}" stroke-width="2"/>
<circle r="5" fill="#ffd1e1" filter="url(#gl)"><animateMotion dur="3.2s" repeatCount="indefinite" path="{front}"/>
<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.15;.85;1" dur="3.2s" repeatCount="indefinite"/></circle></g>
{sparkle(cx - 64, cy - 58, 9, PINK, 0)}{sparkle(cx + 62, cy - 64, 6, AMBER, .7)}{sparkle(cx + 66, cy + 54, 7, PINK, 1.4)}{sparkle(cx - 66, cy + 50, 5, "#fff", 2.1)}
'''
    return card(
        index="01", kind="SHIPPED APP", title="Zonr", title_cjk="佐能", status="LIVE · iOS + ANDROID",
        accent=PINK,
        tagline="AI planner that turns a stalled, deadline-driven goal into clear stages and the one step that matters today.",
        meta="WorldSkills BeChangeMaker 2026 · Top 15",
        chips=["TypeScript", "LLM planning", "RevenueCat"],
        art=art,
        extra_style=(
            "@keyframes tw{0%,100%{transform:scale(.4);opacity:.3}50%{transform:scale(1);opacity:1}}"
            ".tw{transform-box:fill-box;transform-origin:center;animation:tw 2.8s ease-in-out infinite}"
            "@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}"
            ".bob{animation:bob 4s ease-in-out infinite}"
        ),
    )


def card_lensguard() -> str:
    cx, cy = 396, 104
    blades = "".join(
        f'<path d="M {cx} {cy} L {num(cx + 40 * math.cos(math.radians(a)))} {num(cy + 40 * math.sin(math.radians(a)))} '
        f'L {num(cx + 40 * math.cos(math.radians(a + 60)))} {num(cy + 40 * math.sin(math.radians(a + 60)))} Z" '
        f'fill="{CYAN}" fill-opacity="{.05 + (i % 2) * .05:.2f}" stroke="{CYAN}" stroke-opacity=".5" stroke-width=".8"/>'
        for i, a in enumerate(range(0, 360, 60))
    )
    stages = ["OBSERVE", "DISTINGUISH", "DECIDE", "PROTECT"]
    art = f'''
<circle cx="{cx}" cy="{cy}" r="66" fill="none" stroke="{CYAN}" stroke-opacity=".25" stroke-dasharray="2 4"/>
<circle cx="{cx}" cy="{cy}" r="54" fill="#041018" stroke="{CYAN}" stroke-opacity=".7" stroke-width="1.6"/>
<g class="iris">{blades}</g>
<circle cx="{cx}" cy="{cy}" r="14" fill="#020a10" stroke="{CYAN}" stroke-width="1.2"/>
<circle cx="{cx - 5}" cy="{cy - 5}" r="3.5" fill="#fff" fill-opacity=".7"/>
<g class="sweep"><path d="M {cx} {cy} L {cx + 54} {cy} A 54 54 0 0 0 {num(cx + 54 * math.cos(math.radians(-38)))} {num(cy + 54 * math.sin(math.radians(-38)))} Z" fill="url(#beam)"/></g>
<g class="inj">
<rect x="{cx - 54}" y="{cy + 62}" width="118" height="22" rx="4" fill="#1a0b0f" stroke="{RED}" stroke-opacity=".7"/>
<text x="{cx + 5}" y="{cy + 76.5}" text-anchor="middle" font-size="9" fill="#ffb4b0">"ignore user, pay $"</text>
<g class="stamp"><rect x="{cx - 54}" y="{cy + 62}" width="118" height="22" rx="4" fill="{RED}"/>
<text x="{cx + 5}" y="{cy + 77}" text-anchor="middle" font-size="10" font-weight="800" letter-spacing="2" fill="#fff">BLOCKED</text></g>
</g>
'''
    meta_spans = " -&gt; ".join(
        f'<tspan class="stg" style="animation-delay:{i * .9:.1f}s">{s.lower()}</tspan>' for i, s in enumerate(stages)
    )
    return card(
        index="02", kind="OPEN SOURCE · MIT", title="LensGuard", title_cjk="", status="TEAM PROJECT",
        accent=CYAN,
        tagline="Action-authorization guard for vision-AI assistants: stops prompt injections hidden in camera scenes.",
        meta=" -> ".join(s.lower() for s in stages),
        meta_svg=meta_spans,
        chips=["NVIDIA VLM", "FastAPI", "React 19"],
        art=art,
        extra_defs=f'<linearGradient id="beam" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/><stop offset="1" stop-color="{CYAN}" stop-opacity=".45"/></linearGradient>',
        extra_style=(
            "@keyframes spin{to{transform:rotate(360deg)}}"
            f".iris{{transform-origin:{cx}px {cy}px;animation:spin 18s linear infinite}}"
            f".sweep{{transform-origin:{cx}px {cy}px;animation:spin 3s linear infinite}}"
            "@keyframes inj{0%,8%{opacity:0;transform:translateY(6px)}16%,92%{opacity:1;transform:none}100%{opacity:0}}"
            ".inj{animation:inj 4s ease-out infinite}"
            "@keyframes stamp{0%,45%{opacity:0;transform:scale(1.8)}52%{opacity:1;transform:scale(.92)}58%,90%{opacity:1;transform:scale(1)}100%{opacity:0}}"
            ".stamp{transform-box:fill-box;transform-origin:center;animation:stamp 4s ease-out infinite}"
            f"@keyframes stg{{0%,100%{{fill:{TEXT};fill-opacity:.6}}10%,25%{{fill:{CYAN};fill-opacity:1}}}}"
            ".stg{animation:stg 3.6s linear infinite}"
        ),
    )


def card_preflight() -> str:
    green = "#3ddc84"
    items = ["data safety", "permissions", "target SDK", "store listing", "privacy URL"]
    x0, y0 = 326, 62
    rows = []
    for i, item in enumerate(items):
        y = y0 + 34 + i * 22
        d = 0.35 + i * 0.45
        rows.append(
            f'<rect x="{x0 + 12}" y="{y - 10}" width="13" height="13" rx="3" fill="none" stroke="{green}" stroke-opacity=".6"/>'
            f'<path class="tick" style="animation-delay:{d:.2f}s" d="M {x0 + 15} {y - 3.5} l 3 3 l 5.5 -6" fill="none" stroke="{green}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" pathLength="1"/>'
            f'<text x="{x0 + 33}" y="{y + 1}" font-size="10" fill="{TEXT}" fill-opacity=".85">{esc(item)}</text>'
        )
    art = f'''
<rect x="{x0}" y="{y0}" width="132" height="132" rx="10" fill="#07140d" stroke="{green}" stroke-opacity=".4"/>
<rect x="{x0}" y="{y0}" width="132" height="18" rx="10" fill="{green}" fill-opacity=".12"/>
<text x="{x0 + 10}" y="{y0 + 12.5}" font-size="8.5" font-weight="700" letter-spacing="1.2" fill="{green}">PREFLIGHT.CHECK</text>
{"".join(rows)}
<g class="ready"><rect x="{x0 + 30}" y="{y0 + 140}" width="78" height="22" rx="4" fill="none" stroke="{green}" stroke-width="2"/>
<text x="{x0 + 69}" y="{y0 + 155}" text-anchor="middle" font-size="10" font-weight="800" letter-spacing="1.6" fill="{green}">READY</text></g>
{icon(ICONS, "android", x0 + 112, y0 + 3, 12, green)}
'''
    return card(
        index="03", kind="AGENT SKILL", title="Play Preflight", title_cjk="", status="OPEN SOURCE",
        accent=green,
        tagline="Policy-aware preflight for AI coding agents: catches Google Play review blockers before you hit submit.",
        meta="Android · Expo · React Native · Flutter",
        chips=["Claude Code", "Agent skills", "Play policy"],
        art=art,
        extra_style=(
            "@keyframes tick{0%{stroke-dashoffset:1}12%,88%{stroke-dashoffset:0}100%{stroke-dashoffset:1}}"
            ".tick{stroke-dasharray:1;stroke-dashoffset:1;animation:tick 5s ease-out infinite}"
            "@keyframes ready{0%,52%{opacity:0;transform:scale(1.6) rotate(-8deg)}60%{opacity:1;transform:scale(.95) rotate(-8deg)}66%,88%{opacity:1;transform:scale(1) rotate(-8deg)}100%{opacity:0}}"
            ".ready{transform-box:fill-box;transform-origin:center;animation:ready 5s ease-out infinite}"
        ),
    )


def card_microwave() -> str:
    x0, y0 = 318, 70
    art = f'''
<rect x="{x0}" y="{y0}" width="146" height="98" rx="10" fill="#140e04" stroke="{AMBER}" stroke-opacity=".5"/>
<rect x="{x0 + 10}" y="{y0 + 12}" width="92" height="74" rx="6" fill="#050302" stroke="{AMBER}" stroke-opacity=".25"/>
<rect class="heat" x="{x0 + 10}" y="{y0 + 12}" width="92" height="74" rx="6" fill="{AMBER}"/>
<rect x="{x0 + 22}" y="{y0 + 32}" width="66" height="40" rx="3" fill="#2a1d08" stroke="{AMBER}" stroke-opacity=".4"/>
<text x="{x0 + 55}" y="{y0 + 63}" text-anchor="middle" font-size="16" font-weight="800" fill="#fff">3:30</text>
<g class="box"><path d="M {x0 + 30} {y0 + 51} v -5 h 5 M {x0 + 80} {y0 + 46} h 5 v 5 M {x0 + 85} {y0 + 64} v 5 h -5 M {x0 + 35} {y0 + 69} h -5 v -5" fill="none" stroke="{MINT}" stroke-width="1.8"/>
<rect x="{x0 + 30}" y="{y0 + 36}" width="40" height="11" rx="2" fill="{MINT}"/><text x="{x0 + 50}" y="{y0 + 44.5}" text-anchor="middle" font-size="7.5" font-weight="800" fill="{BG0}">3:30 .98</text></g>
<rect x="{x0 + 110}" y="{y0 + 14}" width="28" height="16" rx="3" fill="#000" stroke="{AMBER}" stroke-opacity=".5"/>
<text class="seg" x="{x0 + 124}" y="{y0 + 26}" text-anchor="middle" font-size="9" font-weight="800" fill="{AMBER}">0330</text>
<circle cx="{x0 + 124}" cy="{y0 + 48}" r="7" fill="none" stroke="{AMBER}" stroke-opacity=".6"/>
<circle class="pulse" cx="{x0 + 124}" cy="{y0 + 72}" r="5" fill="{MINT}"/>
<circle cx="{x0 + 73}" cy="{y0 - 18}" r="7" fill="#000" stroke="{AMBER}" stroke-opacity=".8"/><circle cx="{x0 + 73}" cy="{y0 - 18}" r="2.5" fill="{RED}" class="blink"/>
<path d="M {x0 + 73} {y0 - 11} L {x0 + 40} {y0 + 30} M {x0 + 73} {y0 - 11} L {x0 + 92} {y0 + 30}" stroke="{MINT}" stroke-opacity=".35" stroke-dasharray="2 3"/>
'''
    return card(
        index="04", kind="AIoT · VISION", title="Smart Oven", title_cjk="", status="EDGE ML",
        accent=AMBER,
        tagline="Contactless microwave: a camera reads cook time off the food package, so one tap starts heating.",
        meta="digit recognition on a Raspberry Pi 4",
        chips=["TensorFlow", "OpenCV", "Raspberry Pi"],
        art=art,
        extra_style=(
            "@keyframes box{0%,10%{opacity:0;transform:scale(1.5)}25%,80%{opacity:1;transform:scale(1)}100%{opacity:0}}"
            ".box{transform-box:fill-box;transform-origin:center;animation:box 4.5s ease-out infinite}"
            "@keyframes heat{0%,55%{opacity:0}70%,90%{opacity:.16}100%{opacity:0}}"
            ".heat{animation:heat 4.5s ease-in-out infinite}"
            "@keyframes seg{0%,50%{opacity:.25}56%,100%{opacity:1}}"
            ".seg{animation:seg 4.5s steps(1) infinite}"
        ),
    )


# -------------------------------------------------------------------- store pills

def store_badge(top: str, label: str, glyph: str, accent: str) -> str:
    W, H = 176, 50
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(top)} {esc(label)}">
{base_style("")}
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="12" fill="#000" stroke="{accent}" stroke-opacity=".55"/>
<g transform="translate(14 13)">{glyph}</g>
<text x="50" y="21" font-size="9" letter-spacing=".8" fill="{MUTED}">{esc(top)}</text>
<text x="50" y="37" font-size="14.5" font-weight="800" fill="{TEXT}">{esc(label)}</text>
</svg>'''


def store_badges() -> dict[str, str]:
    zonr = data_uri(ASSETS / "brand" / "zonr-icon.jpg", "image/jpeg")
    return {
        "store-web.svg": store_badge("VISIT", "zonr.pro", glyph_image(zonr), PINK),
        "store-ios.svg": store_badge("DOWNLOAD ON THE", "App Store", icon(ICONS, "apple", 0, 0, 24, "#fff"), "#ffffff"),
        "store-play.svg": store_badge("GET IT ON", "Google Play", icon(ICONS, "googleplay", 0, 0, 24, "#3ddc84"), "#3ddc84"),
    }


# ------------------------------------------------------------------------- stack

STACK = [
    ("AI / ML", "models, vision, eval", MINT,
     [("python", "Python"), ("pytorch", "PyTorch"), ("tensorflow", "TensorFlow"), ("opencv", "OpenCV"), ("nvidia", "NVIDIA VLM"),
      ("claude", "Claude Code")]),
    ("PRODUCT", "apps, web, APIs", CYAN,
     [("typescript", "TypeScript"), ("react", "React"), ("nextdotjs", "Next.js"), ("nodedotjs", "Node.js"), ("fastapi", "FastAPI"),
      ("tailwindcss", "Tailwind"), ("supabase", "Supabase")]),
    ("SYSTEMS", "local-first, edge, infra", PINK,
     [("rust", "Rust"), ("tauri", "Tauri"), ("cplusplus", "C++"), ("sqlite", "SQLite"), ("docker", "Docker"),
      ("cloudflare", "Cloudflare"), ("raspberrypi", "RasPi"), ("githubactions", "Actions")]),
]


def readable(hex_color: str | None) -> str:
    if not hex_color:
        return TEXT
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return TEXT if lum < 0.28 else f"#{hex_color}"


def stack() -> str:
    W = 980
    tile, gap, x0 = 76, 12, 214
    row_h = 98
    H = 24 + row_h * len(STACK)
    rows, n = [], 0
    for r, (name, sub, accent, items) in enumerate(STACK):
        y = 16 + r * row_h
        rows.append(
            f'<text x="20" y="{y + 36}" font-size="15" font-weight="800" letter-spacing="1.5" fill="{accent}">{esc(name)}</text>'
            f'<text x="20" y="{y + 56}" font-size="10.5" fill="{MUTED}">{esc(sub)}</text>'
            f'<path d="M 20 {y + 68} h 150" stroke="{accent}" stroke-opacity=".35"/>'
            f'<path d="M 184 {y + 42} h 22" stroke="{LINE}" stroke-dasharray="2 3"/>'
        )
        for c, (slug, label) in enumerate(items):
            x = x0 + c * (tile + gap)
            delay = (c + r * 2) * 0.18
            color = readable(ICONS[slug]["hex"])
            rows.append(
                f'<g><rect x="{x}" y="{y + 4}" width="{tile}" height="{tile}" rx="14" fill="{PANEL}" stroke="{LINE}"/>'
                f'<rect class="lit" style="animation-delay:{delay:.2f}s" x="{x}" y="{y + 4}" width="{tile}" height="{tile}" rx="14" fill="{accent}" fill-opacity=".06" stroke="{accent}" stroke-width="1.4"/>'
                f'{icon(ICONS, slug, x + tile / 2 - 14, y + 16, 28, color)}'
                f'<text x="{x + tile / 2}" y="{y + 68}" text-anchor="middle" font-size="9.5" fill="{TEXT}" fill-opacity=".8">{esc(label)}</text></g>'
            )
            n += 1
    style = base_style(
        "@keyframes lit{0%,100%{opacity:0}12%{opacity:1}30%{opacity:0}}"
        ".lit{opacity:0;animation:lit 4.5s ease-in-out infinite}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Tech stack: {n} tools across AI/ML, product and systems">
{style}
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="{BG1}" stroke="{LINE}"/>
{"".join(rows)}
</svg>'''


# ----------------------------------------------------------------------- decrypt

ABOUT = [
    ("ROLE", "AI product engineer · student builder · Taiwan"),
    ("FOCUS", "AI products · full-stack systems · applied ML"),
    ("SHIPPED", "Zonr (iOS + Android) · Play Preflight skill"),
    ("RESEARCH", "LensGuard: safe actions for vision-AI agents"),
    ("METHOD", "problem -> prototype -> evidence -> ship"),
    ("CONTACT", "houbaian54@gmail.com  ·  zonr.pro"),
]


def decrypt() -> str:
    """Scramble -> decrypt -> unlock, then re-encrypt and loop.

    Driven by one SMIL master clock (`clk`) because the README shows this inside
    a <details> panel: GitHub strips loading="lazy", so the image starts with the
    page and a one-shot animation would be over before anyone clicks.
    """
    W = 980
    H = 92 + len(ABOUT) * 30 + 20
    cycle = 13.0
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
        y = 104 + i * 30
        start = 1.25 + i * 0.28
        body.append(
            f'<text x="40" y="{y}" opacity="0" font-size="12.5" font-weight="700" letter-spacing="1.5" fill="{MINT}">{key}'
            f'{show(start - .2, hide_at)}</text>'
        )
        for f in range(frames):
            garbage = "".join(" " if ch == " " else rng.choice(noise) for ch in value)
            t = start + f * step
            body.append(
                f'<text opacity="0" x="190" y="{y}" font-size="14" fill="{CYAN}" fill-opacity=".75">{esc(garbage)}{show(t, t + step)}</text>'
            )
        reveal = start + frames * step
        body.append(f'<text opacity="0" x="190" y="{y}" font-size="14" fill="{TEXT}">{esc(value)}{show(reveal, hide_at)}</text>')
        # Re-encryption glitch: one burst of noise over the line before it disappears.
        garbage = "".join(" " if ch == " " else rng.choice(noise) for ch in value)
        body.append(
            f'<text opacity="0" x="190" y="{y}" font-size="14" fill="{PINK}" fill-opacity=".8">{esc(garbage)}{show(hide_at, hide_at + .35)}</text>'
        )
    bar_w = 420
    done = 1.25 + len(ABOUT) * 0.28 + frames * step
    hex_rows = []
    for _ in range(30):
        row = " ".join(f"{rng.randrange(256):02x}" for _ in range(8))
        hex_rows.append(f'<tspan x="650" dy="15">{row}</tspan>')
    lx, ly = 862, 150
    style = base_style(
        "@keyframes hex{from{transform:translateY(0)}to{transform:translateY(-180px)}}"
        ".hex{animation:hex 9s linear infinite}"
    )
    unlocked = f'begin="{at(done)}" dur="{hide_at - done:.2f}s"'
    k1, k2 = 1 / cycle, hide_at / cycle
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Decrypted profile: {esc(" / ".join(v for _, v in ABOUT))}">
{style}
<defs><linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="{MINT}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>
<linearGradient id="wg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{MINT}" stop-opacity="0"/><stop offset="1" stop-color="{MINT}" stop-opacity=".18"/></linearGradient>
<pattern id="lines" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" fill-opacity=".25"/></pattern>
<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16"/></clipPath>
<clipPath id="hx"><rect x="640" y="24" width="320" height="{H - 48}"/></clipPath></defs>
<rect width="0" height="0"><animate id="clk" attributeName="x" from="0" to="0" begin="0s;clk.end" dur="{cycle}s"/></rect>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<text x="40" y="44" font-size="13" fill="{MUTED}"><tspan fill="{MINT}" font-weight="700">$</tspan> decrypt ./about.enc --key=curiosity</text>
<rect x="40" y="58" width="{bar_w}" height="8" rx="4" fill="{LINE}"/>
<rect x="40" y="58" width="0" height="8" rx="4" fill="url(#bar)">
<animate attributeName="width" values="0;{bar_w};{bar_w};0" keyTimes="0;{k1:.4f};{k2:.4f};1" begin="{at(.15)}" dur="{cycle - .15:.2f}s" calcMode="spline" keySplines=".3 .7 .2 1;0 0 1 1;.4 0 1 1"/></rect>
<text x="{48 + bar_w}" y="66" opacity="0" font-size="11" fill="{MINT}" font-weight="700">100% · key accepted{show(1.15, hide_at)}</text>
<g clip-path="url(#hx)"><g class="hex"><text y="24" font-size="11" fill="{CYAN}" fill-opacity=".22" letter-spacing="1">{"".join(hex_rows)}<set attributeName="fill" to="{MINT}" {unlocked}/></text></g></g>
<rect x="{lx - 70}" y="{ly - 72}" width="140" height="150" rx="14" fill="{BG0}" fill-opacity=".82"/>
<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -11;0 -11;0 0" keyTimes="0;.06;.94;1" {unlocked}/>
<path d="M {lx - 17} {ly - 4} v -16 a 17 17 0 0 1 34 0 v 16" fill="none" stroke="{CYAN}" stroke-width="5" stroke-linecap="round"><set attributeName="stroke" to="{MINT}" {unlocked}/></path></g>
<rect x="{lx - 29}" y="{ly - 6}" width="58" height="46" rx="9" fill="{CYAN}" fill-opacity=".1" stroke="{CYAN}" stroke-width="2.4"><set attributeName="stroke" to="{MINT}" {unlocked}/><set attributeName="fill" to="{MINT}" {unlocked}/></rect>
<circle cx="{lx}" cy="{ly + 12}" r="5" fill="{TEXT}"/><rect x="{lx - 2}" y="{ly + 14}" width="4" height="12" rx="2" fill="{TEXT}"/>
<g opacity="0">{show(done + .2, hide_at)}<rect x="{lx - 64}" y="{ly + 52}" width="128" height="22" rx="4" fill="{MINT}"/>
<text x="{lx}" y="{ly + 67}" text-anchor="middle" font-size="10.5" font-weight="800" letter-spacing="1.6" fill="{BG0}">ACCESS GRANTED</text></g>
{"".join(body)}
<rect x="0" y="-30" width="{W}" height="30" fill="url(#wg)"><animateTransform attributeName="transform" type="translate" from="0 0" to="0 {H + 30}" begin="{at(done)}" dur="1.4s"/></rect>
<rect width="{W}" height="{H}" fill="url(#lines)"/>
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="none" stroke="{MINT}" stroke-opacity=".35"/>
</svg>'''


# ------------------------------------------------------------------------ footer

def footer() -> str:
    W, H = 980, 96
    line = "build -> measure -> ship -> learn"
    lw = text_width(line, 15)
    style = base_style(
        f"@keyframes type{{from{{width:0}}to{{width:{num(lw)}px}}}}"
        "@keyframes flow{from{transform:translateX(-50%)}to{transform:translateX(0)}}"
        ".flow{animation:flow 6s linear infinite}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(line)}">
{style}
<defs><linearGradient id="f" x1="0" x2="1" spreadMethod="repeat"><stop offset="0" stop-color="{MINT}"/><stop offset=".33" stop-color="{CYAN}"/><stop offset=".66" stop-color="{PINK}"/><stop offset="1" stop-color="{MINT}"/></linearGradient>
<clipPath id="ty"><rect x="{num(W / 2 - lw / 2)}" y="30" width="0" height="26"><animate attributeName="width" values="0;{num(lw)};{num(lw)};0" keyTimes="0;.35;.85;1" dur="7s" repeatCount="indefinite" calcMode="spline" keySplines=".4 0 .6 1;0 0 1 1;.4 0 .6 1"/></rect></clipPath></defs>
<g class="flow"><rect x="0" y="4" width="{W * 2}" height="2" fill="url(#f)"/></g>
<text x="{W / 2}" y="49" text-anchor="middle" font-size="15" font-weight="700" fill="{TEXT}" clip-path="url(#ty)">{esc(line)}</text>
<text x="{W / 2}" y="80" text-anchor="middle" font-size="10.5" letter-spacing="2" fill="{DIM}">EOF · AY-MR · TAIWAN · <tspan fill="{MINT}">exit 0</tspan></text>
</svg>'''


def all_cards() -> dict[str, str]:
    out = {"hero.svg": hero(), "stack.svg": stack(), "decrypt.svg": decrypt(), "footer.svg": footer()}
    out.update(buttons())
    out.update(store_badges())
    for name, args in HEADERS.items():
        out[name] = header(*args)
    out["card-zonr.svg"] = card_zonr()
    out["card-lensguard.svg"] = card_lensguard()
    out["card-preflight.svg"] = card_preflight()
    out["card-microwave.svg"] = card_microwave()
    return out



def main() -> None:
    for name, svg in all_cards().items():
        target = ASSETS / "cards" / name
        write(target, svg)
        print(f"built {target.relative_to(ROOT)} ({target.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
