#!/usr/bin/env python3
"""Build the static, hand-animated SVG cards used by the profile README.

These cards only change when the copy changes, so they are generated locally
(or by the workflow when this file changes) instead of on every metrics run.
Animations are pure CSS keyframes + SMIL so they survive GitHub's image proxy:
no scripts, no external requests.

Art direction: a film title sequence — matte black, bone-white type, one racing
red, a little champagne gold, film grain instead of neon glow.
"""
from __future__ import annotations

import math
import random

from svgkit import (
    ACCENT, BG0, BG1, CJK, DIM, DISPLAY, FONT_SLOT, GOLD, LINE,
    MONO, MUTED, PANEL, ROOT, SOFT, STEEL, TEXT, data_uri, esc, grain,
    grain_layer, icon, load_icons, measure, num, text_width, window_dots, write,
)

ASSETS = ROOT / "assets"
ICONS = load_icons()


def base_style(extra: str) -> str:
    return (
        "<style>" + FONT_SLOT +
        f"text{{font-family:{MONO}}}"
        f".dp{{font-family:{DISPLAY};font-weight:400}}"
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
        f'height="{num(size * 1.05)}" fill="{ACCENT}">{discrete("x", cursor_events, cycle)}</rect>'
    )
    return "".join(defs), "".join(body) + cursor


