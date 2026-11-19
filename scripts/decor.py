# -*- coding: utf-8 -*-
"""decor.py — 程序化矢量插画（几何 / 扁平风）。

不是 AI 绘画，是用矩形、圆、三角、折线拼出的装饰图：
  * cover   封面横幅（渐变底 + 标题 + 几何点缀）
  * pattern 装饰底纹（点阵 / 斜线 / 圆环 / 网格 / 波浪）
  * icon    扁平图标（chart / doc / team / gear / cloud / rocket / check / target / bulb / data）

输出 PNG，复用 raster.Canvas（fontTools 字形 + 扫描线 + zlib）。
"""
import math
import os
import sys

_REG = os.path.dirname(os.path.abspath(__file__))
if _REG not in sys.path:
    sys.path.insert(0, _REG)
import raster  # noqa: E402

OUT = os.environ.get("DIAGRAM_OUT") or os.path.join(os.getcwd(), "diagram-out")


def _rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _lift(col, amount):
    return tuple(min(255, int(v + (255 - v) * amount)) for v in col)


def _rect(c, x, y, w, h, color):
    c.rect(x, y, x + w, y + h, color)


def _ellipse(c, cx, cy, rx, ry, color, sides=36):
    pts = [(cx + rx * math.cos(2 * math.pi * i / sides),
            cy + ry * math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    c.polygon(pts, color)


def _gradient(c, W, H, c1, c2, vertical=True):
    n = H if vertical else W
    for i in range(n):
        f = i / max(n - 1, 1)
        col = tuple(int(c1[k] + (c2[k] - c1[k]) * f) for k in range(3))
        if vertical:
            c.rect(0, i, W, i + 1, col)
        else:
            c.rect(i, 0, i + 1, H, col)


# ======================= 图标 =======================

def _ic_chart(c, cx, cy, s, col):
    bw, gap = s * 0.16, s * 0.09
    base = cy + s * 0.36
    hs = [s * 0.32, s * 0.52, s * 0.72]
    x0 = cx - (3 * bw + 2 * gap) / 2
    for i, h in enumerate(hs):
        x = x0 + i * (bw + gap)
        _rect(c, x, base - h, bw, h, col)
    _rect(c, cx - s * 0.48, base, s * 0.96, s * 0.035, col)


def _ic_doc(c, cx, cy, s, col):
    w, h = s * 0.58, s * 0.74
    x, y = cx - w / 2, cy - h / 2
    _rect(c, x, y, w, h, col)
    fold = s * 0.17
    c.polygon([(x + w - fold, y), (x + w, y), (x + w, y + fold)], (255, 255, 255))
    for i in range(3):
        yy = y + h * 0.42 + i * s * 0.13
        _rect(c, x + s * 0.1, yy, w - s * 0.2, s * 0.03, (255, 255, 255))


def _ic_team(c, cx, cy, s, col):
    r = s * 0.13
    for dx in (-0.21, 0.21):
        _ellipse(c, cx + dx * s, cy - s * 0.14, r, r, col)
        _ellipse(c, cx + dx * s, cy + s * 0.14, r * 1.5, r * 1.15, col)


def _ic_gear(c, cx, cy, s, col):
    teeth = 8
    r_out, r_in = s * 0.44, s * 0.3
    pts = []
    for i in range(teeth * 2):
        a = 2 * math.pi * i / (teeth * 2)
        r = r_out if i % 2 == 0 else r_in * 1.12
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    c.polygon(pts, col)
    _ellipse(c, cx, cy, s * 0.15, s * 0.15, (255, 255, 255))


def _ic_cloud(c, cx, cy, s, col):
    for dx, dy, r in [(-0.2, 0.02, 0.15), (0.0, 0.1, 0.19), (0.2, 0.02, 0.15), (0.0, -0.06, 0.15)]:
        _ellipse(c, cx + dx * s, cy + dy * s, r * s, r * s, col)
    _rect(c, cx - s * 0.35, cy - s * 0.02, s * 0.7, s * 0.2, col)


def _ic_rocket(c, cx, cy, s, col):
    _rect(c, cx - s * 0.07, cy - s * 0.24, s * 0.14, s * 0.44, col)
    c.polygon([(cx, cy - s * 0.44), (cx - s * 0.07, cy - s * 0.24),
               (cx + s * 0.07, cy - s * 0.24)], col)
    c.polygon([(cx - s * 0.07, cy + s * 0.04), (cx - s * 0.23, cy + s * 0.3),
               (cx - s * 0.07, cy + s * 0.3)], col)
    c.polygon([(cx + s * 0.07, cy + s * 0.04), (cx + s * 0.23, cy + s * 0.3),
               (cx + s * 0.07, cy + s * 0.3)], col)
    _ellipse(c, cx, cy + s * 0.22, s * 0.06, s * 0.06, _lift(col, 0.55))


def _ic_check(c, cx, cy, s, col):
    c.line(cx - s * 0.36, cy + s * 0.02, cx - s * 0.06, cy + s * 0.3,
           col, width=s * 0.13)
    c.line(cx - s * 0.06, cy + s * 0.3, cx + s * 0.4, cy - s * 0.3,
           col, width=s * 0.13)


def _ic_target(c, cx, cy, s, col):
    _ellipse(c, cx, cy, s * 0.44, s * 0.44, col)
    _ellipse(c, cx, cy, s * 0.3, s * 0.3, (255, 255, 255))
    _ellipse(c, cx, cy, s * 0.16, s * 0.16, col)


def _ic_bulb(c, cx, cy, s, col):
    _ellipse(c, cx, cy - s * 0.08, s * 0.26, s * 0.26, col)
    _rect(c, cx - s * 0.13, cy + s * 0.14, s * 0.26, s * 0.16, col)
    for i in range(3):
        yy = cy + s * 0.33 + i * s * 0.07
        _rect(c, cx - s * 0.11, yy, s * 0.22, s * 0.03, col)


def _ic_data(c, cx, cy, s, col):
    pts = [(cx - s * 0.4, cy + s * 0.25), (cx - s * 0.15, cy - s * 0.05),
           (cx + s * 0.12, cy + s * 0.1), (cx + s * 0.4, cy - s * 0.3)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        c.line(x1, y1, x2, y2, col, width=s * 0.09)
    for x, y in pts:
        _ellipse(c, x, y, s * 0.07, s * 0.07, col)


_ICONS = {
    "chart": _ic_chart, "doc": _ic_doc, "team": _ic_team, "gear": _ic_gear,
    "cloud": _ic_cloud, "rocket": _ic_rocket, "check": _ic_check,
    "target": _ic_target, "bulb": _ic_bulb, "data": _ic_data,
}


# ======================= 三种装饰 =======================

def _cover(spec, c, W, H, pal):
    _gradient(c, W, H, pal[0], pal[-1])
    _ellipse(c, W * 0.86, H * 0.2, H * 0.26, H * 0.26, _lift(pal[0], 0.16))
    _ellipse(c, W * 0.08, H * 0.9, H * 0.3, H * 0.3, _lift(pal[0], 0.1))
    _ellipse(c, W * 0.72, H * 0.82, H * 0.08, H * 0.08, _lift(pal[0], 0.4))
    c.line(W * 0.12, H * 0.63, W * 0.32, H * 0.63, (255, 255, 255), 3)
    if spec.get("title"):
        c.text(spec["title"], W / 2, H * 0.46, min(68, W / max(len(spec["title"]), 1) * 1.5),
               (255, 255, 255), font=raster.FONT_BOLD, align="center")
    if spec.get("subtitle"):
        c.text(spec["subtitle"], W / 2, H * 0.57, 30, _lift(pal[0], 0.75), align="center")


def _pattern(spec, c, W, H, pal):
    style = spec.get("pattern", "dots")
    col = pal[0]
    if style == "dots":
        step = 38
        for y in range(18, H, step):
            for x in range(18, W, step):
                _ellipse(c, x, y, 3, 3, col)
    elif style == "lines":
        for x in range(-H, W, 34):
            c.line(x, H, x + H, 0, _lift(col, 0.55), 2)
    elif style == "rings":
        for r in range(20, max(W, H), 46):
            _ellipse(c, W / 2, H / 2, r, r, _lift(col, 0.6), sides=64)
    elif style == "grid":
        for x in range(0, W, 48):
            c.line(x, 0, x, H, _lift(col, 0.7), 1)
        for y in range(0, H, 48):
            c.line(0, y, W, y, _lift(col, 0.7), 1)
    elif style == "waves":
        for row in range(5):
            base_y = H * (0.2 + row * 0.15)
            pts = [(x, base_y + math.sin(x / 70.0 + row) * 16) for x in range(0, W + 8, 8)]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                c.line(x1, y1, x2, y2, _lift(col, 0.35 + row * 0.1), 3)
    else:
        raise ValueError("不支持的 pattern: %r" % style)


def _icon(spec, c, W, H, pal):
    name = spec.get("icon", "chart")
    if name not in _ICONS:
        raise ValueError("不支持的图标: %r（可选 %s）" % (name, "/".join(_ICONS)))
    cx = W / 2
    cy = H / 2 - (H * 0.08 if spec.get("label") else 0)
    size = min(W, H) * 0.34
    _ICONS[name](c, cx, cy, size, pal[0])
    if spec.get("label"):
        c.text(spec["label"], W / 2, H * 0.8, 32, pal[0],
               font=raster.FONT_BOLD, align="center")


def render_png(spec, width=960, height=540, theme=None):
    c = raster.Canvas(width, height, bg=(255, 255, 255), ss=2)
    palette = [_rgb(p) for p in spec.get("palette", ["1F4E79", "5B9BD5"])]
    kind = spec.get("kind", "cover")
    if kind == "cover":
        _cover(spec, c, width, height, palette)
    elif kind == "pattern":
        _pattern(spec, c, width, height, palette)
    elif kind == "icon":
        _icon(spec, c, width, height, palette)
    else:
        raise ValueError("不支持的 decor kind: %r（cover/pattern/icon）" % kind)
    return c


DEMOS = {
    "cover": {"type": "decor", "kind": "cover", "title": "2025 年度报告",
              "subtitle": "数据驱动决策", "palette": ["13294B", "3C7DBF"]},
    "cover_light": {"type": "decor", "kind": "cover", "title": "产品发布会",
                    "subtitle": "Reimagine the workflow", "palette": ["2D6A4F", "95D5B2"]},
    "pattern_dots": {"type": "decor", "kind": "pattern", "pattern": "dots"},
    "pattern_rings": {"type": "decor", "kind": "pattern", "pattern": "rings"},
    "pattern_waves": {"type": "decor", "kind": "pattern", "pattern": "waves"},
    "icon_chart": {"type": "decor", "kind": "icon", "icon": "chart", "label": "数据洞察"},
    "icon_team": {"type": "decor", "kind": "icon", "icon": "team", "label": "团队协作"},
    "icon_rocket": {"type": "decor", "kind": "icon", "icon": "rocket", "label": "快速上线"},
}


def main(argv=None):
    import argparse
    import json
    ap = argparse.ArgumentParser(description="程序化矢量插画 -> PNG")
    ap.add_argument("--spec")
    ap.add_argument("-o", "--out")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    ap.add_argument("--demo", action="store_true")
    args, _ = ap.parse_known_args(argv)
    if args.demo or not args.spec:
        os.makedirs(OUT, exist_ok=True)
        for name, spec in DEMOS.items():
            p = os.path.join(OUT, "_decor_%s.png" % name)
            render_png(spec).png(p)
            print("decor:", name, os.path.getsize(p), "bytes")
        return None
    spec = json.load(open(args.spec, encoding="utf-8")) if os.path.exists(args.spec) else json.loads(args.spec)
    out = args.out or os.path.join(OUT, "_decor.png")
    render_png(spec, args.width, args.height).png(out)
    print("saved", out, os.path.getsize(out), "bytes")
    return out


if __name__ == "__main__":
    main()
