# -*- coding: utf-8 -*-
"""pptx_builder.py — 纯标准库 PPTX 生成内核（不依赖 python-pptx / lxml / Pillow）。

设计要点:
  * 单位: 英寸(in) / 磅(pt) -> EMU, 16:9 默认 13.333x7.5in。
  * 形状: rect / roundRect / ellipse / line / arrow / textbox，全部用 DrawingML。
  * 结构: [Content_Types].xml + _rels + presentation + slideMaster + slideLayout + theme + slides。
  * 主题: 默认 Office 配色，可注入 accent 色与字体（供 theme_reader 对齐参考稿）。
"""
import os
import sys
import zipfile
from xml.sax.saxutils import escape

EMU_PER_INCH = 914400
EMU_PER_PT = 12700

NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NSDECL = 'xmlns:a="%s" xmlns:r="%s" xmlns:p="%s"' % (NS_A, NS_R, NS_P)

XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

DEMO_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_demo.pptx")


def in_emu(inch):
    return int(round(inch * EMU_PER_INCH))


def in_inv(emu):
    return emu / float(EMU_PER_INCH)


def pt_emu(pt):
    return int(round(pt * EMU_PER_PT))


def esc(s):
    return escape(str(s), {'"': "&quot;"})


def _image_size(path):
    """纯标准库读 PNG/JPEG 像素尺寸；读不出返回 (None, None)。"""
    with open(path, "rb") as f:
        head = f.read(32)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    if head[:2] == b"\xff\xd8":
        with open(path, "rb") as f:
            data = f.read()
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3):
                return (int.from_bytes(data[i + 7:i + 9], "big"),
                        int.from_bytes(data[i + 5:i + 7], "big"))
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            ln = int.from_bytes(data[i + 2:i + 4], "big")
            i += 2 + ln
    return None, None


def _xfrm(x, y, w, h, flip_h=False, flip_v=False):
    flips = (' flipH="1"' if flip_h else "") + (' flipV="1"' if flip_v else "")
    return (
        '<a:xfrm%s><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
        % (flips, in_emu(x), in_emu(y), max(in_emu(w), 1), max(in_emu(h), 1))
    )


def _solid(color):
    return '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % color


def _ln(color, width_pt, dash=None, arrow=False):
    x = '<a:ln w="%d">%s' % (pt_emu(width_pt), _solid(color))
    if dash:
        x += '<a:prstDash val="%s"/>' % dash
    if arrow:
        x += '<a:tailEnd type="triangle" w="med" len="med"/>'
    return x + "</a:ln>"


def _txbody(text, size=18, bold=False, color="000000", align="l", valign="t",
            font="微软雅黑", wrap=True, inset=0.05, bullet=False, line_sp=1.0):
    anchor = {"t": "t", "c": "ctr", "b": "b"}[valign]
    algn = {"l": "l", "c": "ctr", "r": "r"}[align]
    body = (
        '<a:bodyPr wrap="%s" lIns="%d" rIns="%d" tIns="%d" bIns="%d" anchor="%s"'
        ' rtlCol="0"><a:normAutofit/></a:bodyPr>'
        % ("square" if wrap else "none", in_emu(inset), in_emu(inset),
           in_emu(inset * 0.6), in_emu(inset * 0.6), anchor)
    )
    paras = []
    for line in str(text).split("\n"):
        ppr = '<a:pPr algn="%s">' % algn
        ppr += '<a:buChar char="•"/>' if bullet else "<a:buNone/>"
        ppr += '<a:lnSpc><a:spcPct val="%d"/></a:lnSpc>' % int(line_sp * 100000)
        ppr += "</a:pPr>"
        run = (
            '<a:r><a:rPr lang="zh-CN" altLang="en-US" sz="%d" b="%d" dirty="0">'
            '%s<a:latin typeface="%s"/><a:ea typeface="%s"/></a:rPr>'
            '<a:t>%s</a:t></a:r>'
            % (int(size * 100), 1 if bold else 0, _solid(color),
               esc(font), esc(font), esc(line))
        )
        paras.append("<a:p>%s%s</a:p>" % (ppr, run))
    return "<p:txBody>%s<a:lstStyle/>%s</p:txBody>" % (body, "".join(paras))


