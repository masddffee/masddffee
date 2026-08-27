#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


API = "https://api.github.com"
LOGIN = os.environ.get("GITHUB_LOGIN", "").strip()
TOKEN = os.environ.get("PROFILE_METRICS_TOKEN", "").strip()
OUTPUT = Path(os.environ.get("PROFILE_METRICS_OUTPUT", "metrics/activity.svg"))
TZ = timezone(timedelta(hours=int(os.environ.get("PROFILE_TZ_OFFSET", "8"))))
VISIBLE_WEEKS = 53  # Current week plus the previous 52 weeks.


def request_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-activity-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
        return data, response.headers


def parse_next(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def paged(url: str):
    while url:
        data, headers = request_json(url)
        if not isinstance(data, list):
            raise RuntimeError(f"Expected list response from {url}")
        yield from data
        url = parse_next(headers.get("Link"))


def list_repositories(login: str):
    if TOKEN:
        # An authenticated PAT can see private repositories it has access to.
        query = urllib.parse.urlencode(
            {
                "per_page": 100,
                "affiliation": "owner,collaborator,organization_member",
                "sort": "pushed",
                "direction": "desc",
            }
        )
        url = f"{API}/user/repos?{query}"
    else:
        # Safe fallback: the profile still renders with public data before a PAT is configured.
        query = urllib.parse.urlencode(
            {"per_page": 100, "type": "owner", "sort": "pushed", "direction": "desc"}
        )
        url = f"{API}/users/{urllib.parse.quote(login)}/repos?{query}"

    repos = []
    for repo in paged(url):
        if repo.get("archived") or not repo.get("default_branch"):
            continue
        repos.append(
            {
                "full_name": repo["full_name"],
                "private": bool(repo.get("private")),
                "default_branch": repo["default_branch"],
            }
        )
    return repos


def list_commits(repo, login: str, since: datetime, until: datetime):
    params = urllib.parse.urlencode(
        {
            "author": login,
            "sha": repo["default_branch"],
            "since": since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "until": until.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "per_page": 100,
        }
    )
    url = f"{API}/repos/{repo['full_name']}/commits?{params}"
    try:
        yield from paged(url)
    except Exception:
        # One inaccessible/empty/disabled repository should not break the whole dashboard.
        # Avoid printing the repository name because Actions logs are public on this repo.
        print("Skipping one repository because GitHub returned an API error.", file=sys.stderr)


def commit_day(commit) -> date | None:
    raw = (
        commit.get("commit", {}).get("author", {}).get("date")
        or commit.get("commit", {}).get("committer", {}).get("date")
    )
    if not raw:
        return None
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TZ)
    return dt.date()


def current_streak(counts: Counter[date], today: date) -> int:
    cursor = today
    if counts[cursor] == 0:
        cursor -= timedelta(days=1)
    streak = 0
    while counts[cursor] > 0:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def escape(value) -> str:
    return html.escape(str(value), quote=True)


def level(count: int, max_count: int) -> int:
    if count <= 0:
        return 0
    if max_count <= 1:
        return 4
    ratio = count / max_count
    if ratio <= 0.20:
        return 1
    if ratio <= 0.45:
        return 2
    if ratio <= 0.70:
        return 3
    return 4


