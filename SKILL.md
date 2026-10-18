---
name: diagram
description: 把结构化 JSON 图描述渲染成 PNG / SVG / PPT 原生矢量形状。数据图 15 种（柱状、折线、散点、饼图、环形、面积、雷达、热力、条形、漏斗、瀑布、甘特、对比矩阵、流程图、时间轴），另有程序化装饰插画（封面横幅、底纹、10 种扁平图标）。纯 Python（标准库 + fontTools）本地光栅化，无需 Pillow / 浏览器 / ImageMagick；模型只写几十 token 的 JSON。
whenToUse: 用户要生成图片、画数据图/图表/示意图/流程图/时间轴/对比矩阵；或要求在 PPT 里放一张图；或说"来个图/画个图/生成图片"且内容不属于照片、插画、复杂视觉画面时。
slug: dsh-skill-diagram
displayName: Diagram — JSON 到图
version: 1.0.0
summary: 用几十 token 的 JSON 描述生成 15 种数据图与装饰插画，输出 PNG/SVG/PPTX，纯 Python 光栅化，仅依赖 fontTools。
license: MIT
tags: [dsh, skill, diagram, chart, png, svg, pptx, python, fonttools, harmonyos, agent]
homepage: https://github.com/KongBai-lab/dsh-skill-diagram
---

# diagram：JSON → PNG / SVG / PPT 原生图

## 铁律（省时间、省 token）

**不要手写 SVG 标签，不要自己编码 PNG，不要逐点算坐标。**
只输出一份 JSON 图描述（通常 40–80 token），渲染交给本目录脚本。
模型产出「结构」，像素由本机光栅化。

## 三个出口（同一份 JSON）

| 出口 | 脚本 | 产物 | 用途 |
|---|---|---|---|
| **PNG** | `scripts/diagram_png.py` | 位图 | 发聊天、插文档、默认选择 |
| SVG | `scripts/diagram.py` | 矢量文本 | 网页、需要无损缩放 |
| PPT 原生形状 | `scripts/diagram.py` | `.pptx` | 进 PPT，PowerPoint 里可改 |

## 依赖与安装

```bash
pip install fonttools          # 唯一第三方依赖
# 需要一个中文字体（如 Noto Sans CJK）；脚本会自动在常见目录里找
```

- 依赖：`fontTools`（取字形轮廓）+ 标准库；**不需要** Pillow / cairo / 浏览器 / ImageMagick
- 字体查找顺序：`$DIAGRAM_FONT_DIR` → `/system/fonts`（HarmonyOS）→ `/usr/share/fonts` → `~/.fonts` → Windows/macOS 字体目录
- 找不到字体时设置：`export DIAGRAM_FONT_DIR=/path/to/fonts`
- 嵌入式环境（如放在自定义目录的 fontTools）：`export DIAGRAM_PYLIBS=/path/to/site-packages`
- 默认输出目录可用 `DIAGRAM_OUT` 覆盖

## 用法

### PNG（默认）

```bash
python scripts/diagram_png.py --spec examples/bar.json -o out.png --width 960 --height 540
```

### SVG / PPTX

```bash
python scripts/diagram.py --spec examples/bar.json -o out.svg
python scripts/diagram.py --spec examples/bar.json -o out.pptx
```

在 Python 里直接调用：

```python
import sys, json
sys.path.insert(0, "scripts")
import diagram_png
diagram_png.render_png(spec_dict, "out.png", width=960, height=540)
```

## 五种图的 JSON schema

### bar（柱状图）
```json
{"type":"bar","title":"季度营收（万元）",
 "categories":["Q1","Q2","Q3","Q4"],
 "series":[{"name":"2024","values":[12,18,15,24]}]}
```
`series` 可多组（分组柱）；可选 `"color":"1F4E79"`。

### line（折线图）
```json
{"type":"line","title":"月活趋势",
 "categories":["1月","2月","3月"],
 "series":[{"name":"2024","values":[30,42,38]}]}
```

### flow（流程图）
```json
{"type":"flow","title":"数据链路",
 "nodes":[{"id":"a","text":"采集"},
          {"id":"b","text":"判断","kind":"diamond"},
          {"id":"c","text":"展示"}],
 "edges":[["a","b"],["b","c"]]}
```
`kind` 省略为矩形，`"diamond"` 为菱形。

### timeline（时间轴）
```json
{"type":"timeline","title":"里程碑",
 "events":[{"date":"2025 Q1","text":"立项"},
           {"date":"2025 Q2","text":"上线"}]}
```