class Deck:
    """一个最小 PPTX 文档构建器。"""

    def __init__(self, width_in=13.333333, height_in=7.5, accent="4472C4",
                 accent2="ED7D31", bg="FFFFFF", font="微软雅黑"):
        self.w = width_in
        self.h = height_in
        self.accent = accent
        self.accent2 = accent2
        self.bg = bg
        self.font = font
        self.slides = []
        self._sid = 1
        self._media = {}
        self._img_seq = 0

    def _nid(self):
        self._sid += 1
        return self._sid

    # ---------- slide ----------
    def add_slide(self, bg=None):
        self.slides.append({"bg": bg or self.bg, "shapes": [], "images": []})
        return len(self.slides) - 1

    def add(self, xml):
        self.slides[-1]["shapes"].append(xml)

    # ---------- shapes ----------
    def shape(self, kind="rect", x=0, y=0, w=1, h=1, fill=None, line=None,
              line_w=1.0, text=None, size=18, bold=False, color="000000",
              align="l", valign="t", name=None, dash=None, bullet=False,
              inset=0.05, wrap=True, line_sp=1.0):
        sid = self._nid()
        nm = name or ("Shape %d" % sid)
        prst = '<a:prstGeom prst="%s"><a:avLst/></a:prstGeom>' % kind
        fillx = _solid(fill) if fill else "<a:noFill/>"
        lnx = _ln(line, line_w, dash) if line else "<a:ln><a:noFill/></a:ln>"
        sp_pr = "<p:spPr>%s%s%s%s</p:spPr>" % (_xfrm(x, y, w, h), prst, fillx, lnx)
        nv = ('<p:nvSpPr><p:cNvPr id="%d" name="%s"/><p:cNvSpPr/>'
              "<p:nvPr/></p:nvSpPr>" % (sid, esc(nm)))
        body = ""
        if text is not None:
            body = _txbody(text, size, bold, color, align, valign,
                           self.font, wrap, inset, bullet, line_sp)
        self.add("<p:sp>%s%s%s</p:sp>" % (nv, sp_pr, body))
        return sid

    def textbox(self, x, y, w, h, text, **kw):
        return self.shape("rect", x, y, w, h, text=text, **kw)

    def line(self, x1, y1, x2, y2, color="808080", width_pt=1.5, dash=None, arrow=False):
        sid = self._nid()
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        xf = _xfrm(x, y, max(w, 0.002), max(h, 0.002), x2 < x1, y2 < y1)
        ln = _ln(color, width_pt, dash, arrow)
        sp_pr = '<p:spPr>%s<a:prstGeom prst="line"><a:avLst/></a:prstGeom>%s</p:spPr>' % (xf, ln)
        nv = ('<p:nvSpPr><p:cNvPr id="%d" name="Line %d"/><p:cNvSpPr/>'
              "<p:nvPr/></p:nvSpPr>" % (sid, sid))
        self.add("<p:sp>%s%s</p:sp>" % (nv, sp_pr))
        return sid

    def rect(self, x, y, w, h, **kw):
        kw.setdefault("kind", "rect")
        return self.shape(x=x, y=y, w=w, h=h, **kw)

    def image(self, x, y, w, h, path, name=None, fit="contain"):
        """嵌入位图（png/jpg/jpeg）。

        fit="contain"（默认）等比缩放并居中，不变形、可能留白；
        fit="stretch" 直接拉伸填满，会变形。
        """
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if ext not in ("png", "jpg", "jpeg"):
            raise ValueError("仅支持 png/jpg/jpeg: %s" % path)
        if ext == "jpg":
            ext = "jpeg"
        iw, ih = _image_size(path)
        if fit == "contain" and iw and ih:
            scale = min(w / iw, h / ih)
            nw, nh = iw * scale, ih * scale
            x += (w - nw) / 2
            y += (h - nh) / 2
            w, h = nw, nh
        self._img_seq += 1
        part = "ppt/media/image%d.%s" % (self._img_seq, ext)
        with open(path, "rb") as f:
            self._media[part] = f.read()
        sid = self._nid()
        self.slides[-1]["images"].append(
            {"part": part, "x": x, "y": y, "w": w, "h": h, "id": sid,
             "name": name or ("Picture %d" % sid)})
        return sid

    # ---------- save ----------
    def save(self, path, title="Presentation"):
        n = len(self.slides)
        parts = {}
        parts["[Content_Types].xml"] = _content_types(n, bool(self._media))
        parts["_rels/.rels"] = _root_rels()
        parts["ppt/presentation.xml"] = _presentation_xml(self.w, self.h, n, title)
        parts["ppt/_rels/presentation.xml.rels"] = _presentation_rels(n)
        parts["ppt/slideMasters/slideMaster1.xml"] = _slide_master_xml()
        parts["ppt/slideMasters/_rels/slideMaster1.xml.rels"] = _slide_master_rels()
        parts["ppt/slideLayouts/slideLayout1.xml"] = _slide_layout_xml()
        parts["ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = _slide_layout_rels()
        parts["ppt/theme/theme1.xml"] = _theme_xml(self.accent, self.accent2, self.font)
        for i, sl in enumerate(self.slides, 1):
            rid_map, rels = {}, []
            for j, im in enumerate(sl["images"]):
                rid = "rId%d" % (j + 2)
                rid_map[im["id"]] = rid
                rels.append((rid, "../" + im["part"].split("ppt/", 1)[1]))
            parts["ppt/slides/slide%d.xml" % i] = _slide_xml(sl, rid_map)
            parts["ppt/slides/_rels/slide%d.xml.rels" % i] = _slide_rels(rels)
        for part, data in self._media.items():
            parts[part] = data
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in parts.items():
                if isinstance(data, bytes):
                    z.writestr(name, data)
                else:
                    z.writestr(name, XML_HEAD + data)
        return path


# ==================== 包内部件 ====================

def _content_types(n, has_img=False):
    over = "".join(
        '<Override PartName="/ppt/slides/slide%d.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' % i
        for i in range(1, n + 1)
    )
    imgs = ('<Default Extension="png" ContentType="image/png"/>'
            '<Default Extension="jpeg" ContentType="image/jpeg"/>') if has_img else ""
    return (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + imgs +
        '<Override PartName="/ppt/presentation.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        "%s</Types>" % over
    )


def _root_rels():
    return (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="%s/officeDocument" Target="ppt/presentation.xml"/>'
        "</Relationships>" % NS_R
    )


def _presentation_xml(w, h, n, title):
    ids = "".join(
        '<p:sldId id="%d" r:id="rId%d"/>' % (255 + i, 1 + i) for i in range(1, n + 1)
    )
    return (
        '<p:presentation %s saveSubsetFonts="1">' % NSDECL
        + '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        + "<p:sldIdLst>%s</p:sldIdLst>" % ids
        + '<p:sldSz cx="%d" cy="%d" type="screen16x9"/>' % (in_emu(w), in_emu(h))
        + '<p:notesSz cx="6858000" cy="9144000"/>'
        + "</p:presentation>"
    )


def _presentation_rels(n):
    rels = ['<Relationship Id="rId1" Type="%s/slideMaster" '
            'Target="slideMasters/slideMaster1.xml"/>' % NS_R,
            '<Relationship Id="rId%d" Type="%s/theme" '
            'Target="theme/theme1.xml"/>' % (n + 2, NS_R)]
    for i in range(1, n + 1):
        rels.append('<Relationship Id="rId%d" Type="%s/slide" '
                    'Target="slides/slide%d.xml"/>' % (1 + i, NS_R, i))
    return ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels) + "</Relationships>")


