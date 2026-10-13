#!/usr/bin/env python3
"""The README "orbit": visitors sign in with an issue, their avatar joins the orbit.

    python3 scripts/orbit.py add      # add ORBIT_LOGIN / ORBIT_USER_ID to data/orbit.json
    python3 scripts/orbit.py render   # write metrics/orbit.svg (avatars embedded as data URIs)
    python3 scripts/orbit.py render --demo   # offline preview with placeholder avatars

Only public identity is stored: the GitHub login, numeric user id and join date.
Inputs come from the issue *author* (set by GitHub), never from issue text.
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svgkit import (  # noqa: E402
    ACCENT, BG0, DIM, FONT_SLOT, GOLD, LINE, MONO, MUTED, ROOT, SOFT, STEEL,
    TEXT, esc, grain, grain_layer, num, text_width, window_dots, write,
)

DATA = ROOT / "data" / "orbit.json"
OUTPUT = Path(os.environ.get("ORBIT_OUTPUT", ROOT / "metrics" / "orbit.svg"))
OWNER = os.environ.get("GITHUB_LOGIN", "masddffee").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
INCLUDE_FOLLOWERS = os.environ.get("ORBIT_INCLUDE_FOLLOWERS", "1") == "1"
TZ = timezone(timedelta(hours=int(os.environ.get("PROFILE_TZ_OFFSET", "8"))))
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
MAX_STORED = 120

RINGS = [  # (radius, capacity, seconds per revolution, avatar radius)
    (172, 7, 46, 17),
    (282, 11, 70, 16),
    (392, 15, 98, 15),
]
TILT = 0.42
CX, CY = 490, 262
CYCLE = 15  # seconds per burst -> orbit -> implode loop


# ----------------------------------------------------------------------- data

def load() -> dict:
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    return {"members": []}


def save(state: dict) -> None:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add() -> int:
    login = os.environ.get("ORBIT_LOGIN", "").strip()
    user_id = os.environ.get("ORBIT_USER_ID", "").strip()
    if not LOGIN_RE.match(login) or not user_id.isdigit():
        print("Refusing to add: unexpected login or id.", file=sys.stderr)
        return 2
    if login.lower() == OWNER.lower():
        print("Owner is already the center of the orbit.")
        return 0
    state = load()
    members = state["members"]
    if any(m["id"] == int(user_id) for m in members):
        print(f"@{login} is already in orbit.")
        set_output("status", "existing")
        return 0
    members.insert(0, {"login": login, "id": int(user_id), "joined": datetime.now(TZ).date().isoformat()})
    del members[MAX_STORED:]
    save(state)
    set_output("status", "added")
    print(f"Welcomed @{login} into orbit ({len(members)} total).")
    return 0


def set_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={value}\n")


# ---------------------------------------------------------------------- fetch

def api(url: str):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-orbit"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
        return json.load(resp)


def followers() -> list[dict]:
    try:
        rows = api(f"https://api.github.com/users/{OWNER}/followers?per_page=100")
    except Exception as exc:  # Followers are a nice-to-have.
        print(f"Skipping followers: {exc}", file=sys.stderr)
        return []
    return [{"login": r["login"], "id": r["id"]} for r in rows if r.get("type") == "User"]


def owner_id() -> int | None:
    configured = os.environ.get("GITHUB_OWNER_ID", "").strip()
    if configured.isdigit():
        return int(configured)
    try:
        return api(f"https://api.github.com/users/{OWNER}")["id"]
    except Exception:
        return None


def avatar(user_id: int, size: int) -> str | None:
    url = f"https://avatars.githubusercontent.com/u/{int(user_id)}?s={size}&v=4"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "profile-orbit"}), timeout=20) as resp:
            mime = resp.headers.get_content_type()
            blob = resp.read(300_001)
    except Exception:
        return None
    if mime not in {"image/png", "image/jpeg", "image/gif", "image/webp"} or len(blob) > 300_000:
        return None
    return f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"


def placeholder(login: str) -> str:
    """Monochrome initial so a failed avatar download never breaks the card."""
    shade = 28 + sum(map(ord, login)) % 24
    initial = esc(login[:1].upper())
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="rgb({shade},{shade},{shade + 2})"/>'
        f'<text x="32" y="43" text-anchor="middle" font-family="monospace" font-size="30" font-weight="700" fill="{TEXT}">{initial}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode("ascii")


# --------------------------------------------------------------------- render

def depth_keyframes() -> str:
    """Counter-rotation that keeps avatars upright, plus a depth cue (scale/opacity)."""
    steps = []
    for i in range(17):
        theta = 360 * i / 16
        front = (1 + math.sin(math.radians(theta))) / 2  # 1 at the front (bottom) of the ellipse
        steps.append(
            f"{num(100 * i / 16)}%{{transform:rotate({num(-theta)}deg) scale({0.74 + 0.34 * front:.3f});opacity:{0.42 + 0.58 * front:.2f}}}"
        )
    spin = "@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}"
    return spin + "@keyframes cspin{" + "".join(steps) + "}"


def render(demo: bool = False) -> str:
    state = load()
    members = [m for m in state["members"] if m["login"].lower() != OWNER.lower()]
    guest_ids = {m["id"] for m in members}
    if demo:
        names = ["octocat", "tyc4d", "neo", "trinity", "morpheus", "ada", "linus", "grace", "alan", "margaret", "dennis", "ken"]
        members = [{"login": n, "id": i + 1} for i, n in enumerate(names)]
    elif INCLUDE_FOLLOWERS and TOKEN:
        seen = {m["id"] for m in members}
        members += [f for f in followers() if f["id"] not in seen and f["login"].lower() != OWNER.lower()]

    capacity = sum(c for _, c, _, _ in RINGS)
    visible = members[:capacity]
    me = None if demo else owner_id()
    center_img = (avatar(me, 160) if me else None) or placeholder(OWNER)

    W, H = 980, 470
    rng_seed = 9
    stars = []
    for i in range(70):
        rng_seed = (rng_seed * 1103515245 + 12345) & 0x7FFFFFFF
        x = rng_seed % W
        rng_seed = (rng_seed * 1103515245 + 12345) & 0x7FFFFFFF
        y = 44 + rng_seed % (H - 60)
        r = 0.6 + (i % 3) * 0.45
        stars.append(f'<circle class="star" style="animation-delay:{-(i % 7) * .6:.1f}s" cx="{x}" cy="{y}" r="{r:.2f}" fill="{TEXT}"/>')

    rings_svg, people, slots = [], [], []
    index = 0
    for ring_no, (radius, cap, period, ar) in enumerate(RINGS):
        rings_svg.append(
            f'<ellipse cx="{CX}" cy="{CY}" rx="{radius}" ry="{num(radius * TILT)}" fill="none" stroke="{[TEXT, STEEL, GOLD][ring_no]}" '
            f'stroke-opacity="{[.22, .16, .2][ring_no]}" stroke-dasharray="{"3 6" if ring_no else "1 5"}"/>'
        )
        ring_members = visible[index:index + cap]
        index += cap
        count = len(ring_members)
        ghosts = 0
        if ring_no == 0 and count < 4:
            ghosts = 4 - count
        total = count + ghosts
        for j in range(total):
            phase = j / total + ring_no * 0.13
            delay = -period * phase
            is_ghost = j >= count
            if is_ghost:
                inner = (
                    f'<circle r="{ar}" fill="{BG0}" stroke="{TEXT}" stroke-opacity=".45" stroke-dasharray="3 3"/>'
                    f'<text y="5" text-anchor="middle" font-size="15" font-weight="700" fill="{ACCENT}">?</text>'
                    f'<text y="{ar + 13}" text-anchor="middle" font-size="9" fill="{MUTED}">you?</text>'
                )
            else:
                m = ring_members[j]
                img = placeholder(m["login"]) if demo else (avatar(m["id"], ar * 4) or placeholder(m["login"]))
                label = m["login"] if len(m["login"]) <= 13 else m["login"][:12] + "…"
                ring_color = ACCENT if m["id"] in guest_ids or demo else STEEL
                inner = (
                    f'<circle r="{ar + 2.5}" fill="{BG0}" stroke="{ring_color}" stroke-width="1.4"/>'
                    f'<image href="{img}" x="{-ar}" y="{-ar}" width="{2 * ar}" height="{2 * ar}" clip-path="url(#round)"/>'
                    f'<text y="{ar + 14}" text-anchor="middle" font-size="9" fill="{TEXT}" fill-opacity=".85">@{esc(label)}</text>'
                )
            order = len(people) + len(slots)
            node = (
                f'<g class="burst" style="animation-delay:{.35 + order * .075:.3f}s">'
                f'<g transform="translate({CX} {CY}) scale(1 {TILT})">'
                f'<g class="spin" style="animation-duration:{period}s;animation-delay:{delay:.2f}s">'
                f'<g transform="translate({radius} 0)">'
                f'<g class="cspin" style="animation-duration:{period}s;animation-delay:{delay:.2f}s">'
                f'<g transform="scale(1 {num(1 / TILT)})">{inner}</g></g></g></g></g></g>'
            )
            (slots if is_ghost else people).append(node)

    count_text = f"{len(visible)} IN ORBIT" if visible else "ORBIT OPEN"
    cw = text_width(count_text, 9.5, 1.2) + 30
    style = (
        "<style>" + FONT_SLOT + f"text{{font-family:{MONO}}}"
        + depth_keyframes() +
        ".spin{animation-name:spin;animation-timing-function:linear;animation-iteration-count:infinite}"
        ".cspin{animation-name:cspin;animation-timing-function:linear;animation-iteration-count:infinite}"
        # GitHub strips loading="lazy", so the image inside <details> starts with the page.
        # Loop burst -> orbit -> implode so opening the panel always catches a burst soon.
        f"@keyframes burst{{0%{{transform:scale(0);opacity:0}}4%{{transform:scale(1.16);opacity:1}}"
        f"6%{{transform:scale(.96)}}8%,86%{{transform:scale(1);opacity:1}}91%{{transform:scale(1.12);opacity:1}}"
        f"96%,100%{{transform:scale(0);opacity:0}}}}"
        f".burst{{transform-origin:{CX}px {CY}px;transform:scale(0);opacity:0;"
        f"animation:burst {CYCLE}s cubic-bezier(.25,.8,.3,1) infinite}}"
        f"@keyframes shock{{0%{{transform:scale(.2);opacity:.9}}8%,100%{{transform:scale(9);opacity:0}}}}"
        f".shock{{transform-origin:{CX}px {CY}px;opacity:0;animation:shock {CYCLE}s .2s ease-out infinite}}"
        f"@keyframes flash{{0%,92%{{opacity:0;transform:scale(.4)}}97%{{opacity:.9;transform:scale(1.3)}}100%{{opacity:0;transform:scale(.4)}}}}"
        f".flash{{transform-origin:{CX}px {CY}px;opacity:0;animation:flash {CYCLE}s 1.2s ease-in infinite}}"
        "@keyframes pulse{0%{transform:scale(1);opacity:.8}100%{transform:scale(1.9);opacity:0}}"
        f".pulse{{transform-origin:{CX}px {CY}px;animation:pulse 2.4s ease-out infinite}}"
        "@keyframes tw{0%,100%{opacity:.15}50%{opacity:.8}}.star{animation:tw 3.6s ease-in-out infinite}"
        f".rot{{transform-origin:{CX}px {CY}px;animation:spin 24s linear infinite}}"
        "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}.blink{animation:blink 1.1s steps(1) infinite}"
        "@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
        ".cta{opacity:0;animation:rise .6s 1.6s ease-out forwards}"
        "</style>"
    )
    hint = (
        "JOIN ORBIT -> your avatar lands here in ~1 min"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">The orbit</title>
<desc id="d">{len(visible)} GitHub users orbiting @{esc(OWNER)}: {esc(", ".join("@" + m["login"] for m in visible)) or "nobody yet"}.</desc>
{style}
<defs>
<clipPath id="frame"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18"/></clipPath>
<clipPath id="round" clipPathUnits="objectBoundingBox"><circle cx=".5" cy=".5" r=".5"/></clipPath>
<clipPath id="me"><circle cx="{CX}" cy="{CY}" r="40"/></clipPath>
<radialGradient id="core" cx="50%" cy="56%" r="55%"><stop offset="0" stop-color="#2a100c" stop-opacity=".85"/><stop offset=".5" stop-color="#140c0b" stop-opacity=".55"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
{grain()}
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect width="{W}" height="{H}" fill="url(#core)"/>
{"".join(stars)}
{"".join(rings_svg)}
<circle class="shock" cx="{CX}" cy="{CY}" r="20" fill="none" stroke="{ACCENT}" stroke-width="2"/>
<circle class="flash" cx="{CX}" cy="{CY}" r="60" fill="{TEXT}" fill-opacity=".18"/>
<circle class="pulse" cx="{CX}" cy="{CY}" r="46" fill="none" stroke="{ACCENT}" stroke-opacity=".6"/>
<g class="rot"><circle cx="{CX}" cy="{CY}" r="52" fill="none" stroke="{STEEL}" stroke-opacity=".55" stroke-dasharray="14 8 2 8"/></g>
<circle cx="{CX}" cy="{CY}" r="43" fill="{BG0}" stroke="{ACCENT}" stroke-width="2"/>
<image href="{center_img}" x="{CX - 40}" y="{CY - 40}" width="80" height="80" clip-path="url(#me)"/>
<rect x="{CX - 52}" y="{CY + 58}" width="104" height="18" rx="3" fill="{BG0}" stroke="{LINE}"/>
<text x="{CX}" y="{CY + 70.5}" text-anchor="middle" font-size="10" font-weight="700" fill="{TEXT}">@{esc(OWNER)}</text>
{"".join(slots)}
{"".join(people)}
<rect width="{W}" height="40" fill="#000" fill-opacity=".45"/>
<path d="M0 40.5H{W}" stroke="{LINE}"/>
{window_dots()}
<text x="78" y="24.5" font-size="11.5" fill="{MUTED}"><tspan fill="{ACCENT}">$</tspan> ./orbit --summon <tspan fill="{DIM}">--crew</tspan><tspan class="blink" fill="{ACCENT}"> _</tspan></text>
<rect x="{num(W - 18 - cw)}" y="9" width="{num(cw)}" height="22" rx="3" fill="{BG0}" stroke="{LINE}"/>
<circle class="blink" cx="{num(W - 18 - cw + 13)}" cy="20" r="3" fill="{ACCENT}"/>
<text x="{num(W - 18 - cw + 22)}" y="23.5" font-size="9.5" font-weight="700" letter-spacing="1.2" fill="{SOFT}">{count_text}</text>
<g class="cta"><text x="{W / 2}" y="{H - 16}" text-anchor="middle" font-size="12" letter-spacing=".5" fill="{MUTED}">{esc(hint)}</text></g>
{grain_layer(W, H)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="none" stroke="{LINE}" stroke-width="1.5"/>
</svg>'''


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "render"
    if command == "add":
        return add()
    if command == "render":
        svg = render(demo="--demo" in sys.argv)
        write(OUTPUT, svg)
        print(f"Rendered {OUTPUT}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
