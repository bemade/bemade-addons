# -*- coding: utf-8 -*-
"""Geometry figures for practice cards (UC-25), drawn from a short spec.

A spec is a shape name followed by ``key=value`` settings, separated by spaces::

    tri kind=isosceles rot=20 s=.8
    quad kind=square rot=45
    poly pts=0,0/2,0/2,1.4/1,2.3/0,1.4 marks=none
    regular n=8 rot=10
    circle mark=diameter label=12_cm
    angle deg=35 rot=200
    lines kind=perpendicular rot=30
    solid kind=pyramid4 view=left s=.7

``render(spec)`` returns a standalone SVG document (light strokes on a transparent
background, for the dark lesson screen) that the screen shows as an image; ``facts(spec)``
returns what the drawing shows (number of sides, triangle / quadrilateral names from the
measured sides and angles, the solid's faces / edges / vertices…), so the cards can be
checked against the figure they carry. The marks are computed from the drawn geometry
itself: equal sides get the same tick marks, right angles a small square, parallel sides the
same arrows, so a figure never claims what it does not draw.

Common settings: ``rot`` (degrees), ``s`` (size, 0.4–1), ``labels`` (vertex letters, e.g.
``ABC``), ``marks`` (``s`` equal sides, ``a`` right angles, ``p`` parallel sides, ``e`` equal
angles, comma-separated, or ``none``). Plain Python: no Odoo import.
"""
import math
import re
from xml.etree import ElementTree as ET

W, H = 320, 240
INK = "#f5f7fb"
MARK = "#fca311"
SOFT = "#aab4c8"
SVG_NS = "http://www.w3.org/2000/svg"
POLYGON_NAMES = {3: "triangle", 4: "quadrilatère", 5: "pentagone", 6: "hexagone", 7: "heptagone", 8: "octogone"}

TRIANGLES = {
    "equilateral": [(0, 0), (2, 0), (1, math.sqrt(3))],
    "isosceles": [(0, 0), (2, 0), (1, 2.4)],
    "isosceles-obtuse": [(0, 0), (3, 0), (1.5, 0.8)],
    "scalene": [(0, 0), (3, 0), (0.8, 1.9)],
    "obtuse": [(0, 0), (3.2, 0), (-0.9, 1.4)],
    "right": [(0, 0), (3, 0), (0, 2)],
    "right-isosceles": [(0, 0), (2.2, 0), (0, 2.2)],
}
_R65 = (math.cos(math.radians(65)) * 2, math.sin(math.radians(65)) * 2)
QUADS = {
    "square": ([(0, 0), (2, 0), (2, 2), (0, 2)], "s,a"),
    "rectangle": ([(0, 0), (3, 0), (3, 1.6), (0, 1.6)], "s,a"),
    "rhombus": ([(0, 0), (2, 0), (2 + _R65[0], _R65[1]), _R65], "s"),
    "parallelogram": ([(0, 0), (3, 0), (3.8, 1.6), (0.8, 1.6)], "s,p"),
    "trapezoid": ([(0, 0), (3.4, 0), (2.4, 1.6), (0.8, 1.6)], "p"),
    "isosceles-trapezoid": ([(0, 0), (3.2, 0), (2.4, 1.6), (0.8, 1.6)], "p,s"),
    "right-trapezoid": ([(0, 0), (3.2, 0), (2, 1.7), (0, 1.7)], "p,a"),
    "any": ([(0, 0), (3, 0.3), (2.6, 1.9), (0.4, 1.4)], "none"),
}


def _box(w, h, d):
    v = [(0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0), (0, 0, d), (w, 0, d), (w, h, d), (0, h, d)]
    return v, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (3, 2, 6, 7), (0, 3, 7, 4), (1, 2, 6, 5)]


def _prism(base, d):
    """A prism lying with its base polygon (x, y) facing the viewer, ``d`` deep."""
    n = len(base)
    v = [(x, y, 0) for x, y in base] + [(x, y, d) for x, y in base]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, faces


def _standing_prism(base, h):
    """A prism standing on its base polygon (x, z), ``h`` high."""
    n = len(base)
    v = [(x, 0, z) for x, z in base] + [(x, h, z) for x, z in base]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, faces


def _pyramid(base, apex):
    """A pyramid on its base polygon (x, z) with its apex (x, y, z)."""
    n = len(base)
    v = [(x, 0, z) for x, z in base] + [apex]
    return v, [tuple(range(n))] + [(i, (i + 1) % n, n) for i in range(n)]


