import html

WIDTH = 640


def _esc(text):
    return html.escape(str(text))


def _fmt(value):
    return f"{value:.1f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)


def _step(peak, limit=5):
    return next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000) if peak / s <= limit)


def _legend(series, y=16, x=0):
    """Legend keys; each is a focusable group naming its series (data-series), so hovering or focusing a key
    highlights that series' marks (site.js)."""
    out = []
    for cls, name in series:
        w = 18 + 6.4 * len(name)
        out.append(f'<g class="key" data-series="{_esc(cls)}" tabindex="0">'
                   f'<rect class="key-hit" x="{x - 3}" y="{y - 13}" width="{w + 6:.1f}" height="18"/>'
                   f'<rect class="{cls}" x="{x}" y="{y - 10}" width="12" height="12"/>'
                   f'<text x="{x + 18}" y="{y}">{_esc(name)}</text></g>')
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


def _wrap(text, width=30):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur]


def pie(label, rows, unit="papers", cx=320, cy=200, r=112, link="areas/{key}/"):
    """A pie of (key, name, value) rows, largest first, clockwise from 12 o'clock. Each area keeps its own colour
    (class pie-<key>, style.css), so a resort moves a slice but never repaints it. Slice, leader line and label form
    one link to the area's page (`link`): hovering or focusing any of them highlights the area. Labels sit on the slice's side, pushed apart by
    their own height."""
    import math
    rows = sorted([r for r in rows if r[2]], key=lambda x: -x[2])
    total = sum(r[2] for r in rows) or 1
    out = [f'<svg class="chart pie" viewBox="0 0 {WIDTH} {2 * cy}" role="img" aria-label="{_esc(label)}">']
    labels, start, slices = [], 0.0, {}
    for k, (key, name, value) in enumerate(rows):
        sweep = 2 * math.pi * value / total
        a0, a1 = start, start + sweep
        p0 = (cx + r * math.sin(a0), cy - r * math.cos(a0))
        p1 = (cx + r * math.sin(a1), cy - r * math.cos(a1))
        share = 100 * value / total
        tip = _esc(f"{name}: {_fmt(value)} {unit} ({share:.0f}%)")
        slices[key] = (f'<path class="slice" d="M{cx},{cy} L{p0[0]:.1f},{p0[1]:.1f} A{r},{r} 0 '
                       f'{1 if sweep > math.pi else 0} 1 {p1[0]:.1f},{p1[1]:.1f} Z"><title>{tip}</title></path>', tip)
        mid = (a0 + a1) / 2
        count = f"{_fmt(value)} ({share:.0f}%)"
        lines = _wrap(name, 34)
        if len(lines[-1]) + 1 + len(count) > 34:
            lines.append(count)
        else:
            lines[-1] = f"{lines[-1]} {count}"
        labels.append({"key": key, "mid": mid, "lines": lines, "value": count, "h": 12 * len(lines) + 3,
                       "right": math.sin(mid) >= 0, "y": cy - (r + 18) * math.cos(mid)})
        start = a1
    top, bottom = 8, 2 * cy - 8
    for side in (True, False):
        group = sorted((l for l in labels if l["right"] == side), key=lambda l: l["y"])
        for i, l in enumerate(group):  # centre y of each label: push apart top to bottom, then back inside the box
            low = top + l["h"] / 2 if i == 0 else group[i - 1]["ly"] + (group[i - 1]["h"] + l["h"]) / 2
            l["ly"] = max(l["y"], low)
        for i in range(len(group) - 1, -1, -1):
            high = bottom - group[i]["h"] / 2 if i == len(group) - 1 else group[i + 1]["ly"] - (group[i + 1]["h"] + group[i]["h"]) / 2
            group[i]["ly"] = min(group[i]["ly"], high)
    for l in labels:
        ex, ey = cx + (r + 2) * math.sin(l["mid"]), cy - (r + 2) * math.cos(l["mid"])
        side = 1 if l["right"] else -1
        kx = cx + side * (r + 30)
        tx = kx + side * 4
        leader = (f'<polyline class="leader" points="{ex:.1f},{ey:.1f} {kx - side * 10:.1f},{l["ly"]:.1f} {kx:.1f},{l["ly"]:.1f}"/>')
        y0 = l["ly"] - 6 * (len(l["lines"]) - 1) + 4
        spans = []
        for i, t in enumerate(l["lines"]):
            if i == len(l["lines"]) - 1 and t.endswith(l["value"]):  # the count, in bold, at the end of the last line
                head = t[: -len(l["value"])].strip()
                t = (f'{_esc(head)} ' if head else "") + f'<tspan class="value">{_esc(l["value"])}</tspan>'
            else:
                t = _esc(t)
            spans.append(f'<tspan x="{tx:.1f}" y="{y0 + 12 * i:.1f}">{t}</tspan>')
        hit_x = tx if l["right"] else tx - 200
        path, tip = slices[l["key"]]
        out.append(f'<a class="pie-item pie-{l["key"]}" href="{link.format(key=l["key"])}" aria-label="{tip}">{path}{leader}'
                   f'<rect class="pie-hit" x="{hit_x:.1f}" y="{l["ly"] - l["h"] / 2:.1f}" width="200" height="{l["h"]:.1f}"/>'
                   f'<text class="pie-label" text-anchor="{"start" if l["right"] else "end"}">{"".join(spans)}</text></a>')
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


def multi_lines(label, years, series):
    width, left, right, top, plot_h, bottom = 880, 34, 300, 14, 240, 26
    plot_w, base = width - left - right, top + plot_h
    peak = max((v for _, _, values, _ in series for v in values), default=0) or 1
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
    gap, lo, hi = 16, top + 4, base
    ends = sorted(([y_of(values[-1]), k] for k, (_, _, values, _) in enumerate(series)), key=lambda e: e[0])
    for k in range(len(ends)):
        ends[k][0] = max(ends[k][0], lo if k == 0 else ends[k - 1][0] + gap)
    for k in range(len(ends) - 1, -1, -1):
        ends[k][0] = min(ends[k][0], hi if k == len(ends) - 1 else ends[k + 1][0] - gap)
    label_y = {k: y for y, k in ends}
    kx = xs[-1] + 12
    for k, (cls, name, values, key) in enumerate(series):
        pts = " ".join(f"{x:.1f},{y_of(v):.1f}" for x, v in zip(xs, values))
        ly = label_y[k]
        out.append(f'<g class="series {cls}" data-key="{_esc(key)}" tabindex="0">')
        out.append(f'<polyline class="trend-hit" points="{pts}"/><polyline class="trend" points="{pts}"/>')
        for x, y, v in zip(xs, years, values):
            out.append(f'<circle class="trend-dot" cx="{x:.1f}" cy="{y_of(v):.1f}" r="4"><title>{_esc(f"{name}, {y}: {v} papers")}</title></circle>')
        out.append(f'<line class="trend trend-key" x1="{kx:.1f}" y1="{ly:.1f}" x2="{kx + 24:.1f}" y2="{ly:.1f}"/>'
                   f'<text class="trend-label" x="{kx + 30:.1f}" y="{ly + 4:.1f}">{_esc(name)}</text>'
                   f'<rect class="trend-label-hit" x="{kx - 4:.1f}" y="{ly - 8:.1f}" width="{right - 16}" height="16"/>')
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)
