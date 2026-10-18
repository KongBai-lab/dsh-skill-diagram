# -*- coding: utf-8 -*-
"""diagram.py — 图 IR 的双渲染器。

同一份 JSON 图描述，两个出口：
  render_svg(spec) -> <svg> 文本（独立交付 / 网页 / 可嵌 PPT 参考）
  render_pptx(spec, deck, x, y, w, h) -> 直接往 Deck 里加原生矢量形状

支持类型: bar / line / flow / timeline / matrix
坐标: SVG 用像素，PPT 用英寸；两者各自按绘图区归一化。
"""
import os
import sys
from xml.sax.saxutils import escape

_REG = os.path.dirname(os.path.abspath(__file__))
if _REG not in sys.path:
    sys.path.insert(0, _REG)
import pptx_builder as pb  # noqa: E402

THEME = {
    "accent": "1F4E79",
    "accent2": "C00000",
    "text": "333333",
    "grid": "BFBFBF",
    "light": "EAF0F6",
    "font": "Microsoft YaHei, PingFang SC, sans-serif",
}


def _e(s):
    return escape(str(s))


def _hex(c):
    return c if c.startswith("#") else "#" + c


# ======================= SVG =======================

def render_svg(spec, width=960, height=540, theme=None):
    t = dict(THEME)
    if theme:
        t.update(theme)
    kind = spec.get("type")
    body = {
        "bar": _svg_bar,
        "line": _svg_line,
        "flow": _svg_flow,
        "timeline": _svg_timeline,
        "matrix": _svg_matrix,
    }.get(kind)
    if body is None:
        raise ValueError("不支持的图类型: %r（支持 bar/line/flow/timeline/matrix）" % kind)
    parts = body(spec, width, height, t)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="%s">'
        '<rect width="100%%" height="100%%" fill="#FFFFFF"/>%s</svg>'
        % (width, height, width, height, t["font"], "".join(parts))
    )


def _title_svg(spec, W, t):
    if spec.get("title"):
        return '<text x="%d" y="34" font-size="22" font-weight="bold" fill="%s" text-anchor="middle">%s</text>' % (
            W // 2, _hex(t["text"]), _e(spec["title"]))
    return ""


def _svg_bar(spec, W, H, t):
    cats, series = spec["categories"], spec["series"]
    pl, pr, pt, pb = 80, 40, 70, 70
    pw, ph = W - pl - pr, H - pt - pb
    maxv = max(max(s["values"]) for s in series) or 1
    n, ns = len(cats), len(series)
    slot = pw / n
    gw, bw = slot * 0.72, slot * 0.72 / ns
    out = [_title_svg(spec, W, t)]
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (pl, pt, pl, pt + ph, _hex(t["grid"])))
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (pl, pt + ph, pl + pw, pt + ph, _hex(t["grid"])))
    for si, s in enumerate(series):
        color = s.get("color") or (t["accent"] if si == 0 else t["accent2"])
        for i, v in enumerate(s["values"]):
            bh = v / maxv * ph
            x = pl + slot * i + (slot - gw) / 2 + bw * si
            y = pt + ph - bh
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                       % (x, y, bw * 0.92, bh, _hex(color)))
            out.append('<text x="%.1f" y="%.1f" font-size="13" fill="%s" text-anchor="middle">%s</text>'
                       % (x + bw * 0.46, y - 7, _hex(t["text"]), _e(v)))
    for i, c in enumerate(cats):
        x = pl + slot * i + slot / 2
        out.append('<text x="%.1f" y="%d" font-size="15" fill="%s" text-anchor="middle">%s</text>'
                   % (x, pt + ph + 28, _hex(t["text"]), _e(c)))
    return out