_HEX = [(1 + math.cos(math.radians(60 * i)), 1 + math.sin(math.radians(60 * i))) for i in range(6)]
SOLIDS = {
    # name: (French name, model or None for a round solid)
    "cube": ("cube", _box(2, 2, 2)),
    "box": ("prisme à base rectangulaire", _box(3, 1.6, 1.6)),
    "prism3": ("prisme à base triangulaire", _prism([(0, 0), (2.4, 0), (1.2, 1.8)], 2.6)),
    "prism6": ("prisme à base hexagonale", _standing_prism(_HEX, 2.2)),
    "pyramid4": ("pyramide à base carrée", _pyramid([(0, 0), (2.2, 0), (2.2, 2.2), (0, 2.2)], (1.1, 2.2, 1.1))),
    "pyramid3": ("pyramide à base triangulaire", _pyramid([(0, 0), (2.6, 0), (1.1, 2.0)], (1.2, 2.2, 0.7))),
    "cylinder": ("cylindre", None),
    "cone": ("cône", None),
    "sphere": ("boule", None),
}


# ----------------------------------------------------------------------------- parsing
def parse(spec):
    tokens = (spec or "").split()
    if not tokens:
        raise ValueError("empty figure spec")
    params = {}
    for token in tokens[1:]:
        key, sep, value = token.partition("=")
        params[key] = value if sep else "1"
    return tokens[0], params


def _f(params, key, default):
    return float(params.get(key, default))


def _points(text):
    return [tuple(float(c) for c in p.split(",")) for p in text.split("/")]


# ----------------------------------------------------------------------------- geometry
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _len(v):
    return math.hypot(v[0], v[1])


def _unit(v):
    n = _len(v) or 1.0
    return (v[0] / n, v[1] / n)


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _angle_at(pts, i):
    p, a, b = pts[i], pts[i - 1], pts[(i + 1) % len(pts)]
    u, v = _unit(_sub(a, p)), _unit(_sub(b, p))
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(u, v)))))


def _groups(values, close):
    """Indices grouped by equal value (only groups of 2 or more), in order of first index."""
    out, used = [], set()
    for i, a in enumerate(values):
        if i in used:
            continue
        group = [i] + [j for j in range(i + 1, len(values)) if j not in used and close(a, values[j])]
        if len(group) > 1:
            out.append(group)
            used.update(group)
    return out


def analyse(pts):
    """What a closed polygon shows: sides, convexity, equal sides, right angles, parallel sides."""
    n = len(pts)
    sides = [_sub(pts[(i + 1) % n], pts[i]) for i in range(n)]
    lengths = [_len(s) for s in sides]
    angles = [_angle_at(pts, i) for i in range(n)]
    turns = [_cross(sides[i], sides[(i + 1) % n]) for i in range(n)]
    convex = all(t > 0 for t in turns) or all(t < 0 for t in turns)
    if not convex:  # interior angle at a reflex vertex
        sign = 1 if sum(turns) > 0 else -1
        angles = [a if turns[i - 1] * sign > 0 else 360 - a for i, a in enumerate(angles)]
    tol = 1e-3 * max(lengths)
    equal = _groups(lengths, lambda a, b: abs(a - b) < tol)
    right = [i for i, a in enumerate(angles) if abs(a - 90) < 0.5]
    parallel = _groups([_unit(s) for s in sides], lambda a, b: abs(_cross(a, b)) < 1e-3)
    return {"n": n, "lengths": lengths, "angles": angles, "convex": convex, "equal": equal,
            "right": right, "parallel": parallel}


def triangle_names(pts):
    """The names a triangle earns from its measured sides and angles."""
    a = analyse(pts)
    biggest = max((len(g) for g in a["equal"]), default=1)
    names = {"équilatéral", "isocèle"} if biggest == 3 else {"isocèle"} if biggest == 2 else {"scalène"}
    top = max(a["angles"])
    names.add("rectangle" if abs(top - 90) < 0.5 else "obtusangle" if top > 90 else "acutangle")
    return names


