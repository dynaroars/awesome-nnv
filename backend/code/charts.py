import html

WIDTH = 640


def _esc(text):
    return html.escape(str(text))


def _fmt(value):
    return f"{value:.1f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)


def _step(peak, limit=5):
    return next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000) if peak / s <= limit)


def _legend(series, y=16, x=0):
    out = []
    for cls, name in series:
        out.append(f'<rect class="{cls}" x="{x}" y="{y - 10}" width="12" height="12"/>'
                   f'<text x="{x + 18}" y="{y}">{_esc(name)}</text>')
        x += 30 + 6.4 * len(name)
    return "".join(out)


def stacked_columns(label, years, series, tip_word="papers"):
    left, right, top, plot_h, bottom = 34, 10, 34, 180, 24
    totals = [sum(values[k] for _, _, values in series) for k in range(len(years))]
    peak = max(totals, default=0) or 1
    step = _step(peak)
    top_value = step * -(-peak // step)
    base, plot_w = top + plot_h, WIDTH - left - right
    band = plot_w / max(len(years), 1)
    bar = min(30, band * 0.62)
    out = [f'<svg class="chart" viewBox="0 0 {WIDTH} {base + bottom}" role="img" aria-label="{_esc(label)}">',
           _legend([(cls, name) for cls, name, _ in series], x=left)]
    value = 0
    while value <= top_value:
        y = base - value / top_value * plot_h
        out.append(f'<line class="{"axis" if value == 0 else "grid"}" x1="{left}" y1="{y:.1f}" x2="{WIDTH - right}" '
                   f'y2="{y:.1f}"/><text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{value}</text>')
        value += step
    for k, year in enumerate(years):
        cx = left + band * (k + 0.5)
        lower = 0
        for cls, name, values in series:
            v = values[k]
            if not v:
                continue
            h = v / top_value * plot_h
            y = base - (lower + v) / top_value * plot_h
            out.append(f'<rect class="{cls} seg" x="{cx - bar / 2:.1f}" y="{y:.1f}" width="{bar:.1f}" height="{h:.1f}">'
                       f'<title>{_esc(f"{year}, {name}: {v} {tip_word}")}</title></rect>')
            lower += v
        if totals[k]:
            y = base - totals[k] / top_value * plot_h
            out.append(f'<text class="value" x="{cx:.1f}" y="{y - 5:.1f}" text-anchor="middle">{totals[k]}</text>')
        out.append(f'<text x="{cx:.1f}" y="{base + 17}" text-anchor="middle">{year}</text>')
    out.append("</svg>")
    return "".join(out)


def hbars(label, rows, unit="papers"):
    name_w, right, row_h, bar_h, top = 250, 46, 24, 14, 6
    peak = max((v for _, _, v in rows), default=0) or 1
    height = top + row_h * len(rows) + 4
    scale = (WIDTH - name_w - right) / peak
    out = [f'<svg class="chart bars" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{_esc(label)}">']
    for k, (cls, name, value) in enumerate(rows):
        y = top + k * row_h
        out.append(f'<text x="{name_w - 8}" y="{y + bar_h - 2}" text-anchor="end">{_esc(name)}</text>')
        w = value * scale
        if value:
            out.append(f'<rect class="{cls}" x="{name_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="2">'
                       f'<title>{_esc(f"{name}: {_fmt(value)} {unit}")}</title></rect>')
        out.append(f'<text class="value" x="{name_w + w + 6:.1f}" y="{y + bar_h - 2}">{_fmt(value)}</text>')
    out.append("</svg>")
    return "".join(out)
