"""Render a benchmark summary as light and dark SVG bar charts for the README.

Usage: python bench/chart.py bench/results/<name>
Writes assets/bench-<name>-light.svg and assets/bench-<name>-dark.svg.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Categorical slots 1-3, validated light and dark with the dataviz palette validator.
THEMES = {
    "light": {"bg": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "grid": "#e4e3df",
              "series": ["#2a78d6", "#eb6834", "#1baf7a"]},
    "dark": {"bg": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "grid": "#33322f",
             "series": ["#3987e5", "#d95926", "#199e70"]},
}
FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"


def panel(x0, title, rows, fmt, t, width=360):
    """One horizontal bar panel: a single measure on a single axis, values labelled."""
    top, bar_h, gap, label_w = 70, 26, 14, 92
    vmax = max(v for _, v in rows) or 1
    plot_w = width - label_w - 70
    out = [f'<text x="{x0}" y="40" font-size="15" font-weight="600" fill="{t["ink"]}">{title}</text>']
    for i, (name, v) in enumerate(rows):
        y = top + i * (bar_h + gap)
        w = max(4, plot_w * v / vmax)
        out.append(f'<text x="{x0}" y="{y + 17}" font-size="13" fill="{t["ink2"]}">{name}</text>')
        out.append(f'<rect x="{x0 + label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="4" fill="{t["series"][i]}"/>')
        out.append(f'<text x="{x0 + label_w + w + 8:.1f}" y="{y + 17}" font-size="13" font-weight="600" fill="{t["ink"]}">{fmt(v)}</text>')
    base = top + len(rows) * (bar_h + gap) - gap + 6
    out.append(f'<line x1="{x0 + label_w}" y1="{top - 6}" x2="{x0 + label_w}" y2="{base}" stroke="{t["grid"]}" stroke-width="1"/>')
    return "\n".join(out)


def render(summary, theme, caption):
    t = THEMES[theme]
    configs = list(summary)
    cps = [(c, summary[c]["cost_usd"] / summary[c]["solved"] if summary[c]["solved"] else 0) for c in configs]
    mins = [(c, summary[c]["wall_s"] / 60) for c in configs]
    solved = [(c, summary[c]["solved"]) for c in configs]
    runs = summary[configs[0]]["runs"]
    body = "\n".join([
        panel(24, "Cost per solved task (list price)", cps, lambda v: f"${v:.2f}", t),
        panel(410, "Total wall time", mins, lambda v: f"{v:.0f} min", t),
        panel(796, f"Tasks solved (of {runs})", solved, lambda v: f"{v:.0f}", t, width=260),
    ])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="230" viewBox="0 0 1080 230" font-family="{FONT}" role="img" aria-label="Benchmark: cost per solved task, wall time and tasks solved for each configuration">
<rect width="1080" height="230" rx="12" fill="{t["bg"]}"/>
{body}
<text x="24" y="214" font-size="12" fill="{t["ink2"]}">{caption}</text>
</svg>
'''


def main():
    d = Path(sys.argv[1])
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    caption = (f"honojs/hono, real PRs merged after the models' training cutoff · Claude Code "
               f"{meta.get('claude_version', '').split()[0]} · Opus 5.5 · one run per task and configuration")
    for theme in THEMES:
        out = ROOT / "assets" / f"bench-{d.name}-{theme}.svg"
        out.write_text(render(summary, theme, caption), encoding="utf-8")
        print(out)


if __name__ == "__main__":
    main()