def quad_names(pts):
    """The names a quadrilateral earns (Québec definitions: a trapèze has at least one pair
    of parallel sides, so every parallélogramme is also a trapèze)."""
    a = analyse(pts)
    names = {"quadrilatère"}
    pairs = len(a["parallel"])
    if a["convex"] and pairs >= 1:
        names.add("trapèze")
    if pairs == 2:
        names.add("parallélogramme")
    if any(len(g) == 4 for g in a["equal"]):
        names.add("losange")
    if len(a["right"]) == 4:
        names.add("rectangle")
    if {"losange", "rectangle"} <= names:
        names.add("carré")
    return names


def most_specific(names):
    for name in ("carré", "rectangle", "losange", "parallélogramme", "trapèze", "quadrilatère"):
        if name in names:
            return name
    return None


def solid_counts(kind):
    """(faces, edges, vertices) of a polyhedron model, counted from the model itself."""
    _name, model = SOLIDS[kind]
    verts, faces = model
    edges = {tuple(sorted((f[i], f[(i + 1) % len(f)]))) for f in faces for i in range(len(f))}
    return len(faces), len(edges), len(verts)


# ----------------------------------------------------------------------------- facts
def shape_points(kind, params):
    if kind == "tri":
        return list(TRIANGLES[params["kind"]])
    if kind == "quad":
        return list(QUADS[params["kind"]][0])
    if kind == "regular":
        n = int(params["n"])
        return [(math.cos(2 * math.pi * i / n - math.pi / 2), math.sin(2 * math.pi * i / n - math.pi / 2))
                for i in range(n)]
    if kind == "poly":
        return _points(params["pts"])
    return None


def facts(spec):
    kind, params = parse(spec)
    pts = shape_points(kind, params)
    if pts is not None:
        a = analyse(pts)
        out = {"polygon": True, "closed": True, "sides": a["n"], "vertices": a["n"], "convex": a["convex"],
               "name": POLYGON_NAMES.get(a["n"])}
        if a["n"] == 3:
            out["triangle"] = triangle_names(pts)
        if a["n"] == 4:
            out["quad"] = quad_names(pts)
        return out
    if kind == "open":
        return {"polygon": False, "closed": False, "line": "brisée"}
    if kind == "curve":
        closed = params.get("kind") == "closed"
        return {"polygon": False, "closed": closed, "line": "courbe"}
    if kind == "semidisk":
        return {"polygon": False, "closed": True, "line": "mixte"}
    if kind == "circle":
        return {"mark": params.get("mark", "none")}
    if kind == "angle":
        deg = _f(params, "deg", 90)
        return {"angle": "droit" if abs(deg - 90) < 0.5 else "aigu" if deg < 90 else "obtus" if deg < 180 else "plat"}
    if kind == "lines":
        return {"lines": {"parallel": "parallèles", "perpendicular": "perpendiculaires",
                          "secant": "sécantes"}[params["kind"]]}
    if kind == "solid":
        name, model = SOLIDS[params["kind"]]
        out = {"solid": name, "curved": model is None}
        if model:
            out["faces"], out["edges"], out["vertices"] = solid_counts(params["kind"])
        return out
    raise ValueError("unknown figure: %s" % kind)


# ----------------------------------------------------------------------------- drawing
def _n(x):
    return ("%.1f" % x).rstrip("0").rstrip(".") if abs(x) >= 0.05 else "0"


def _pt(p):
    return "%s,%s" % (_n(p[0]), _n(p[1]))


def _place(pts, params, margin=(80, 70), flip=True):
    """Rotate, flip to screen coordinates (y down) and fit in the canvas, centred, at size ``s``."""
    rot = math.radians(_f(params, "rot", 0))
    s = max(0.35, min(1.0, _f(params, "s", 1)))
    c, si = math.cos(rot), math.sin(rot)
    out = [(x * c - y * si, -(x * si + y * c) if flip else (x * si + y * c)) for x, y in pts]
    xs, ys = [p[0] for p in out], [p[1] for p in out]
    w, h = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
    k = s * min((W - margin[0]) / w, (H - margin[1]) / h)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return [(W / 2 + (x - cx) * k, H / 2 + (y - cy) * k) for x, y in out], k


def _line(a, b, color=INK, width=4, dash=False):
    extra = ' stroke-dasharray="9 7"' if dash else ""
    return '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"%s/>' % (
        _n(a[0]), _n(a[1]), _n(b[0]), _n(b[1]), color, width, extra)