def _svg_line(spec, W, H, t):
    cats, series = spec["categories"], spec["series"]
    pl, pr, pt, pb = 80, 40, 70, 70
    pw, ph = W - pl - pr, H - pt - pb
    maxv = max(max(s["values"]) for s in series) or 1
    n = len(cats)
    step = pw / max(n - 1, 1)
    out = [_title_svg(spec, W, t)]
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (pl, pt + ph, pl + pw, pt + ph, _hex(t["grid"])))
    for si, s in enumerate(series):
        color = s.get("color") or (t["accent"] if si == 0 else t["accent2"])
        pts = []
        for i, v in enumerate(s["values"]):
            x = pl + step * i
            y = pt + ph - v / maxv * ph
            pts.append((x, y))
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.5"/>'
                   % (" ".join("%.1f,%.1f" % p for p in pts), _hex(color)))
        for x, y in pts:
            out.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s"/>' % (x, y, _hex(color)))
    for i, c in enumerate(cats):
        out.append('<text x="%.1f" y="%d" font-size="15" fill="%s" text-anchor="middle">%s</text>'
                   % (pl + step * i, pt + ph + 30, _hex(t["text"]), _e(c)))
    return out


def _svg_flow(spec, W, H, t):
    nodes = spec["nodes"]
    edges = spec.get("edges", [])
    n = len(nodes)
    out = [_title_svg(spec, W, t)]
    bw, bh = 200, 64
    gap = (H - 120 - n * bh) / max(n - 1, 1) if n > 1 else 0
    pos = {}
    for i, nd in enumerate(nodes):
        cx = W / 2
        cy = 90 + i * (bh + gap) + bh / 2
        pos[nd["id"]] = (cx, cy)
        kind = nd.get("kind", "rect")
        if kind == "diamond":
            w2, h2 = bw * 0.55, bh * 0.85
            out.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" stroke="%s"/>'
                       % (cx, cy - h2 / 2, cx + w2 / 2, cy, cx, cy + h2 / 2, cx - w2 / 2, cy,
                          _hex(t["light"]), _hex(t["accent"])))
        else:
            out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="8" fill="%s" stroke="%s"/>'
                       % (cx - bw / 2, cy - bh / 2, bw, bh, _hex(t["light"]), _hex(t["accent"])))
        out.append('<text x="%.1f" y="%.1f" font-size="16" fill="%s" text-anchor="middle" dominant-baseline="middle">%s</text>'
                   % (cx, cy, _hex(t["text"]), _e(nd["text"])))
    for a, b in edges:
        if a not in pos or b not in pos:
            continue
        (x1, y1), (x2, y2) = pos[a], pos[b]
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2" marker-end="url(#arrow)"/>'
                   % (x1, y1 + bh / 2, x2, y2 - bh / 2, _hex(t["grid"])))
    return ["<defs><marker id=\"arrow\" markerWidth=\"10\" markerHeight=\"10\" refX=\"9\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L9,3 L0,6 z\" fill=\"%s\"/></marker></defs>" % _hex(t["grid"])] + out


def _svg_timeline(spec, W, H, t):
    ev = spec["events"]
    out = [_title_svg(spec, W, t)]
    pl, pr = 70, 70
    pw = W - pl - pr
    y0 = H / 2
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3"/>'
               % (pl, y0, pl + pw, y0, _hex(t["accent"])))
    step = pw / max(len(ev) - 1, 1)
    for i, e in enumerate(ev):
        x = pl + step * i
        out.append('<circle cx="%.1f" cy="%.1f" r="7" fill="%s"/>' % (x, y0, _hex(t["accent"])))
        up = i % 2 == 0
        ty = y0 - 42 if up else y0 + 58
        out.append('<text x="%.1f" y="%.1f" font-size="14" font-weight="bold" fill="%s" text-anchor="middle">%s</text>'
                   % (x, ty, _hex(t["accent2"]), _e(e["date"])))
        out.append('<text x="%.1f" y="%.1f" font-size="14" fill="%s" text-anchor="middle">%s</text>'
                   % (x, ty + 22, _hex(t["text"]), _e(e["text"])))
    return out


