# -*- coding: utf-8 -*-
"""diagram_png.py — 图 IR 的 PNG 出口（纯 Python 光栅化，不依赖 Pillow）。

与 diagram.py 的 SVG 出口共用同一份 JSON；本模块把图元直接画到 raster.Canvas。
"""
import math
import os
import sys

_REG = os.path.dirname(os.path.abspath(__file__))
if _REG not in sys.path:
    sys.path.insert(0, _REG)
import raster  # noqa: E402
from diagram import THEME  # noqa: E402

OUT = os.environ.get("DIAGRAM_OUT") or os.path.join(os.getcwd(), "diagram-out")


def _rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rect(c, x, y, w, h, color):
    c.rect(x, y, x + w, y + h, color)


def _outline(c, x, y, w, h, color, width=1.5):
    c.line(x, y, x + w, y, color, width)
    c.line(x + w, y, x + w, y + h, color, width)
    c.line(x + w, y + h, x, y + h, color, width)
    c.line(x, y + h, x, y, color, width)


def _circle(c, cx, cy, r, color, sides=24):
    import math
    pts = [(cx + r * math.cos(2 * math.pi * i / sides),
            cy + r * math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    c.polygon(pts, color)


def _arrow_head(c, x, y, direction, color, size=9):
    """direction: 'down' 或 'up'"""
    if direction == "down":
        c.polygon([(x, y), (x - size * 0.55, y - size), (x + size * 0.55, y - size)], color)
    else:
        c.polygon([(x, y), (x - size * 0.55, y + size), (x + size * 0.55, y + size)], color)


def _title(spec, c, W, t):
    if spec.get("title"):
        c.text(spec["title"], W // 2, 34, 22, _rgb(t["text"]), font=raster.FONT_BOLD, align="center")


def render_png(spec, width=960, height=540, theme=None):
    t = dict(THEME)
    t.update(theme or {})
    c = raster.Canvas(width, height, bg=(255, 255, 255), ss=2)
    if spec.get("type") == "decor":
        import decor
        return decor.render_png(spec, width, height, theme)
    fn = {"bar": _png_bar, "line": _png_line, "flow": _png_flow,
          "timeline": _png_timeline, "matrix": _png_matrix,
          "scatter": _png_scatter, "pie": _png_pie, "donut": _png_donut,
          "area": _png_area, "radar": _png_radar, "hbar": _png_hbar,
          "heatmap": _png_heatmap, "funnel": _png_funnel,
          "waterfall": _png_waterfall, "gantt": _png_gantt}.get(spec.get("type"))
    if fn is None:
        raise ValueError("不支持的图类型: %r" % spec.get("type"))
    fn(spec, c, width, height, t)
    return c


def render_png_file(spec, path, width=960, height=540, theme=None):
    render_png(spec, width, height, theme).png(path)
    return path


def _png_bar(spec, c, W, H, t):
    cats, series = spec["categories"], spec["series"]
    pl, pr, pt, pb = 80, 40, 70, 70
    pw, ph = W - pl - pr, H - pt - pb
    maxv = max(max(s["values"]) for s in series) or 1
    n, ns = len(cats), len(series)
    slot = pw / n
    gw = slot * 0.72
    bw = gw / ns
    _title(spec, c, W, t)
    c.line(pl, pt, pl, pt + ph, _rgb(t["grid"]), 1)
    c.line(pl, pt + ph, pl + pw, pt + ph, _rgb(t["grid"]), 1)
    for si, s in enumerate(series):
        color = _rgb(s.get("color") or (t["accent"] if si == 0 else t["accent2"]))
        for i, v in enumerate(s["values"]):
            bh = v / maxv * ph
            x = pl + slot * i + (slot - gw) / 2 + bw * si
            y = pt + ph - bh
            _rect(c, x, y, bw * 0.92, bh, color)
            c.text(str(v), x + bw * 0.46, y - 7, 13, _rgb(t["text"]), align="center")
    for i, cat in enumerate(cats):
        c.text(cat, pl + slot * i + slot / 2, pt + ph + 28, 15, _rgb(t["text"]), align="center")


def _png_line(spec, c, W, H, t):
    cats, series = spec["categories"], spec["series"]
    pl, pr, pt, pb = 80, 40, 70, 70
    pw, ph = W - pl - pr, H - pt - pb
    maxv = max(max(s["values"]) for s in series) or 1
    n = len(cats)
    step = pw / max(n - 1, 1)
    _title(spec, c, W, t)
    c.line(pl, pt + ph, pl + pw, pt + ph, _rgb(t["grid"]), 1)
    for si, s in enumerate(series):
        color = _rgb(s.get("color") or (t["accent"] if si == 0 else t["accent2"]))
        pts = [(pl + step * i, pt + ph - v / maxv * ph) for i, v in enumerate(s["values"])]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            c.line(x1, y1, x2, y2, color, 2.5)
        for x, y in pts:
            _circle(c, x, y, 4, color)
    for i, cat in enumerate(cats):
        c.text(cat, pl + step * i, pt + ph + 30, 15, _rgb(t["text"]), align="center")


def _png_flow(spec, c, W, H, t):
    nodes, edges = spec["nodes"], spec.get("edges", [])
    n = len(nodes)
    bw, bh = 200, 64
    gap = (H - 120 - n * bh) / max(n - 1, 1) if n > 1 else 0
    pos = {}
    _title(spec, c, W, t)
    for i, nd in enumerate(nodes):
        cx, cy = W / 2, 90 + i * (bh + gap) + bh / 2
        pos[nd["id"]] = (cx, cy)
        if nd.get("kind") == "diamond":
            w2, h2 = bw * 0.55, bh * 0.85
            pts = [(cx, cy - h2 / 2), (cx + w2 / 2, cy), (cx, cy + h2 / 2), (cx - w2 / 2, cy)]
            c.polygon(pts, _rgb(t["light"]))
            for j in range(4):
                x1, y1 = pts[j]
                x2, y2 = pts[(j + 1) % 4]
                c.line(x1, y1, x2, y2, _rgb(t["accent"]), 1.5)
        else:
            _rect(c, cx - bw / 2, cy - bh / 2, bw, bh, _rgb(t["light"]))
            _outline(c, cx - bw / 2, cy - bh / 2, bw, bh, _rgb(t["accent"]), 1.5)
        c.text(nd["text"], cx, cy + 6, 16, _rgb(t["text"]), align="center")
    for a, b in edges:
        if a not in pos or b not in pos:
            continue
        (x1, y1), (x2, y2) = pos[a], pos[b]
        c.line(x1, y1 + bh / 2, x2, y2 - bh / 2 - 9, _rgb(t["grid"]), 2)
        _arrow_head(c, x2, y2 - bh / 2, "down", _rgb(t["grid"]))


def _png_timeline(spec, c, W, H, t):
    ev = spec["events"]
    pl, pr = 70, 70
    pw = W - pl - pr
    y0 = H / 2
    _title(spec, c, W, t)
    c.line(pl, y0, pl + pw, y0, _rgb(t["accent"]), 3)
    step = pw / max(len(ev) - 1, 1)
    for i, e in enumerate(ev):
        x = pl + step * i
        _circle(c, x, y0, 7, _rgb(t["accent"]))
        up = i % 2 == 0
        ty = y0 - 42 if up else y0 + 58
        c.text(e["date"], x, ty, 14, _rgb(t["accent2"]), font=raster.FONT_BOLD, align="center")
        c.text(e["text"], x, ty + 22, 14, _rgb(t["text"]), align="center")


def _png_matrix(spec, c, W, H, t):
    cols, rows, cells = spec["columns"], spec["rows"], spec["cells"]
    pl, pt, cw, ch = 150, 80, (W - 190) / len(cols), 52
    _title(spec, c, W, t)
    for j, col in enumerate(cols):
        _rect(c, pl + cw * j, pt, cw, ch, _rgb(t["accent"]))
        c.text(col, pl + cw * j + cw / 2, pt + ch / 2 + 6, 16, (255, 255, 255),
               font=raster.FONT_BOLD, align="center")
    for i, row in enumerate(rows):
        ry = pt + ch + i * ch
        c.text(row, pl - 14, ry + ch / 2 + 6, 15, _rgb(t["text"]), align="right")
        for j in range(len(cols)):
            v = cells[i][j] if i < len(cells) and j < len(cells[i]) else ""
            _rect(c, pl + cw * j, ry, cw, ch, _rgb(t["light"]))
            _outline(c, pl + cw * j, ry, cw, ch, _rgb(t["grid"]), 1)
            c.text(str(v), pl + cw * j + cw / 2, ry + ch / 2 + 6, 15, _rgb(t["text"]), align="center")


# ==================== 扩展图类型 ====================

_PALETTE = ["1F4E79", "C00000", "5B9BD5", "70AD47", "FFC000", "A5A5A5", "ED7D31", "264478"]


def _png_scatter(spec, c, W, H, t):
    series = spec["series"]
    pl, pr, pt, pb = 90, 40, 70, 70
    pw, ph = W - pl - pr, H - pt - pb
    xs = [p[0] for s in series for p in s["points"]]
    ys = [p[1] for s in series for p in s["points"]]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmax == xmin:
        xmax += 1
    if ymax == ymin:
        ymax += 1
    _title(spec, c, W, t)
    c.line(pl, pt, pl, pt + ph, _rgb(t["grid"]), 1)
    c.line(pl, pt + ph, pl + pw, pt + ph, _rgb(t["grid"]), 1)
    for si, s in enumerate(series):
        color = _rgb(s.get("color") or (t["accent"] if si == 0 else t["accent2"]))
        for xv, yv in s["points"]:
            x = pl + (xv - xmin) / (xmax - xmin) * pw
            y = pt + ph - (yv - ymin) / (ymax - ymin) * ph
            _circle(c, x, y, 5, color)
    c.text(str(xmin), pl, pt + ph + 28, 13, _rgb(t["text"]), align="center")
    c.text(str(xmax), pl + pw, pt + ph + 28, 13, _rgb(t["text"]), align="center")
    c.text(str(ymin), pl - 12, pt + ph, 13, _rgb(t["text"]), align="right")
    c.text(str(ymax), pl - 12, pt, 13, _rgb(t["text"]), align="right")


def _png_pie(spec, c, W, H, t, hole=0.0):
    items = spec["items"]
    total = sum(i["value"] for i in items) or 1
    cx, cy = W / 2, H / 2 + 15
    r = min(W, H) * 0.33
    _title(spec, c, W, t)
    angle = -math.pi / 2
    for i, it in enumerate(items):
        sweep = it["value"] / total * 2 * math.pi
        color = _rgb(it.get("color") or _PALETTE[i % len(_PALETTE)])
        n = max(12, int(sweep / (2 * math.pi) * 90))
        outer = [(cx + r * math.cos(angle + sweep * k / n),
                  cy + r * math.sin(angle + sweep * k / n)) for k in range(n + 1)]
        if hole > 0:
            inner = [(cx + r * hole * math.cos(angle + sweep * (n - k) / n),
                      cy + r * hole * math.sin(angle + sweep * (n - k) / n)) for k in range(n + 1)]
            c.polygon(outer + inner, color)
        else:
            c.polygon([(cx, cy)] + outer, color)
        mid = angle + sweep / 2
        lr = r * (0.65 if hole == 0 else (1 + hole) / 2)
        c.text("%s %d%%" % (it["label"], round(it["value"] / total * 100)),
               cx + lr * math.cos(mid), cy + lr * math.sin(mid) + 5, 13,
               (255, 255, 255), align="center")
        angle += sweep


def _png_donut(spec, c, W, H, t):
    _png_pie(spec, c, W, H, t, hole=0.55)


def _png_area(spec, c, W, H, t):
    cats, series = spec["categories"], spec["series"]
    pl, pr, pt, pb = 80, 40, 70, 70
    pw, ph = W - pl - pr, H - pt - pb
    maxv = max(max(s["values"]) for s in series) or 1
    n = len(cats)
    step = pw / max(n - 1, 1)
    _title(spec, c, W, t)
    c.line(pl, pt + ph, pl + pw, pt + ph, _rgb(t["grid"]), 1)
    for si, s in enumerate(series):
        color = _rgb(s.get("color") or (t["accent"] if si == 0 else t["accent2"]))
        pts = [(pl + step * i, pt + ph - v / maxv * ph) for i, v in enumerate(s["values"])]
        c.polygon([(pl, pt + ph)] + pts + [(pl + pw, pt + ph)], _rgb(t["light"]))
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            c.line(x1, y1, x2, y2, color, 2.5)
    for i, cat in enumerate(cats):
        c.text(cat, pl + step * i, pt + ph + 28, 15, _rgb(t["text"]), align="center")


def _png_radar(spec, c, W, H, t):
    axes, series = spec["axes"], spec["series"]
    n = len(axes)
    cx, cy = W / 2, H / 2 + 20
    r = min(W, H) * 0.32
    _title(spec, c, W, t)

    def pt(k, level):
        a = -math.pi / 2 + 2 * math.pi * k / n
        return (cx + r * level * math.cos(a), cy + r * level * math.sin(a))

    for level in (0.25, 0.5, 0.75, 1.0):
        ring = [pt(k, level) for k in range(n)]
        for j in range(n):
            c.line(ring[j][0], ring[j][1], ring[(j + 1) % n][0], ring[(j + 1) % n][1],
                   _rgb(t["grid"]), 1)
    for k in range(n):
        c.line(cx, cy, pt(k, 1.0)[0], pt(k, 1.0)[1], _rgb(t["grid"]), 1)
        lx, ly = pt(k, 1.16)
        c.text(axes[k], lx, ly + 5, 13, _rgb(t["text"]), align="center")
    for si, s in enumerate(series):
        color = _rgb(s.get("color") or (t["accent"] if si == 0 else t["accent2"]))
        poly = [pt(k, s["values"][k]) for k in range(n)]
        for j in range(n):
            c.line(poly[j][0], poly[j][1], poly[(j + 1) % n][0], poly[(j + 1) % n][1], color, 2)
            _circle(c, poly[j][0], poly[j][1], 3, color)


def _png_hbar(spec, c, W, H, t):
    cats, series = spec["categories"], spec["series"]
    pl, pr, pt, pb = 120, 40, 70, 60
    pw, ph = W - pl - pr, H - pt - pb
    maxv = max(max(s["values"]) for s in series) or 1
    n, ns = len(cats), len(series)
    slot = ph / n
    gw = slot * 0.72
    bh = gw / ns
    _title(spec, c, W, t)
    c.line(pl, pt, pl, pt + ph, _rgb(t["grid"]), 1)
    c.line(pl, pt + ph, pl + pw, pt + ph, _rgb(t["grid"]), 1)
    for si, s in enumerate(series):
        color = _rgb(s.get("color") or (t["accent"] if si == 0 else t["accent2"]))
        for i, v in enumerate(s["values"]):
            bw = v / maxv * pw
            y = pt + slot * i + (slot - gw) / 2 + bh * si
            _rect(c, pl, y, bw, bh * 0.92, color)
            c.text(str(v), pl + bw + 8, y + bh * 0.5 + 5, 13, _rgb(t["text"]))
    for i, cat in enumerate(cats):
        c.text(cat, pl - 12, pt + slot * i + slot / 2 + 5, 14, _rgb(t["text"]), align="right")


def _png_heatmap(spec, c, W, H, t):
    rows, cols, vals = spec["rows"], spec["cols"], spec["values"]
    pl, pt = 130, 90
    cw = (W - pl - 40) / len(cols)
    chh = (H - pt - 50) / len(rows)
    _title(spec, c, W, t)
    flat = [v for r in vals for v in r]
    vmin, vmax = min(flat), max(flat)
    span = (vmax - vmin) or 1
    for j, col in enumerate(cols):
        c.text(col, pl + cw * j + cw / 2, pt - 12, 14, _rgb(t["text"]), align="center")
    for i, r in enumerate(rows):
        c.text(r, pl - 12, pt + chh * i + chh / 2 + 5, 14, _rgb(t["text"]), align="right")
        for j in range(len(cols)):
            v = vals[i][j]
            f = (v - vmin) / span
            color = (int(31 + f * 180), int(78 + f * 40), int(121 + f * 40))
            _rect(c, pl + cw * j, pt + chh * i, cw, chh, color)
            c.text(str(v), pl + cw * j + cw / 2, pt + chh * i + chh / 2 + 5, 13,
                   (255, 255, 255) if f > 0.45 else (30, 30, 30), align="center")


def _png_funnel(spec, c, W, H, t):
    items = spec["items"]
    n = len(items)
    top = 90
    hh = (H - top - 50) / n
    maxv = max(i["value"] for i in items) or 1
    _title(spec, c, W, t)
    for i, it in enumerate(items):
        w = it["value"] / maxv * (W * 0.7)
        next_w = (items[i + 1]["value"] / maxv * (W * 0.7)) if i + 1 < n else w * 0.8
        y = top + i * hh
        cx = W / 2
        c.polygon([(cx - w / 2, y), (cx + w / 2, y),
                   (cx + next_w / 2, y + hh), (cx - next_w / 2, y + hh)],
                  _rgb(_PALETTE[i % len(_PALETTE)]))
        c.text("%s  %d" % (it["label"], it["value"]), cx, y + hh / 2 + 5, 15,
               (255, 255, 255), align="center")


def _png_waterfall(spec, c, W, H, t):
    cats, vals = spec["categories"], spec["values"]
    pl, pr, pt, pb = 80, 40, 80, 70
    pw, ph = W - pl - pr, H - pt - pb
    n = len(vals)
    slot = pw / n
    bw = slot * 0.55
    top_v = max(sum(v for v in vals if v > 0), -sum(v for v in vals if v < 0)) * 1.15 or 1
    _title(spec, c, W, t)
    c.line(pl, pt + ph, pl + pw, pt + ph, _rgb(t["grid"]), 1)
    scale = ph / top_v
    running = 0
    for i, v in enumerate(vals):
        x = pl + slot * i + (slot - bw) / 2
        y0 = pt + ph - running * scale
        y1 = pt + ph - (running + v) * scale
        color = _rgb(t["accent"]) if v >= 0 else _rgb(t["accent2"])
        c.rect(x, min(y0, y1), x + bw, max(y0, y1), color)
        running += v
        c.text(str(v), x + bw / 2, min(y0, y1) - 7, 13, _rgb(t["text"]), align="center")
    for i, cat in enumerate(cats):
        c.text(cat, pl + slot * i + slot / 2, pt + ph + 28, 14, _rgb(t["text"]), align="center")


def _png_gantt(spec, c, W, H, t):
    tasks, periods = spec["tasks"], spec["periods"]
    pl, pr, pt, pb = 150, 40, 80, 60
    pw, ph = W - pl - pr, H - pt - pb
    n = len(tasks)
    slot = ph / n
    bh = slot * 0.55
    _title(spec, c, W, t)
    span = max(tk["end"] for tk in tasks) or 1
    k = len(periods)
    for i, p in enumerate(periods):
        x = pl + pw * i / k
        c.line(x, pt, x, pt + ph, _rgb(t["grid"]), 1)
        c.text(p, x + pw / k / 2, pt - 14, 13, _rgb(t["text"]), align="center")
    for i, task in enumerate(tasks):
        y = pt + slot * i + (slot - bh) / 2
        x0 = pl + pw * task["start"] / span
        x1 = pl + pw * task["end"] / span
        _rect(c, x0, y, x1 - x0, bh, _rgb(_PALETTE[i % len(_PALETTE)]))
        c.text(task["name"], pl - 12, y + bh / 2 + 5, 14, _rgb(t["text"]), align="right")


DEMOS = {
    "bar": {"type": "bar", "title": "季度营收（万元）",
            "categories": ["Q1", "Q2", "Q3", "Q4"],
            "series": [{"name": "2024", "values": [12, 18, 15, 24]}]},
    "line": {"type": "line", "title": "月活趋势",
             "categories": ["1月", "2月", "3月", "4月", "5月", "6月"],
             "series": [{"name": "2024", "values": [30, 42, 38, 55, 61, 72]}]},
    "flow": {"type": "flow", "title": "数据链路",
             "nodes": [{"id": "a", "text": "数据采集"},
                       {"id": "b", "text": "清洗入库"},
                       {"id": "c", "text": "指标计算", "kind": "diamond"},
                       {"id": "d", "text": "看板展示"}],
             "edges": [["a", "b"], ["b", "c"], ["c", "d"]]},
    "timeline": {"type": "timeline", "title": "项目里程碑",
                 "events": [{"date": "2024 Q1", "text": "立项"},
                            {"date": "2024 Q2", "text": "原型"},
                            {"date": "2024 Q3", "text": "内测"},
                            {"date": "2024 Q4", "text": "上线"}]},
    "matrix": {"type": "matrix", "title": "方案对比",
               "columns": ["方案 A", "方案 B"],
               "rows": ["成本", "交付速度", "可维护性"],
               "cells": [["高", "低"], ["慢", "快"], ["中", "高"]]},
    "scatter": {"type": "scatter", "title": "广告投入 vs 销售额",
                "series": [{"name": "门店", "points": [[2, 8], [3, 12], [4, 11], [5, 17],
                                                       [6, 16], [7, 22], [8, 21], [9, 26]]}]},
    "pie": {"type": "pie", "title": "渠道占比",
            "items": [{"label": "线上", "value": 45}, {"label": "门店", "value": 30},
                      {"label": "分销", "value": 25}]},
    "donut": {"type": "donut", "title": "收入结构",
              "items": [{"label": "产品", "value": 55}, {"label": "服务", "value": 25},
                        {"label": "其他", "value": 20}]},
    "area": {"type": "area", "title": "累计用户",
             "categories": ["1月", "2月", "3月", "4月", "5月"],
             "series": [{"name": "2024", "values": [10, 22, 35, 48, 60]}]},
    "radar": {"type": "radar", "title": "能力评估",
              "axes": ["技术", "产品", "运营", "销售", "服务"],
              "series": [{"name": "A", "values": [0.9, 0.7, 0.6, 0.5, 0.8]}]},
    "hbar": {"type": "hbar", "title": "各部门人数",
             "categories": ["研发", "销售", "运营", "客服"],
             "series": [{"values": [42, 28, 15, 9]}]},
    "heatmap": {"type": "heatmap", "title": "月度活跃热力",
                "rows": ["周一", "周三", "周五"],
                "cols": ["上午", "下午", "晚间"],
                "values": [[12, 34, 56], [23, 45, 67], [34, 56, 78]]},
    "funnel": {"type": "funnel", "title": "转化漏斗",
               "items": [{"label": "曝光", "value": 1000}, {"label": "点击", "value": 420},
                         {"label": "加购", "value": 180}, {"label": "下单", "value": 76}]},
    "waterfall": {"type": "waterfall", "title": "利润拆解",
                  "categories": ["收入", "成本", "费用", "税", "净利"],
                  "values": [100, -45, -20, -10, 25]},
    "gantt": {"type": "gantt", "title": "项目排期",
              "periods": ["1月", "2月", "3月", "4月"],
              "tasks": [{"name": "调研", "start": 0, "end": 1},
                        {"name": "设计", "start": 1, "end": 2},
                        {"name": "开发", "start": 2, "end": 4},
                        {"name": "测试", "start": 3.5, "end": 4.5}]},
}


def main(argv=None):
    import argparse
    import json
    ap = argparse.ArgumentParser(description="图 IR -> PNG（纯 Python 光栅化）")
    ap.add_argument("--spec", help="JSON 文件或内联 JSON")
    ap.add_argument("-o", "--out")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    ap.add_argument("--demo", action="store_true")
    args, _ = ap.parse_known_args(argv)
    if args.demo or not args.spec:
        os.makedirs(OUT, exist_ok=True)
        for name, spec in DEMOS.items():
            p = os.path.join(OUT, "_png_%s.png" % name)
            render_png_file(spec, p)
            print("png:", name, os.path.getsize(p), "bytes")
        return None
    spec = json.load(open(args.spec, encoding="utf-8")) if os.path.exists(args.spec) else json.loads(args.spec)
    out = args.out or os.path.join(OUT, "_chart.png")
    render_png_file(spec, out, args.width, args.height)
    print("saved", out, os.path.getsize(out), "bytes")
    return out


if __name__ == "__main__":
    main()