def _text(p, label, size=20, color=SOFT):
    return ('<text x="%s" y="%s" fill="%s" stroke="none" font-size="%s" font-family="sans-serif" '
            'font-weight="700" text-anchor="middle" dominant-baseline="central">%s</text>') % (
        _n(p[0]), _n(p[1]), color, size, _esc(label))


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _ticks(a, b, count, at=0.5):
    u = _unit(_sub(b, a))
    nrm = (-u[1], u[0])
    m = (a[0] + (b[0] - a[0]) * at, a[1] + (b[1] - a[1]) * at)
    out = []
    for i in range(count):
        o = (i - (count - 1) / 2) * 7
        c = (m[0] + u[0] * o, m[1] + u[1] * o)
        out.append(_line((c[0] + nrm[0] * 10, c[1] + nrm[1] * 10), (c[0] - nrm[0] * 10, c[1] - nrm[1] * 10), MARK, 3))
    return out


def _arrows(a, b, count, ref, at=0.5):
    u = _unit(_sub(b, a))
    if _dot(u, ref) < 0:
        u = (-u[0], -u[1])
    nrm = (-u[1], u[0])
    m = (a[0] + (b[0] - a[0]) * at, a[1] + (b[1] - a[1]) * at)
    out = []
    for i in range(count):
        o = (i - (count - 1) / 2) * 9 + 4
        tip = (m[0] + u[0] * o, m[1] + u[1] * o)
        back = (tip[0] - u[0] * 10, tip[1] - u[1] * 10)
        out.append('<polyline points="%s %s %s" stroke="%s" stroke-width="3" fill="none"/>' % (
            _pt((back[0] + nrm[0] * 8, back[1] + nrm[1] * 8)), _pt(tip),
            _pt((back[0] - nrm[0] * 8, back[1] - nrm[1] * 8)), MARK))
    return out


def _square(v, a, b, size=16):
    u, w = _unit(_sub(a, v)), _unit(_sub(b, v))
    p1 = (v[0] + u[0] * size, v[1] + u[1] * size)
    p2 = (p1[0] + w[0] * size, p1[1] + w[1] * size)
    p3 = (v[0] + w[0] * size, v[1] + w[1] * size)
    return '<polyline points="%s %s %s" stroke="%s" stroke-width="3" fill="none"/>' % (_pt(p1), _pt(p2), _pt(p3), MARK)


def _arc(v, a, b, r, color=MARK, reflex=False):
    u, w = _unit(_sub(a, v)), _unit(_sub(b, v))
    p, q = (v[0] + u[0] * r, v[1] + u[1] * r), (v[0] + w[0] * r, v[1] + w[1] * r)
    sweep = 1 if _cross(u, w) > 0 else 0
    if reflex:
        sweep = 1 - sweep
    return '<path d="M %s A %s %s 0 %d %d %s" stroke="%s" stroke-width="3" fill="none"/>' % (
        _pt(p), _n(r), _n(r), 1 if reflex else 0, sweep, _pt(q), color)


def _marks_wanted(params, default):
    marks = params.get("marks", default)
    return set() if marks in ("none", "") else set(marks.split(","))


def _polygon(pts, params, default_marks="none"):
    screen, _k = _place(pts, params)
    a = analyse(screen)
    n = len(screen)
    wanted = _marks_wanted(params, default_marks)
    body = ['<polygon points="%s" stroke="%s" stroke-width="4" fill="%s" fill-opacity=".10" stroke-linejoin="round"/>'
            % (" ".join(_pt(p) for p in screen), INK, INK)]
    ticked = set()
    if "s" in wanted:
        for k, group in enumerate(a["equal"], start=1):
            for i in group:
                ticked.add(i)
                body += _ticks(screen[i], screen[(i + 1) % n], k, at=0.5)
    if "p" in wanted:
        for k, group in enumerate(a["parallel"], start=1):
            ref = _unit(_sub(screen[(group[0] + 1) % n], screen[group[0]]))
            for i in group:
                body += _arrows(screen[i], screen[(i + 1) % n], k, ref, at=0.72 if i in ticked else 0.5)
    if "a" in wanted:
        for i in a["right"]:
            body.append(_square(screen[i], screen[i - 1], screen[(i + 1) % n]))
    if "e" in wanted:
        angle_groups = _groups(a["angles"], lambda x, y: abs(x - y) < 0.5)
        for k, group in enumerate(angle_groups, start=1):
            for i in group:
                if i in a["right"]:
                    continue
                for j in range(k):
                    body.append(_arc(screen[i], screen[i - 1], screen[(i + 1) % n], 22 + 6 * j))
    labels = params.get("labels", "")
    if labels:
        cx = sum(p[0] for p in screen) / n
        cy = sum(p[1] for p in screen) / n
        for i, label in enumerate(labels[:n]):
            d = _unit(_sub(screen[i], (cx, cy)))
            body.append(_text((screen[i][0] + d[0] * 20, screen[i][1] + d[1] * 20), label))
    return body