def _svg_matrix(spec, W, H, t):
    cols, rows, cells = spec["columns"], spec["rows"], spec["cells"]
    out = [_title_svg(spec, W, t)]
    pl, pt, cw, ch = 150, 80, (W - 190) / len(cols), 52
    for j, c in enumerate(cols):
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s"/>'
                   % (pl + cw * j, pt, cw, ch, _hex(t["accent"])))
        out.append('<text x="%.1f" y="%.1f" font-size="16" fill="#FFFFFF" font-weight="bold" text-anchor="middle" dominant-baseline="middle">%s</text>'
                   % (pl + cw * j + cw / 2, pt + ch / 2, _e(c)))
    for i, r in enumerate(rows):
        ry = pt + ch + i * ch
        out.append('<text x="%.1f" y="%.1f" font-size="15" fill="%s" text-anchor="end" dominant-baseline="middle">%s</text>'
                   % (pl - 14, ry + ch / 2, _hex(t["text"]), _e(r)))
        for j in range(len(cols)):
            v = cells[i][j] if i < len(cells) and j < len(cells[i]) else ""
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" fill="%s" stroke="%s"/>'
                       % (pl + cw * j, ry, cw, ch, _hex(t["light"]), _hex(t["grid"])))
            out.append('<text x="%.1f" y="%.1f" font-size="15" fill="%s" text-anchor="middle" dominant-baseline="middle">%s</text>'
                       % (pl + cw * j + cw / 2, ry + ch / 2, _hex(t["text"]), _e(v)))
    return out


# ======================= PPTX 原生形状 =======================

def render_pptx(spec, deck, x, y, w, h, theme=None, draw_title=True):
    t = dict(THEME)
    if theme:
        t.update(theme)
    kind = spec.get("type")
    fn = {
        "bar": _pptx_bar,
        "line": _pptx_line,
        "flow": _pptx_flow,
        "timeline": _pptx_timeline,
        "matrix": _pptx_matrix,
    }.get(kind)
    if fn is None:
        raise ValueError("不支持的图类型: %r" % kind)
    if draw_title and spec.get("title"):
        deck.textbox(x, y, w, 0.5, spec["title"], size=17, bold=True,
                     color=t["text"], align="c", valign="c")
        y += 0.55
        h -= 0.55
    fn(spec, deck, x, y, w, h, t)


def _pptx_bar(spec, d, x, y, w, h, t):
    cats, series = spec["categories"], spec["series"]
    pl, pr, pt, pb = 0.7, 0.3, 0.15, 0.55
    pw, ph = w - pl - pr, h - pt - pb
    maxv = max(max(s["values"]) for s in series) or 1
    n, ns = len(cats), len(series)
    slot, gw = pw / n, pw / n * 0.72
    bw = gw / ns
    d.line(x + pl, y + pt, x + pl, y + pt + ph, color=t["grid"])
    d.line(x + pl, y + pt + ph, x + pl + pw, y + pt + ph, color=t["grid"])
    for si, s in enumerate(series):
        color = s.get("color") or (t["accent"] if si == 0 else t["accent2"])
        for i, v in enumerate(s["values"]):
            bh = v / maxv * ph
            bx = x + pl + slot * i + (slot - gw) / 2 + bw * si
            by = y + pt + ph - bh
            d.rect(bx, by, bw * 0.92, bh, fill=color, line=None)
            d.textbox(bx - 0.1, by - 0.34, bw + 0.2, 0.3, str(v), size=11,
                      color=t["text"], align="c")
    for i, c in enumerate(cats):
        cx = x + pl + slot * i + slot / 2
        d.textbox(cx - 0.6, y + pt + ph + 0.08, 1.2, 0.35, c, size=12,
                  color=t["text"], align="c")