def globe(cx: float, cy: float, r: float) -> str:
    out = []
    period = 22.0
    samples = 36
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r * 1.6}" fill="url(#globeGlow)"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#0d0d0f" stroke="{STEEL}" stroke-opacity=".5" stroke-width="1.1"/>')
    for lat in (-60, -30, 0, 30, 60):
        rad = math.radians(lat)
        rx = r * math.cos(rad)
        out.append(
            f'<ellipse cx="{cx}" cy="{num(cy - r * math.sin(rad))}" rx="{num(rx)}" ry="{num(rx * .22)}" '
            f'fill="none" stroke="{STEEL}" stroke-opacity="{".16" if lat else ".3"}" stroke-width=".8"/>'
        )
    # Meridians: great circles whose apparent width follows |sin| as the globe spins.
    values = ";".join(num(r * abs(math.sin(2 * math.pi * j / samples))) for j in range(samples + 1))
    for k in range(6):
        begin = -period * k / 12
        out.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r}" fill="none" stroke="{STEEL}" '
            f'stroke-opacity=".24" stroke-width=".8"><animate attributeName="rx" dur="{period}s" '
            f'begin="{num(begin)}s" repeatCount="indefinite" values="{values}"/></ellipse>'
        )
    # Data nodes riding on the surface; dim when they pass behind the globe.
    rng = random.Random(11)
    for i in range(12):
        lat = math.radians(rng.uniform(-58, 62))
        lon = rng.uniform(0, 2 * math.pi)
        xs, ops = [], []
        for j in range(samples + 1):
            a = lon + 2 * math.pi * j / samples
            xs.append(num(cx + r * math.cos(lat) * math.sin(a)))
            ops.append("1" if math.cos(a) > 0 else ".1")
        y = cy - r * math.sin(lat)
        color = ACCENT if i % 4 == 0 else TEXT
        out.append(
            f'<circle cy="{num(y)}" r="{2.6 if color == ACCENT else 1.9}" fill="{color}">'
            f'<animate attributeName="cx" dur="{period}s" repeatCount="indefinite" values="{";".join(xs)}"/>'
            f'<animate attributeName="opacity" dur="{period}s" repeatCount="indefinite" values="{";".join(ops)}"/>'
            "</circle>"
        )
    orbit = f"M {num(cx - r * 1.5)} {cy} a {num(r * 1.5)} {num(r * .36)} 0 1 0 {num(r * 3)} 0 a {num(r * 1.5)} {num(r * .36)} 0 1 0 {num(-r * 3)} 0"
    out.append(
        f'<g transform="rotate(-16 {cx} {cy})"><path d="{orbit}" fill="none" stroke="{GOLD}" '
        f'stroke-opacity=".45" stroke-width=".9" stroke-dasharray="1 5"/>'
    )
    for begin, color in (("0s", ACCENT), ("-5.5s", TEXT)):
        out.append(
            f'<circle r="3" fill="{color}"><animateMotion dur="11s" begin="{begin}" '
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
        dur = rng.uniform(8, 15)
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
        y = 68 + i * 15
        width = text_width("[ OK ] " + a + b + c, 11)
        begin = 0.25 + i * 0.32
        boot_defs.append(
            f'<clipPath id="boot{i}"><rect x="44" y="{y - 12}" width="0" height="16">'
            f'<animate attributeName="width" from="0" to="{num(width + 4)}" begin="{begin:.2f}s" '
            f'dur=".3s" fill="freeze"/></rect></clipPath>'
        )
        boot_lines.append(
            f'<text clip-path="url(#boot{i})" x="44" y="{y}" font-size="11" fill="{DIM}">'
            f'<tspan fill="{STEEL}">[ OK ]</tspan> {esc(a)}<tspan fill="{SOFT}">{esc(b)}</tspan>{esc(c)}</text>'
        )

    phrases = [
        [("shipping ", "p"), ("Zonr", "k"), (" -> AI goal planner, iOS + Android", "p")],
        [("guarding vision-AI agents with ", "p"), ("LensGuard", "k")],
        [("building ", "p"), ("agent skills", "k"), (" that catch review blockers", "p")],
        [("turning ", "p"), ("ML prototypes", "k"), (" into products people use", "p")],
    ]
    type_defs, type_body = typing_track(phrases, 128, 324, 14, 5.0, "tp")

    ticker = "AI PRODUCTS // FULL-STACK SYSTEMS // AGENT TOOLING // COMPUTER VISION // EDGE ML // SHIP > DEMO // "
    tick_w = text_width(ticker, 10.5, 2.2)

    title_size = 126
    title_w = measure("AY-MR", title_size, "Anton", spacing=4)
    style = base_style(
        f".rain{{fill:{STEEL};opacity:.07;animation:rain linear infinite}}"
        f".rain .hd{{fill:{TEXT};opacity:.9}}"
        "@keyframes rain{from{transform:translateY(0)}to{transform:translateY(760px)}}"
        "@keyframes leak{0%,100%{opacity:.35;transform:translateX(0)}50%{opacity:.75;transform:translateX(40px)}}"
        ".leak{animation:leak 9s ease-in-out infinite}"
        "@keyframes tick{from{transform:translateX(0)}to{transform:translateX(-" + num(tick_w) + "px)}}"
        ".tick{animation:tick 44s linear infinite}"
        "@keyframes intro{0%{opacity:0;transform:translateY(10px)}35%{opacity:1}42%{opacity:.25}"
        "50%{opacity:1}100%{opacity:1;transform:translateY(0)}}"
        ".intro{opacity:0;animation:intro 1s 1.45s ease-out forwards}"
        ".intro2{opacity:0;animation:fadein .9s 2.2s ease-out forwards}"
        "@keyframes ghost{0%,86%,100%{opacity:0;transform:translate(0,0)}"
        "87%{opacity:.85;transform:translate(-6px,1px);clip-path:inset(10% 0 58% 0)}"
        "89%{transform:translate(5px,-1px);clip-path:inset(60% 0 8% 0)}"
        "91%{transform:translate(-3px,0);clip-path:inset(32% 0 40% 0)}"
        "93%{opacity:.85;transform:translate(4px,1px);clip-path:inset(0 0 76% 0)}"
        "94%{opacity:0}}"
        ".ghost{animation:ghost 7s 3.2s infinite steps(1)}"
        f".p{{fill:{SOFT}}}.k{{fill:{TEXT};font-weight:700}}"
        "@keyframes callout{0%{opacity:0}100%{opacity:1}}"
        ".co{opacity:0;animation:callout .6s ease-out forwards}"
        "@keyframes bar{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        ".ubar{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:bar 1s 2s cubic-bezier(.2,.9,.2,1) forwards}"
        "@keyframes eq{0%,100%{transform:scaleY(.25)}50%{transform:scaleY(1)}}"
        ".eq{transform-box:fill-box;transform-origin:bottom;animation:eq 1.3s ease-in-out infinite}"
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
            f'<path d="M {num(px)} {num(py)} L {num(bx + w / 2)} {num(ly + 9)}" stroke="{STEEL}" stroke-opacity=".35" stroke-width=".8" fill="none"/>'
            f'<circle cx="{num(px)}" cy="{num(py)}" r="2" fill="{TEXT}"/>'
            f'<rect x="{num(bx)}" y="{ly}" width="{num(w)}" height="18" rx="2" fill="{BG0}" fill-opacity=".9" stroke="{STEEL}" stroke-opacity=".35"/>'
            f'<text x="{num(bx + w / 2)}" y="{ly + 12.5}" text-anchor="middle" font-size="9.5" letter-spacing="1.5" fill="{SOFT}" font-weight="700">{label}</text></g>'
        )

    brackets = "".join(
        f'<path d="M {x} {y + dy * 16} V {y} H {x + dx * 16}" stroke="{STEEL}" stroke-opacity=".45" fill="none" stroke-width="1.2"/>'
        for (x, y, dx, dy) in ((650, 62, 1, 1), (954, 62, -1, 1), (650, 352, 1, -1), (954, 352, -1, -1))
    )
    eq = "".join(
        f'<rect class="eq" x="{896 + i * 6}" y="320" width="3" height="18" fill="{ACCENT if i in (2, 5) else STEEL}" fill-opacity=".8" style="animation-delay:{-i * .17:.2f}s"/>'
        for i in range(8)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">AY-MR — AI product engineer</title>
<desc id="d">Cinematic terminal-style banner: AI product engineer building Zonr, LensGuard and agent tooling, Taiwan.</desc>
{style}
<defs>
<clipPath id="frame"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20"/></clipPath>
<radialGradient id="warm" cx="8%" cy="95%" r="65%"><stop offset="0" stop-color="#3a120d" stop-opacity=".75"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<radialGradient id="cool" cx="82%" cy="52%" r="48%"><stop offset="0" stop-color="#1a1d22" stop-opacity=".9"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<radialGradient id="globeGlow"><stop offset="0" stop-color="{STEEL}" stop-opacity=".09"/><stop offset="1" stop-color="{STEEL}" stop-opacity="0"/></radialGradient>
<radialGradient id="vig" cx="50%" cy="50%" r="75%"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".7"/></radialGradient>
<linearGradient id="leakG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff6a3d" stop-opacity=".16"/><stop offset=".5" stop-color="#ff6a3d" stop-opacity="0"/></linearGradient>
<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="160" y2="0">
<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
<animateTransform attributeName="gradientTransform" type="translate" values="-200 0;-200 0;{num(title_w + 260)} 0" keyTimes="0;.55;1" dur="6s" begin="2.4s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="border" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".9"/><stop offset=".3" stop-color="{LINE}"/><stop offset="1" stop-color="{LINE}"/>
<animateTransform attributeName="gradientTransform" type="rotate" from="0 .5 .5" to="360 .5 .5" dur="14s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="rainFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".25" stop-color="#fff"/><stop offset=".8" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<mask id="rainMask"><rect x="590" y="40" width="390" height="320" fill="url(#rainFade)"/></mask>
{grain()}
{"".join(boot_defs)}{type_defs}
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect width="{W}" height="{H}" fill="url(#warm)"/>
<rect width="{W}" height="{H}" fill="url(#cool)"/>
<g mask="url(#rainMask)">{"".join(rain)}</g>
{globe(gx, gy, gr)}
{brackets}
<text x="664" y="80" font-size="9" letter-spacing="1.6" fill="{STEEL}" fill-opacity=".7">NEURAL.MAP // LIVE</text>
<text x="940" y="80" text-anchor="end" font-size="9" letter-spacing="1.4" fill="{SOFT}"><tspan class="pulse" fill="{ACCENT}">●</tspan> NOMINAL</text>
<text x="664" y="344" font-size="9" letter-spacing="1.2" fill="{DIM}">LAT 23.69N  LON 120.96E  //  UTC+8</text>
{eq}
{"".join(co)}

<rect x="0" y="0" width="{W}" height="40" fill="#000" fill-opacity=".45"/>
<path d="M0 40.5H{W}" stroke="{LINE}"/>
{window_dots()}
<text x="{W / 2}" y="24.5" text-anchor="middle" font-size="11.5" fill="{DIM}">ay-mr@taiwan: <tspan fill="{SOFT}">~/profile</tspan> — zsh — 980×400</text>
<text x="{W - 24}" y="24.5" text-anchor="end" font-size="10.5" font-weight="700" letter-spacing="1.5" fill="{ACCENT}"><tspan class="blink">●</tspan> REC</text>

{"".join(boot_lines)}

<g class="intro">
<text class="dp ghost" x="40" y="252" font-size="{title_size}" letter-spacing="4" fill="{ACCENT}">AY-MR</text>
<text class="dp" x="40" y="252" font-size="{title_size}" letter-spacing="4" fill="{TEXT}">AY-MR</text>
<text class="dp" x="40" y="252" font-size="{title_size}" letter-spacing="4" fill="url(#shine)" opacity=".55">AY-MR</text>
</g>
<rect class="ubar" x="44" y="266" width="64" height="4" fill="{ACCENT}"/>
<rect class="ubar" x="114" y="266" width="10" height="4" fill="{TEXT}" fill-opacity=".6"/>
<g class="intro2">
<text x="{num(54 + title_w)}" y="150" font-size="10" letter-spacing="2.4" fill="{DIM}" transform="rotate(90 {num(54 + title_w)} 150)">TW · EST. 2024</text>
<text x="44" y="296" font-size="16" fill="{SOFT}">AI product engineer <tspan fill="{DIM}">/</tspan> full-stack <tspan fill="{DIM}">/</tspan> applied ML <tspan fill="{DIM}">/</tspan> agents</text>
<text x="44" y="324" font-size="14" fill="{ACCENT}" font-weight="700">$ <tspan fill="{STEEL}">./now</tspan></text>
{type_body}
</g>

<path d="M0 362.5H{W}" stroke="{LINE}"/>
<rect x="0" y="363" width="{W}" height="{H - 363}" fill="#000" fill-opacity=".45"/>
<g class="tick"><text x="24" y="385.5" font-size="10.5" letter-spacing="2.2" fill="{DIM}">{esc(ticker * 4)}</text></g>

<rect class="leak" x="-80" y="0" width="520" height="{H}" fill="url(#leakG)"/>
{grain_layer(W, H, moving=True)}
<rect width="{W}" height="{H}" fill="url(#vig)"/>
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="none" stroke="url(#border)" stroke-width="1.4"/>
</svg>'''


# ------------------------------------------------------------------------ buttons

def rect_perimeter(w: float, h: float, r: float) -> float:
    return 2 * (w + h) - (8 - 2 * math.pi) * r


def button(label: str, sub: str, glyph: str) -> str:
    W, H, R = 232, 56, 10
    per = rect_perimeter(W - 2, H - 2, R)
    style = base_style(
        f"@keyframes run{{from{{stroke-dashoffset:0}}to{{stroke-dashoffset:-{num(per)}}}}}"
        ".run{animation:run 4.2s linear infinite}"
        "@keyframes nudge{0%,60%,100%{transform:translateX(0)}75%{transform:translateX(4px)}}"
        ".arr{animation:nudge 2.4s ease-in-out infinite}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)} — {esc(sub)}">
{style}
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{R}" fill="{PANEL}" stroke="{LINE}"/>
<rect class="run" x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{R}" fill="none" stroke="{ACCENT}" stroke-width="1.4" stroke-linecap="round" stroke-dasharray="38 {num(per - 38)}"/>
<rect x="12" y="12" width="32" height="32" rx="6" fill="#1a1a1d" stroke="{LINE}"/>
<g transform="translate(16 16)">{glyph}</g>
<text x="56" y="27" class="dp" font-size="17" letter-spacing="1.4" fill="{TEXT}">{esc(label)}</text>
<text x="56" y="42" font-size="9.5" fill="{MUTED}">{esc(sub)}</text>
<g class="arr"><text x="{W - 18}" y="33" text-anchor="end" font-size="15" font-weight="700" fill="{ACCENT}">-&gt;</text></g>
</svg>'''


def glyph_lens(color: str) -> str:
    return (
        f'<circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="12" cy="12" r="5.5" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="12" cy="12" r="1.8" fill="{ACCENT}"/>'
        f'<path d="M12 2 L15 8 M22 12 L16 15 M12 22 L9 16 M2 12 L8 9" stroke="{color}" stroke-width="1.1"/>'
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
        "btn-zonr.svg": button("ZONR.PRO", "official site + app", glyph_image(planet)),
        "btn-lensguard.svg": button("LENSGUARD", "open-source vision AI", glyph_lens(TEXT)),
        "btn-email.svg": button("EMAIL", "houbaian54@gmail.com", icon(ICONS, "gmail", 0, 0, 24, TEXT)),
        "btn-orbit.svg": button("JOIN ORBIT", "drop your avatar here", glyph_orbit(TEXT)),
    }


# ----------------------------------------------------------------------- headers

def header(index: str, title: str, command: str) -> str:
    W, H = 980, 64
    style = base_style(
        "@keyframes sweep{from{transform:translateX(-160px)}to{transform:translateX(1000px)}}"
        ".sw{animation:sweep 6s cubic-bezier(.6,0,.4,1) infinite}"
    )
    tw = measure(title, 32, "Anton", spacing=2)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">
{style}
<defs><linearGradient id="s" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/><stop offset=".5" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>
<text x="4" y="40" font-size="12" font-weight="700" fill="{ACCENT}">{esc(index)}</text>
<rect x="30" y="18" width="1" height="26" fill="{LINE}"/>
<text x="44" y="42" class="dp" font-size="32" letter-spacing="2" fill="{TEXT}">{esc(title)}</text>
<rect class="blink" x="{num(52 + tw)}" y="20" width="11" height="22" fill="{ACCENT}"/>
<text x="{W - 4}" y="38" text-anchor="end" font-size="12" fill="{DIM}"><tspan fill="{ACCENT}">$</tspan> {esc(command)}</text>
<rect x="4" y="54" width="{W - 8}" height="1" fill="{LINE}"/>
<rect class="sw" x="0" y="53" width="160" height="3" rx="1.5" fill="url(#s)"/>
</svg>'''


HEADERS = {
    "h-work.svg": ("01", "SELECTED WORK", "ls ~/projects --featured"),
    "h-journey.svg": ("02", "THE JOURNEY", "git log --reverse --oneline"),
    "h-stack.svg": ("03", "TECH STACK", "cat ~/.stack.yml"),
    "h-activity.svg": ("04", "ENGINEERING ACTIVITY", "git log --since=1y | viz"),
    "h-orbit.svg": ("05", "THE ORBIT", "./orbit --summon"),
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
        f'<text x="26" y="{118 + i * 18}" font-size="12.5" fill="{MUTED}">{esc(line)}</text>'
        for i, line in enumerate(wrapped)
    )
    meta_y = 118 + max(len(wrapped), 3) * 18 + 8
    chip_svg, cx = [], 26.0
    for chip in chips:
        w = text_width(chip, 10.5) + 18
        chip_svg.append(
            f'<rect x="{num(cx)}" y="232" width="{num(w)}" height="24" rx="3" fill="#1a1a1d" stroke="{LINE}"/>'
            f'<text x="{num(cx + w / 2)}" y="248" text-anchor="middle" font-size="10.5" fill="{SOFT}">{esc(chip)}</text>'
        )
        cx += w + 8
    sw = text_width(status, 9.5, 1.2) + 30
    tw = measure(title, 38, "Anton", spacing=1)
    cjk = (
        f'<text class="cjk" x="{num(32 + tw)}" y="88" font-size="19" font-weight="700" fill="{accent}">{esc(title_cjk)}</text>'
        if title_cjk else ""
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)} — {esc(tagline)}">
{style}
<defs>
<radialGradient id="glow" cx="80%" cy="35%" r="55%"><stop offset="0" stop-color="{accent}" stop-opacity=".09"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{accent}" stop-opacity=".55"/><stop offset=".35" stop-color="{LINE}"/><stop offset="1" stop-color="{LINE}"/></linearGradient>
<clipPath id="cardclip"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>
<filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
{grain()}
{extra_defs}
</defs>
<g clip-path="url(#cardclip)">
<rect width="{W}" height="{H}" fill="{PANEL}"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>
{art}
{grain_layer(W, H)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="url(#edge)" stroke-width="1.2"/>
<text x="26" y="38" font-size="11" font-weight="700" letter-spacing="1.2" fill="{accent}">{esc(index)} <tspan fill="{DIM}">/ {esc(kind)}</tspan></text>
<rect x="{num(W - 22 - sw)}" y="22" width="{num(sw)}" height="22" rx="3" fill="{BG0}" fill-opacity=".8" stroke="{LINE}"/>
<circle class="pulse" cx="{num(W - 22 - sw + 13)}" cy="33" r="3" fill="{ACCENT}"/>
<text x="{num(W - 22 - sw + 22)}" y="36.5" font-size="9.5" font-weight="700" letter-spacing="1.2" fill="{SOFT}">{esc(status)}</text>
<text class="dp" x="26" y="90" font-size="38" letter-spacing="1" fill="{TEXT}">{esc(title)}</text>
{cjk}
{lines}
<text x="26" y="{meta_y}" font-size="11" fill="{accent}">&gt; <tspan fill="{SOFT}">{meta_svg or esc(meta)}</tspan></text>
{"".join(chip_svg)}
<text x="{W - 24}" y="249" text-anchor="end" font-size="13" font-weight="700" fill="{ACCENT}">open -&gt;</text>
</svg>'''


def sparkle(x: float, y: float, s: float, color: str, delay: float) -> str:
    d = f"M0 {-s} C {s * .15} {-s * .15} {s * .15} {-s * .15} {s} 0 C {s * .15} {s * .15} {s * .15} {s * .15} 0 {s} C {-s * .15} {s * .15} {-s * .15} {s * .15} {-s} 0 C {-s * .15} {-s * .15} {-s * .15} {-s * .15} 0 {-s} Z"
    return f'<g transform="translate({num(x)} {num(y)})"><path class="tw" style="animation-delay:{delay}s" d="{d}" fill="{color}"/></g>'


def card_zonr() -> str:
    uri = data_uri(ASSETS / "brand" / "zonr-planet.jpg", "image/jpeg")
    cx, cy, r = 396, 124, 66
    back = f"M {cx - 96} {cy + 8} A 96 26 0 0 1 {cx + 96} {cy - 8}"
    front = f"M {cx + 96} {cy - 8} A 96 26 0 0 1 {cx - 96} {cy + 8}"
    art = f'''
<g transform="rotate(-12 {cx} {cy})"><path d="{back}" fill="none" stroke="{GOLD}" stroke-opacity=".4" stroke-width="1" stroke-dasharray="2 4"/></g>
<circle cx="{cx}" cy="{cy}" r="{r + 14}" fill="url(#halo)"/>
<g class="drift"><clipPath id="pl"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>
<image href="{uri}" x="{cx - r * 1.19}" y="{cy - r * 1.2}" width="{r * 2.55}" height="{r * 2.55}" clip-path="url(#pl)"/>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#terminator)"/>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GOLD}" stroke-opacity=".25"/></g>
<g transform="rotate(-12 {cx} {cy})"><path d="{front}" fill="none" stroke="{GOLD}" stroke-width="1.3" stroke-opacity=".85"/>
<circle r="3.6" fill="{TEXT}"><animateMotion dur="4.4s" repeatCount="indefinite" path="{front}"/>
<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.15;.85;1" dur="4.4s" repeatCount="indefinite"/></circle></g>
{sparkle(cx - 84, cy - 62, 6, GOLD, 0)}{sparkle(cx + 78, cy - 70, 4, TEXT, .9)}{sparkle(cx + 86, cy + 58, 5, GOLD, 1.8)}
'''
    return card(
        index="01", kind="SHIPPED APP", title="ZONR", title_cjk="佐能", status="LIVE · iOS + ANDROID",
        accent=GOLD,
        tagline="AI planner that turns a stalled, deadline-driven goal into clear stages and the one step that matters today.",
        meta="WorldSkills BeChangeMaker 2026 · Top 15",
        chips=["TypeScript", "LLM planning", "RevenueCat"],
        art=art,
        extra_defs=(
            f'<radialGradient id="halo"><stop offset=".75" stop-color="{GOLD}" stop-opacity=".12"/><stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="terminator" cx="30%" cy="28%" r="85%"><stop offset=".45" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>'
        ),
        extra_style=(
            "@keyframes tw{0%,100%{transform:scale(.4);opacity:.2}50%{transform:scale(1);opacity:.9}}"
            ".tw{transform-box:fill-box;transform-origin:center;animation:tw 3.4s ease-in-out infinite}"
            "@keyframes drift{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}"
            ".drift{animation:drift 6s ease-in-out infinite}"
        ),
    )


def card_lensguard() -> str:
    cx, cy = 396, 104
    blades = "".join(
        f'<path d="M {cx} {cy} L {num(cx + 40 * math.cos(math.radians(a)))} {num(cy + 40 * math.sin(math.radians(a)))} '
        f'L {num(cx + 40 * math.cos(math.radians(a + 60)))} {num(cy + 40 * math.sin(math.radians(a + 60)))} Z" '
        f'fill="{TEXT}" fill-opacity="{.03 + (i % 2) * .04:.2f}" stroke="{STEEL}" stroke-opacity=".45" stroke-width=".8"/>'
        for i, a in enumerate(range(0, 360, 60))
    )
    stages = ["observe", "distinguish", "decide", "protect"]
    art = f'''
<circle cx="{cx}" cy="{cy}" r="66" fill="none" stroke="{STEEL}" stroke-opacity=".2" stroke-dasharray="2 4"/>
<circle cx="{cx}" cy="{cy}" r="54" fill="#0c0c0e" stroke="{STEEL}" stroke-opacity=".6" stroke-width="1.4"/>
<g class="iris">{blades}</g>
<circle cx="{cx}" cy="{cy}" r="14" fill="#050506" stroke="{STEEL}" stroke-width="1.1"/>
<circle cx="{cx}" cy="{cy}" r="4" fill="{ACCENT}" class="pulse"/>
<circle cx="{cx - 6}" cy="{cy - 6}" r="2.6" fill="#fff" fill-opacity=".55"/>
<g class="sweep"><path d="M {cx} {cy} L {cx + 54} {cy} A 54 54 0 0 0 {num(cx + 54 * math.cos(math.radians(-38)))} {num(cy + 54 * math.sin(math.radians(-38)))} Z" fill="url(#beam)"/></g>
<g class="inj">
<rect x="{cx - 54}" y="{cy + 62}" width="118" height="22" rx="2" fill="#0c0c0e" stroke="{ACCENT}" stroke-opacity=".6"/>
<text x="{cx + 5}" y="{cy + 76.5}" text-anchor="middle" font-size="9" fill="{MUTED}">"ignore user, pay $"</text>
<g class="stamp"><rect x="{cx - 54}" y="{cy + 62}" width="118" height="22" rx="2" fill="{ACCENT}"/>
<text x="{cx + 5}" y="{cy + 77.5}" text-anchor="middle" class="dp" font-size="13" letter-spacing="3" fill="{TEXT}">BLOCKED</text></g>
</g>
'''
    meta_spans = " -&gt; ".join(
        f'<tspan class="stg" style="animation-delay:{i * .9:.1f}s">{s}</tspan>' for i, s in enumerate(stages)
    )
    return card(
        index="02", kind="OPEN SOURCE · MIT", title="LENSGUARD", title_cjk="", status="TEAM PROJECT",
        accent=ACCENT,
        tagline="Action-authorization guard for vision-AI assistants: stops prompt injections hidden in camera scenes.",
        meta=" -> ".join(stages),
        meta_svg=meta_spans,
        chips=["NVIDIA VLM", "FastAPI", "React 19"],
        art=art,
        extra_defs=f'<linearGradient id="beam" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/><stop offset="1" stop-color="{ACCENT}" stop-opacity=".35"/></linearGradient>',
        extra_style=(
            "@keyframes spin{to{transform:rotate(360deg)}}"
            f".iris{{transform-origin:{cx}px {cy}px;animation:spin 22s linear infinite}}"
            f".sweep{{transform-origin:{cx}px {cy}px;animation:spin 3.4s linear infinite}}"
            "@keyframes inj{0%,8%{opacity:0;transform:translateY(6px)}16%,92%{opacity:1;transform:none}100%{opacity:0}}"
            ".inj{animation:inj 4.4s ease-out infinite}"
            "@keyframes stamp{0%,45%{opacity:0;transform:scale(1.7)}52%{opacity:1;transform:scale(.94)}58%,90%{opacity:1;transform:scale(1)}100%{opacity:0}}"
            ".stamp{transform-box:fill-box;transform-origin:center;animation:stamp 4.4s ease-out infinite}"
            f"@keyframes stg{{0%,100%{{fill:{SOFT}}}10%,25%{{fill:{ACCENT}}}}}"
            ".stg{animation:stg 3.6s linear infinite}"
        ),
    )


def card_preflight() -> str:
    items = ["data safety", "permissions", "target SDK", "store listing", "privacy URL"]
    x0, y0 = 326, 62
    rows = []
    for i, item in enumerate(items):
        y = y0 + 34 + i * 22
        d = 0.35 + i * 0.45
        rows.append(
            f'<rect x="{x0 + 12}" y="{y - 10}" width="13" height="13" rx="2" fill="none" stroke="{STEEL}" stroke-opacity=".5"/>'
            f'<path class="tick" style="animation-delay:{d:.2f}s" d="M {x0 + 15} {y - 3.5} l 3 3 l 5.5 -6" fill="none" stroke="{TEXT}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" pathLength="1"/>'
            f'<text x="{x0 + 33}" y="{y + 1}" font-size="10" fill="{SOFT}">{esc(item)}</text>'
        )
    art = f'''
<rect x="{x0}" y="{y0}" width="132" height="132" rx="6" fill="#0c0c0e" stroke="{LINE}"/>
<rect x="{x0}" y="{y0}" width="132" height="20" rx="6" fill="#1a1a1d"/>
<text x="{x0 + 10}" y="{y0 + 13.5}" font-size="8.5" font-weight="700" letter-spacing="1.2" fill="{STEEL}">PREFLIGHT.CHECK</text>
{icon(ICONS, "android", x0 + 112, y0 + 4, 12, STEEL)}
{"".join(rows)}
<g class="ready"><rect x="{x0 + 26}" y="{y0 + 140}" width="86" height="24" rx="2" fill="none" stroke="{ACCENT}" stroke-width="2"/>
<text x="{x0 + 69}" y="{y0 + 157.5}" text-anchor="middle" class="dp" font-size="14" letter-spacing="3" fill="{ACCENT}">APPROVED</text></g>
'''
    return card(
        index="03", kind="AGENT SKILL", title="PLAY PREFLIGHT", title_cjk="", status="OPEN SOURCE",
        accent=STEEL,
        tagline="Policy-aware preflight for AI coding agents: catches Google Play review blockers before you hit submit.",
        meta="Android · Expo · React Native · Flutter",
        chips=["Claude Code", "Agent skills", "Play policy"],
        art=art,
        extra_style=(
            "@keyframes tick{0%{stroke-dashoffset:1}12%,88%{stroke-dashoffset:0}100%{stroke-dashoffset:1}}"
            ".tick{stroke-dasharray:1;stroke-dashoffset:1;animation:tick 5s ease-out infinite}"
            "@keyframes ready{0%,52%{opacity:0;transform:scale(1.6) rotate(-7deg)}60%{opacity:1;transform:scale(.95) rotate(-7deg)}66%,88%{opacity:1;transform:scale(1) rotate(-7deg)}100%{opacity:0}}"
            ".ready{transform-box:fill-box;transform-origin:center;animation:ready 5s ease-out infinite}"
        ),
    )


def card_microwave() -> str:
    x0, y0 = 318, 70
    art = f'''
<rect x="{x0}" y="{y0}" width="146" height="98" rx="6" fill="#0c0c0e" stroke="{LINE}"/>
<rect x="{x0 + 10}" y="{y0 + 12}" width="92" height="74" rx="4" fill="#060607" stroke="{GOLD}" stroke-opacity=".2"/>
<rect class="heat" x="{x0 + 10}" y="{y0 + 12}" width="92" height="74" rx="4" fill="url(#heatG)"/>
<rect x="{x0 + 22}" y="{y0 + 32}" width="66" height="40" rx="2" fill="#16130e" stroke="{GOLD}" stroke-opacity=".35"/>
<text x="{x0 + 55}" y="{y0 + 63}" text-anchor="middle" class="dp" font-size="20" letter-spacing="1" fill="{TEXT}">3:30</text>
<g class="box"><path d="M {x0 + 30} {y0 + 51} v -5 h 5 M {x0 + 80} {y0 + 46} h 5 v 5 M {x0 + 85} {y0 + 64} v 5 h -5 M {x0 + 35} {y0 + 69} h -5 v -5" fill="none" stroke="{ACCENT}" stroke-width="1.6"/>
<rect x="{x0 + 30}" y="{y0 + 35}" width="42" height="11" rx="1" fill="{ACCENT}"/><text x="{x0 + 51}" y="{y0 + 43.5}" text-anchor="middle" font-size="7.5" font-weight="800" fill="{TEXT}">3:30 .98</text></g>
<rect x="{x0 + 110}" y="{y0 + 14}" width="28" height="16" rx="2" fill="#000" stroke="{LINE}"/>
<text class="seg" x="{x0 + 124}" y="{y0 + 26}" text-anchor="middle" font-size="9" font-weight="800" fill="{GOLD}">0330</text>
<circle cx="{x0 + 124}" cy="{y0 + 48}" r="7" fill="none" stroke="{STEEL}" stroke-opacity=".4"/>
<circle class="pulse" cx="{x0 + 124}" cy="{y0 + 72}" r="4" fill="{ACCENT}"/>
<circle cx="{x0 + 73}" cy="{y0 - 18}" r="7" fill="#000" stroke="{STEEL}" stroke-opacity=".6"/><circle cx="{x0 + 73}" cy="{y0 - 18}" r="2.5" fill="{ACCENT}" class="blink"/>
<path d="M {x0 + 73} {y0 - 11} L {x0 + 40} {y0 + 30} M {x0 + 73} {y0 - 11} L {x0 + 92} {y0 + 30}" stroke="{STEEL}" stroke-opacity=".25" stroke-dasharray="2 3"/>
'''
    return card(
        index="04", kind="AIoT · VISION", title="SMART OVEN", title_cjk="", status="EDGE ML",
        accent=GOLD,
        tagline="Contactless microwave: a camera reads cook time off the food package, so one tap starts heating.",
        meta="digit recognition on a Raspberry Pi 4",
        chips=["TensorFlow", "OpenCV", "Raspberry Pi"],
        art=art,
        extra_defs=f'<radialGradient id="heatG" cx="50%" cy="60%" r="70%"><stop offset="0" stop-color="{GOLD}" stop-opacity=".35"/><stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></radialGradient>',
        extra_style=(
            "@keyframes box{0%,10%{opacity:0;transform:scale(1.5)}25%,80%{opacity:1;transform:scale(1)}100%{opacity:0}}"
            ".box{transform-box:fill-box;transform-origin:center;animation:box 4.5s ease-out infinite}"
            "@keyframes heat{0%,55%{opacity:0}70%,90%{opacity:1}100%{opacity:0}}"
            ".heat{animation:heat 4.5s ease-in-out infinite}"
            "@keyframes seg{0%,50%{opacity:.25}56%,100%{opacity:1}}"
            ".seg{animation:seg 4.5s steps(1) infinite}"
        ),
    )


# -------------------------------------------------------------------- store pills

def store_badge(top: str, label: str, glyph: str) -> str:
    W, H = 176, 50
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(top)} {esc(label)}">
{base_style("")}
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="8" fill="#000" stroke="{LINE}"/>
<rect x="1" y="{H - 3}" width="{W - 2}" height="2" fill="{ACCENT}" fill-opacity=".8"/>
<g transform="translate(14 13)">{glyph}</g>
<text x="50" y="21" font-size="8.5" letter-spacing="1" fill="{MUTED}">{esc(top)}</text>
<text x="50" y="38" class="dp" font-size="17" letter-spacing="1" fill="{TEXT}">{esc(label)}</text>
</svg>'''


def store_badges() -> dict[str, str]:
    planet = data_uri(ASSETS / "brand" / "zonr-planet.jpg", "image/jpeg")
    return {
        "store-web.svg": store_badge("VISIT", "ZONR.PRO", glyph_image(planet)),
        "store-ios.svg": store_badge("DOWNLOAD ON THE", "APP STORE", icon(ICONS, "apple", 0, 0, 24, TEXT)),
        "store-play.svg": store_badge("GET IT ON", "GOOGLE PLAY", icon(ICONS, "googleplay", 0, 0, 24, TEXT)),
    }


# ------------------------------------------------------------------------ journey

JOURNEY = [  # (stamp, title, line 1, line 2) — only publicly verifiable milestones
    ("ORIGINS", "ML SNAKE", "a DQN agent teaches itself", "to play Snake · PyTorch"),
    ("ORIGINS", "SMART OVEN", "a camera reads cook time;", "contactless AIoT on a Pi"),
    ("2026", "ZONR SHIPS", "AI goal planner goes live", "on iOS + Google Play"),
    ("2026", "GLOBAL TOP 15", "WorldSkills BeChangeMaker", "2026 · team Zonr"),
    ("2026.06", "PLAY PREFLIGHT", "open-source agent skill", "for Play Store review"),
    ("2026.09", "LENSGUARD", "safe actions for vision-AI", "assistants · team build"),
    ("NEXT", "NEXT FRAME", "rendering…", "say hi: houbaian54@gmail.com"),
]


def journey() -> str:
    W, H = 980, 250
    fw, gap = 268, 12
    strip_w = len(JOURNEY) * (fw + gap)
    top, bottom = 34, 216
    frames = []
    for copy in range(2):  # two copies make the scroll seamless
        for i, (stamp, title, l1, l2) in enumerate(JOURNEY):
            x = copy * strip_w + i * (fw + gap) + 6
            hot = stamp == "NEXT"
            frames.append(
                f'<g transform="translate({x} {top + 22})">'
                f'<rect width="{fw}" height="{bottom - top - 44}" rx="3" fill="#141416" stroke="{ACCENT if hot else LINE}" stroke-opacity="{.7 if hot else 1}"/>'
                f'<rect width="{fw}" height="{bottom - top - 44}" rx="3" fill="url(#frameVig)"/>'
                f'<text x="14" y="22" font-size="9" letter-spacing="1.6" fill="{DIM}">FRAME {i + 1:02d}</text>'
                f'<text x="{fw - 14}" y="22" text-anchor="end" font-size="10" font-weight="700" letter-spacing="1.4" fill="{ACCENT}">{esc(stamp)}</text>'
                f'<text x="14" y="70" class="dp" font-size="30" letter-spacing="1.2" fill="{TEXT}">{esc(title)}</text>'
                f'<text x="14" y="98" font-size="11" fill="{MUTED}">{esc(l1)}</text>'
                f'<text x="14" y="115" font-size="11" fill="{MUTED}">{esc(l2)}</text>'
                f'<rect x="14" y="128" width="{"28" if not hot else "8"}" height="2" fill="{ACCENT if not hot else TEXT}"{" class=\"blink\"" if hot else ""}/>'
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
        ".reel{animation:reel 90s linear infinite}"
        "@keyframes flicker{0%,100%{opacity:.0}7%{opacity:.05}9%{opacity:0}53%{opacity:.03}55%{opacity:0}}"
        ".flk{animation:flicker 2.2s steps(1) infinite}"
    )
    alt = " / ".join(f"{s} {t}: {a} {b}" for s, t, a, b in JOURNEY)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Journey film strip — {esc(alt)}">
{style}
<defs>
<clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>
<radialGradient id="frameVig" cx="40%" cy="35%" r="80%"><stop offset=".5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".45"/></radialGradient>
<linearGradient id="edgeFade" x1="0" x2="1"><stop offset="0" stop-color="{BG0}"/><stop offset=".07" stop-color="{BG0}" stop-opacity="0"/><stop offset=".93" stop-color="{BG0}" stop-opacity="0"/><stop offset="1" stop-color="{BG0}"/></linearGradient>
{grain()}
</defs>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect x="0" y="{top}" width="{W}" height="{bottom - top}" fill="#1b1b1e"/>
<g class="reel">{"".join(holes)}{"".join(frames)}</g>
<rect x="0" y="{top}" width="{W}" height="{bottom - top}" fill="#fff" class="flk"/>
<rect width="{W}" height="{H}" fill="url(#edgeFade)"/>
<text x="24" y="22" font-size="9.5" letter-spacing="2" fill="{DIM}">REEL 01 · AY-MR · <tspan fill="{SOFT}">ORIGINS -&gt; NOW</tspan></text>
<text x="{W - 24}" y="22" text-anchor="end" font-size="9.5" letter-spacing="2" fill="{ACCENT}"><tspan class="blink">●</tspan> <tspan fill="{SOFT}">PLAYING</tspan></text>
<text x="24" y="{H - 10}" font-size="9" letter-spacing="1.6" fill="{DIM}">35MM · 24 FPS · ONLY PUBLICLY VERIFIABLE MILESTONES</text>
{grain_layer(W, H, moving=True)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="{LINE}"/>
</svg>'''


# ------------------------------------------------------------------------- stack

STACK = [
    ("AI / ML", "models, vision, eval",
     [("python", "Python"), ("pytorch", "PyTorch"), ("tensorflow", "TensorFlow"), ("opencv", "OpenCV"), ("nvidia", "NVIDIA VLM"),
      ("claude", "Claude Code")]),
    ("PRODUCT", "apps, web, APIs",
     [("typescript", "TypeScript"), ("react", "React"), ("nextdotjs", "Next.js"), ("nodedotjs", "Node.js"), ("fastapi", "FastAPI"),
      ("tailwindcss", "Tailwind"), ("supabase", "Supabase")]),
    ("SYSTEMS", "local-first, edge, infra",
     [("rust", "Rust"), ("tauri", "Tauri"), ("cplusplus", "C++"), ("sqlite", "SQLite"), ("docker", "Docker"),
      ("cloudflare", "Cloudflare"), ("raspberrypi", "RasPi"), ("githubactions", "Actions")]),
]


def stack() -> str:
    W = 980
    tile, gap, x0 = 76, 12, 214
    row_h = 98
    H = 24 + row_h * len(STACK)
    rows, n = [], 0
    for r, (name, sub, items) in enumerate(STACK):
        y = 16 + r * row_h
        rows.append(
            f'<text x="22" y="{y + 40}" class="dp" font-size="24" letter-spacing="1.5" fill="{TEXT}">{esc(name)}</text>'
            f'<text x="22" y="{y + 58}" font-size="10.5" fill="{MUTED}">{esc(sub)}</text>'
            f'<rect x="22" y="{y + 68}" width="26" height="2" fill="{ACCENT}"/>'
            f'<path d="M 184 {y + 42} h 22" stroke="{LINE}" stroke-dasharray="2 3"/>'
        )
        for c, (slug, label) in enumerate(items):
            x = x0 + c * (tile + gap)
            delay = (c + r * 2) * 0.2
            rows.append(
                f'<g><rect x="{x}" y="{y + 4}" width="{tile}" height="{tile}" rx="8" fill="{PANEL}" stroke="{LINE}"/>'
                f'<rect class="lit" style="animation-delay:{delay:.2f}s" x="{x}" y="{y + 4}" width="{tile}" height="{tile}" rx="8" fill="{ACCENT}" fill-opacity=".05" stroke="{ACCENT}" stroke-width="1.2"/>'
                f'{icon(ICONS, slug, x + tile / 2 - 13, y + 17, 26, TEXT, " fill-opacity=\".88\"")}'
                f'<text x="{x + tile / 2}" y="{y + 68}" text-anchor="middle" font-size="9.5" fill="{MUTED}">{esc(label)}</text></g>'
            )
            n += 1
    style = base_style(
        "@keyframes lit{0%,100%{opacity:0}12%{opacity:1}30%{opacity:0}}"
        ".lit{opacity:0;animation:lit 5s ease-in-out infinite}"
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
            f'<text x="40" y="{y}" opacity="0" font-size="12.5" font-weight="700" letter-spacing="1.5" fill="{STEEL}">{key}'
            f'{show(start - .2, hide_at)}</text>'
        )
        for f in range(frames):
            garbage = "".join(" " if ch == " " else rng.choice(noise) for ch in value)
            t = start + f * step
            body.append(
                f'<text opacity="0" x="190" y="{y}" font-size="14" fill="{DIM}">{esc(garbage)}{show(t, t + step)}</text>'
            )
        reveal = start + frames * step
        body.append(f'<text opacity="0" x="190" y="{y}" font-size="14" fill="{TEXT}">{esc(value)}{show(reveal, hide_at)}</text>')
        garbage = "".join(" " if ch == " " else rng.choice(noise) for ch in value)
        body.append(
            f'<text opacity="0" x="190" y="{y}" font-size="14" fill="{ACCENT}" fill-opacity=".85">{esc(garbage)}{show(hide_at, hide_at + .35)}</text>'
        )
    bar_w = 420
    done = 1.25 + len(ABOUT) * 0.28 + frames * step
    hex_rows = []
    for _ in range(30):
        row = " ".join(f"{rng.randrange(256):02x}" for _ in range(8))
        hex_rows.append(f'<tspan x="650" dy="15">{row}</tspan>')
    lx, ly = 862, 150
    gw = measure("ACCESS GRANTED", 14, "Anton", spacing=2) + 22
    style = base_style(
        "@keyframes hex{from{transform:translateY(0)}to{transform:translateY(-180px)}}"
        ".hex{animation:hex 9s linear infinite}"
    )
    unlocked = f'begin="{at(done)}" dur="{hide_at - done:.2f}s"'
    k1, k2 = 1 / cycle, hide_at / cycle
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Decrypted profile: {esc(" / ".join(v for _, v in ABOUT))}">
{style}
<defs><clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>
<linearGradient id="wg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{TEXT}" stop-opacity="0"/><stop offset="1" stop-color="{TEXT}" stop-opacity=".1"/></linearGradient>
<clipPath id="hx"><rect x="640" y="24" width="320" height="{H - 48}"/></clipPath>{grain()}</defs>
<rect width="0" height="0"><animate id="clk" attributeName="x" from="0" to="0" begin="0s;clk.end" dur="{cycle}s"/></rect>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<text x="40" y="44" font-size="13" fill="{MUTED}"><tspan fill="{ACCENT}" font-weight="700">$</tspan> decrypt ./about.enc --key=curiosity</text>
<rect x="40" y="58" width="{bar_w}" height="4" fill="{LINE}"/>
<rect x="40" y="58" width="0" height="4" fill="{ACCENT}">
<animate attributeName="width" values="0;{bar_w};{bar_w};0" keyTimes="0;{k1:.4f};{k2:.4f};1" begin="{at(.15)}" dur="{cycle - .15:.2f}s" calcMode="spline" keySplines=".3 .7 .2 1;0 0 1 1;.4 0 1 1"/></rect>
<text x="{48 + bar_w}" y="63" opacity="0" font-size="11" fill="{SOFT}" font-weight="700">100% · key accepted{show(1.15, hide_at)}</text>
<g clip-path="url(#hx)"><g class="hex"><text y="24" font-size="11" fill="{STEEL}" fill-opacity=".14" letter-spacing="1">{"".join(hex_rows)}<set attributeName="fill-opacity" to=".26" {unlocked}/></text></g></g>
<rect x="{lx - 70}" y="{ly - 72}" width="140" height="150" rx="8" fill="{BG0}" fill-opacity=".85"/>
<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -11;0 -11;0 0" keyTimes="0;.06;.94;1" {unlocked}/>
<path d="M {lx - 17} {ly - 4} v -16 a 17 17 0 0 1 34 0 v 16" fill="none" stroke="{STEEL}" stroke-width="5" stroke-linecap="round"><set attributeName="stroke" to="{ACCENT}" {unlocked}/></path></g>
<rect x="{lx - 29}" y="{ly - 6}" width="58" height="46" rx="6" fill="#141416" stroke="{STEEL}" stroke-width="2.2"><set attributeName="stroke" to="{ACCENT}" {unlocked}/></rect>
<circle cx="{lx}" cy="{ly + 12}" r="5" fill="{TEXT}"/><rect x="{lx - 2}" y="{ly + 14}" width="4" height="12" rx="2" fill="{TEXT}"/>
<g opacity="0">{show(done + .2, hide_at)}<rect x="{num(lx - gw / 2)}" y="{ly + 52}" width="{num(gw)}" height="24" rx="2" fill="{ACCENT}"/>
<text x="{lx}" y="{ly + 69}" text-anchor="middle" class="dp" font-size="14" letter-spacing="2" fill="{TEXT}">ACCESS GRANTED</text></g>
{"".join(body)}
<rect x="0" y="-30" width="{W}" height="30" fill="url(#wg)"><animateTransform attributeName="transform" type="translate" from="0 0" to="0 {H + 30}" begin="{at(done)}" dur="1.4s"/></rect>
{grain_layer(W, H)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="none" stroke="{LINE}"/>
</svg>'''


# ------------------------------------------------------------------------ footer

def footer() -> str:
    W, H = 980, 120
    line = "build -> measure -> ship -> learn"
    lw = text_width(line, 14)
    style = base_style(
        "@keyframes flow{from{transform:translateX(-100%)}to{transform:translateX(100%)}}"
        ".flow{animation:flow 5s cubic-bezier(.6,0,.4,1) infinite}"
        "@keyframes fin{0%,100%{opacity:.82}50%{opacity:1}}"
        ".fin{animation:fin 4s ease-in-out infinite}"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Fin — {esc(line)}">
{style}
<defs><linearGradient id="f" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/><stop offset=".5" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient>
<clipPath id="ty"><rect x="{num(W / 2 - lw / 2)}" y="70" width="0" height="24"><animate attributeName="width" values="0;{num(lw)};{num(lw)};0" keyTimes="0;.35;.85;1" dur="7s" repeatCount="indefinite" calcMode="spline" keySplines=".4 0 .6 1;0 0 1 1;.4 0 .6 1"/></rect></clipPath></defs>
<rect x="4" y="4" width="{W - 8}" height="1" fill="{LINE}"/>
<g class="flow"><rect x="0" y="3" width="{W}" height="3" fill="url(#f)"/></g>
<text class="dp fin" x="{W / 2}" y="60" text-anchor="middle" font-size="36" letter-spacing="10" fill="{TEXT}">FIN.</text>
<text x="{W / 2}" y="87" text-anchor="middle" font-size="14" font-weight="700" fill="{SOFT}" clip-path="url(#ty)">{esc(line)}</text>
<text x="{W / 2}" y="112" text-anchor="middle" font-size="9.5" letter-spacing="2" fill="{DIM}">A FILM BY AY-MR · SHOT IN TAIWAN · <tspan fill="{ACCENT}">exit 0</tspan></text>
</svg>'''


def all_cards() -> dict[str, str]:
    out = {
        "hero.svg": hero(),
        "journey.svg": journey(),
        "stack.svg": stack(),
        "decrypt.svg": decrypt(),
        "footer.svg": footer(),
    }
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