def _ellipse(c, rx, ry, start, end, steps=40):
    return [(c[0] + rx * math.cos(math.radians(start + (end - start) * i / steps)),
             c[1] - ry * math.sin(math.radians(start + (end - start) * i / steps))) for i in range(steps + 1)]


def _polyline(pts, color=INK, width=4, dash=False, fill="none"):
    extra = ' stroke-dasharray="9 7"' if dash else ""
    return '<polyline points="%s" stroke="%s" stroke-width="%s" fill="%s"%s/>' % (
        " ".join(_pt(p) for p in pts), color, width, fill, extra)


def _solid(params):
    kind = params["kind"]
    _name, model = SOLIDS[kind]
    s = max(0.35, min(1.0, _f(params, "s", 1)))
    if model is None:
        return _round_solid(kind, s)
    theta = math.radians(145 if params.get("view") == "left" else 35)
    k = 0.5
    verts, faces = model
    proj = [(x + k * z * math.cos(theta), y + k * z * math.sin(theta)) for x, y, z in verts]
    screen, _scale = _place(proj, {"s": s})
    centre = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
    view = (k * math.cos(theta), k * math.sin(theta), -1)
    visible = []
    for f in faces:
        p0, p1, p2 = (verts[f[0]], verts[f[1]], verts[f[2]])
        e1 = [p1[i] - p0[i] for i in range(3)]
        e2 = [p2[i] - p0[i] for i in range(3)]
        nrm = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
        fc = [sum(verts[j][i] for j in f) / len(f) for i in range(3)]
        if sum(nrm[i] * (fc[i] - centre[i]) for i in range(3)) < 0:
            nrm = [-x for x in nrm]
        visible.append(sum(nrm[i] * view[i] for i in range(3)) > 1e-9)
    edge_faces = {}
    for fi, f in enumerate(faces):
        for i in range(len(f)):
            edge_faces.setdefault(tuple(sorted((f[i], f[(i + 1) % len(f)]))), []).append(fi)
    hidden, shown = [], []
    for (a, b), fs in sorted(edge_faces.items()):
        (shown if any(visible[fi] for fi in fs) else hidden).append(_line(screen[a], screen[b], INK, 4, dash=not any(
            visible[fi] for fi in fs)))
    return hidden + shown


def _round_solid(kind, s):
    r = 70 * s
    c = (W / 2, H / 2)
    if kind == "sphere":
        return ['<circle cx="%s" cy="%s" r="%s" stroke="%s" stroke-width="4" fill="%s" fill-opacity=".10"/>' % (
                    _n(c[0]), _n(c[1]), _n(r * 1.3), INK, INK),
                _polyline(_ellipse(c, r * 1.3, r * 0.38, 0, 180), dash=True),
                _polyline(_ellipse(c, r * 1.3, r * 0.38, 180, 360))]
    ry, h = r * 0.32, r * 2.0
    top, bottom = (c[0], c[1] - h / 2), (c[0], c[1] + h / 2)
    base = [_polyline(_ellipse(bottom, r, ry, 0, 180), dash=True), _polyline(_ellipse(bottom, r, ry, 180, 360))]
    if kind == "cylinder":
        return base + [_polyline(_ellipse(top, r, ry, 0, 360)),
                       _line((top[0] - r, top[1]), (bottom[0] - r, bottom[1])),
                       _line((top[0] + r, top[1]), (bottom[0] + r, bottom[1]))]
    return base + [_line(top, (bottom[0] - r, bottom[1])), _line(top, (bottom[0] + r, bottom[1]))]  # cone