def _pptx_line(spec, d, x, y, w, h, t):
    cats, series = spec["categories"], spec["series"]
    pl, pr, pt, pb = 0.7, 0.3, 0.15, 0.55
    pw, ph = w - pl - pr, h - pt - pb
    maxv = max(max(s["values"]) for s in series) or 1
    n = len(cats)
    step = pw / max(n - 1, 1)
    d.line(x + pl, y + pt + ph, x + pl + pw, y + pt + ph, color=t["grid"])
    for si, s in enumerate(series):
        color = s.get("color") or (t["accent"] if si == 0 else t["accent2"])
        pts = [(x + pl + step * i, y + pt + ph - v / maxv * ph) for i, v in enumerate(s["values"])]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            d.line(x1, y1, x2, y2, color=color, width_pt=2.5)
        for px, py in pts:
            d.shape("ellipse", px - 0.06, py - 0.06, 0.12, 0.12, fill=color)
    for i, c in enumerate(cats):
        d.textbox(x + pl + step * i - 0.6, y + pt + ph + 0.08, 1.2, 0.35, c,
                  size=12, color=t["text"], align="c")


def _pptx_flow(spec, d, x, y, w, h, t):
    nodes, edges = spec["nodes"], spec.get("edges", [])
    n = len(nodes)
    bw, bh = min(2.1, w * 0.42), 0.62
    gap = (h - n * bh) / max(n - 1, 1) if n > 1 else 0
    pos = {}
    cx = x + w / 2
    for i, nd in enumerate(nodes):
        cy = y + i * (bh + gap) + bh / 2
        pos[nd["id"]] = (cx, cy)
        kind = "diamond" if nd.get("kind") == "diamond" else "roundRect"
        d.shape(kind, cx - bw / 2, cy - bh / 2, bw, bh,
                fill=t["light"], line=t["accent"], line_w=1.5,
                text=nd["text"], size=13, color=t["text"], align="c", valign="c")
    for a, b in edges:
        if a not in pos or b not in pos:
            continue
        (x1, y1), (x2, y2) = pos[a], pos[b]
        d.line(x1, y1 + bh / 2, x2, y2 - bh / 2, color=t["grid"],
               width_pt=1.6, arrow=True)


def _pptx_timeline(spec, d, x, y, w, h, t):
    ev = spec["events"]
    pl, pr = 0.6, 0.6
    pw = w - pl - pr
    y0 = y + h / 2
    d.line(x + pl, y0, x + pl + pw, y0, color=t["accent"], width_pt=3)
    step = pw / max(len(ev) - 1, 1)
    for i, e in enumerate(ev):
        px = x + pl + step * i
        d.shape("ellipse", px - 0.09, y0 - 0.09, 0.18, 0.18, fill=t["accent"])
        up = i % 2 == 0
        ty = y0 - 0.95 if up else y0 + 0.2
        d.textbox(px - 0.85, ty, 1.7, 0.32, e["date"], size=12, bold=True,
                  color=t["accent2"], align="c")
        d.textbox(px - 0.85, ty + 0.34, 1.7, 0.4, e["text"], size=12,
                  color=t["text"], align="c")


def _pptx_matrix(spec, d, x, y, w, h, t):
    cols, rows, cells = spec["columns"], spec["rows"], spec["cells"]
    pl = 1.5
    pt, ch = 0.1, 0.5
    cw = (w - pl - 0.1) / len(cols)
    for j, c in enumerate(cols):
        d.rect(x + pl + cw * j, y + pt, cw, ch, fill=t["accent"], line=None,
               text=c, size=13, bold=True, color="FFFFFF", align="c", valign="c")
    for i, r in enumerate(rows):
        ry = y + pt + ch + i * ch
        d.textbox(x, ry, pl - 0.1, ch, r, size=12, color=t["text"],
                  align="r", valign="c")
        for j in range(len(cols)):
            v = cells[i][j] if i < len(cells) and j < len(cells[i]) else ""
            d.rect(x + pl + cw * j, ry, cw, ch, fill=t["light"], line=t["grid"],
                   line_w=0.75, text=v, size=12, color=t["text"],
                   align="c", valign="c")


