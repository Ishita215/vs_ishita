#!/usr/bin/env python3
"""
Generates a custom isometric 3D contribution skyline as a single SVG.
No dependencies: uses only the Python standard library.

Usage:
    GITHUB_TOKEN=xxx USERNAME=Yash-Choubey09 python scripts/generate_skyline.py assets/skyline.svg
    python scripts/generate_skyline.py out.svg --mock      # offline preview with fake data
"""
import json
import math
import os
import random
import sys
import urllib.request
from datetime import date

# ---------------------------------------------------------------- data
QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount weekday } }
      }
    }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "skyline-generator"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[d["contributionCount"] for d in w["contributionDays"]] for w in cal["weeks"]]
    dates = [[d["date"] for d in w["contributionDays"]] for w in cal["weeks"]]
    return weeks, dates, cal["totalContributions"]


def mock():
    random.seed(7)
    weeks, dates = [], []
    for w in range(53):
        col, dts = [], []
        for d in range(7):
            base = random.random()
            c = 0 if base < 0.45 else int(random.random() ** 2 * 18)
            if 30 < w < 44:
                c += random.randint(0, 10)
            if d in (0, 6):
                c = c // 2
            col.append(c)
            dts.append(f"2026-01-{(w * 7 + d) % 28 + 1:02d}")
        weeks.append(col)
        dates.append(dts)
    return weeks, dates, sum(sum(w) for w in weeks)


def streaks(weeks):
    flat = [c for w in weeks for c in w]
    # ignore trailing days of the current week that haven't happened yet (count 0 is fine)
    longest = run = 0
    for c in flat:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    cur = 0
    i = len(flat) - 1
    if flat and flat[i] == 0:  # today may not have contributions yet
        i -= 1
    while i >= 0 and flat[i] > 0:
        cur += 1
        i -= 1
    return cur, longest


# ---------------------------------------------------------------- colours
STOPS = [(0.0, (31, 182, 212)), (0.5, (124, 92, 255)), (1.0, (255, 94, 168))]


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def ramp(t):
    t = max(0.0, min(1.0, t))
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return STOPS[-1][1]


def shade(c, k):
    return tuple(max(0, min(255, v * k)) for v in c)


def hx(c):
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c)


# ---------------------------------------------------------------- render
CW, CH = 900, 380            # canvas
WV = (13.6, 4.4)             # one week step on screen
DV = (-8.6, 6.4)             # one day step on screen
MAXH = 78                    # tallest bar in px