def _circle(params):
    s = max(0.35, min(1.0, _f(params, "s", 1)))
    r = 95 * s
    c = (W / 2, H / 2)
    rot = math.radians(_f(params, "rot", 20))
    mark = params.get("mark", "none")
    label = params.get("label", "").replace("_", " ")
    edge = lambda deg: (c[0] + r * math.cos(rot + math.radians(deg)), c[1] - r * math.sin(rot + math.radians(deg)))
    body = []
    if mark == "disk":
        body.append('<circle cx="%s" cy="%s" r="%s" stroke="%s" stroke-width="4" fill="%s" fill-opacity=".55"/>' % (
            _n(c[0]), _n(c[1]), _n(r), INK, MARK))
    else:
        body.append('<circle cx="%s" cy="%s" r="%s" stroke="%s" stroke-width="%s" fill="none"/>' % (
            _n(c[0]), _n(c[1]), _n(r), MARK if mark == "circumference" else INK, 6 if mark == "circumference" else 4))
    if mark == "radius":
        body.append(_line(c, edge(0), MARK, 5))
    elif mark == "diameter":
        body.append(_line(edge(180), edge(0), MARK, 5))
    elif mark == "angle":
        a, b = edge(0), edge(70)
        body += [_line(c, a, INK, 4), _line(c, b, INK, 4), _arc(c, a, b, 26, MARK)]
        body.append('<path d="M %s L %s A %s %s 0 0 0 %s Z" stroke="none" fill="%s" fill-opacity=".35"/>' % (
            _pt(c), _pt((c[0] + (a[0] - c[0]) * 26 / r, c[1] + (a[1] - c[1]) * 26 / r)), 26, 26,
            _pt((c[0] + (b[0] - c[0]) * 26 / r, c[1] + (b[1] - c[1]) * 26 / r)), MARK))
    elif mark == "chord":
        body.append(_line(edge(200), edge(320), MARK, 5))
    dot = MARK if mark == "center" else INK
    body.append('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="none"/>' % (_n(c[0]), _n(c[1]), 7 if mark == "center" else 5, dot))
    if label:
        if mark in ("radius", "diameter"):
            nrm = (-math.sin(rot), -math.cos(rot))  # perpendicular to the segment, towards the top
            mid = c if mark == "diameter" else ((c[0] + edge(0)[0]) / 2, (c[1] + edge(0)[1]) / 2)
            body.append(_text((mid[0] + nrm[0] * 22, mid[1] + nrm[1] * 22), label, 22, MARK))
        else:
            body.append(_text((c[0], c[1] - 24), label, 22, MARK))
    return body


def _angle(params):
    deg = _f(params, "deg", 90)
    rot = math.radians(_f(params, "rot", 0))
    s = max(0.35, min(1.0, _f(params, "s", 1)))
    length = 150 * s
    # the vertex sits so both rays fit the canvas
    rays = [(math.cos(rot), -math.sin(rot)), (math.cos(rot + math.radians(deg)), -math.sin(rot + math.radians(deg)))]
    pts = [(0, 0)] + [(u[0] * length, u[1] * length) for u in rays]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    v = (W / 2 - (max(xs) + min(xs)) / 2, H / 2 - (max(ys) + min(ys)) / 2)
    a, b = (v[0] + pts[1][0], v[1] + pts[1][1]), (v[0] + pts[2][0], v[1] + pts[2][1])
    body = [_line(v, a), _line(v, b)]
    body.append(_square(v, a, b, 20) if abs(deg - 90) < 0.5 else _arc(v, a, b, 30))
    body.append('<circle cx="%s" cy="%s" r="5" fill="%s" stroke="none"/>' % (_n(v[0]), _n(v[1]), INK))
    return body


def _lines(params):
    kind = params["kind"]
    rot = math.radians(_f(params, "rot", 0))
    s = max(0.35, min(1.0, _f(params, "s", 1)))
    half = 120 * s
    c = (W / 2, H / 2)
    u = (math.cos(rot), -math.sin(rot))
    if kind == "parallel":
        nrm = (-u[1], u[0])
        gap = 34 * s + 12
        body = []
        for side in (-1, 1):
            m = (c[0] + nrm[0] * gap * side, c[1] + nrm[1] * gap * side)
            a, b = (m[0] - u[0] * half, m[1] - u[1] * half), (m[0] + u[0] * half, m[1] + u[1] * half)
            body += [_line(a, b)] + _arrows(a, b, 1, u)
        return body
    deg = 90 if kind == "perpendicular" else _f(params, "deg", 55)
    w = (math.cos(rot + math.radians(deg)), -math.sin(rot + math.radians(deg)))
    body = [_line((c[0] - u[0] * half, c[1] - u[1] * half), (c[0] + u[0] * half, c[1] + u[1] * half)),
            _line((c[0] - w[0] * half * 0.8, c[1] - w[1] * half * 0.8), (c[0] + w[0] * half * 0.8, c[1] + w[1] * half * 0.8))]
    if kind == "perpendicular":
        body.append(_square(c, (c[0] + u[0] * 10, c[1] + u[1] * 10), (c[0] + w[0] * 10, c[1] + w[1] * 10), 18))
    return body