# ======================= 自测 =======================

DEMOS = {
    "bar": {
        "type": "bar", "title": "季度营收（万元）",
        "categories": ["Q1", "Q2", "Q3", "Q4"],
        "series": [{"name": "2024", "values": [12, 18, 15, 24]}],
    },
    "line": {
        "type": "line", "title": "月活趋势",
        "categories": ["1月", "2月", "3月", "4月", "5月", "6月"],
        "series": [{"name": "2024", "values": [30, 42, 38, 55, 61, 72]}],
    },
    "flow": {
        "type": "flow", "title": "数据链路",
        "nodes": [
            {"id": "a", "text": "数据采集"},
            {"id": "b", "text": "清洗入库"},
            {"id": "c", "text": "指标计算", "kind": "diamond"},
            {"id": "d", "text": "看板展示"},
        ],
        "edges": [("a", "b"), ("b", "c"), ("c", "d")],
    },
    "timeline": {
        "type": "timeline", "title": "项目里程碑",
        "events": [
            {"date": "2024 Q1", "text": "立项"},
            {"date": "2024 Q2", "text": "原型"},
            {"date": "2024 Q3", "text": "内测"},
            {"date": "2024 Q4", "text": "上线"},
        ],
    },
    "matrix": {
        "type": "matrix", "title": "方案对比",
        "columns": ["方案 A", "方案 B"],
        "rows": ["成本", "交付速度", "可维护性"],
        "cells": [["高", "低"], ["慢", "快"], ["中", "高"]],
    },
}

OUT = os.environ.get("DIAGRAM_OUT") or os.path.join(os.getcwd(), "diagram-out")


def _selftest():
    os.makedirs(OUT, exist_ok=True)
    for name, spec in DEMOS.items():
        svg = render_svg(spec)
        with open(os.path.join(OUT, "_diagram_%s.svg" % name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("svg:", name, len(svg), "bytes")
    d = pb.Deck(accent="1F4E79", accent2="C00000")
    for name in ("bar", "line", "flow", "timeline", "matrix"):
        d.add_slide()
        d.textbox(0.7, 0.35, 11.9, 0.7, DEMOS[name]["title"], size=24, bold=True,
                  color="1F4E79")
        d.line(0.7, 1.1, 12.6, 1.1, color="C00000", width_pt=2)
        render_pptx(DEMOS[name], d, 0.8, 1.35, 11.7, 5.5, draw_title=False)
    out = os.path.join(OUT, "_diagrams.pptx")
    d.save(out)
    print("pptx:", out)


def main(argv=None):
    """CLI: diagram.py --spec spec.json -o out.svg   (或内联 JSON / .pptx 输出)"""
    import argparse
    import json
    ap = argparse.ArgumentParser(description="图 IR -> SVG / PPTX（纯标准库）")
    ap.add_argument("--spec", help="JSON 文件路径，或内联 JSON 字符串")
    ap.add_argument("-o", "--out", help="输出路径（.svg 或 .pptx）")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    ap.add_argument("--demo", action="store_true", help="跑内置自测")
    args, _unknown = ap.parse_known_args(argv)
    if args.demo or not args.spec:
        _selftest()
        return None
    if os.path.exists(args.spec):
        with open(args.spec, encoding="utf-8") as f:
            spec = json.load(f)
    else:
        spec = json.loads(args.spec)
    out = args.out or os.path.join(OUT, "_diagram.svg")
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    if out.lower().endswith(".pptx"):
        d = pb.Deck()
        d.add_slide()
        render_pptx(spec, d, 0.8, 1.0, 11.7, 5.6)
        d.save(out)
    else:
        svg = render_svg(spec, args.width, args.height)
        with open(out, "w", encoding="utf-8") as f:
            f.write(svg)
    print("saved", out)
    return out


if __name__ == "__main__":
    main()