def build(weeks, dates, total, login):
    n_w = len(weeks)
    mx = max((c for w in weeks for c in w), default=0) or 1
    cur, longest = streaks(weeks)
    best = max(((c, dates[wi][di]) for wi, w in enumerate(weeks) for di, c in enumerate(w)),
               default=(0, ""))

    def base(w, d):
        return (w * WV[0] + d * DV[0], w * WV[1] + d * DV[1])

    cells = []
    for wi, col in enumerate(weeks):
        for di, c in enumerate(col):
            t = (c / mx) ** 0.6 if c else 0
            h = 1.6 if c == 0 else 5 + t * MAXH
            cells.append((wi + di, wi, di, c, h, t))
    cells.sort(key=lambda x: (x[0], x[2]))

    # extents for centring
    xs, ys = [], []
    for _, wi, di, c, h, t in cells:
        bx, by = base(wi, di)
        xs += [bx, bx + WV[0], bx + DV[0], bx + WV[0] + DV[0]]
        ys += [by - h, by + WV[1] + DV[1], by + DV[1]]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad = 34
    s = min((CW - 2 * pad) / (maxx - minx), (CH - 2 * pad) / (maxy - miny))
    ox = (CW - (maxx - minx) * s) / 2 - minx * s
    oy = (CH - (maxy - miny) * s) / 2 - miny * s

    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CW} {CH}" width="{CW}" height="{CH}" '
             f'role="img" aria-label="3D contribution skyline for {login}">')
    o.append("""<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#090c16"/><stop offset="1" stop-color="#131a30"/>
  </linearGradient>
  <radialGradient id="halo" cx="0.62" cy="0.55" r="0.55">
    <stop offset="0" stop-color="#7c5cff" stop-opacity="0.20"/>
    <stop offset="1" stop-color="#7c5cff" stop-opacity="0"/>
  </radialGradient>
  <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="3.2" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <style>
    .rise{animation:rise .8s cubic-bezier(.2,.8,.2,1) both}
    @keyframes rise{from{opacity:0;transform:translateY(-26px)}to{opacity:1;transform:translateY(0)}}
    .pulse{animation:pulse 3.2s ease-in-out infinite}
    @keyframes pulse{0%,100%{opacity:.55}50%{opacity:1}}
    text{font-family:'Fira Code','SFMono-Regular',Consolas,'Liberation Mono',monospace}
  </style>
</defs>""")
    o.append(f'<rect width="{CW}" height="{CH}" rx="18" fill="url(#bg)"/>')
    o.append(f'<rect width="{CW}" height="{CH}" rx="18" fill="url(#halo)"/>')
    o.append(f'<rect x="0.5" y="0.5" width="{CW-1}" height="{CH-1}" rx="18" fill="none" stroke="#222c4a"/>')

    # floor plate
    def P(w, d, h=0):
        bx, by = base(w, d)
        return f"{ox + bx * s:.1f},{oy + (by - h) * s:.1f}"

    m = 0.6
    floor = [P(-m, -m), P(n_w + m - 1 + 1, -m), P(n_w + m - 1 + 1, 7 + m - 0), P(-m, 7 + m)]
    o.append(f'<polygon points="{" ".join(floor)}" fill="#ffffff" fill-opacity="0.025" '
             f'stroke="#7c5cff" stroke-opacity="0.25" stroke-width="1"/>')

    o.append('<g>')
    for order, wi, di, c, h, t in cells:
        bx, by = base(wi, di)
        p = lambda dx, dy, hh=0: f"{ox + (bx + dx) * s:.1f},{oy + (by + dy - hh) * s:.1f}"
        if c == 0:
            top = "#1b2340"
            left = "#141b33"
            right = "#10162b"
            glow = False
        else:
            col = ramp(t)
            top = hx(shade(col, 1.08))
            left = hx(shade(col, 0.60))
            right = hx(shade(col, 0.40))
            glow = t > 0.72
        W, D = WV, DV
        front = f"{p(D[0], D[1])} {p(W[0] + D[0], W[1] + D[1])} {p(W[0] + D[0], W[1] + D[1], h)} {p(D[0], D[1], h)}"
        side = f"{p(W[0], W[1])} {p(W[0] + D[0], W[1] + D[1])} {p(W[0] + D[0], W[1] + D[1], h)} {p(W[0], W[1], h)}"
        topf = f"{p(0, 0, h)} {p(W[0], W[1], h)} {p(W[0] + D[0], W[1] + D[1], h)} {p(D[0], D[1], h)}"
        attrs = ''
        if c:
            delay = (wi * 0.018 + di * 0.01)
            attrs = f' class="rise" style="animation-delay:{delay:.2f}s"'
        g = f'<g{attrs}>'
        g += f'<polygon points="{front}" fill="{left}"/><polygon points="{side}" fill="{right}"/>'
        g += f'<polygon points="{topf}" fill="{top}"'
        if glow:
            g += ' filter="url(#glow)"'
        g += '/></g>'
        o.append(g)
    o.append('</g>')

    # --- text: bottom-left hero number, top-right mini stats (empty corners of the diagonal)
    o.append(f'<text x="38" y="{CH-150}" fill="#ffffff" font-size="15" font-weight="700">@{login}</text>')
    o.append(f'<text x="38" y="{CH-130}" fill="#8b93b5" font-size="12">Java &#183; MERN &#183; Quantum &amp; AI</text>')
    o.append(f'<text x="38" y="{CH-84}" fill="#8b93b5" font-size="11" letter-spacing="2">LAST 12 MONTHS</text>')
    o.append(f'<text x="38" y="{CH-42}" fill="#ffffff" font-size="46" font-weight="700">{total:,}</text>')
    o.append(f'<text x="38" y="{CH-22}" fill="#8b93b5" font-size="13">contributions</text>')

    rx = CW - 38
    def stat(y, val, label, color):
        o.append(f'<text x="{rx}" y="{y}" fill="{color}" font-size="26" font-weight="700" text-anchor="end">{val}</text>')
        o.append(f'<text x="{rx}" y="{y+17}" fill="#8b93b5" font-size="11" text-anchor="end" letter-spacing="1.5">{label}</text>')
    stat(52, f"{cur}d", "CURRENT STREAK", "#2ee6c5")
    stat(112, f"{longest}d", "LONGEST STREAK", "#a98bff")
    stat(172, f"{best[0]}", "BEST DAY", "#ff7eb6")

    o.append('</svg>')
    return "\n".join(o)


def main():
    out = next((a for a in sys.argv[1:] if not a.startswith("--")), "assets/skyline.svg")
    login = os.environ.get("USERNAME", "Yash-Choubey09")
    if "--mock" in sys.argv:
        weeks, dates, total = mock()
    else:
        weeks, dates, total = fetch(login, os.environ["GITHUB_TOKEN"])
    svg = build(weeks, dates, total, login)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {out} ({len(svg)//1024} KB)")


if __name__ == "__main__":
    main()