def _open(params):
    screen, _k = _place(_points(params["pts"]), params)
    return [_polyline(screen)]


def _curve(params):
    if params.get("kind") == "closed":
        d = "M 70 130 C 60 50, 170 40, 200 80 C 230 120, 270 110, 255 165 C 240 215, 90 205, 70 130 Z"
        return ['<path d="%s" stroke="%s" stroke-width="4" fill="%s" fill-opacity=".10"/>' % (d, INK, INK)]
    d = "M 50 170 C 90 40, 150 60, 170 130 C 190 200, 250 190, 275 70"
    return ['<path d="%s" stroke="%s" stroke-width="4" fill="none"/>' % (d, INK)]


def _semidisk(params):
    """Half a disc: a closed figure with one curved side (not a polygon)."""
    rot = math.radians(_f(params, "rot", 0))
    r = 110 * max(0.35, min(1.0, _f(params, "s", 1)))
    c, si = math.cos(rot), math.sin(rot)

    def at(x, y):  # turn (screen coordinates) around the canvas centre
        return (W / 2 + x * c + y * si, H / 2 - x * si + y * c)
    return ['<path d="M %s A %s %s 0 0 1 %s Z" stroke="%s" stroke-width="4" fill="%s" fill-opacity=".10"/>' % (
        _pt(at(-r, r / 2)), _n(r), _n(r), _pt(at(r, r / 2)), INK, INK)]


def render(spec):
    """The SVG document for ``spec`` (a standalone, script-free image)."""
    kind, params = parse(spec)
    if kind == "tri":
        body = _polygon(TRIANGLES[params["kind"]], params, "s,a")
    elif kind == "quad":
        pts, default = QUADS[params["kind"]]
        body = _polygon(pts, params, default)
    elif kind in ("regular", "poly"):
        body = _polygon(shape_points(kind, params), params, "none")
    elif kind == "open":
        body = _open(params)
    elif kind == "curve":
        body = _curve(params)
    elif kind == "semidisk":
        body = _semidisk(params)
    elif kind == "circle":
        body = _circle(params)
    elif kind == "angle":
        body = _angle(params)
    elif kind == "lines":
        body = _lines(params)
    elif kind == "solid":
        body = _solid(params)
    else:
        raise ValueError("unknown figure: %s" % kind)
    svg = ('<svg xmlns="%s" viewBox="0 0 %d %d" width="%d" height="%d" stroke-linecap="round" '
           'stroke-linejoin="round">%s</svg>') % (SVG_NS, W, H, W, H, "".join(body))
    if not is_safe(svg):  # never ship a figure that would not pass the item check
        raise ValueError("unsafe figure: %s" % spec)
    return svg


# ----------------------------------------------------------------------------- safety
ALLOWED_TAGS = {"svg", "g", "line", "polyline", "polygon", "path", "circle", "ellipse", "rect", "text"}
ALLOWED_ATTRS = {
    "xmlns", "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
    "points", "d", "fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap",
    "stroke-linejoin", "stroke-opacity", "opacity", "font-size", "font-family", "font-weight", "text-anchor",
    "dominant-baseline", "transform", "role",
}
_VALUE = re.compile(r"^[#\w\s.,\- %]*$")


def is_safe(svg):
    """A figure is a plain drawing: an ``<svg>`` root with a viewBox, drawing elements only
    (no script, foreignObject, image, use, style, animation), no event handler (``on…``), no
    link (``href``) and no ``url(…)``/``javascript:`` in any value."""
    if not svg:
        return True
    if re.search(r"<!(DOCTYPE|ENTITY)|<\?", svg, re.I):
        return False
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return False
    if root.tag != "{%s}svg" % SVG_NS or not root.get("viewBox"):
        return False
    for el in root.iter():
        tag = el.tag.split("}", 1)[-1]
        if not el.tag.startswith("{%s}" % SVG_NS) or tag not in ALLOWED_TAGS:
            return False
        for name, value in el.attrib.items():
            if name not in ALLOWED_ATTRS or not _VALUE.match(value):
                return False
    return True
