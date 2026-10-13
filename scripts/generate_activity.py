#!/usr/bin/env python3
"""Render metrics/activity.svg from GitHub's contribution graph.

Data comes from the GraphQL `contributionsCollection`, the same source as the
green squares on a GitHub profile, so the numbers match what GitHub shows:

* PROFILE_METRICS_TOKEN — a classic PAT of the profile owner with only the
  `read:user` scope. GitHub then includes private and internal contributions
  in full (no code or repository access is needed).
* GITHUB_TOKEN — the workflow's built-in token. Public contributions, plus
  anonymous private counts when "Private contributions" is switched on in the
  owner's profile settings.

Only aggregate counts are rendered; no repository names or commit messages.

Local preview without network: `python3 scripts/generate_activity.py --demo`.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svgkit import (  # noqa: E402
    ACCENT, BG0, DISPLAY, FONT_SLOT, LINE, MONO, MUTED, ROOT, TEXT, esc, grain,
    grain_layer, num, text_width, window_dots, write,
)

API = "https://api.github.com/graphql"
LOGIN = os.environ.get("GITHUB_LOGIN", "").strip()
OWNER_TOKEN = os.environ.get("PROFILE_METRICS_TOKEN", "").strip()
FALLBACK_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
OUTPUT = Path(os.environ.get("PROFILE_METRICS_OUTPUT", ROOT / "metrics" / "activity.svg"))
TZ = timezone(timedelta(hours=int(os.environ.get("PROFILE_TZ_OFFSET", "8"))))

LAST_YEAR_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionYears
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""


@dataclass
class Stats:
    days: list[tuple[date, int]]  # last-year calendar, oldest first
    total_year: int
    all_time: int
    first_year: int
    current_streak: int
    longest_streak: int
    commits: int
    pull_requests: int
    reviews: int
    issues: int
    repositories: int
    private: int
    mode: str  # "owner" | "public+private" | "public"
    generated: datetime = field(default_factory=lambda: datetime.now(TZ))


# ---------------------------------------------------------------------- fetch

def graphql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-activity-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=40) as response:
        payload = json.load(response)
    if payload.get("errors"):
        messages = "; ".join(e.get("message", "?") for e in payload["errors"])
        raise RuntimeError(f"GraphQL error: {messages}")
    return payload["data"]


def viewer_login(token: str) -> str | None:
    try:
        return graphql(token, "query { viewer { login } }", {})["viewer"]["login"]
    except Exception:
        return None


def year_calendars(token: str, login: str, years: list[int], now: datetime) -> dict[date, int]:
    parts = []
    for year in sorted(years):
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = min(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc), now.astimezone(timezone.utc))
        parts.append(
            f'y{year}: contributionsCollection(from: "{start:%Y-%m-%dT%H:%M:%SZ}", to: "{end:%Y-%m-%dT%H:%M:%SZ}") '
            "{ contributionCalendar { weeks { contributionDays { date contributionCount } } } }"
        )
    query = "query($login: String!) { user(login: $login) { " + " ".join(parts) + " } }"
    data = graphql(token, query, {"login": login})["user"]
    counts: dict[date, int] = {}
    for year in years:
        for week in data[f"y{year}"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                d = date.fromisoformat(day["date"])
                if d.year == year:
                    counts[d] = max(counts.get(d, 0), day["contributionCount"])
    return counts


def streaks(counts: dict[date, int], today: date) -> tuple[int, int]:
    longest = run = 0
    prev = None
    for d in sorted(counts):
        if counts[d] > 0:
            run = run + 1 if prev is not None and d - prev == timedelta(days=1) else 1
            prev = d
            longest = max(longest, run)
    cursor = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    current = 0
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def fetch() -> Stats:
    if not LOGIN:
        raise SystemExit("GITHUB_LOGIN is required.")
    token = OWNER_TOKEN or FALLBACK_TOKEN
    if not token:
        raise SystemExit("Set PROFILE_METRICS_TOKEN or GITHUB_TOKEN.")
    now = datetime.now(TZ)
    owner = bool(OWNER_TOKEN) and (viewer_login(OWNER_TOKEN) or "").lower() == LOGIN.lower()

    collection = graphql(token, LAST_YEAR_QUERY, {"login": LOGIN})["user"]["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    days = [
        (date.fromisoformat(day["date"]), day["contributionCount"])
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]
    years = collection["contributionYears"] or [now.year]
    history = year_calendars(token, LOGIN, years, now)
    for d, c in days:  # The rolling calendar is the freshest source for recent days.
        history[d] = max(history.get(d, 0), c)
    current, longest = streaks(history, now.date())

    private = collection["restrictedContributionsCount"]
    mode = "owner" if owner else ("public+private" if private else "public")
    return Stats(
        days=days,
        total_year=calendar["totalContributions"],
        all_time=sum(history.values()),
        first_year=min(years),
        current_streak=current,
        longest_streak=longest,
        commits=collection["totalCommitContributions"],
        pull_requests=collection["totalPullRequestContributions"],
        reviews=collection["totalPullRequestReviewContributions"],
        issues=collection["totalIssueContributions"],
        repositories=collection["totalRepositoryContributions"],
        private=private,
        mode=mode,
    )


def demo() -> Stats:
    rng = random.Random(42)
    today = datetime.now(TZ).date()
    start = today - timedelta(days=(today.weekday() + 1) % 7) - timedelta(weeks=52)
    days, d = [], start
    while d <= today:
        busy = 0.35 + 0.5 * (math.sin((d - start).days / 40) + 1) / 2
        count = 0 if rng.random() > busy else int(rng.expovariate(1 / 7)) + 1
        days.append((d, count))
        d += timedelta(days=1)
    counts = dict(days)
    current, longest = streaks(counts, today)
    total = sum(c for _, c in days)
    return Stats(
        days=days, total_year=total, all_time=total + 912, first_year=2024,
        current_streak=current, longest_streak=longest,
        commits=int(total * .62), pull_requests=int(total * .16), reviews=int(total * .07),
        issues=int(total * .04), repositories=12, private=0, mode="owner",
    )


# --------------------------------------------------------------------- render

U = (11.4, -3.1)   # one week step on screen
V = (6.6, 5.0)     # one weekday step on screen
X0, Y0 = 24, 366   # screen position of week 0 / Sunday
HMAX = 124
LEVELS = ["#18181b", "#3b3632", "#6e655c", "#b3a998", "#efe9de"]


def shade(hex_color: str, factor: float) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(*(int(c * factor) for c in (r, g, b)))


def iso(w: float, d: float, h: float = 0.0) -> tuple[float, float]:
    return X0 + w * U[0] + d * V[0], Y0 + w * U[1] + d * V[1] - h


def pts(*points) -> str:
    return " ".join(f"{num(x)},{num(y)}" for x, y in points)


def quartile_levels(counts: list[int]) -> list[int]:
    nonzero = sorted(c for c in counts if c > 0)
    if not nonzero:
        return [0] * len(counts)
    q = [nonzero[int(len(nonzero) * f) - 1 if int(len(nonzero) * f) else 0] for f in (.25, .5, .75)]
    return [0 if c == 0 else 1 if c <= q[0] else 2 if c <= q[1] else 3 if c <= q[2] else 4 for c in counts]


def skyline(stats: Stats) -> tuple[str, str]:
    first = stats.days[0][0]
    origin = first - timedelta(days=(first.weekday() + 1) % 7)
    peak = max((c for _, c in stats.days), default=0) or 1
    levels = quartile_levels([c for _, c in stats.days])
    today = stats.generated.date()
    k = 0.8
    cells = []
    for (d, count), lvl in zip(stats.days, levels):
        offset = (d - origin).days
        w, wd = offset // 7, offset % 7
        cells.append((wd, -w, w, d, count, lvl))
    cells.sort()  # back-to-front: low weekday first, then later weeks first

    floor, bars, marks = [], [], []
    for wd, _, w, d, count, lvl in cells:
        a, b, c, e = iso(w, wd), iso(w + k, wd), iso(w + k, wd + k), iso(w, wd + k)
        if count == 0:
            floor.append(f'<polygon points="{pts(a, b, c, e)}" fill="{LEVELS[0]}"/>')
            continue
        h = 5 + (HMAX - 5) * (count / peak) ** 0.6
        top = ACCENT if count == peak else LEVELS[lvl]
        at, bt, ct, et = (iso(w, wd, h), iso(w + k, wd, h), iso(w + k, wd + k, h), iso(w, wd + k, h))
        ox, oy = e
        delay = 0.35 + w * 0.028 + wd * 0.01
        bars.append(
            f'<g class="b" style="transform-origin:{num(ox)}px {num(oy)}px;animation-delay:{delay:.2f}s">'
            f'<polygon points="{pts(a, e, et, at)}" fill="{shade(top, .55)}"/>'
            f'<polygon points="{pts(e, c, ct, et)}" fill="{shade(top, .38)}"/>'
            f'<polygon points="{pts(at, bt, ct, et)}" fill="{top}"/></g>'
        )
        if count == peak:
            px, py = iso(w + k / 2, wd + k / 2, h)
            label = f"PEAK {count} · {d:%b %d}".upper()
            lw = text_width(label, 10.5, 1.2) + 18
            if py - 50 >= 62:  # room above the bar
                box_x, box_y, lead = px - lw / 2, py - 50, f"M {num(px)} {num(py - 4)} V {num(py - 30)}"
            else:  # too close to the title bar: hang the label off to the left
                box_x, box_y = px - 26 - lw, max(py - 10, 62)
                lead = f"M {num(px - 3)} {num(py - 2)} L {num(px - 26)} {num(box_y + 9)}"
            marks.append(
                f'<g class="pin"><path d="{lead}" stroke="{ACCENT}" stroke-width="1" fill="none"/>'
                f'<circle cx="{num(px)}" cy="{num(py - 2)}" r="2.5" fill="{TEXT}"/>'
                f'<rect x="{num(box_x)}" y="{num(box_y)}" width="{num(lw)}" height="20" rx="3" fill="{BG0}" stroke="{ACCENT}" stroke-opacity=".7"/>'
                f'<text x="{num(box_x + lw / 2)}" y="{num(box_y + 14)}" text-anchor="middle" font-size="10.5" letter-spacing="1.2" font-weight="700" fill="{ACCENT}">{esc(label)}</text></g>'
            )
        if d == today:
            tx, ty = iso(w + k / 2, wd + k / 2, h)
            marks.append(f'<g class="pin"><circle class="ping" cx="{num(tx)}" cy="{num(ty)}" r="6" fill="none" stroke="{TEXT}" stroke-width="1.5"/></g>')

    grid = []
    weeks = (stats.days[-1][0] - origin).days // 7 + 1
    for wd in (0, 7):
        (x1, y1), (x2, y2) = iso(-0.3, wd), iso(weeks + 0.1, wd)
        grid.append(f'<path d="M {num(x1)} {num(y1)} L {num(x2)} {num(y2)}" stroke="{LINE}"/>')
    month_labels = []
    seen = set()
    for d, _ in stats.days:  # one label per quarter keeps the floor quiet
        if d.month in (1, 4, 7, 10) and d.day <= 7 and d.weekday() == 6 and (d.year, d.month) not in seen:
            seen.add((d.year, d.month))
            w = (d - origin).days // 7
            x, y = iso(w, 8.2)
            month = f"{d:%b}".upper()
            month_labels.append(
                f'<text transform="translate({num(x)} {num(y)}) rotate(-15.2)" font-size="10.5" letter-spacing="1.5" fill="{MUTED}">{month}</text>'
            )
            (gx1, gy1), (gx2, gy2) = iso(w, -0.2), iso(w, 7.2)
            grid.append(f'<path d="M {num(gx1)} {num(gy1)} L {num(gx2)} {num(gy2)}" stroke="{LINE}" stroke-opacity=".7"/>')
    labels = ""
    return "".join(grid) + "".join(month_labels) + labels + "".join(floor), "".join(bars) + "".join(marks)


DIGIT_W = 0.494  # Anton digits share one advance (except "1", centred in the slot)
COMMA_W = 0.236


def odometer(value: str, x: float, y: float, size: float, color: str, base_delay: float, cid: str) -> tuple[str, str]:
    """Slot-machine counter: each digit is a 0-9 strip that rolls up to its final value."""
    lh = size * 1.25
    widths = [size * (DIGIT_W if ch.isdigit() else COMMA_W) for ch in value]
    defs = (
        # Anton digits stand 0.87em tall; the window shows exactly one row of the
        # 1.25em-spaced strip, with a little air above and below.
        f'<clipPath id="{cid}"><rect x="{num(x - 2)}" y="{num(y - size * .93)}" '
        f'width="{num(sum(widths) + 4)}" height="{num(size * .97)}"/></clipPath>'
    )
    body = [f'<g clip-path="url(#{cid})">']
    static = []  # separators sit outside the clip so a comma keeps its tail
    digits = [i for i, ch in enumerate(value) if ch.isdigit()]
    cursor = x
    for i, (ch, w) in enumerate(zip(value, widths)):
        mid = cursor + w / 2
        cursor += w
        if not ch.isdigit():
            static.append(f'<text class="dp" x="{num(mid)}" y="{num(y)}" text-anchor="middle" font-size="{size}" fill="{color}">{esc(ch)}</text>')
            continue
        order = digits.index(i)
        spans = "".join(
            f'<tspan x="{num(mid)}" dy="{num(lh) if j else 0}">{j % 10}</tspan>' for j in range(10 + int(ch) + 1)
        )
        body.append(
            f'<g class="od o{ch}" style="animation-delay:{base_delay + order * .12:.2f}s">'
            f'<text class="dp" y="{num(y)}" text-anchor="middle" font-size="{size}" fill="{color}">{spans}</text></g>'
        )
    body.append("</g>")
    return defs, "".join(body) + "".join(static), cursor - x


def render(stats: Stats) -> str:
    W, H = 980, 440
    size = 46
    lh = size * 1.25
    odo_keys = "".join(
        f"@keyframes o{d}{{from{{transform:translateY(0)}}to{{transform:translateY(-{num((10 + d) * lh)}px)}}}}.o{d}{{animation-name:o{d}}}"
        for d in range(10)
    )
    style = (
        "<style>" + FONT_SLOT + f"text{{font-family:{MONO}}}.dp{{font-family:{DISPLAY}}}"
        "@keyframes rise{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
        ".b{transform:scaleY(0);animation:rise .9s cubic-bezier(.2,1.2,.35,1) forwards}"
        ".od{animation-duration:1.8s;animation-timing-function:cubic-bezier(.15,.85,.25,1);animation-fill-mode:both}"
        + odo_keys +
        "@keyframes fade{from{opacity:0}to{opacity:1}}"
        ".pin{opacity:0;animation:fade .5s 2.4s forwards}"
        "@keyframes ping{0%{transform:scale(.6);opacity:1}100%{transform:scale(2.4);opacity:0}}"
        ".ping{transform-box:fill-box;transform-origin:center;animation:ping 1.6s ease-out infinite}"
        "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        ".grow{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow 1.4s 1s cubic-bezier(.2,.9,.2,1) forwards}"
        "@keyframes sweep{0%{transform:translateX(-200px)}60%,100%{transform:translateX(900px)}}"
        ".sweep{animation:sweep 7s 2.2s ease-in-out infinite;transform:translateX(-200px)}"
        "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}.blink{animation:blink 1.1s steps(1) infinite}"
        "</style>"
    )

    stats_col = [
        ("CONTRIBUTIONS · 12 MO", f"{stats.total_year:,}", ""),
        ("CURRENT STREAK", str(stats.current_streak), "D"),
        ("LONGEST STREAK", str(stats.longest_streak), "D"),
    ]
    show_split = stats.private > 0
    if not show_split:
        stats_col.append((f"ALL-TIME · SINCE {stats.first_year}", f"{stats.all_time:,}", ""))
    sx = 724
    col_defs, col_body = [], []
    for i, (label, value, suffix) in enumerate(stats_col):
        y0 = 62 + i * 84
        d, b, vw = odometer(value, sx, y0 + 46, size, TEXT, 0.3 + i * 0.15, f"od{i}")
        col_defs.append(d)
        col_body.append(b)
        if suffix:
            col_body.append(f'<text class="dp" x="{num(sx + 6 + vw)}" y="{y0 + 46}" font-size="24" fill="{ACCENT}">{suffix}</text>')
        col_body.append(f'<text x="{sx + 1}" y="{y0 + 68}" font-size="11" font-weight="700" letter-spacing="2" fill="{MUTED}">{esc(label)}</text>')
        if i < len(stats_col) - 1 or show_split:
            col_body.append(f'<rect x="{sx}" y="{y0 + 80}" width="232" height="1" fill="{LINE}"/>')

    split = ""
    if show_split:
        public = max(stats.total_year - stats.private, 0)
        pw = 232
        share = public / max(stats.total_year, 1)
        y0 = 62 + 3 * 84 + 8
        split = (
            f'<text x="{sx + 1}" y="{y0 + 14}" font-size="11" font-weight="700" letter-spacing="2" fill="{MUTED}">PUBLIC / PRIVATE</text>'
            f'<g class="grow"><rect x="{sx}" y="{y0 + 26}" width="{num(max(pw * share - 2, 2))}" height="6" fill="{TEXT}"/>'
            f'<rect x="{num(sx + pw * share)}" y="{y0 + 26}" width="{num(pw * (1 - share))}" height="6" fill="{ACCENT}"/></g>'
            f'<text class="dp" x="{sx}" y="{y0 + 64}" font-size="24" fill="{TEXT}">{public:,}</text>'
            f'<text class="dp" x="{sx + pw}" y="{y0 + 64}" text-anchor="end" font-size="24" fill="{ACCENT}">{stats.private:,}</text>'
        )

    floor, bars = skyline(stats)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Engineering activity</title>
<desc id="d">{stats.total_year:,} contributions in the last 12 months ({stats.private:,} in private repositories), {stats.all_time:,} since {stats.first_year}. Current streak {stats.current_streak} days, longest {stats.longest_streak} days.</desc>
{style}
<defs>
<clipPath id="frame"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18"/></clipPath>
<clipPath id="sky"><rect x="0" y="40" width="700" height="{H - 40}"/></clipPath>
<radialGradient id="glow" cx="30%" cy="85%" r="60%"><stop offset="0" stop-color="#2e0f0b" stop-opacity=".8"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<linearGradient id="sw" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
{grain()}
{"".join(col_defs)}
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>
<rect width="{W}" height="36" fill="#000" fill-opacity=".45"/>
<path d="M0 36.5H{W}" stroke="{LINE}"/>
{window_dots(18)}
<text x="{W - 24}" y="22.5" text-anchor="end" font-size="10.5" font-weight="700" letter-spacing="2" fill="{MUTED}"><tspan class="blink" fill="{ACCENT}">●</tspan> LAST 12 MONTHS</text>
{floor}
{bars}
<g clip-path="url(#sky)"><rect class="sweep" x="0" y="40" width="160" height="{H - 40}" fill="url(#sw)" transform="skewX(-20)"/></g>
<path d="M 700 58 V {H - 22}" stroke="{LINE}"/>
{"".join(col_body)}
{split}
{grain_layer(W, H)}
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="none" stroke="{LINE}" stroke-width="1.5"/>
</svg>'''


def main() -> int:
    stats = demo() if "--demo" in sys.argv else fetch()
    write(OUTPUT, render(stats))
    print(
        f"Generated {OUTPUT} · {stats.total_year:,} contributions in the last year · "
        f"{stats.all_time:,} all-time · mode={stats.mode}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
