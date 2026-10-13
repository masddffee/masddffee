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
    ACCENT, ASH, BG0, DIM, DISPLAY, FONT_SLOT, GOLD, LINE, MONO, MUTED, PANEL,
    ROOT, SOFT, STEEL, TEXT, esc, grain, grain_layer, num, text_width,
    window_dots, write,
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

U = (10.6, -2.9)   # one week step on screen
V = (6.0, 4.6)     # one weekday step on screen
X0, Y0 = 34, 420   # screen position of week 0 / Sunday
HMAX = 108
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
            lw = text_width(label, 9.5, 1) + 14
            if py - 48 >= 170:  # room above the bar
                box_x, box_y, lead = px - lw / 2, py - 48, f"M {num(px)} {num(py - 4)} V {num(py - 30)}"
            else:  # too close to the section title: hang the label off to the left
                box_x, box_y = px - 26 - lw, max(py - 9, 170)
                lead = f"M {num(px - 3)} {num(py - 2)} L {num(px - 26)} {num(box_y + 9)}"
            marks.append(
                f'<g class="pin"><path d="{lead}" stroke="{ACCENT}" stroke-width="1" fill="none"/>'
                f'<circle cx="{num(px)}" cy="{num(py - 2)}" r="2.5" fill="{TEXT}"/>'
                f'<rect x="{num(box_x)}" y="{num(box_y)}" width="{num(lw)}" height="18" rx="4" fill="{BG0}" stroke="{ACCENT}" stroke-opacity=".7"/>'
                f'<text x="{num(box_x + lw / 2)}" y="{num(box_y + 12.5)}" text-anchor="middle" font-size="9.5" letter-spacing="1" font-weight="700" fill="{ACCENT}">{esc(label)}</text></g>'
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
    for d, _ in stats.days:
        if d.day <= 7 and (d.year, d.month) not in seen and d.weekday() == 6:
            seen.add((d.year, d.month))
            w = (d - origin).days // 7
            x, y = iso(w, 7.9)
            month_labels.append(
                f'<text transform="translate({num(x)} {num(y)}) rotate(-15.3)" font-size="9" fill="{DIM}">{d:%b}</text>'
            )
            (gx1, gy1), (gx2, gy2) = iso(w, -0.2), iso(w, 7.2)
            grid.append(f'<path d="M {num(gx1)} {num(gy1)} L {num(gx2)} {num(gy2)}" stroke="{LINE}" stroke-opacity=".6"/>')
    wx, wy = iso(-1.2, 1.5)
    labels = (
        f'<text x="{num(wx)}" y="{num(wy)}" font-size="8.5" fill="{DIM}" text-anchor="end">Mon</text>'
        f'<text x="{num(iso(-1.2, 5.5)[0])}" y="{num(iso(-1.2, 5.5)[1])}" font-size="8.5" fill="{DIM}" text-anchor="end">Fri</text>'
    )
    return "".join(grid) + "".join(month_labels) + labels + "".join(floor), "".join(bars) + "".join(marks)


DIGIT_W = 0.494  # Anton digits share one advance (except "1", centred in the slot)
COMMA_W = 0.236


def odometer(value: str, x: float, y: float, size: float, color: str, base_delay: float, cid: str) -> tuple[str, str]:
    """Slot-machine counter: each digit is a 0-9 strip that rolls up to its final value."""
    lh = size * 1.25
    widths = [size * (DIGIT_W if ch.isdigit() else COMMA_W) for ch in value]
    defs = (
        f'<clipPath id="{cid}"><rect x="{num(x - 2)}" y="{num(y - size * .92)}" '
        f'width="{num(sum(widths) + 4)}" height="{num(size * 1.02)}"/></clipPath>'
    )
    body = [f'<g clip-path="url(#{cid})">']
    digits = [i for i, ch in enumerate(value) if ch.isdigit()]
    cursor = x
    for i, (ch, w) in enumerate(zip(value, widths)):
        mid = cursor + w / 2
        cursor += w
        if not ch.isdigit():
            body.append(f'<text class="dp" x="{num(mid)}" y="{num(y)}" text-anchor="middle" font-size="{size}" fill="{color}">{esc(ch)}</text>')
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
    return defs, "".join(body), cursor - x


def render(stats: Stats) -> str:
    W, H = 980, 520
    size = 34
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
        ".grow{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow 1.2s .8s cubic-bezier(.2,.9,.2,1) forwards}"
        "@keyframes up{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
        ".up{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:up .8s cubic-bezier(.2,1.1,.3,1) forwards}"
        "@keyframes sweep{0%{transform:translateX(-200px)}60%,100%{transform:translateX(900px)}}"
        ".sweep{animation:sweep 6s 2.2s ease-in-out infinite;transform:translateX(-200px)}"
        "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}.blink{animation:blink 1.1s steps(1) infinite}"
        "</style>"
    )

    mode_text, mode_color = {
        "owner": ("PUBLIC + PRIVATE · OWNER TOKEN", SOFT),
        "public+private": ("PUBLIC + PRIVATE (ANONYMIZED)", SOFT),
        "public": ("PUBLIC ONLY · ENABLE PRIVATE COUNTS", GOLD),
    }[stats.mode]

    active = sum(1 for _, c in stats.days if c > 0)
    best_day, best = max(stats.days, key=lambda x: (x[1], x[0]))
    tiles = [
        ("CONTRIBUTIONS", f"{stats.total_year:,}", "last 12 months", ""),
        ("ALL-TIME", f"{stats.all_time:,}", f"since {stats.first_year}", ""),
        ("CURRENT STREAK", str(stats.current_streak), "days in a row", "d"),
        ("LONGEST STREAK", str(stats.longest_streak), "all-time record", "d"),
        ("BEST DAY", str(best), f"{best_day:%Y-%m-%d}", ""),
        ("ACTIVE DAYS", str(active), f"{active * 100 // max(len(stats.days), 1)}% of the year", ""),
    ]
    tile_w, gap, tx0 = 148, 10, 24
    tile_defs, tile_body = [], []
    accents = [ACCENT] * 6
    for i, (label, value, sub, suffix) in enumerate(tiles):
        x = tx0 + i * (tile_w + gap)
        tile_body.append(
            f'<rect x="{x}" y="56" width="{tile_w}" height="76" rx="6" fill="{PANEL}" stroke="{LINE}"/>'
            f'<rect x="{x}" y="56" width="3" height="76" rx="1.5" fill="{accents[i]}"/>'
            f'<text x="{x + 14}" y="76" font-size="9" font-weight="700" letter-spacing="1.2" fill="{MUTED}">{label}</text>'
            f'<text x="{x + 14}" y="125" font-size="9.5" fill="{DIM}">{esc(sub)}</text>'
        )
        d, b, vw = odometer(value, x + 14, 112, size, TEXT, 0.25 + i * 0.1, f"od{i}")
        tile_defs.append(d)
        tile_body.append(b)
        if suffix:
            tile_body.append(f'<text class="dp" x="{num(x + 18 + vw)}" y="112" font-size="18" fill="{accents[i]}">{suffix}</text>')

    floor, bars = skyline(stats)

    # Breakdown of what the contributions are made of.
    parts = [
        ("commits", stats.commits, TEXT),
        ("pull requests", stats.pull_requests, STEEL),
        ("code reviews", stats.reviews, ASH),
        ("issues", stats.issues, GOLD),
        ("private (anon)", stats.private, ACCENT),
    ]
    other = max(stats.total_year - sum(v for _, v, _ in parts), 0)
    if other:
        parts.append(("other", other, DIM))
    parts = [p for p in parts if p[1] > 0]
    total_parts = sum(v for _, v, _ in parts) or 1
    px0, pw = 718, 238
    seg, cursor = [], px0
    for _, value, color in parts:
        w = pw * value / total_parts
        seg.append(f'<rect x="{num(cursor)}" y="178" width="{num(max(w - 1.5, .5))}" height="10" fill="{color}"/>')
        cursor += w
    legend = []
    for i, (name, value, color) in enumerate(parts):
        y = 212 + i * 19
        legend.append(
            f'<rect x="{px0}" y="{y - 8}" width="8" height="8" rx="2" fill="{color}"/>'
            f'<text x="{px0 + 16}" y="{y}" font-size="10.5" fill="{TEXT}" fill-opacity=".85">{esc(name)}</text>'
            f'<text x="{px0 + pw}" y="{y}" text-anchor="end" font-size="10.5" font-weight="700" fill="{TEXT}">{value:,}</text>'
        )

    # Weekday rhythm (average contributions per weekday).
    sums, counts_ = [0] * 7, [0] * 7
    for d, c in stats.days:
        wd = (d.weekday() + 1) % 7
        sums[wd] += c
        counts_[wd] += 1
    avgs = [s / n if n else 0 for s, n in zip(sums, counts_)]
    top = max(avgs) or 1
    wy0 = 466
    week_bars = []
    for i, avg in enumerate(avgs):
        h = 6 + 50 * avg / top
        x = px0 + 6 + i * 33
        color = ACCENT if avg == top else STEEL
        week_bars.append(
            f'<rect class="up" style="animation-delay:{1.2 + i * .07:.2f}s" x="{x}" y="{num(wy0 - h)}" width="20" height="{num(h)}" rx="3" fill="{color}" fill-opacity="{1 if avg == top else .3}"/>'
            f'<text x="{x + 10}" y="{wy0 + 14}" text-anchor="middle" font-size="9.5" fill="{MUTED}">{"SMTWTFS"[i]}</text>'
        )
    busiest = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][avgs.index(top)]

    months: dict[tuple[int, int], int] = {}
    for d, c in stats.days:
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
    (my, mm), mtotal = max(months.items(), key=lambda kv: kv[1])
    weekend = sum(c for d, c in stats.days if d.weekday() >= 5)
    signals = [
        ("busiest month", f"{date(my, mm, 1):%b %Y} · {mtotal:,}"),
        ("avg per active day", f"{sum(c for _, c in stats.days) / max(active, 1):.1f}"),
        ("weekend share", f"{weekend * 100 // max(sum(c for _, c in stats.days), 1)}%"),
    ]
    sig_y0 = 212 + len(parts) * 19 + 16
    signal_svg = "".join(
        f'<text x="{px0}" y="{sig_y0 + i * 16}" font-size="10" fill="{MUTED}">{esc(k)}</text>'
        f'<text x="{px0 + pw}" y="{sig_y0 + i * 16}" text-anchor="end" font-size="10" font-weight="700" fill="{ACCENT}">{esc(v)}</text>'
        for i, (k, v) in enumerate(signals)
    )

    mw = text_width(mode_text, 9.5, 1.2) + 30
    stamp = stats.generated.strftime("%Y-%m-%d %H:%M") + f" UTC{stats.generated.utcoffset().total_seconds() / 3600:+.0f}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Engineering activity</title>
