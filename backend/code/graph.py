import collections
import itertools
import math

import networkx as nx

from common import LABEL_MIN

WIDTH = 1600
PAD = 30
LABEL_W = 7.2


def edges_of(papers, ids):
    weight = collections.Counter()
    for p in papers:
        for a, b in itertools.combinations(sorted(s for s in p["slugs"] if s in ids), 2):
            weight[(a, b)] += 1
    return weight


def radius_of(papers):
    return round(7 + 2.2 * math.sqrt(papers), 1)


def boxes(pos, size):
    return {k: (x - size[k][0], y - 11, x + size[k][1], y + 11) for k, (x, y) in pos.items()}


def separate(pos, size, rounds=400, gap=6):
    pos = {k: list(v) for k, v in pos.items()}
    keys = sorted(pos)
    for _ in range(rounds):
        moved = False
        b = boxes(pos, size)
        for i, a in enumerate(keys):
            for c in keys[i + 1:]:
                ax0, ay0, ax1, ay1 = b[a]
                cx0, cy0, cx1, cy1 = b[c]
                ox = min(ax1, cx1) - max(ax0, cx0) + gap
                oy = min(ay1, cy1) - max(ay0, cy0) + gap
                if ox <= 0 or oy <= 0:
                    continue
                moved = True
                if oy < ox:
                    d = oy / 2 * (1 if pos[a][1] >= pos[c][1] else -1)
                    pos[a][1] += d
                    pos[c][1] -= d
                else:
                    d = ox / 2 * (1 if pos[a][0] >= pos[c][0] else -1)
                    pos[a][0] += d
                    pos[c][0] -= d
                b[a] = (pos[a][0] - size[a][0], pos[a][1] - 11, pos[a][0] + size[a][1], pos[a][1] + 11)
                b[c] = (pos[c][0] - size[c][0], pos[c][1] - 11, pos[c][0] + size[c][1], pos[c][1] + 11)
        if not moved:
            break
    return {k: tuple(v) for k, v in pos.items()}


def component_layout(g, size, seed, group_of):
    n = g.number_of_nodes()
    if n == 1:
        return {next(iter(g.nodes)): (0.0, 0.0)}
    for a, b, d in g.edges(data=True):
        d["dist"] = (0.75 if group_of[a] == group_of[b] else 1.25) / math.sqrt(d["weight"])
    pos = nx.kamada_kawai_layout(g, weight="dist")
    span = 105 * math.sqrt(n)
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    s = span / max((max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1)
    pos = {k: ((x - min(xs)) * s * 1.35, (y - min(ys)) * s) for k, (x, y) in pos.items()}
    pos = separate(pos, size)
    x0 = min(x - size[k][0] for k, (x, _) in pos.items())
    y0 = min(y for _, y in pos.values())
    return {k: (x - x0, y - y0) for k, (x, y) in pos.items()}


def geometry(shape, x, y, r):
    if shape == "square":
        h = 0.89 * r
        return {"rx": round(x - h, 1), "ry": round(y - h, 1), "side": round(2 * h, 1)}
    if shape == "diamond":
        d = 1.25 * r
        pts = [(x, y - d), (x + d, y), (x, y + d), (x - d, y)]
    elif shape == "triangle":
        c = 1.56 * r
        pts = [(x, y - c), (x + c * 0.866, y + c / 2), (x - c * 0.866, y + c / 2)]
    else:
        return {}
    return {"points": " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}


def layout(researchers, groups, papers):
    ids = {r["slug"] for r in researchers}
    by_slug = {r["slug"]: r for r in researchers}
    weight = edges_of(papers, ids)
    g = nx.Graph()
    for (a, b), w in weight.items():
        g.add_edge(a, b, weight=w)
    comps = sorted(nx.connected_components(g), key=lambda c: (-len(c), min(c)))
    placed, x0, y0, row_h = {}, PAD, PAD, 0
    size = {s: (radius_of(r["papers"]) + 2, radius_of(r["papers"]) + 8 + LABEL_W * len(r["name"]))
            for s, r in by_slug.items()}
    for k, comp in enumerate(comps):
        pos = component_layout(g.subgraph(comp).copy(), size, seed=k + 1, group_of={x: by_slug[x]["group"] for x in comp})
        w = max(x + size[s][1] for s, (x, _) in pos.items()) + 24
        h = max(y for _, y in pos.values()) + 30
        if x0 + w > WIDTH - PAD and x0 > PAD:
            x0, y0, row_h = PAD, y0 + row_h + 40, 0
        for s, (x, y) in pos.items():
            placed[s] = (x0 + x + 12, y0 + y + 12)
        x0 += w + 40
        row_h = max(row_h, h)
    height = y0 + row_h + PAD
    width = max([WIDTH] + [x + LABEL_W * len(by_slug[s]["name"]) + 30 for s, (x, _) in placed.items()])
    degree = dict(g.degree())
    nodes = []
    for s, (x, y) in placed.items():
        r = by_slug[s]
        radius = radius_of(r["papers"])
        nodes.append({"id": s, "name": r["name"], "x": round(x, 1), "y": round(y, 1), "r": radius,
                      "lx": round(x + radius + 4, 1), "ly": round(y + 4, 1), "color": r["color"], "hue": r["hue"], "shape": r["shape"],
                      "filled": r["filled"], **geometry(r["shape"], x, y, radius),
                      "papers": r["papers"], "degree": degree[s], "group": r["group_name"], "group_slug": r["group"],
                      "url": f"researchers/{s}/"})
    edges = []
    for (a, b), w in weight.items():
        (x1, y1), (x2, y2) = placed[a], placed[b]
        edges.append({"a": a, "b": b, "a_name": by_slug[a]["name"], "b_name": by_slug[b]["name"], "weight": w,
                      "x1": round(x1, 1), "y1": round(y1, 1), "x2": round(x2, 1), "y2": round(y2, 1),
                      "wx": round((x1 + x2) / 2, 1), "wy": round((y1 + y2) / 2, 1),
                      "width": round(1.2 + 1.3 * math.sqrt(w), 1)})
    drawn = {n["color"] for n in nodes}
    legend = [{"color": gr["color"], "hue": gr["hue"], "shape": gr["shape"], "filled": gr["filled"], "label": gr["name"],
               "slug": gr["slug"], "logo": gr["logo"], "country": gr["country"], "country_name": gr["country_name"]}
              for gr in sorted((x for x in groups if x["legend_order"] is not None), key=lambda x: x["legend_order"])
              if gr["color"] in drawn]
    if "other" in drawn:
        legend.append({"color": "other", "hue": 0, "shape": "circle", "filled": False, "label": "", "slug": ""})
    on_graph = {n["group_slug"] for n in nodes}
    info = {gr["slug"]: {"name": gr["name"], "description": gr["description"], "tools": gr["tools"],
                         "researchers": len(gr["members"]), "papers": gr["papers"], "logo": gr["logo"],
                         "country": gr["country"], "country_name": gr["country_name"],
                         "hue": gr["hue"], "shape": gr["shape"], "filled": gr["filled"]}
            for gr in groups if gr["slug"] in on_graph}
    return {"width": round(width), "height": round(height), "nodes": nodes, "edges": edges, "legend": legend,
            "groups": info}
