"""docx 원고 → 원고 HWPX(서식 옮기기 엔진 format_transfer.py의 입력). 한글 없이 zipfile + lxml로 만든다.

왜: 이 PC의 한글 2020 자동화는 Word 계열(docx·doc·rtf)을 열지 못한다(2026-10-19 확인 — 형식 이름 OOXML·DOCX·
MSWORD·DOCRTF·RTF 등 18가지 모두 실패, txt·html은 열림). 그래서 docx를 직접 읽어 엔진이 읽는 HWPX로 옮긴다.

원칙: 원고 글자는 그대로 옮긴다(직접 친 번호·기호 포함). 서식은 엔진의 판정에 쓰이는 것만 옮긴다.
  - 문단 개요 수준: 문단·스타일의 outlineLvl, 없으면 스타일 이름 '개요 N'·'Heading N'·'제목 N' → 개요 문단 번호 수준 N-1.
    개요 번호 모양은 비워 둔다(원고처럼 직접 친 번호만 보이게) — 엔진은 직접 친 번호로 장·수준을 판정한다.
  - Word 자동 번호(numPr): 화면에 보이는 번호를 글자로 앞에 붙인다(엔진에는 직접 친 번호처럼 보임). 번호 뒤 탭은 빈칸 하나.
  - 글자: 굵게·기울임·밑줄·글자색(엔진의 '부분 강조' 목록용), 탭, 줄 바꿈, 필드는 결과 글자만, 기호(w:sym).
  - 표: 격자 칸 너비, 칸 합치기(gridSpan·vMerge), 머리행(tblHeader), 셀 세로 정렬. 행 높이는 trHeight, 없으면 줄 수로 어림
    (한글은 셀 높이를 최솟값으로 보고 내용에 맞춰 늘린다).
  - 그림: 글자처럼 놓인 그림(wp:inline). 떠 있는 그림(wp:anchor)도 글자처럼 넣고 기록에 남긴다.
  - 구역마다 머리말 글자 → 그 구역 첫 문단의 머리말 컨트롤(엔진이 장별 머리말로 쓴다). 구역이 바뀌면 쪽 나눔.
옮기지 않는 것은 변환 기록에 개수를 남긴다: 각주·미주 글, 글상자 글, VML 그림, 수식, 꼬리말, 변경 추적의 지운 글.
단위: 1 twip = 5 HWPUNIT, 1 HWPUNIT = 127 EMU.
"""
import copy
import itertools
import posixpath
import re
import time
import zipfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from lxml import etree

import format_transfer as ft
from format_transfer import local, own_text, q

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
TWIP, EMU = 5, 127
HEADING_NAME = re.compile(r"^(?:개요|heading|제목)\s*(\d)$", re.I)
ALIGN = {"center": "CENTER", "right": "RIGHT", "end": "RIGHT", "both": "JUSTIFY", "distribute": "DISTRIBUTE",
         "left": "LEFT", "start": "LEFT"}
VALIGN = {"top": "TOP", "center": "CENTER", "bottom": "BOTTOM"}
OFF = ("0", "false", "off", "none")
BULLET_PUA = {"": "•", "": "▪", "": "➢", "": "✓", "": "❖", "": "■", "": "◆"}
LINE_H = 1600  # 줄 수로 행 높이를 어림할 때 한 줄(HWPUNIT)
CELL_M = 141   # 셀 안 여백 기본값(HWPUNIT, 0.5 mm)


def w(tag):
    return f"{{{W}}}{tag}"


def wval(el, default=None):
    return el.get(w("val"), default) if el is not None else default


def on(el):
    """w:b 같은 켜기/끄기 속성 — 요소가 있고 val이 끄기가 아니면 켜짐."""
    return el is not None and (wval(el, "1") or "1").lower() not in OFF