<desc id="d">{stats.total_year:,} contributions in the last 12 months, {stats.all_time:,} since {stats.first_year}. Current streak {stats.current_streak} days, longest {stats.longest_streak} days.</desc>
{style}
<defs>
<clipPath id="frame"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18"/></clipPath>
<clipPath id="sky"><rect x="0" y="140" width="700" height="350"/></clipPath>
<radialGradient id="glow" cx="30%" cy="85%" r="60%"><stop offset="0" stop-color="#2e0f0b" stop-opacity=".8"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></radialGradient>
<linearGradient id="sw" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
{grain()}
{"".join(tile_defs)}
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="{BG0}"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>
<rect width="{W}" height="40" fill="#000" fill-opacity=".45"/>
<path d="M0 40.5H{W}" stroke="{LINE}"/>
{window_dots()}
<text x="78" y="24.5" font-size="11.5" fill="{MUTED}"><tspan fill="{ACCENT}">$</tspan> git log --all --since=1y <tspan fill="{DIM}">|</tspan> skyline --3d<tspan class="blink" fill="{ACCENT}"> _</tspan></text>
<rect x="{num(W - 18 - mw)}" y="9" width="{num(mw)}" height="22" rx="3" fill="{BG0}" stroke="{LINE}"/>
<circle cx="{num(W - 18 - mw + 13)}" cy="20" r="3" fill="{ACCENT}" class="blink"/>
<text x="{num(W - 18 - mw + 22)}" y="23.5" font-size="9.5" font-weight="700" letter-spacing="1.2" fill="{mode_color}">{mode_text}</text>
{"".join(tile_body)}
<text x="24" y="160" font-size="10" font-weight="700" letter-spacing="1.4" fill="{MUTED}">CONTRIBUTION SKYLINE <tspan fill="{DIM}" font-weight="400">· 1 block = 1 day · height = volume</tspan></text>
{floor}
{bars}
<g clip-path="url(#sky)"><rect class="sweep" x="0" y="150" width="160" height="320" fill="url(#sw)" transform="skewX(-20)"/></g>
<path d="M 702 150 V 494" stroke="{LINE}"/>
<text x="{px0}" y="160" font-size="10" font-weight="700" letter-spacing="1.4" fill="{MUTED}">BREAKDOWN</text>
<g class="grow">{"".join(seg)}</g>
{"".join(legend)}
<path d="M {px0} {sig_y0 - 15} h {pw}" stroke="{LINE}" stroke-dasharray="2 3"/>
{signal_svg}
<text x="{px0}" y="{wy0 - 72}" font-size="10" font-weight="700" letter-spacing="1.4" fill="{MUTED}">WEEKDAY RHYTHM <tspan fill="{ACCENT}" font-weight="400">· peak {busiest}</tspan></text>
{"".join(week_bars)}
<text x="24" y="504" font-size="9.5" fill="{DIM}">source: GitHub GraphQL contributionsCollection · aggregate counts only · refreshed {esc(stamp)}</text>
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