### matrix（对比矩阵）
```json
{"type":"matrix","title":"方案对比",
 "columns":["方案 A","方案 B"],
 "rows":["成本","速度"],
 "cells":[["高","低"],["慢","快"]]}
```

### scatter（散点图）
```json
{"type":"scatter","title":"广告投入 vs 销售额",
 "series":[{"name":"门店","points":[[2,8],[3,12],[5,17]]}]}
```

### pie / donut（饼图 / 环形图）
```json
{"type":"pie","title":"渠道占比",
 "items":[{"label":"线上","value":45},{"label":"门店","value":30},{"label":"分销","value":25}]}
```
`type` 换成 `"donut"` 即环形图。

### area（面积图）
```json
{"type":"area","title":"累计用户",
 "categories":["1月","2月","3月"],
 "series":[{"values":[10,22,35]}]}
```

### radar（雷达图）
```json
{"type":"radar","title":"能力评估",
 "axes":["技术","产品","运营","销售","服务"],
 "series":[{"values":[0.9,0.7,0.6,0.5,0.8]}]}
```

### hbar（条形图，横向）
```json
{"type":"hbar","title":"各部门人数",
 "categories":["研发","销售","运营"],
 "series":[{"values":[42,28,15]}]}
```

### heatmap（热力图）
```json
{"type":"heatmap","title":"月度活跃热力",
 "rows":["周一","周三"],"cols":["上午","下午","晚间"],
 "values":[[12,34,56],[23,45,67]]}
```

### funnel（漏斗图）
```json
{"type":"funnel","title":"转化漏斗",
 "items":[{"label":"曝光","value":1000},{"label":"点击","value":420},{"label":"下单","value":76}]}
```

### waterfall（瀑布图）
```json
{"type":"waterfall","title":"利润拆解",
 "categories":["收入","成本","费用","净利"],
 "values":[100,-45,-20,35]}
```

### gantt（甘特图）
```json
{"type":"gantt","title":"项目排期",
 "periods":["1月","2月","3月","4月"],
 "tasks":[{"name":"调研","start":0,"end":1},{"name":"开发","start":2,"end":4}]}
```

### decor（程序化装饰插画）

几何 / 扁平风装饰元素，不是数据图。只支持 PNG 出口。三种 `kind`：

**cover 封面横幅**
```json
{"type":"decor","kind":"cover","title":"2025 年度报告",
 "subtitle":"数据驱动决策","palette":["13294B","3C7DBF"]}
```

**pattern 装饰底纹**
```json
{"type":"decor","kind":"pattern","pattern":"dots","palette":["1F4E79"]}
```
`pattern` 可选：`dots` / `lines` / `rings` / `grid` / `waves`。

**icon 扁平图标**
```json
{"type":"decor","kind":"icon","icon":"chart","label":"数据洞察","palette":["1F4E79"]}
```
`icon` 可选：`chart` / `doc` / `team` / `gear` / `cloud` / `rocket` / `check` / `target` / `bulb` / `data`。

`palette` 是颜色数组（不带 `#`），第一个为主色。

## 主题

默认：accent `1F4E79`、accent2 `C00000`、文字 `333333`、网格 `BFBFBF`、浅底 `EAF0F6`。
单组改色用 `series[].color`；全局改色传 `theme={...}` 给 `render_png` / `render_svg`。

## 限制（如实告知用户）

- **照片、写实插画不能生成**：本库只做数据图、示意图与几何/扁平风矢量装饰；需要照片请走外部生图 API 或图库。
- PNG 是光栅化结果（默认 960×540，2× 超采样抗锯齿），放大不如 SVG 清晰。
- 中文字形来自系统字体；生僻字可能缺。
- 图内长文本**不自动换行**，标题过长请自行拆短。
- PNG 单张约 0.2–1 秒（纯 Python 逐像素），大尺寸会变慢。

## 自检

- PNG：读文件头应为 `89 50 4E 47`，用 `struct.unpack(">II", data[16:24])` 核对尺寸
- SVG：`xml.etree.ElementTree.fromstring` 解析
- **用视觉能力目视检查**——文字缺字、标签重叠、孔洞填实等问题只有看图才能发现
- 图内数字与 `series.values` 一致

## 已知踩坑（已在本库内解决，改代码时别退回去）

- 字形填充必须**多轮廓合并做 even-odd**，逐轮廓单独填充会把 `o`、`口` 的孔洞填实。
- 扫描线 y 取 `y + 0.5`，边界判断用半开区间，避免重复填充。
- 2× 超采样后再降采样，否则中文小字锯齿严重。
