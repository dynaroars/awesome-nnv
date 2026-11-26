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
    peak = max(totals + [4])
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


def tidy_top(peak):
    return next(s for s in (4, 5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200) if peak <= s)


def venue_panel(name, field, years, counts, totals, missing, not_held, top):
    width, left, right, top_pad, plot_h, bottom = 240, 22, 6, 8, 70, 18
    plot_w, base = width - left - right, top_pad + plot_h
    band = plot_w / len(years)
    bar = band * 0.62
    out = [f'<svg class="chart mini" viewBox="0 0 {width} {base + bottom}" role="img" '
           f'aria-label="{_esc(name)}: NNV papers per year">',
           f'<line class="grid" x1="{left}" y1="{top_pad}" x2="{width - right}" y2="{top_pad}"/>',
           f'<text x="{left - 4}" y="{top_pad + 4}" text-anchor="end">{top}</text>',
           f'<line class="axis" x1="{left}" y1="{base}" x2="{width - right}" y2="{base}"/>',
           f'<text x="{left - 4}" y="{base + 4}" text-anchor="end">0</text>']
    for k, y in enumerate(years):
        x = left + band * k
        cx = x + band / 2
        n, total = counts.get(str(y), 0), totals.get(str(y), 0)
        if y in not_held:
            tip = f"{name} {y}: not held"
        elif y in missing:
            out.append(f'<circle class="pending" cx="{cx:.1f}" cy="{base}" r="2.6"/>')
            tip = f"{name} {y}: not yet in dblp"
        else:
            if n:
                h = max(n / top * plot_h, 1.5)
                r = min(2.5, h, bar / 2)
                bx, by = cx - bar / 2, base - h
                out.append(f'<path class="ar-{field}" d="M{bx:.1f},{base} V{by + r:.1f} Q{bx:.1f},{by:.1f} {bx + r:.1f},{by:.1f} '
                           f'H{bx + bar - r:.1f} Q{bx + bar:.1f},{by:.1f} {bx + bar:.1f},{by + r:.1f} V{base} Z"/>')
            share = f" ({100 * n / total:.1f}%)" if total else ""
            tip = f"{name} {y}: {n} of {total:,} papers{share}"
        out.append(f'<rect class="hit" x="{x:.1f}" y="{top_pad}" width="{band:.1f}" height="{plot_h}"><title>{_esc(tip)}</title></rect>')
    out.append(f'<text x="{left + band / 2:.1f}" y="{base + 14}" text-anchor="middle">{years[0]}</text>')
    out.append(f'<text x="{left + band * (len(years) - 0.5):.1f}" y="{base + 14}" text-anchor="middle">{years[-1]}</text>')
    out.append("</svg>")
    return "".join(out)


def multi_lines(label, years, series, note=None):
    width, left, right, top, plot_h, bottom = 860, 34, 290, 14, 230, 26
    plot_w, base = width - left - right, top + plot_h
    peak = max((v for _, _, values in series for v in values), default=0) or 1
    step = _step(peak, 5)
    top_value = step * -(-peak // step)
    xs = [left + plot_w * k / max(len(years) - 1, 1) for k in range(len(years))]
    y_of = lambda v: base - v / top_value * plot_h
    out = [f'<svg class="chart lines" viewBox="0 0 {width} {base + bottom}" role="img" aria-label="{_esc(label)}">']
    v = 0
    while v <= top_value:
        out.append(f'<line class="{"axis" if v == 0 else "grid"}" x1="{left}" y1="{y_of(v):.1f}" x2="{left + plot_w}" '
                   f'y2="{y_of(v):.1f}"/><text x="{left - 6}" y="{y_of(v) + 4:.1f}" text-anchor="end">{v}</text>')
        v += step
    for x, y in zip(xs, years):
        out.append(f'<text x="{x:.1f}" y="{base + 17}" text-anchor="middle">{y}</text>')
    ends = sorted(([y_of(values[-1]), k] for k, (_, _, values) in enumerate(series)), key=lambda e: e[0])
    for k in range(1, len(ends)):
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 15)
    label_y = {k: y for y, k in ends}
    for k, (cls, name, values) in enumerate(series):
        pts = " ".join(f"{x:.1f},{y_of(v):.1f}" for x, v in zip(xs, values))
        out.append(f'<g class="series {cls}" tabindex="0">')
        out.append(f'<polyline class="trend-hit" points="{pts}"/><polyline class="trend" points="{pts}"/>')
        for x, y, v in zip(xs, years, values):
            out.append(f'<circle class="trend-dot" cx="{x:.1f}" cy="{y_of(v):.1f}" r="3.5"><title>{_esc(f"{name}, {y}: {v} papers")}</title></circle>')
        ly = label_y[k]
        out.append(f'<circle class="trend-key" cx="{xs[-1] + 14:.1f}" cy="{ly:.1f}" r="4"/>'
                   f'<text class="trend-label" x="{xs[-1] + 22:.1f}" y="{ly + 4:.1f}">{_esc(name)}</text>'
                   f'<rect class="trend-label-hit" x="{xs[-1] + 8:.1f}" y="{ly - 8:.1f}" width="{right - 12}" height="16"/>')
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)
