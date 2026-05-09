#!/usr/bin/env python3
"""Render GitHub contribution grid with red theme + multi-segment snake."""
import json
import os
import sys
import random
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

SNAKE_LEN = 5
SNAKE_COLORS = ["#ff2b2b", "#d10000", "#a30000", "#7a0000", "#520000"]

DURATION_S = 24
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


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


def build_path(cells_by_pos, n_weeks):
    """Build chaotic snake path: prioritize colored cells, then random walk filler."""
    rng = random.Random(42)
    visited = set()
    path = []

    colored = [pos for pos, lvl in cells_by_pos.items() if lvl > 0]
    rng.shuffle(colored)

    if not colored:
        for r in range(7):
            cols = list(range(n_weeks))
            if r % 2:
                cols.reverse()
            for c in cols:
                pos = (c, r)
                if pos in cells_by_pos:
                    path.append(pos)
                    visited.add(pos)
        return path

    cur = colored[0]
    path.append(cur)
    visited.add(cur)
    targets = colored[1:]

    def neighbors(p):
        x, y = p
        opts = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [n for n in opts if n in cells_by_pos and n not in visited]

    def shortest_path(src, dst):
        from collections import deque

        q = deque([(src, [src])])
        seen = {src}
        while q:
            node, p = q.popleft()
            if node == dst:
                return p
            x, y = node
            for nb in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                if nb in cells_by_pos and nb not in seen:
                    seen.add(nb)
                    q.append((nb, p + [nb]))
        return [src, dst]

    while targets:
        targets.sort(key=lambda t: abs(t[0] - cur[0]) + abs(t[1] - cur[1]))
        nxt = targets.pop(0)
        seg = shortest_path(cur, nxt)
        for s in seg[1:]:
            path.append(s)
            visited.add(s)
        cur = nxt

    for r in range(7):
        cols = list(range(n_weeks))
        if r % 2:
            cols.reverse()
        for c in cols:
            pos = (c, r)
            if pos in cells_by_pos and pos not in visited:
                path.append(pos)
                visited.add(pos)
    return path


def render(weeks):
    n_weeks = len(weeks)
    grid_w = n_weeks * STEP - GAP
    grid_h = 7 * STEP - GAP
    width = PAD_LEFT + grid_w + PAD_RIGHT
    height = PAD_TOP + grid_h + PAD_BOTTOM

    cells_by_pos = {}
    cell_levels = {}
    for w_idx, week in enumerate(weeks):
        for d in week["contributionDays"]:
            pos = (w_idx, d["weekday"])
            level = LEVEL_IDX.get(d["contributionLevel"], 0)
            cells_by_pos[pos] = level
            cell_levels[pos] = level

    path = build_path(cells_by_pos, n_weeks)
    n_path = len(path)
    if n_path == 0:
        n_path = 1

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="-apple-system, Segoe UI, sans-serif">'
    )
    out.append("<style>")
    out.append(".cell{shape-rendering:geometricPrecision}")

    seg_dur = DURATION_S / n_path

    snake_steps_x = []
    snake_steps_y = []
    for i, (cx, cy) in enumerate(path):
        pct = (i / n_path) * 100
        x = PAD_LEFT + cx * STEP
        y = PAD_TOP + cy * STEP
        snake_steps_x.append(f"{pct:.4f}%{{transform:translateX({x}px)}}")
        snake_steps_y.append(f"{pct:.4f}%{{transform:translateY({y}px)}}")

    out.append("@keyframes sx{" + "".join(snake_steps_x) + "}")
    out.append("@keyframes sy{" + "".join(snake_steps_y) + "}")

    for i, pos in enumerate(path):
        lvl = cell_levels.get(pos, 0)
        if lvl == 0:
            continue
        cx, cy = pos
        eat_pct = (i / n_path) * 100
        kf = f"e_{cx}_{cy}"
        out.append(
            f"@keyframes {kf}{{"
            f"0%,{eat_pct:.4f}%{{fill:{PALETTE[lvl]}}}"
            f"{eat_pct + 0.1:.4f}%,100%{{fill:{PALETTE[0]}}}"
            f"}}"
        )
        out.append(
            f".c_{cx}_{cy}{{animation:{kf} {DURATION_S}s linear infinite}}"
        )

    out.append("</style>")
    out.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')

    prev_month = None
    for w_idx, week in enumerate(weeks):
        first_day = week["contributionDays"][0]
        m = int(first_day["date"][5:7])
        if m != prev_month:
            x = PAD_LEFT + w_idx * STEP
            out.append(f'<text x="{x}" y="14" fill="{FG}" font-size="9">{MONTHS[m - 1]}</text>')
            prev_month = m

    for wd_idx, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = PAD_TOP + wd_idx * STEP + 9
        out.append(f'<text x="0" y="{y}" fill="{FG}" font-size="9">{label}</text>')

    for pos, lvl in cells_by_pos.items():
        cx, cy = pos
        x = PAD_LEFT + cx * STEP
        y = PAD_TOP + cy * STEP
        cls = f"cell c_{cx}_{cy}" if lvl > 0 else "cell"
        out.append(
            f'<rect class="{cls}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="2" ry="2" fill="{PALETTE[lvl]}"/>'
        )

    legend_y = PAD_TOP + grid_h + 14
    legend_x = width - 165
    out.append(f'<text x="{legend_x}" y="{legend_y + 9}" fill="{FG}" font-size="9">Less</text>')
    for i, c in enumerate(PALETTE):
        x = legend_x + 28 + i * (CELL + 3)
        out.append(
            f'<rect x="{x}" y="{legend_y}" width="{CELL}" height="{CELL}" rx="2" ry="2" fill="{c}"/>'
        )
    out.append(
        f'<text x="{legend_x + 28 + 5 * (CELL + 3) + 5}" y="{legend_y + 9}" fill="{FG}" font-size="9">More</text>'
    )

    for seg_i in range(SNAKE_LEN):
        delay = -seg_i * seg_dur * 1.0
        size = CELL + 2 - seg_i * 0.6
        radius = 4 - seg_i * 0.4
        color = SNAKE_COLORS[min(seg_i, len(SNAKE_COLORS) - 1)]
        opacity = 1.0 - seg_i * 0.08
        glow = ""
        if seg_i == 0:
            glow = "filter:drop-shadow(0 0 4px #ff0000);"
        out.append(
            f'<g style="animation:sx {DURATION_S}s linear infinite {delay:.4f}s;{glow}">'
            f'<g style="animation:sy {DURATION_S}s linear infinite {delay:.4f}s">'
            f'<rect width="{size:.2f}" height="{size:.2f}" rx="{radius:.2f}" ry="{radius:.2f}" '
            f'fill="{color}" opacity="{opacity:.2f}"/>'
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