def _empty_tree():
    return (
        "<p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        "</p:spTree>"
    )


def _slide_master_xml():
    return (
        '<p:sldMaster %s>' % NSDECL
        + "<p:cSld>%s</p:cSld>" % _empty_tree()
        + '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" '
          'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
          'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        + '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        + "<p:txStyles>"
          '<p:titleStyle><a:lvl1pPr><a:defRPr sz="4400"/></a:lvl1pPr></p:titleStyle>'
          '<p:bodyStyle><a:lvl1pPr><a:defRPr sz="2000"/></a:lvl1pPr></p:bodyStyle>'
          '<p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle>'
          "</p:txStyles>"
        + "</p:sldMaster>"
    )


def _slide_master_rels():
    return (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="%s/slideLayout" '
        'Target="../slideLayouts/slideLayout1.xml"/>'
        '<Relationship Id="rId2" Type="%s/theme" Target="../theme/theme1.xml"/>'
        "</Relationships>" % (NS_R, NS_R)
    )


def _slide_layout_xml():
    return (
        '<p:sldLayout %s type="blank" preserve="1">' % NSDECL
        + '<p:cSld name="Blank">%s</p:cSld>' % _empty_tree()
        + "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        + "</p:sldLayout>"
    )


def _slide_layout_rels():
    return (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="%s/slideMaster" '
        'Target="../slideMasters/slideMaster1.xml"/>'
        "</Relationships>" % NS_R
    )


def _slide_rels(images=None):
    rels = ['<Relationship Id="rId1" Type="%s/slideLayout" '
            'Target="../slideLayouts/slideLayout1.xml"/>' % NS_R]
    for rid, target in (images or []):
        rels.append('<Relationship Id="%s" Type="%s/image" Target="%s"/>'
                    % (rid, NS_R, target))
    return ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels) + "</Relationships>")


