#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染 README 自托管组件图，输出到 assets/。

stats / top-langs / pin 卡 / 年度活动曲线全部用 GITHUB_TOKEN 直连 GitHub API
（REST + GraphQL，限额 5000/h）本地渲染，不依赖 vercel.app 公共实例
（其对本仓库 Actions 出口 IP 返回 503/402，见 2026-09-13 运行日志）。
仅依赖 Python 标准库。任一组件渲染失败时保留旧图并继续。
"""
import base64
import json
import os
import urllib.parse
import urllib.request

OWNER = "Stargazed-Dreamer"
OUT = "assets"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

THEMES = {
    "dark": {"bg": "#141321", "title": "#fe428e", "text": "#a9fef7", "sub": "#79e8fb", "border": None},
    "light": {"bg": "#ffffff", "title": "#7e57c2", "text": "#434d58", "sub": "#586069", "border": "#e1e4e8"},
}
LANG_COLORS = {
    "Python": "#3572A5", "C#": "#178600", "C++": "#f34b7d", "C": "#555555",
    "Rust": "#dea584", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Kotlin": "#A97BFF", "Dart": "#00B4AB", "Go": "#00ADD8", "HTML": "#e34c26",
    "CSS": "#663399", "Shell": "#89e051", "Jupyter Notebook": "#DA5B0B",
    "Lua": "#000080", "GDScript": "#355570", "Java": "#b07219", "Vue": "#41b883",
}


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dw(s):
    """显示宽度：CJK 算 2，ASCII 算 1"""
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)


def wrap_text(s, max_units=56, max_lines=3):
    lines, cur, cur_w = [], "", 0
    for ch in s:
        w = 2 if ord(ch) > 0x2E80 else 1
        if cur_w + w > max_units and cur:
            lines.append(cur)
            cur, cur_w = ("" if ch == " " else ch), (0 if ch == " " else w)
        else:
            cur += ch
            cur_w += w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:-2] + "…"
    return lines


def save(name, svg):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  wrote {name} ({len(svg)}B)")


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"User-Agent": "widgets-renderer", "Accept": "application/vnd.github+json",
                 "Authorization": f"bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def graphql(query):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"User-Agent": "widgets-renderer", "Authorization": f"bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    if "errors" in data:
        raise RuntimeError(f"graphql errors: {data['errors']}")
    return data["data"]


# ---------------- stats 卡 ----------------
def render_stats(mode, stars, commits, prs, issues, contributed):
    t = THEMES[mode]
    rows = [
        ("★", "Total Stars", str(stars)),
        ("⟳", "Total Commits", f"{commits} (last yr)"),
        ("⇅", "Total PRs", str(prs)),
        ("⚠", "Total Issues", str(issues)),
        ("📦", "Contributed to", f"{contributed} repos"),
    ]
    stroke = f' stroke="{t["border"]}"' if t["border"] else ""
    body, y = "", 74
    for glyph, label, val in rows:
        body += (f'<text x="25" y="{y}" font-size="15" fill="{t["sub"]}">{glyph}</text>'
                 f'<text x="48" y="{y}" font-size="14" fill="{t["text"]}">{label}</text>'
                 f'<text x="475" y="{y}" text-anchor="end" font-size="14" font-weight="700" '
                 f'fill="{t["text"]}">{esc(val)}</text>')
        y += 30
    save(f"stats-{mode}.svg",
         f'<svg width="500" height="215" viewBox="0 0 500 215" xmlns="http://www.w3.org/2000/svg" role="img">'
         f'<rect x="0.5" y="0.5" width="499" height="214" rx="6" fill="{t["bg"]}"{stroke}/>'
         f'<text x="25" y="42" font-size="17" font-weight="600" fill="{t["title"]}" '
         f'font-family="Segoe UI,sans-serif">{OWNER}&#39;s GitHub Stats</text>{body}</svg>')


# ---------------- top-langs 卡 ----------------
def render_langs(mode, lang_rows):
    t = THEMES[mode]
    stroke = f' stroke="{t["border"]}"' if t["border"] else ""
    body, y = "", 52
    for k, p in lang_rows:
        c = LANG_COLORS.get(k, "#8b949e")
        body += (f'<circle cx="30" cy="{y - 4}" r="6" fill="{c}"/>'
                 f'<text x="44" y="{y}" font-size="13" fill="{t["text"]}" font-family="Segoe UI,sans-serif">{esc(k)}</text>'
                 f'<text x="325" y="{y}" text-anchor="end" font-size="13" fill="{t["sub"]}">{p:.1f}%</text>')
        y += 26
    save(f"langs-{mode}.svg",
         f'<svg width="350" height="{y + 6}" viewBox="0 0 350 {y + 6}" xmlns="http://www.w3.org/2000/svg" role="img">'
         f'<rect x="0.5" y="0.5" width="349" height="{y + 5}" rx="6" fill="{t["bg"]}"{stroke}/>'
         f'<text x="25" y="30" font-size="14" font-weight="600" fill="{t["title"]}" '
         f'font-family="Segoe UI,sans-serif">Most Used Languages</text>{body}</svg>')


# ---------------- pin 卡 ----------------
def render_pins(pins):
    metas = []
    for p in pins:
        lines = wrap_text(p.get("description") or "")
        metas.append({"name": p["name"], "desc": lines, "lang": p.get("language") or "Other",
                      "stars": p["stargazers_count"], "forks": p["forks_count"]})
    max_lines = max(len(m["desc"]) for m in metas)
    h = 56 + max_lines * 17 + 36
    for m in metas:
        body = (f'<text x="20" y="30" font-size="12.5" fill="#586069" font-family="Segoe UI,sans-serif">'
                f'{OWNER}/<tspan font-weight="700" font-size="15" fill="#0969da">{esc(m["name"])}</tspan></text>')
        y = 56
        for ln in m["desc"]:
            body += f'<text x="20" y="{y}" font-size="12.5" fill="#434d58" font-family="Segoe UI,sans-serif">{esc(ln)}</text>'
            y += 17
        y += (max_lines - len(m["desc"])) * 17
        dot = LANG_COLORS.get(m["lang"], "#8b949e")
        body += (f'<circle cx="27" cy="{h - 15}" r="7" fill="{dot}"/>'
                 f'<text x="40" y="{h - 10}" font-size="12.5" fill="#434d58" font-family="Segoe UI,sans-serif">{esc(m["lang"])}</text>'
                 f'<text x="330" y="{h - 10}" font-size="12.5" fill="#434d58" font-family="Segoe UI,sans-serif">&#9733; {m["stars"]}</text>'
                 f'<text x="378" y="{h - 10}" text-anchor="end" font-size="12.5" fill="#434d58" '
                 f'font-family="Segoe UI,sans-serif">&#9096; {m["forks"]}</text>')
        save(f"pin-{m['name']}.svg",
             f'<svg width="400" height="{h}" viewBox="0 0 400 {h}" xmlns="http://www.w3.org/2000/svg" role="img">'
             f'<rect x="0.5" y="0.5" width="399" height="{h - 1}" rx="6" fill="#ffffff" stroke="#e1e4e8"/>{body}</svg>')


# ---------------- 年度活动曲线 ----------------
def render_activity(days):
    w, h, pad = 850, 200, 14
    n = len(days)
    mx = max(days) or 1
    step = (w - 2 * pad) / max(n - 1, 1)
    pts = [(pad + i * step, h - pad - (c / mx) * (h - 2 * pad)) for i, c in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M{pts[0][0]:.1f},{h - pad} " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{h - pad} Z"
    save("activity-graph.svg",
         f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img">'
         f'<path d="{area}" fill="#8A2BE2" fill-opacity="0.16"/>'
         f'<polyline points="{line}" fill="none" stroke="#FF6EC7" stroke-width="2.5" stroke-linejoin="round"/>'
         f'</svg>')


def main():
    os.makedirs(OUT, exist_ok=True)
    repos = api(f"/users/{OWNER}/repos?per_page=100")
    orig = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in orig)
    pin_names = ["mesugaki", "MelodyMark", "MusePlayer", "localAgent-public"]
    pins = [r for r in repos if r["name"] in pin_names]
    print(f"repos={len(repos)} orig={len(orig)} stars={stars}")

    prs = api(f"/search/issues?q={urllib.parse.quote(f'author:{OWNER} type:pr')}")["total_count"]
    issues = api(f"/search/issues?q={urllib.parse.quote(f'author:{OWNER} type:issue')}")["total_count"]

    data = graphql("""query($login:String!){
      user(login:$login){
        contributionsCollection{ totalCommitContributions contributionCalendar{ weeks{ contributionDays{ contributionCount } } } }
        repositoriesContributedTo(first:1){ totalCount }
      }
    }""")
    u = data["user"]
    commits = u["contributionsCollection"]["totalCommitContributions"]
    contributed = u["repositoriesContributedTo"]["totalCount"]
    days = [d["contributionCount"] for w in u["contributionsCollection"]["contributionCalendar"]["weeks"]
            for d in w["contributionDays"]]
    print(f"commits={commits} contributed_to={contributed} prs={prs} issues={issues} calendar_days={len(days)}")

    lang_bytes = {}
    for r in orig:
        try:
            for k, v in api(r["languages_url"].replace("https://api.github.com", "")).items():
                lang_bytes[k] = lang_bytes.get(k, 0) + v
        except Exception as e:
            print(f"  WARN languages {r['name']}: {e}")
    top = sorted(lang_bytes.items(), key=lambda kv: -kv[1])[:5]
    total = sum(v for _, v in top) or 1
    lang_rows = [(k, v / total * 100) for k, v in top]

    failures = 0
    for mode in THEMES:
        try:
            render_stats(mode, stars, commits, prs, issues, contributed)
            render_langs(mode, lang_rows)
        except Exception as e:
            failures += 1
            print(f"  WARN render {mode}: {e}")
    try:
        render_pins(pins)
    except Exception as e:
        failures += 1
        print(f"  WARN render pins: {e}")
    try:
        render_activity(days)
    except Exception as e:
        failures += 1
        print(f"  WARN render activity: {e}")
    print(f"render done, failures={failures}")
    raise SystemExit(1 if failures >= 4 else 0)


if __name__ == "__main__":
    main()