def roman(n):
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                 (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out, n = out + s, n - v
    return out


def word_num(v: int, fmt: str) -> str:
    if fmt in ("upperRoman", "lowerRoman"):
        r = roman(v)
        return r if fmt == "upperRoman" else r.lower()
    if fmt in ("upperLetter", "lowerLetter"):
        s = chr(ord("A") + (v - 1) % 26) * ((v - 1) // 26 + 1)
        return s if fmt == "upperLetter" else s.lower()
    if fmt == "ganada":
        return "가나다라마바사아자차카타파하"[(v - 1) % 14]
    if fmt == "chosung":
        return "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"[(v - 1) % 14]
    if fmt == "decimalEnclosedCircle" and 1 <= v <= 20:
        return chr(0x2460 + v - 1)
    if fmt == "decimalZero":
        return f"{v:02d}"
    if fmt == "none":
        return ""
    return str(v)


# ======================================================================= docx 읽기

class Lists:
    """Word 자동 번호(numbering.xml) → 화면에 보이는 번호 글자. 번호 인스턴스(numId)마다 수준별로 센다."""

    def __init__(self, numbering):
        self.abstract = {a.get(w("abstractNumId")): a for a in numbering.findall(w("abstractNum"))}
        self.nums = {}
        for n in numbering.findall(w("num")):
            over = {int(o.get(w("ilvl"))): o for o in n.findall(w("lvlOverride"))}
            self.nums[n.get(w("numId"))] = (wval(n.find(w("abstractNumId"))), over)
        self.count = {}

    def lvl(self, num_id, ilvl):
        aid, over = self.nums.get(num_id, (None, {}))
        o = over.get(ilvl)
        if o is not None and o.find(w("lvl")) is not None:
            return o.find(w("lvl")), o
        a = self.abstract.get(aid)
        for L in (a.findall(w("lvl")) if a is not None else []):
            if int(L.get(w("ilvl"))) == ilvl:
                return L, o
        return None, o

    def label(self, num_id, ilvl):
        if num_id in (None, "0") or num_id not in self.nums:
            return None
        L, o = self.lvl(num_id, ilvl)
        if L is None:
            return None
        c = self.count.setdefault(num_id, {})

        def start(level, ov):
            so = ov.find(w("startOverride")) if ov is not None else None
            return int(wval(so) if so is not None else wval(level.find(w("start")), "1"))
        c[ilvl] = c[ilvl] + 1 if ilvl in c else start(L, o)
        for k in [k for k in c if k > ilvl]:
            del c[k]
        fmt = wval(L.find(w("numFmt")), "decimal")
        text = wval(L.find(w("lvlText")), "") or ""
        if fmt == "bullet":
            s = "".join(BULLET_PUA.get(ch, ch) for ch in text)
        else:
            def rep(m):
                k = int(m.group(1)) - 1
                L2, o2 = self.lvl(num_id, k)
                if L2 is None:
                    return ""
                return word_num(c.get(k, start(L2, o2)), wval(L2.find(w("numFmt")), "decimal"))
            s = re.sub(r"%(\d)", rep, text)
        return s + ("" if wval(L.find(w("suff")), "tab") == "nothing" else " ")


class Docx:
    def __init__(self, path: Path):
        self.z = zipfile.ZipFile(path)
        self.names = set(self.z.namelist())
        self.doc = self.xml("word/document.xml")
        self.rels = self.rels_of("word/document.xml")
        self.styles, self.default_style, self.rpr_default = {}, None, None
        if "word/styles.xml" in self.names:
            st = self.xml("word/styles.xml")
            for s in st.iter(w("style")):
                self.styles[s.get(w("styleId"))] = s
                if s.get(w("type")) == "paragraph" and s.get(w("default")) in ("1", "true"):
                    self.default_style = s.get(w("styleId"))
            self.rpr_default = st.find(f"{w('docDefaults')}/{w('rPrDefault')}/{w('rPr')}")
        self.lists = Lists(self.xml("word/numbering.xml")) if "word/numbering.xml" in self.names else None

    def xml(self, name):
        return etree.fromstring(self.z.read(name), PARSER)

    def rels_of(self, part):
        d, b = part.rsplit("/", 1)
        name = f"{d}/_rels/{b}.rels"
        if name not in self.names:
            return {}
        out = {}
        for r in self.xml(name):
            t = r.get("Target") or ""
            if r.get("TargetMode") != "External":
                t = t[1:] if t.startswith("/") else posixpath.normpath(f"{d}/{t}")
            out[r.get("Id")] = (r.get("Type", "").rsplit("/", 1)[-1], t)
        return out

    def chain(self, sid):
        """스타일과 그 바탕 스타일들(자기 → 바탕 순)."""
        out, seen = [], set()
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            out.append(self.styles[sid])
            sid = wval(self.styles[sid].find(w("basedOn")))
        return out

    def pstyle(self, p):
        e = p.find(f"{w('pPr')}/{w('pStyle')}")
        return wval(e) if e is not None else self.default_style

    def style_name(self, sid):
        s = self.styles.get(sid)
        return wval(s.find(w("name")), sid) if s is not None else (sid or "")

    def ppr(self, p, tag):
        """문단 속성: 문단 직접 → 문단 스타일(바탕 스타일까지)."""
        e = p.find(f"{w('pPr')}/{w(tag)}")
        if e is not None:
            return e
        for s in self.chain(self.pstyle(p)):
            e = s.find(f"{w('pPr')}/{w(tag)}")
            if e is not None:
                return e
        return None

    def outline_level(self, p):
        e = self.ppr(p, "outlineLvl")
        if e is not None:
            v = int(wval(e, "9"))
            return v if v < 9 else None
        for s in self.chain(self.pstyle(p)):
            m = HEADING_NAME.match(wval(s.find(w("name")), "") or "")
            if m:
                return int(m.group(1)) - 1
        return None

    def num_label(self, p):
        if self.lists is None:
            return None
        e = self.ppr(p, "numPr")
        if e is None:
            return None
        num_id = wval(e.find(w("numId")))
        ilvl = int(wval(e.find(w("ilvl")), "0") or 0)
        return self.lists.label(num_id, ilvl)

    def run_feat(self, p, r):
        """(굵게, 기울임, 밑줄, 색) — 문서 기본 → 문단 스타일 → 글자 스타일 → 직접 순으로 덮어쓴다."""
        layers = [self.rpr_default] + [s.find(w("rPr")) for s in reversed(self.chain(self.pstyle(p)))]
        rpr = r.find(w("rPr")) if r is not None else None
        if rpr is not None and rpr.find(w("rStyle")) is not None:
            layers += [s.find(w("rPr")) for s in reversed(self.chain(wval(rpr.find(w("rStyle")))))]
        layers.append(rpr)
        f = {"b": False, "i": False, "u": False, "color": None}
        for L in layers:
            if L is None:
                continue
            for k in ("b", "i"):
                if L.find(w(k)) is not None:
                    f[k] = on(L.find(w(k)))
            if L.find(w("u")) is not None:
                f["u"] = (wval(L.find(w("u")), "single") or "single") != "none"
            c = L.find(w("color"))
            if c is not None:
                v = wval(c, "auto") or "auto"
                f["color"] = None if v == "auto" else "#" + v.upper()
        return f

    def plain(self, p):
        """독립 대조용 docx 문단 글자: 문단 안 w:t(글상자 안 문단 제외) + 탭 — 변환 결과와 맞춰 본다."""
        out = []
        for e in p.iter(w("t"), w("tab"), w("ptab")):
            anc, inner = e.getparent(), False
            while anc is not None and anc is not p:
                if local(anc) in ("p", "del", "moveFrom"):
                    inner = True
                    break
                anc = anc.getparent()
            if inner:
                continue
            if local(e) == "t":
                out.append(e.text or "")
            elif local(e.getparent()) == "r":  # w:tabs 정의(pPr 안)는 글자가 아님
                out.append("\t")
        return "".join(out)


# ======================================================================= HWPX 만들기

def sub(parent, tag, **attrs):
    e = etree.SubElement(parent, q(tag))
    for k, v in attrs.items():
        e.set(k, str(v))
    return e


def last_t(run):
    if len(run) and local(run[-1]) == "t":
        return run[-1]
    return etree.SubElement(run, q("hp:t"))


def put_text(run, s):
    if not s:
        return
    t = last_t(run)
    if len(t):
        t[-1].tail = (t[-1].tail or "") + s
    else:
        t.text = (t.text or "") + s


def put_tab(run):
    sub(last_t(run), "hp:tab", width=4000, leader=0, type=1)


def put_br(run):
    sub(last_t(run), "hp:lineBreak")


class Hwpx:
    """바탕 HWPX(양식 프로필의 본문 양식)의 헤더·구역 설정을 빌려 원고 HWPX를 만든다."""

    def __init__(self, base: ft.Pkg):
        self.base = base
        self.dst = ft.Dst(base)
        self.bins = ft.Bins()
        st0 = base.items("style")["0"]
        self.pp0, self.cp0 = st0.get("paraPrIDRef"), st0.get("charPrIDRef")
        self.styles = {s.get("name"): s.get("id") for s in base.items("style").values() if s.get("type") == "PARA"}
        oid = base.sections[0].find(f".//{q('hp:secPr')}").get("outlineShapeIDRef")
        num = copy.deepcopy(self.dst.get("numbering", oid))
        for ph in num.findall(q("hh:paraHead")):
            ph.text = None  # 번호 모양 없음 — 직접 친 번호만 보이게
        self.outline = self.dst.add("numbering", num, dedupe=False)
        bf = copy.deepcopy(self.dst.get("borderFill", "1"))
        for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            e = bf.find(q("hh:" + side))
            e.set("type", "SOLID")
            e.set("width", "0.12 mm")
        self.cell_bf = self.dst.add("borderFill", bf)
        self.ids = itertools.count(1100000001)
        self.pp_memo, self.cp_memo = {}, {}

    def para_pr(self, level, align):
        key = (level, align)
        if key not in self.pp_memo:
            def fn(n):
                if level is None and not align:
                    return False
                if level is not None:
                    hd = n.find(q("hh:heading"))
                    hd.set("type", "OUTLINE")
                    hd.set("idRef", "0")
                    hd.set("level", str(level))
                if align:
                    n.find(q("hh:align")).set("horizontal", align)
            self.pp_memo[key] = self.dst.variant("paraPr", self.pp0, fn)
        return self.pp_memo[key]

    def char_pr(self, f):
        key = (f["b"], f["i"], f["u"], f["color"])
        if key not in self.cp_memo:
            def fn(n):
                if not (f["b"] or f["i"] or f["u"] or (f["color"] and f["color"] != n.get("textColor"))):
                    return False
                at = list(n).index(n.find(q("hh:offset"))) + 1
                for tag, want in (("italic", f["i"]), ("bold", f["b"])):  # 순서: offset, italic, bold, underline
                    if want and n.find(q("hh:" + tag)) is None:
                        n.insert(at, etree.Element(q("hh:" + tag)))
                        at += 1
                if f["u"]:
                    n.find(q("hh:underline")).set("type", "BOTTOM")
                if f["color"]:
                    n.set("textColor", f["color"])
            self.cp_memo[key] = self.dst.variant("charPr", self.cp0, fn)
        return self.cp_memo[key]

    def para(self, level=None, align=None, style_name=None):
        p = etree.Element(q("hp:p"))
        for k, v in (("id", "0"), ("paraPrIDRef", self.para_pr(level, align)),
                     ("styleIDRef", self.styles.get(style_name, "0")), ("pageBreak", "0"), ("columnBreak", "0"),
                     ("merged", "0")):
            p.set(k, v)
        return p

    def run(self, p, cid):
        r = sub(p, "hp:run")
        r.set("charPrIDRef", cid)
        return r

    def pic(self, data: bytes, ext: str, wd: int, ht: int):
        bid = self.bins.add(data, ext)
        cw, ch = wd, ht
        try:
            import io
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                cw, ch = im.size[0] * 75, im.size[1] * 75  # 원본 그림 크기(96 dpi 화소 → HWPUNIT)
        except Exception:
            pass
        pic = etree.Element(q("hp:pic"))
        for k, v in (("id", next(self.ids)), ("zOrder", 0), ("numberingType", "PICTURE"), ("textWrap", "TOP_AND_BOTTOM"),
                     ("textFlow", "BOTH_SIDES"), ("lock", 0), ("dropcapstyle", "None"), ("href", ""), ("groupLevel", 0),
                     ("instid", next(self.ids)), ("reverse", 0)):
            pic.set(k, str(v))
        sub(pic, "hp:offset", x=0, y=0)
        sub(pic, "hp:orgSz", width=wd, height=ht)
        sub(pic, "hp:curSz", width=wd, height=ht)
        sub(pic, "hp:flip", horizontal=0, vertical=0)
        sub(pic, "hp:rotationInfo", angle=0, centerX=wd // 2, centerY=ht // 2, rotateimage=1)
        ri = sub(pic, "hp:renderingInfo")
        for m in ("transMatrix", "scaMatrix", "rotMatrix"):
            sub(ri, "hc:" + m, e1=1, e2=0, e3=0, e4=0, e5=1, e6=0)
        ir = sub(pic, "hp:imgRect")
        for n, (x, y) in enumerate(((0, 0), (wd, 0), (wd, ht), (0, ht))):
            sub(ir, f"hc:pt{n}", x=x, y=y)
        sub(pic, "hp:imgClip", left=0, right=cw, top=0, bottom=ch)
        sub(pic, "hp:inMargin", left=0, right=0, top=0, bottom=0)
        sub(pic, "hc:img", binaryItemIDRef=bid, bright=0, contrast=0, effect="REAL_PIC", alpha=0)
        sub(pic, "hp:effects")
        sub(pic, "hp:sz", width=wd, widthRelTo="ABSOLUTE", height=ht, heightRelTo="ABSOLUTE", protect=0)
        sub(pic, "hp:pos", treatAsChar=1, affectLSpacing=0, flowWithText=1, allowOverlap=0, holdAnchorAndSO=0,
            vertRelTo="PARA", horzRelTo="PARA", vertAlign="TOP", horzAlign="LEFT", vertOffset=0, horzOffset=0)
        sub(pic, "hp:outMargin", left=0, right=0, top=0, bottom=0)
        return pic


# ======================================================================= 옮기기

class Converter:
    def __init__(self, dx: Docx, hx: Hwpx):
        self.dx, self.hx = dx, hx
        self.log = Counter()
        self.fld = []
        self.checks = []  # (docx 글자, 붙인 번호, hp:p) — 끝에 글자 대조

    # --- 문단 안
    def content(self, out, p, el, rels):
        for c in el:
            tag = local(c)
            if tag == "r":
                self.run(out, p, c, rels)
            elif tag in ("hyperlink", "ins", "moveTo", "smartTag", "customXml", "fldSimple", "dir", "bdo"):
                self.content(out, p, c, rels)
            elif tag == "sdt":
                sc = c.find(w("sdtContent"))
                if sc is not None:
                    self.content(out, p, sc, rels)
            elif tag in ("del", "moveFrom"):
                self.log["변경 추적의 지운 글(옮기지 않음)"] += 1
            elif tag in ("oMath", "oMathPara"):
                self.log["수식(옮기지 않음)"] += 1
            elif tag not in ("pPr", "bookmarkStart", "bookmarkEnd", "proofErr", "commentRangeStart", "commentRangeEnd",
                             "permStart", "permEnd"):
                self.log[f"모르는 문단 요소 {tag}(옮기지 않음)"] += 1

    def run(self, out, p, r, rels):
        cid = self.hx.char_pr(self.dx.run_feat(p, r))
        hr = None

        def R():
            nonlocal hr
            if hr is None:
                hr = self.hx.run(out, cid)
            return hr
        for c in r:
            tag = local(c)
            if tag == "fldChar":
                kind = c.get(w("fldCharType"))
                if kind == "begin":
                    self.fld.append("instr")
                elif kind == "separate" and self.fld:
                    self.fld[-1] = "result"
                elif kind == "end" and self.fld:
                    self.fld.pop()
                continue
            if self.fld and self.fld[-1] == "instr":
                continue
            if tag == "t":
                put_text(R(), c.text or "")
            elif tag in ("tab", "ptab"):
                put_tab(R())
            elif tag in ("br", "cr"):
                if c.get(w("type")) in ("page", "column"):
                    self.log["쪽·단 나누기(옮기지 않음 — 엔진이 장마다 새 쪽)"] += 1
                else:
                    put_br(R())
            elif tag == "noBreakHyphen":
                put_text(R(), "-")
            elif tag == "sym":
                put_text(R(), chr(int(c.get(w("char"), "20"), 16)))
                self.log["기호(w:sym) → 글자"] += 1
            elif tag == "drawing":
                obj = self.drawing(c, rels)
                if obj is not None:
                    R().append(obj)
            elif tag in ("pict", "object"):
                n = len("".join(x.text or "" for x in c.iter(w("t"))))
                self.log[f"VML 그림·OLE 개체(옮기지 않음{f', 안 글자 {n}자' if n else ''})"] += 1
            elif tag in ("footnoteReference", "endnoteReference"):
                self.log["각주·미주(본문 글은 옮기지 않음)"] += 1
            elif tag not in ("rPr", "lastRenderedPageBreak", "annotationRef", "commentReference", "instrText",
                             "delText", "separator", "continuationSeparator", "softHyphen"):
                self.log[f"모르는 글자 요소 {tag}(옮기지 않음)"] += 1

    def drawing(self, d, rels):
        box = d.find(f"{{{WP}}}inline")
        anchored = box is None
        if anchored:
            box = d.find(f"{{{WP}}}anchor")
        if box is None:
            return None
        txt = "".join(x.text or "" for x in box.iter(w("t")))
        if txt:
            self.log[f"글상자 글(옮기지 않음, {len(txt)}자)"] += 1
        blip = box.find(f".//{{{A}}}blip")
        if blip is None:
            self.log["그림 아닌 그리기 개체(옮기지 않음)"] += 1
            return None
        target = rels.get(blip.get(f"{{{REL}}}embed"), (None, None))[1]
        if not target or target not in self.dx.names:
            self.log["연결된 그림 파일 없음(옮기지 않음)"] += 1
            return None
        ext = box.find(f"{{{WP}}}extent")
        wd, ht = round(int(ext.get("cx")) / EMU), round(int(ext.get("cy")) / EMU)
        self.log["떠 있는 그림 → 글자처럼 취급" if anchored else "그림(글자처럼 취급)"] += 1
        return self.hx.pic(self.dx.z.read(target), target.rsplit(".", 1)[-1].lower(), wd, ht)

    # --- 문단·표
    def paragraph(self, p, rels, outline=True):
        level = self.dx.outline_level(p) if outline else None
        align = ALIGN.get(wval(self.dx.ppr(p, "jc"), "") or "")
        out = self.hx.para(level, align, self.dx.style_name(self.dx.pstyle(p)))
        if level is not None:
            self.log[f"개요 수준 {level + 1} 문단"] += 1
        label = self.dx.num_label(p)
        if label:
            put_text(self.hx.run(out, self.hx.char_pr(self.dx.run_feat(p, None))), label)
            self.log["Word 자동 번호 → 글자"] += 1
        self.content(out, p, p, rels)
        if out.find(q("hp:run")) is None:
            self.hx.run(out, self.hx.cp0)
        self.checks.append((self.dx.plain(p), label or "", out))
        return out

    def blocks(self, parent, rels, outline=True):
        out = []
        for el in parent:
            tag = local(el)
            if tag == "p":
                out.append(self.paragraph(el, rels, outline))
            elif tag == "tbl":
                out.append(self.table_para(el, rels))
            elif tag == "sdt":
                sc = el.find(w("sdtContent"))
                if sc is not None:
                    out += self.blocks(sc, rels, outline)
            elif tag == "customXml":
                out += self.blocks(el, rels, outline)
            elif tag not in ("sectPr", "bookmarkStart", "bookmarkEnd", "proofErr", "tblPr", "tblGrid", "tcPr", "trPr"):
                self.log[f"모르는 블록 {tag}(옮기지 않음)"] += 1
        return out

    def table_para(self, tbl, rels):
        out = self.hx.para(None, ALIGN.get(wval(tbl.find(f"{w('tblPr')}/{w('jc')}"), "") or ""))
        run = self.hx.run(out, self.hx.cp0)
        run.append(self.table(tbl, rels))
        sub(run, "hp:t")
        self.log["표"] += 1
        return out

    def table(self, tbl, rels):
        grid = [int(g.get(w("w"), "0") or 0) * TWIP for g in tbl.findall(f"{w('tblGrid')}/{w('gridCol')}")]
        mar = {k: CELL_M for k in ("left", "right", "top", "bottom")}
        cm = tbl.find(f"{w('tblPr')}/{w('tblCellMar')}")
        for k in mar:
            e = cm.find(w(k)) if cm is not None else None
            if e is None and cm is not None:
                e = cm.find(w({"left": "start", "right": "end"}.get(k, k)))
            if e is not None and e.get(w("w")):
                mar[k] = int(e.get(w("w"))) * TWIP
        rows = tbl.findall(w("tr"))
        placed = []
        for ri, tr in enumerate(rows):
            col = int(wval(tr.find(f"{w('trPr')}/{w('gridBefore')}"), "0") or 0)
            for tc in tr.findall(w("tc")):
                pr = tc.find(w("tcPr"))
                gs = pr.find(w("gridSpan")) if pr is not None else None
                span = int(wval(gs, "1")) if gs is not None else 1
                vm = pr.find(w("vMerge")) if pr is not None else None
                state = None if vm is None else ("restart" if wval(vm) == "restart" else "continue")
                placed.append((ri, col, span, tc, state))
                col += span
        need = max((c + s for _, c, s, _, _ in placed), default=0)
        if len(grid) < need:
            grid += [grid[-1] if grid else 8000] * (need - len(grid))
            self.log["표 격자 칸 수 보충"] += 1
        cells, open_ = [], {}
        for ri, col, span, tc, state in placed:
            if state == "continue" and col in open_:
                open_[col]["rs"] += 1
                continue
            cell = {"r": ri, "c": col, "cs": span, "rs": 1, "tc": tc}
            cells.append(cell)
            for k in range(col, col + span):
                open_.pop(k, None)
            if state == "restart":
                open_[col] = cell
        heights = []
        for ri, tr in enumerate(rows):
            th = tr.find(f"{w('trPr')}/{w('trHeight')}")
            est = max([self.lines(c["tc"]) * LINE_H for c in cells if c["r"] == ri and c["rs"] == 1] or [LINE_H])
            est += mar["top"] + mar["bottom"]
            heights.append(max(est, int(wval(th, "0") or 0) * TWIP) if th is not None else est)
        heads = [ri for ri, tr in enumerate(rows) if tr.find(f"{w('trPr')}/{w('tblHeader')}") is not None]
        t = etree.Element(q("hp:tbl"))
        for k, v in (("id", next(self.hx.ids)), ("zOrder", 0), ("numberingType", "TABLE"), ("textWrap", "TOP_AND_BOTTOM"),
                     ("textFlow", "BOTH_SIDES"), ("lock", 0), ("dropcapstyle", "None"), ("pageBreak", "CELL"),
                     ("repeatHeader", 1 if heads else 0), ("rowCnt", len(rows)), ("colCnt", len(grid)),
                     ("cellSpacing", 0), ("borderFillIDRef", self.hx.cell_bf), ("noAdjust", 0)):
            t.set(k, str(v))
        sub(t, "hp:sz", width=sum(grid), widthRelTo="ABSOLUTE", height=sum(heights), heightRelTo="ABSOLUTE", protect=0)
        sub(t, "hp:pos", treatAsChar=1, affectLSpacing=0, flowWithText=1, allowOverlap=0, holdAnchorAndSO=0,
            vertRelTo="PARA", horzRelTo="PARA", vertAlign="TOP", horzAlign="LEFT", vertOffset=0, horzOffset=0)
        sub(t, "hp:outMargin", left=CELL_M, right=CELL_M, top=CELL_M, bottom=CELL_M)
        sub(t, "hp:inMargin", **mar)
        for ri in range(len(rows)):
            tr = sub(t, "hp:tr")
            for c in sorted((c for c in cells if c["r"] == ri), key=lambda c: c["c"]):
                tc = sub(tr, "hp:tc", name="", header=1 if ri in heads else 0, hasMargin=0, protect=0, editable=0,
                         dirty=0, borderFillIDRef=self.hx.cell_bf)
                va = VALIGN.get(wval(c["tc"].find(f"{w('tcPr')}/{w('vAlign')}"), "top") or "top", "TOP")
                sl = sub(tc, "hp:subList", id="", textDirection="HORIZONTAL", lineWrap="BREAK", vertAlign=va,
                         linkListIDRef=0, linkListNextIDRef=0, textWidth=0, textHeight=0, hasTextRef=0, hasNumRef=0)
                for p in self.blocks(c["tc"], rels, outline=False) or [self.hx.para()]:
                    if p.find(q("hp:run")) is None:
                        self.hx.run(p, self.hx.cp0)
                    sl.append(p)
                sub(tc, "hp:cellAddr", colAddr=c["c"], rowAddr=ri)
                sub(tc, "hp:cellSpan", colSpan=c["cs"], rowSpan=c["rs"])
                sub(tc, "hp:cellSz", width=sum(grid[c["c"]:c["c"] + c["cs"]]), height=sum(heights[ri:ri + c["rs"]]))
                sub(tc, "hp:cellMargin", **mar)
        return t

    @staticmethod
    def lines(tc):
        n = 0
        for p in tc.iter(w("p")):
            n += 1 + sum(1 for b in p.iter(w("br")) if b.get(w("type")) not in ("page", "column"))
        return max(n, 1)

    # --- 머리말
    def header_ctrl(self, part, template_header, hid):
        h = copy.deepcopy(template_header)
        h.set("id", str(hid))
        sl = h.find(q("hp:subList"))
        for p in sl.findall(q("hp:p")):
            sl.remove(p)
        root = self.dx.xml(part)
        for p in self.blocks(root, self.dx.rels_of(part), outline=False) or [self.hx.para()]:
            if p.find(q("hp:run")) is None:
                self.hx.run(p, self.hx.cp0)
            sl.append(p)
        ft.strip_layout(h)
        return h


def flatten(body):
    """본문 블록(문단·표)을 차례대로 — 내용 컨트롤(sdt) 안 블록도 펼친다."""
    out = []
    for el in body:
        tag = local(el)
        if tag in ("p", "tbl"):
            out.append(el)
        elif tag == "sdt" and el.find(w("sdtContent")) is not None:
            out += flatten(el.find(w("sdtContent")))
        elif tag == "customXml":
            out += flatten(el)
    return out


def set_page(sec_pr, sect):
    """docx 구역의 용지·여백 → HWPX 구역 설정. Word 위 여백 = 머리말 거리 + 머리말 영역(한글은 둘을 따로 적는다)."""
    pg = sec_pr.find(q("hp:pagePr"))
    sz, mg = sect.find(w("pgSz")), sect.find(w("pgMar"))
    if sz is not None:
        pg.set("width", str(int(sz.get(w("w"))) * TWIP))
        pg.set("height", str(int(sz.get(w("h"))) * TWIP))
        pg.set("landscape", "NARROWLY" if sz.get(w("orient")) == "landscape" else "WIDELY")
    if mg is not None:
        g = {k: int(mg.get(w(k), "0") or 0) * TWIP for k in ("top", "bottom", "left", "right", "header", "footer", "gutter")}
        m = pg.find(q("hp:margin"))
        vals = {"left": g["left"], "right": g["right"], "gutter": g["gutter"],
                "top": g["header"], "header": max(abs(g["top"]) - g["header"], 0),
                "bottom": g["footer"], "footer": max(abs(g["bottom"]) - g["footer"], 0)}
        for k, v in vals.items():
            m.set(k, str(v))
        pg.set("gutterType", "LEFT_ONLY")


def convert(src: Path, dst: Path, base: ft.Pkg, vpkg: ft.Pkg = None) -> dict:
    """docx → 원고 HWPX. 돌려주는 값: 변환 기록(개수·글자 대조)."""
    dx = Docx(src)
    hx = Hwpx(base)
    cv = Converter(dx, hx)
    body = dx.doc.find(w("body"))
    blocks = flatten(body)
    sects, starts = [], [0]
    for k, el in enumerate(blocks):
        sp = el.find(f"{w('pPr')}/{w('sectPr')}") if local(el) == "p" else None
        if sp is not None:
            sects.append(sp)
            starts.append(k + 1)
    if body.find(w("sectPr")) is not None:
        sects.append(body.find(w("sectPr")))
    starts = starts[:len(sects)] or [0]
    outs = [cv.paragraph(el, dx.rels) if local(el) == "p" else cv.table_para(el, dx.rels) for el in blocks]
    if not outs:
        raise SystemExit(f"docx 본문이 비어 있다: {src}")

    sec = copy.deepcopy(base.sections[0])
    for p in sec.findall(q("hp:p")):
        sec.remove(p)
    first = copy.deepcopy(base.paras()[0])
    runs = first.findall(q("hp:run"))
    keep = next(r for r in runs if r.find(q("hp:secPr")) is not None)
    for r in runs:
        if r is not keep:
            first.remove(r)
    for c in [c for c in keep if local(c) == "t"]:
        keep.remove(c)
    ft.strip_layout(first)
    sp = first.find(f".//{q('hp:secPr')}")
    sp.set("outlineShapeIDRef", hx.outline)
    sp.find(q("hp:startNum")).set("page", "1")
    if sects:
        set_page(sp, sects[0])
    tmpl_hdr = base.sections[0].find(f".//{q('hp:header')}")
    # 첫 문단 = 바탕 양식의 구역 설정 문단 + docx 첫 문단의 모양·글자
    first.set("paraPrIDRef", outs[0].get("paraPrIDRef"))
    first.set("styleIDRef", outs[0].get("styleIDRef"))
    for r in outs[0].findall(q("hp:run")):
        first.append(r)
    cv.checks = [(a, b, first if p is outs[0] else p) for a, b, p in cv.checks]
    outs[0] = first
    hdr_part, n_hdr = None, 0
    for k, (s, sect) in enumerate(zip(starts, sects)):
        ref = next((h for h in sect.findall(w("headerReference")) if h.get(w("type"), "default") == "default"), None)
        if ref is not None:  # 머리말을 안 적은 구역은 앞 구역 머리말을 이어 쓴다(Word 규칙)
            hdr_part = dx.rels.get(ref.get(f"{{{REL}}}id"), (None, None))[1]
        if s >= len(outs):
            continue
        if k:
            outs[s].set("pageBreak", "1")
        if hdr_part and tmpl_hdr is not None:
            n_hdr += 1
            run = etree.Element(q("hp:run"))
            run.set("charPrIDRef", hx.cp0)
            sub(run, "hp:ctrl").append(cv.header_ctrl(hdr_part, tmpl_hdr, n_hdr))
            p = outs[s]
            runs = p.findall(q("hp:run"))
            after = runs[1:] if p is first else runs  # 첫 문단은 구역 설정 run 뒤에
            if after:
                p.insert(list(p).index(after[0]), run)
            else:
                p.append(run)
    for p in outs:
        sec.append(p)
    ft.strip_layout(sec)

    # 글자 대조: docx 문단 글자 = 변환 문단 글자(앞에 붙인 자동 번호 제외)
    diffs = []
    for want, label, p in cv.checks:
        got = own_text(p)
        if label and got.startswith(label):
            got = got[len(label):]
        if got != want:
            diffs.append((want[:40], got[:40]))
    write(dst, hx, sec, vpkg or base, outs)
    return {"구역": len(sects), "머리말": n_hdr, "블록": len(outs), "문단(셀 안 포함)": len(cv.checks),
            "기록": dict(cv.log), "글자 대조 차이": diffs, "그림": len(hx.bins.items)}


def write(dst: Path, hx: Hwpx, sec, vpkg: ft.Pkg, outs):
    base = hx.base
    hx.dst.header.set("secCnt", "1")
    hx.dst.header.set("version", vpkg.header.get("version"))
    ctx = SimpleNamespace(base=base, bins=hx.bins)
    title = next((s for p in outs if (s := own_text(p).strip())), "")[:80]
    prv = "\r\n".join(s for p in outs if (s := own_text(p).strip()))[:1000]
    parts = [("version.xml", vpkg.z.read("version.xml"), False),
             ("Contents/header.xml", ft.tostr(hx.dst.header), False),
             ("Contents/section0.xml", ft.tostr(sec), False)]
    parts += [(b["href"], b["data"], False) for b in hx.bins.items]
    parts += [("Preview/PrvText.txt", prv.encode("utf-8"), False),
              ("settings.xml", base.z.read("settings.xml"), False),
              ("META-INF/container.rdf", ft.build_rdf(ctx, 1), False),
              ("Contents/content.hpf", ft.build_hpf(ctx, 1, title), False),
              ("META-INF/container.xml", base.z.read("META-INF/container.xml"), False),
              ("META-INF/manifest.xml", base.z.read("META-INF/manifest.xml"), False)]
    dst.parent.mkdir(parents=True, exist_ok=True)
    now = time.localtime()[:6]
    tmp = dst.with_name(dst.name + ".tmp")
    with zipfile.ZipFile(tmp, "w") as zo:
        zo.writestr(zipfile.ZipInfo("mimetype", date_time=now), base.z.read("mimetype"), compress_type=zipfile.ZIP_STORED)
        for name, data, store in parts:
            zo.writestr(zipfile.ZipInfo(name, date_time=now), data,
                        compress_type=zipfile.ZIP_STORED if store else zipfile.ZIP_DEFLATED)
    tmp.replace(dst)


def report_md(src: Path, dst: Path, rep: dict) -> str:
    L = [f"# docx 변환 기록 — {src.name}", "", f"- 결과: `{dst.name}` (한글 없이 docx_hwpx.py로 변환, {time.strftime('%Y-%m-%d %H:%M')})",
         f"- 구역 {rep['구역']}개(머리말 {rep['머리말']}개), 본문 블록 {rep['블록']}개, 문단 {rep['문단(셀 안 포함)']}개(표 셀 안 포함), 그림 {rep['그림']}개",
         "", "## 옮긴 것·옮기지 않은 것", ""]
    L += [f"- {k}: {v}" for k, v in sorted(rep["기록"].items())] or ["- (없음)"]
    d = rep["글자 대조 차이"]
    L += ["", "## 글자 대조(docx 문단 글자 = 변환 문단 글자, 붙인 자동 번호 제외)", "",
          f"- {'✅ 차이 0' if not d else f'❌ 차이 {len(d)}건'}"]
    L += [f"  - docx '{a}' / 변환 '{b}'" for a, b in d[:20]]
    return "\n".join(L) + "\n"