def _pic_xml(im, rid):
    return (
        '<p:pic><p:nvPicPr><p:cNvPr id="%d" name="%s"/>'
        '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        '<p:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        '<p:spPr>%s<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        % (im["id"], esc(im["name"]), rid, _xfrm(im["x"], im["y"], im["w"], im["h"]))
    )


def _slide_xml(sl, rid_map=None):
    tree = ""
    if sl["bg"] and sl["bg"].upper() != "FFFFFF":
        tree += '<p:bg><p:bgPr>%s<a:effectLst/></p:bgPr></p:bg>' % _solid(sl["bg"])
    pics = "".join(_pic_xml(im, (rid_map or {}).get(im["id"], "rId2"))
                   for im in sl.get("images", []))
    tree += ('<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/>'
             '<p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/>'
             '<a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>'
             "</a:xfrm></p:grpSpPr>%s%s</p:spTree>" % ("".join(sl["shapes"]), pics))
    return ('<p:sld %s><p:cSld>%s</p:cSld>'
            "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
            % (NSDECL, tree))


def _theme_xml(accent, accent2, font):
    clr = (
        '<a:clrScheme name="Office">'
        '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
        '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="44546A"/></a:dk2>'
        '<a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>'
        '<a:accent1><a:srgbClr val="%s"/></a:accent1>'
        '<a:accent2><a:srgbClr val="%s"/></a:accent2>'
        '<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>'
        '<a:accent4><a:srgbClr val="FFC000"/></a:accent4>'
        '<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5>'
        '<a:accent6><a:srgbClr val="70AD47"/></a:accent6>'
        '<a:hlink><a:srgbClr val="0563C1"/></a:hlink>'
        '<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>'
        "</a:clrScheme>" % (accent, accent2)
    )
    fonts = (
        '<a:fontScheme name="Office">'
        '<a:majorFont><a:latin typeface="%s"/><a:ea typeface="%s"/>'
        '<a:cs typeface=""/></a:majorFont>'
        '<a:minorFont><a:latin typeface="%s"/><a:ea typeface="%s"/>'
        '<a:cs typeface=""/></a:minorFont>'
        "</a:fontScheme>" % (esc(font), esc(font), esc(font), esc(font))
    )
    return ('<a:theme %s name="Office Theme"><a:themeElements>%s%s%s</a:themeElements>'
            "</a:theme>" % (NSDECL, clr, fonts, _fmt_scheme()))


def _fmt_scheme():
    # 标准 Office fmtScheme：四个列表各 3 项，缺项会被 PowerPoint 判非法
    return (
        '<a:fmtScheme name="Office">'
        "<a:fillStyleLst>"
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:gradFill rotWithShape="1"><a:gsLst>'
        '<a:gs pos="0"><a:schemeClr val="phClr"><a:lumMod val="110000"/>'
        '<a:satMod val="105000"/><a:tint val="67000"/></a:schemeClr></a:gs>'
        '<a:gs pos="50000"><a:schemeClr val="phClr"><a:lumMod val="105000"/>'
        '<a:satMod val="103000"/><a:tint val="73000"/></a:schemeClr></a:gs>'
        '<a:gs pos="100000"><a:schemeClr val="phClr"><a:lumMod val="105000"/>'
        '<a:satMod val="109000"/><a:tint val="81000"/></a:schemeClr></a:gs>'
        '</a:gsLst><a:lin ang="5400000" scaled="0"/></a:gradFill>'
        '<a:gradFill rotWithShape="1"><a:gsLst>'
        '<a:gs pos="0"><a:schemeClr val="phClr"><a:satMod val="103000"/>'
        '<a:lumMod val="102000"/><a:tint val="94000"/></a:schemeClr></a:gs>'
        '<a:gs pos="50000"><a:schemeClr val="phClr"><a:satMod val="110000"/>'
        '<a:lumMod val="100000"/><a:shade val="100000"/></a:schemeClr></a:gs>'
        '<a:gs pos="100000"><a:schemeClr val="phClr"><a:lumMod val="99000"/>'
        '<a:satMod val="120000"/><a:shade val="78000"/></a:schemeClr></a:gs>'
        '</a:gsLst><a:lin ang="5400000" scaled="0"/></a:gradFill>'
        "</a:fillStyleLst>"
        "<a:lnStyleLst>"
        '<a:ln w="6350" cap="flat" cmpd="sng" algn="ctr">'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:prstDash val="solid"/></a:ln>'
        '<a:ln w="12700" cap="flat" cmpd="sng" algn="ctr">'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:prstDash val="solid"/></a:ln>'
        '<a:ln w="19050" cap="flat" cmpd="sng" algn="ctr">'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:prstDash val="solid"/></a:ln>'
        "</a:lnStyleLst>"
        "<a:effectStyleLst>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        '<a:effectStyle><a:effectLst><a:outerShdw blurRad="57150" dist="19050" '
        'dir="5400000" algn="ctr" rotWithShape="0"><a:srgbClr val="000000">'
        '<a:alpha val="63000"/></a:srgbClr></a:outerShdw></a:effectLst></a:effectStyle>'
        "</a:effectStyleLst>"
        "<a:bgFillStyleLst>"
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"><a:tint val="95000"/>'
        '<a:satMod val="170000"/></a:schemeClr></a:solidFill>'
        '<a:gradFill rotWithShape="1"><a:gsLst>'
        '<a:gs pos="0"><a:schemeClr val="phClr"><a:tint val="93000"/>'
        '<a:satMod val="150000"/><a:shade val="98000"/>'
        '<a:lumMod val="102000"/></a:schemeClr></a:gs>'
        '<a:gs pos="50000"><a:schemeClr val="phClr"><a:tint val="98000"/>'
        '<a:satMod val="130000"/><a:shade val="90000"/>'
        '<a:lumMod val="103000"/></a:schemeClr></a:gs>'
        '<a:gs pos="100000"><a:schemeClr val="phClr"><a:shade val="63000"/>'
        '<a:satMod val="120000"/></a:schemeClr></a:gs>'
        '</a:gsLst><a:lin ang="5400000" scaled="0"/></a:gradFill>'
        "</a:bgFillStyleLst>"
        "</a:fmtScheme>"
    )


