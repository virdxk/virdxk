#!/usr/bin/env python3
"""Render GitHub contribution grid with red theme + snake animation."""
import json
import os
import sys
import datetime
import urllib.request

USER = "virdxk"
TOKEN = os.environ["GH_TOKEN"]

CELL = 11
GAP = 3
STEP = CELL + GAP
PAD_LEFT = 32
PAD_TOP = 22
PAD_BOTTOM = 30
PAD_RIGHT = 12

PALETTE = ["#161616", "#5c0000", "#8b0000", "#b00000", "#ff0000"]
LEVEL_IDX = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}
BG = "#0a0a0a"
FG = "#888"
SNAKE_COLOR = "#8b0000"
SNAKE_SHADOW = "#ff0000"

DURATION_S = 18
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def gql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_calendar():
    q = (
        'query { user(login: "%s") { contributionsCollection { '
        "contributionCalendar { weeks { contributionDays { "
        "date contributionLevel weekday } } } } } }"
    ) % USER
    data = gql(q)
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]


def render(weeks):
    n_weeks = len(weeks)
    grid_w = n_weeks * STEP - GAP
    grid_h = 7 * STEP - GAP
    width = PAD_LEFT + grid_w + PAD_RIGHT
    height = PAD_TOP + grid_h + PAD_BOTTOM

    cells = []
    for w_idx, week in enumerate(weeks):
        for d in week["contributionDays"]:
            wd = d["weekday"]
            level = LEVEL_IDX.get(d["contributionLevel"], 0)
            cells.append((w_idx, wd, level, d["date"]))

    cells.sort(key=lambda c: (c[1], c[0]))
    n_cells = len(cells)

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="-apple-system, Segoe UI, sans-serif">'
    )
    out.append("<style>")
    out.append(
        ".snake-head{filter:drop-shadow(0 0 3px " + SNAKE_SHADOW + ");}"
        ".cell{transition:fill .1s;}"
    )
    keyframes_snake_x = []
    keyframes_snake_y = []
    keyframes_cells = []
    head_steps = []

    rows = [[] for _ in range(7)]
    for c in cells:
        rows[c[1]].append(c)
    path = []
    for r_idx, row in enumerate(rows):
        ordered = row if r_idx % 2 == 0 else list(reversed(row))
        path.extend(ordered)

    n_path = len(path)
    for i, c in enumerate(path):
        w_idx, wd, level, _ = c
        x = PAD_LEFT + w_idx * STEP
        y = PAD_TOP + wd * STEP
        head_steps.append((x, y, i / n_path))

    snake_kf_x = []
    snake_kf_y = []
    for x, y, t in head_steps:
        pct = t * 100
        snake_kf_x.append(f"{pct:.3f}%{{transform:translateX({x}px)}}")
        snake_kf_y.append(f"{pct:.3f}%{{transform:translateY({y}px)}}")

    out.append("@keyframes snake-x{" + "".join(snake_kf_x) + "}")
    out.append("@keyframes snake-y{" + "".join(snake_kf_y) + "}")

    for i, c in enumerate(path):
        w_idx, wd, level, _ = c
        if level == 0:
            continue
        eat_pct = (i / n_path) * 100
        kf_name = f"e{w_idx}_{wd}"
        out.append(
            f"@keyframes {kf_name}{{"
            f"0%,{eat_pct:.3f}%{{fill:{PALETTE[level]}}}"
            f"{eat_pct + 0.05:.3f}%,100%{{fill:{PALETTE[0]}}}"
            f"}}"
        )
        out.append(
            f".c{w_idx}_{wd}{{animation:{kf_name} {DURATION_S}s linear infinite}}"
        )

    out.append(
        ".sx{animation:snake-x " + str(DURATION_S) + "s linear infinite;transform-box:fill-box}"
        ".sy{animation:snake-y " + str(DURATION_S) + "s linear infinite;transform-box:fill-box}"
    )
    out.append("</style>")

    out.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')

    prev_month = None
    for w_idx, week in enumerate(weeks):
        first_day = week["contributionDays"][0]
        m = int(first_day["date"][5:7])
        if m != prev_month and (prev_month is None or w_idx > 0):
            x = PAD_LEFT + w_idx * STEP
            if w_idx == 0 or w_idx >= 1:
                out.append(
                    f'<text x="{x}" y="14" fill="{FG}" font-size="9">{MONTH_LABELS[m - 1]}</text>'
                )
            prev_month = m

    for wd_idx, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = PAD_TOP + wd_idx * STEP + 9
        out.append(f'<text x="0" y="{y}" fill="{FG}" font-size="9">{label}</text>')

    for c in cells:
        w_idx, wd, level, _ = c
        x = PAD_LEFT + w_idx * STEP
        y = PAD_TOP + wd * STEP
        cls = f"c{w_idx}_{wd}" if level > 0 else ""
        out.append(
            f'<rect class="cell {cls}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="2" ry="2" fill="{PALETTE[level]}"/>'
        )

    legend_y = PAD_TOP + grid_h + 14
    legend_x = width - 165
    out.append(
        f'<text x="{legend_x}" y="{legend_y + 9}" fill="{FG}" font-size="9">Less</text>'
    )
    for i, c in enumerate(PALETTE):
        x = legend_x + 28 + i * (CELL + 3)
        out.append(
            f'<rect x="{x}" y="{legend_y}" width="{CELL}" height="{CELL}" rx="2" ry="2" fill="{c}"/>'
        )
    out.append(
        f'<text x="{legend_x + 28 + 5 * (CELL + 3) + 5}" y="{legend_y + 9}" fill="{FG}" font-size="9">More</text>'
    )

    out.append(
        f'<g class="sx"><g class="sy">'
        f'<rect class="snake-head" width="{CELL + 2}" height="{CELL + 2}" rx="3" ry="3" fill="{SNAKE_COLOR}"/>'
        f"</g></g>"
    )

    out.append("</svg>")
    return "\n".join(out)


def main():
    weeks = fetch_calendar()
    svg = render(weeks)
    out_path = sys.argv[1] if len(sys.argv) > 1 else "dist/contrib-snake.svg"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"wrote {out_path} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