def render_svg(
    counts: Counter[date],
    public_commits: int,
    private_commits: int,
    repo_count: int,
    today: date,
    private_aware: bool,
) -> str:
    # Align to Sunday so rows match the familiar GitHub contribution calendar.
    current_week_start = today - timedelta(days=(today.weekday() + 1) % 7)
    start = current_week_start - timedelta(weeks=VISIBLE_WEEKS - 1)
    end = today

    dates = []
    cursor = start
    while cursor <= end:
        dates.append(cursor)
        cursor += timedelta(days=1)

    total = sum(counts[d] for d in dates)
    active_days = sum(1 for d in dates if counts[d] > 0)
    streak = current_streak(counts, today)
    peak = max((counts[d] for d in dates), default=0)

    width = 980
    height = 300
    cell = 11
    gap = 3
    grid_x = 30
    grid_y = 188
    step = cell + gap
    palette = ["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"]

    status_text = "PUBLIC + PRIVATE" if private_aware else "PUBLIC DATA"
    status_color = "#39d353" if private_aware else "#d29922"
    split_text = (
        f"{private_commits:,} private · {public_commits:,} public"
        if private_aware
        else f"{public_commits:,} public commits"
    )

    stat_boxes = [
        ("COMMITS", f"{total:,}"),
        ("ACTIVE DAYS", f"{active_days:,}"),
        ("CURRENT STREAK", f"{streak}d"),
        ("REPOS TOUCHED", f"{repo_count:,}"),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">GitHub engineering activity</title>',
        f'<desc id="desc">{escape(total)} commits across {escape(active_days)} active days in the visible period.</desc>',
        "<defs>",
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">',
        '<stop offset="0%" stop-color="#0d1117"/>',
        '<stop offset="100%" stop-color="#111827"/>',
        "</linearGradient>",
        '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">',
        '<feGaussianBlur stdDeviation="8" result="blur"/>',
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        "</filter>",
        "</defs>",
        '<rect x="0.75" y="0.75" width="978.5" height="298.5" rx="18" fill="url(#bg)" stroke="#30363d" stroke-width="1.5"/>',
        '<circle cx="32" cy="34" r="5" fill="#39d353" filter="url(#glow)"/>',
        '<text x="48" y="40" fill="#f0f6fc" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="20" font-weight="700">Engineering activity</text>',
        f'<text x="48" y="63" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="12">Last 53 weeks · default-branch commits · {escape(split_text)}</text>',
        f'<rect x="804" y="23" width="146" height="28" rx="14" fill="{status_color}" fill-opacity="0.12" stroke="{status_color}" stroke-opacity="0.55"/>',
        f'<text x="877" y="41" text-anchor="middle" fill="{status_color}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="11" font-weight="700">{status_text}</text>',
    ]

    box_y = 85
    box_w = 218
    box_h = 70
    for i, (label, value) in enumerate(stat_boxes):
        x = 30 + i * 238
        parts += [
            f'<rect x="{x}" y="{box_y}" width="{box_w}" height="{box_h}" rx="12" fill="#161b22" stroke="#30363d"/>',
            f'<text x="{x + 16}" y="{box_y + 25}" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10" font-weight="700" letter-spacing="1.2">{label}</text>',
            f'<text x="{x + 16}" y="{box_y + 54}" fill="#f0f6fc" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="24" font-weight="750">{escape(value)}</text>',
        ]

    # Build a 53-week × 7-day calendar.
    for d in dates:
        day_index = (d - start).days
        week = day_index // 7
        row = day_index % 7
        x = grid_x + week * step
        y = grid_y + row * step
        count = counts[d]
        color = palette[level(count, peak)]
        opacity = "0.30" if d > today else "1"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{color}" opacity="{opacity}"><title>{d.isoformat()}: {count} commit{"s" if count != 1 else ""}</title></rect>'
        )

    for row, label_text in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = grid_y + row * step + 9
        parts.append(
            f'<text x="10" y="{y}" fill="#6e7681" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="8">{label_text}</text>'
        )

    legend_y = 286
    parts.append(
        f'<text x="783" y="{legend_y}" fill="#6e7681" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="9">Less</text>'
    )
    lx = 812
    for color in palette:
        parts.append(
            f'<rect x="{lx}" y="{legend_y - 9}" width="9" height="9" rx="2" fill="{color}"/>'
        )
        lx += 13
    parts.append(
        f'<text x="{lx + 2}" y="{legend_y}" fill="#6e7681" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="9">More</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    if not LOGIN:
        print("GITHUB_LOGIN is required.", file=sys.stderr)
        return 2

    today = datetime.now(TZ).date()
    current_week_start = today - timedelta(days=(today.weekday() + 1) % 7)
    start_day = current_week_start - timedelta(weeks=VISIBLE_WEEKS - 1)
    since = datetime.combine(start_day, datetime.min.time(), tzinfo=TZ)
    until = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=TZ)

    repos = list_repositories(LOGIN)
    counts: Counter[date] = Counter()
    public_commits = 0
    private_commits = 0
    touched_repos = 0

    for repo in repos:
        repo_commits = 0
        for commit in list_commits(repo, LOGIN, since, until):
            day = commit_day(commit)
            if not day or day < start_day or day > today:
                continue
            counts[day] += 1
            repo_commits += 1
            if repo["private"]:
                private_commits += 1
            else:
                public_commits += 1
        if repo_commits:
            touched_repos += 1

    has_private_access = any(repo["private"] for repo in repos)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        render_svg(
            counts=counts,
            public_commits=public_commits,
            private_commits=private_commits,
            repo_count=touched_repos,
            today=today,
            private_aware=has_private_access,
        ),
        encoding="utf-8",
    )

    total = public_commits + private_commits
    print(
        f"Generated {OUTPUT} with {total} commits across {touched_repos} repositories "
        f"({'private-aware' if has_private_access else 'public-only'} mode)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