# ==================== 自测 ====================

def _demo(out_path=None):
    d = Deck(accent="1F4E79", accent2="C00000")
    # 封面
    d.add_slide(bg="1F4E79")
    d.textbox(1.2, 2.2, 11, 1.2, "PPT 生成内核自测", size=40, bold=True,
              color="FFFFFF", valign="c")
    d.textbox(1.2, 3.5, 11, 0.7, "纯标准库 · 无 python-pptx", size=18, color="C9D6E3")
    d.line(1.2, 4.4, 5.0, 4.4, color="C00000", width_pt=4)
    # 内容页
    d.add_slide()
    d.textbox(0.9, 0.6, 11.5, 0.9, "一、路线判断", size=30, bold=True, color="1F4E79")
    d.line(0.9, 1.55, 12.4, 1.55, color="C00000", width_pt=2)
    d.textbox(1.1, 2.0, 11.2, 4.4,
              "图 = 矢量形状，不是位图\n"
              "PPT = zip + OOXML，纯字符串可造\n"
              "主题色/字体从参考稿注入\n"
              "换行按字数估算，保守留边距",
              size=22, color="333333", line_sp=1.4, bullet=True)
    # 柱状图页
    d.add_slide()
    d.textbox(0.9, 0.6, 11.5, 0.9, "二、矢量柱状图（原生形状）", size=30,
              bold=True, color="1F4E79")
    d.line(0.9, 1.55, 12.4, 1.55, color="C00000", width_pt=2)
    _bar(d, 1.6, 2.2, 10.0, 4.4, ["Q1", "Q2", "Q3", "Q4"], [12, 18, 15, 24])
    out_path = out_path or DEMO_OUT
    d.save(out_path)
    print("saved", out_path)
    return out_path


def _bar(d, x, y, w, h, cats, vals, color="1F4E79"):
    maxv = max(vals) or 1
    axis_y = y + h - 0.5
    d.line(x, y + 0.2, x, axis_y, color="7F7F7F", width_pt=1.2)
    d.line(x, axis_y, x + w, axis_y, color="7F7F7F", width_pt=1.2)
    n = len(vals)
    slot = w / n
    bw = slot * 0.45
    for i, (c, v) in enumerate(zip(cats, vals)):
        bh = (v / maxv) * (h - 0.9)
        bx = x + slot * i + (slot - bw) / 2
        by = axis_y - bh
        d.rect(bx, by, bw, bh, fill=color, line=None)
        d.textbox(bx - 0.2, by - 0.42, bw + 0.4, 0.35, str(v), size=14,
                  color="333333", align="c")
        d.textbox(bx - 0.2, axis_y + 0.08, bw + 0.4, 0.35, c, size=14,
                  color="333333", align="c")


if __name__ == "__main__":
    _demo()
