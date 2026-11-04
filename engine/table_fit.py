"""표가 쪽을 넘지 않게: 표 높이 어림(한글 없이)과 쪽 나눔 설정.

한글은 표 행 높이를 파일에 '최소 높이'로만 적고(셀 cellSz), 실제 높이는 열 때 글자에 맞춰 다시 잰다.
그래서 높이는 셀 글자를 직접 줄로 나눠 어림한다 — 글자 크기·상대 크기·장평·자간, 칸 너비·안 여백,
문단 여백·첫 줄 들여쓰기, 줄 간격, 줄 나눔 단위(어절/글자), 칸 안 그림·표.

한글이 저장한 파일의 줄 배치 정보(linesegarray)로 맞춰 본 결과(2026-11-03, 셀 문단 약 6,000개·표 110여 개):
- 줄 수가 같은 문단 95~100 %, 어긋나면 대개 1줄 많게(높게) 어림한다.
- 글자처럼 취급한 표가 든 줄 높이(한글 vertsize)와 쪽에서 차지할 높이 어림이 글자 표는 같거나 조금 크다.
- 줄 높이 = 글자 크기 × 줄 간격 %(vertsize = 글자 크기, spacing = 나머지). 셀·캡션 맨 끝 줄은 줄 간격 몫을 빼고 센다.
- 글자처럼 취급 그림만 있는 줄: 높이 = 그림 높이, 줄 간격 몫은 문단 글자 크기로(다음 줄이 있으면 더한다).
- 자리 차지로 떠 있는 그림은 그 아래로 문단 줄(빈 줄이라도)이 이어진다. 글 앞으로·뒤로 개체는 자리를 차지하지 않는다.
- 한글 파일의 줄 나눔 단위는 이름과 반대: breakNonLatinWord "BREAK_WORD" = 어절, "KEEP_WORD" = 글자.
  영어 단위는 이름대로: breakLatinWord "KEEP_WORD" = 단어, "HYPHENATION" = 하이픈, "BREAK_WORD" = 글자
  (2026-11-04 한글 2020: 자동화 API로 '글자'를 넣어 저장한 값과 PDF의 줄 끊김으로 확인 → BREAK_LATIN·BREAK_NON_LATIN).
  어림에서 이어진 영어는 영어 단위와 상관없이 한 묶음으로 센다(크게 어림 — para_lines 참고).

쪽 나눔(한글 PDF로 확인, 2026-11-03):
- '글자처럼 취급'(treatAsChar=1) 표는 쪽 경계에서 나뉘지 않는다 → 쪽보다 길면 아래가 꼬리말 쪽으로 넘친다.
  한 쪽 안에 들어가면 쪽 끝에 걸릴 때 통째로 다음 쪽으로 넘어간다(넘치지 않음).
- 나뉘려면 글자처럼 취급을 끄고 본문과의 배치를 '자리 차지'(textWrap TOP_AND_BOTTOM)로.
- pageBreak 값도 이름과 반대: "CELL" = 한글 [표] 탭 '쪽 경계에서: 나눔'(행 중간에서도 나뉨),
  "TABLE" = '셀 단위로 나눔'(행을 통째로 다음 쪽으로), "NONE" = '나누지 않음'.
- '셀 단위로 나눔'은 한 행(+ 반복되는 머리행)이 쪽보다 길면 그 행이 쪽 아래로 넘친다 → 그런 표는 '나눔'으로.
"""
from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
OBJ_TAGS = {"tbl", "pic", "container", "ole", "equation", "rect", "ellipse", "line", "arc", "polygon", "curve",
            "connectLine", "textart", "video", "chart"}

# 한 쪽을 넘는 표만 나눈다(사용자 결정 2026-11-03). 어림 오차(맞춰 본 표 270여 개에서 최대 0.2 %)에 여유를 둬
# 쪽에서 차지할 높이가 본문 높이의 99 %를 넘으면 '한 쪽을 넘는 표'로 본다 — 쪽 넘침은 절대 안 되므로.
FIT = 0.99
PAGE_BREAK = {"나눔": "CELL", "셀 단위로 나눔": "TABLE"}  # 설문 답(한글 메뉴 이름) → pageBreak 값
PAGE_BREAK_NAME = {v: k for k, v in PAGE_BREAK.items()}
# 문단 모양 [기본] 탭 '줄 나눔 기준'(한글 메뉴 이름) → hh:breakSetting 값. 한글 단위는 이름과 반대로 저장된다.
BREAK_LATIN = {"단어": "KEEP_WORD", "하이픈": "HYPHENATION", "글자": "BREAK_WORD"}  # breakLatinWord(영어 단위)
BREAK_NON_LATIN = {"어절": "BREAK_WORD", "글자": "KEEP_WORD"}  # breakNonLatinWord(한글 단위)


def _q(ns, n):
    return f"{{{ns}}}{n}"


def _local(e):
    return etree.QName(e).localname if isinstance(e.tag, str) else ""


def _s32(v) -> int:
    """HWPX 위치 값(부호 없는 32비트로 적힌 음수) → 정수."""
    v = int(v or 0)
    return v - (1 << 32) if v >= (1 << 31) else v


# 글자 너비(글자 크기에 대한 비율) — 한글 글꼴 기준 어림. 공백은 반 글자(한양·휴먼 계열 글꼴로 맞춰 봄)
_ASCII_W = {" ": 0.5, ".": 0.28, ",": 0.28, ":": 0.28, ";": 0.28, "!": 0.3, "|": 0.3, "'": 0.25, '"': 0.4,
            "(": 0.35, ")": 0.35, "[": 0.35, "]": 0.35, "{": 0.4, "}": 0.4, "-": 0.36, "/": 0.4, "\\": 0.4,
            "%": 0.85, "&": 0.75, "@": 0.9, "#": 0.6, "~": 0.6, "+": 0.6, "=": 0.6, "<": 0.6, ">": 0.6,
            "*": 0.5, "_": 0.5, "?": 0.5, "^": 0.5, "$": 0.55, "`": 0.3}


def char_kind(ch: str) -> str:
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
        return "hangul"
    if o < 0x80:
        return "latin"
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF:
        return "hanja"
    if 0x3040 <= o <= 0x30FF:
        return "japanese"
    if o < 0x250 or 0x370 <= o <= 0x52F:  # 라틴 확장·그리스·키릴
        return "latin"
    return "symbol"


def char_em(ch: str, kind: str) -> float:
    if kind in ("hangul", "hanja", "japanese"):
        return 1.0
    if kind == "latin":
        if ch in _ASCII_W:
            return _ASCII_W[ch]
        if ch.isdigit():
            return 0.55
        if "A" <= ch <= "Z":
            return 0.66
        if "a" <= ch <= "z":
            return 0.62 if ch in "mw" else 0.27 if ch in "ijlft" else 0.5
        if ch in "²³¹°":
            return 0.35
        if ch == "·":
            return 0.5
        return 0.6
    o = ord(ch)
    if 0x2000 <= o <= 0x206F:  # 일반 문장 부호(‘’“”–— 등)
        return 1.0 if ch in "※…‥—" else 0.5
    if 0xFF61 <= o <= 0xFFDC:  # 반각
        return 0.5
    return 1.0  # 기호(①○□※㎡∼ 등)는 한글 글꼴에서 대개 전각


class Metrics:
    """헤더(hh:head)의 글자·문단 모양으로 문단·셀·표 높이를 어림한다(HWPUNIT)."""

    def __init__(self, header):
        self.cp = {e.get("id"): e for e in header.iter(_q(HH, "charPr"))}
        self.pp = {e.get("id"): e for e in header.iter(_q(HH, "paraPr"))}
        self._c, self._p = {}, {}

    def char(self, cid):
        if cid not in self._c:
            e = self.cp.get(cid)
            size = int(e.get("height")) if e is not None else 1000
            info = {}
            for k in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user"):
                def g(tag, d):
                    x = e.find(_q(HH, tag)) if e is not None else None
                    return int(x.get(k, d)) if x is not None else int(d)
                info[k] = (size * g("relSz", 100) / 100, g("ratio", 100) / 100, g("spacing", 0) / 100)
            self._c[cid] = (size, info)
        return self._c[cid]

    def para(self, pid):
        if pid not in self._p:
            e = self.pp.get(pid)
            d = {"left": 0, "right": 0, "intent": 0, "prev": 0, "next": 0, "ls_type": "PERCENT", "ls": 160,
                 "word_hangul": False}
            if e is not None:
                bs = e.find(_q(HH, "breakSetting"))
                if bs is not None:  # 한글 단위는 이름과 반대(BREAK_WORD = 어절). 영어 단위는 보지 않는다 — para_lines 참고
                    d["word_hangul"] = bs.get("breakNonLatinWord", BREAK_NON_LATIN["글자"]) == BREAK_NON_LATIN["어절"]
                sw = e.find(_q(HP, "switch"))
                case = sw.find(_q(HP, "case")) if sw is not None else None
                src, scale = (case, 1.0) if case is not None else ((sw.find(_q(HP, "default")) if sw is not None else e), 0.5)
                m = src.find(_q(HH, "margin")) if src is not None else None
                for k in ("left", "right", "intent", "prev", "next"):
                    x = m.find(_q(HC, k)) if m is not None else None
                    if x is not None:
                        d[k] = int(int(x.get("value")) * scale)
                ls = src.find(_q(HH, "lineSpacing")) if src is not None else None
                if ls is None:
                    ls = e.find(f".//{_q(HH, 'lineSpacing')}")
                if ls is not None:
                    d["ls_type"] = ls.get("type", "PERCENT")
                    v = int(ls.get("value", "160"))
                    d["ls"] = v if d["ls_type"] == "PERCENT" else int(v * scale)
            self._p[pid] = d
        return self._p[pid]

    @staticmethod
    def line_pitch(h, pd):
        t, v = pd["ls_type"], pd["ls"]
        if t == "PERCENT":
            return h * v / 100
        if t == "FIXED":
            return v
        if t == "BETWEEN_LINES":
            return h + v
        return max(h, v)  # AT_LEAST

    def para_lines(self, p, width):
        """문단 → (글자 줄마다 가장 큰 글자 높이 목록, 문단 모양, 개체 정보, 첫 글자 크기).
        개체 정보: inline = 글자처럼 취급 개체를 줄 너비로 묶은 줄 높이 목록, float = 자리 차지 개체 높이 합,
        floor = 어울림 개체 아래 끝(문단이 적어도 그만큼)."""
        pd = self.para(p.get("paraPrIDRef"))
        avail = max(width - pd["left"] - pd["right"], 600)
        first_w = avail - max(pd["intent"], 0)
        rest_w = avail - max(-pd["intent"], 0)
        chars = []  # (글자, 너비, 높이)
        inline, float_h, floor = [], 0, 0
        base_size = None
        for run in p.findall(_q(HP, "run")):
            size, info = self.char(run.get("charPrIDRef"))
            base_size = base_size or size
            for el in run:
                n = _local(el)
                if n == "t":
                    pieces = [el.text or ""]
                    for c in el:
                        cn = _local(c)
                        pieces.append(("\t" if cn == "tab" else "\n" if cn == "lineBreak" else
                                       " " if cn in ("nbSpace", "fwSpace") else "") + (c.tail or ""))
                    for ch in "".join(pieces):
                        if ch in "\t\n":
                            chars.append((ch, size * 2 if ch == "\t" else 0, size))
                            continue
                        k = char_kind(ch)
                        fs, ratio, sp = info.get(k, info["hangul"])
                        chars.append((ch, fs * char_em(ch, k) * ratio + size * sp, fs))
                elif n in OBJ_TAGS:
                    w, h = obj_box(el, self)
                    pos = el.find(_q(HP, "pos"))
                    wrap = el.get("textWrap", "TOP_AND_BOTTOM")
                    if pos is None or pos.get("treatAsChar") == "1":
                        inline.append((w, h))
                    elif wrap in ("IN_FRONT_OF_TEXT", "BEHIND_TEXT"):  # 글 앞으로·뒤로: 자리를 차지하지 않는다
                        continue
                    else:
                        off = _s32(pos.get("vertOffset", "0")) if pos.get("vertRelTo") == "PARA" else 0
                        if wrap == "TOP_AND_BOTTOM":  # 자리 차지: 개체 아래로 문단 줄이 이어진다
                            float_h += max(off, 0) + h
                        else:  # 어울림 등: 글이 옆으로 흐른다 → 문단이 적어도 개체 아래 끝까지
                            floor = max(floor, off + h)
        obj_lines, cur, line_h = [], 0, 0  # 글자처럼 취급 개체는 줄 너비만큼 한 줄에, 줄 높이는 가장 큰 개체
        for w, h in inline:
            if cur and cur + w > avail:
                obj_lines.append(line_h)
                cur, line_h = 0, 0
            cur, line_h = cur + w, max(line_h, h)
        if line_h:
            obj_lines.append(line_h)
        base_size = base_size or 1000
        # 나눔 단위: 한글 어절이면 공백 사이 글자 묶음, 글자면 한 글자씩. 이어진 영어는 영어 단위가 '글자'여도 늘 묶음 —
        # 한글은 그때 영어를 줄 끝까지 꽉 채우는데, 영어 글자 너비 어림이 조금만 작아도 줄이 모자라게 센다(2026-11-04 한글 2020:
        # 긴 경로·주소를 넣은 칸 문단 277개 중 글자로 세면 3개가 1줄 적게, 묶어 세면 적게 센 것 0개). 쪽 넘침은 절대 안 되므로.
        units = []
        for c in chars:
            if c[0] in " \t\n":
                units.append((c[0], [c]))
            elif units and units[-1][0] == "w" and (
                    pd["word_hangul"] or (char_kind(c[0]) == "latin" and char_kind(units[-1][1][-1][0]) == "latin")):
                units[-1][1].append(c)
            else:
                units.append(("w", [c]))
        lines = []
        cur_w, cur_h, line_w = 0.0, 0, first_w

        def newline():
            nonlocal cur_w, cur_h, line_w
            lines.append(cur_h or base_size)
            cur_w, cur_h, line_w = 0.0, 0, rest_w

        for kind, cs in units:
            if kind == "\n":
                newline()
                continue
            if kind != "w":  # 공백·탭: 줄 끝에서는 넘쳐도 줄을 바꾸지 않는다
                if cur_w + cs[0][1] <= line_w:
                    cur_w += cs[0][1]
                continue
            uw, uh = sum(c[1] for c in cs), max(c[2] for c in cs)
            if cur_w + uw <= line_w:
                cur_w, cur_h = cur_w + uw, max(cur_h, uh)
                continue
            if cur_w > 0:
                newline()
            if uw <= line_w:
                cur_w, cur_h = uw, uh
                continue
            for _, w, h in cs:  # 한 줄보다 긴 묶음은 글자 단위로
                if cur_w + w > line_w and cur_w > 0:
                    newline()
                cur_w, cur_h = cur_w + w, max(cur_h, h)
        if cur_w > 0 or not lines:
            lines.append(cur_h or base_size)
        has_text = any(c[0] not in " \t\n" for c in chars)
        return lines, pd, {"inline": obj_lines, "float": float_h, "floor": floor, "text": has_text}, base_size

    def para_height(self, p, width):
        """(높이, 줄 수, 마지막 줄의 줄 간격 몫) — 마지막 몫은 셀·캡션 맨 끝 문단이면 빼고 센다."""
        lines, pd, obj, base = self.para_lines(p, width)
        extra = max(self.line_pitch(base, pd) - base, 0)  # 줄 간격 몫(글자 크기 기준)
        if obj["inline"] and not obj["text"]:  # 글자처럼 취급 개체만 있는 문단: 줄 높이 = 개체 높이
            body = sum(obj["inline"]) + extra * len(obj["inline"])
            n, last = len(obj["inline"]), extra
        else:
            pitch = [self.line_pitch(h, pd) for h in lines]
            body = sum(pitch) + sum(obj["inline"]) + extra * len(obj["inline"])
            n, last = len(lines) + len(obj["inline"]), max(pitch[-1] - lines[-1], 0)
        h = max(pd["prev"] + obj["float"] + body + pd["next"], obj["floor"])
        return h, n, last

    def paras_height(self, ps, width):
        """여러 문단 높이 — 한글은 셀·캡션 맨 끝 줄의 줄 간격 몫을 높이에 넣지 않는다."""
        hs = [self.para_height(p, width) for p in ps]
        return sum(h[0] for h in hs) - (hs[-1][2] if hs else 0)

    def cell_height(self, tc, tbl):
        ms = tc.find(_q(HP, "cellMargin")) if tc.get("hasMargin") == "1" else None
        if ms is None:
            ms = tbl.find(_q(HP, "inMargin"))
        m = {k: int(ms.get(k, "0")) for k in ("left", "right", "top", "bottom")} if ms is not None else \
            {"left": 510, "right": 510, "top": 141, "bottom": 141}
        w = int(tc.find(_q(HP, "cellSz")).get("width")) - m["left"] - m["right"]
        return m["top"] + self.paras_height(tc.find(_q(HP, "subList")).findall(_q(HP, "p")), w) + m["bottom"]

    def table_rows(self, tbl):
        """행 높이 어림 목록. 셀에 적힌 높이는 최소 높이로 본다(한글은 내용에 맞춰 늘린다)."""
        n = int(tbl.get("rowCnt"))
        rows = [0] * n
        spans = []
        for tr in tbl.findall(_q(HP, "tr")):
            for tc in tr.findall(_q(HP, "tc")):
                a, s = tc.find(_q(HP, "cellAddr")), tc.find(_q(HP, "cellSpan"))
                r, rs = int(a.get("rowAddr")), int(s.get("rowSpan"))
                need = max(self.cell_height(tc, tbl), int(tc.find(_q(HP, "cellSz")).get("height")))
                if rs == 1:
                    rows[r] = max(rows[r], need)
                else:
                    spans.append((r, rs, need))
        for r, rs, need in sorted(spans, key=lambda x: x[1]):
            have = sum(rows[r:r + rs])
            if need > have:
                rows[min(r + rs, n) - 1] += need - have
        return rows

    def table_height(self, tbl):
        """(표 높이 = 행 합 + 캡션 + 바깥 여백, 행 높이 목록) — 글자처럼 취급이면 한글 줄 높이(vertsize)와 같다."""
        rows = self.table_rows(tbl)
        body = sum(rows)
        cap = tbl.find(_q(HP, "caption"))
        if cap is not None:
            ps = cap.find(_q(HP, "subList")).findall(_q(HP, "p"))
            if cap.get("side") in ("LEFT", "RIGHT"):  # 옆 캡션: 표 옆에 놓여 높이를 더하지 않는다(더 길면 그만큼)
                body = max(body, self.paras_height(ps, int(cap.get("width") or 8504)))
            else:  # 위·아래 캡션: lastWidth가 0이면 표 너비로
                cw = int(cap.get("lastWidth") or 0) or int(tbl.find(_q(HP, "sz")).get("width"))
                body += int(cap.get("gap", "850")) + self.paras_height(ps, cw)
        om = tbl.find(_q(HP, "outMargin"))
        out = int(om.get("top", "0")) + int(om.get("bottom", "0")) if om is not None else 0
        return body + out, rows

    def page_height(self, tbl):
        """쪽에서 차지할 높이 = 표 높이 + 표를 담은 문단의 위·아래 간격 + 그 줄의 줄 간격 몫. (높이, 행 높이 목록)"""
        total, rows = self.table_height(tbl)
        run = tbl.getparent()
        p = run.getparent() if run is not None else None
        if p is not None and _local(p) == "p":
            pd = self.para(p.get("paraPrIDRef"))
            size = self.char(run.get("charPrIDRef"))[0]
            total += pd["prev"] + pd["next"] + max(self.line_pitch(size, pd) - size, 0)
        return total, rows


def obj_box(el, metrics=None):
    """개체가 차지하는 (너비, 높이) — 바깥 여백 포함. 표는 어림한 높이와 적힌 높이 중 큰 것."""
    sz = el.find(_q(HP, "sz"))
    w = int(sz.get("width")) if sz is not None else 0
    h = int(sz.get("height")) if sz is not None else 0
    om = el.find(_q(HP, "outMargin"))
    ml = int(om.get("left", "0")) + int(om.get("right", "0")) if om is not None else 0
    mt = int(om.get("top", "0")) + int(om.get("bottom", "0")) if om is not None else 0
    if metrics is not None and _local(el) == "tbl" and el.find(_q(HP, "tr")) is not None:
        return w + ml, max(h + mt, metrics.table_height(el)[0])  # table_height에는 캡션·바깥 여백이 들어 있다
    return w + ml, h + mt


def head_rows(tbl) -> int:
    """머리행 수(첫 행 셀이 걸친 행 수)."""
    tr = tbl.find(_q(HP, "tr"))
    if tr is None:
        return 0
    return max(int(tc.find(_q(HP, "cellSpan")).get("rowSpan")) for tc in tr.findall(_q(HP, "tc")))


def repeats_header(tbl) -> bool:
    return tbl.get("repeatHeader") == "1" and any(
        tc.get("header") == "1" for tr in tbl.findall(_q(HP, "tr")) for tc in tr.findall(_q(HP, "tc")))


def row_too_tall(rows, head: int, repeat: bool, limit: float) -> bool:
    """'셀 단위로 나눔'(행 통째)이면 넘치는가: 다음 쪽에 반복되는 머리행 + 가장 긴 본문 행 > 본문 높이(여유 FIT)."""
    body = rows[head:] or rows
    top = sum(rows[:head]) if repeat else 0
    return top + max(body) > FIT * limit


def top_tables(sec):
    """구역의 본문 표(셀 안 표, 머리말·꼬리말·글상자 안 표는 뺀다)."""
    out = []
    for p in sec.findall(_q(HP, "p")):
        for run in p.findall(_q(HP, "run")):
            out += [o for o in run if _local(o) == "tbl"]
    return out


def has_text(tbl) -> bool:
    """칸 문단에 글자가 있는 표(칸 안 표 포함). 그림과 그 위 글상자 이름표만 담은 그림 틀은 나눠도 소용없어 뺀다."""
    for tr in tbl.findall(_q(HP, "tr")):
        for tc in tr.findall(_q(HP, "tc")):
            for p in tc.find(_q(HP, "subList")).findall(_q(HP, "p")):
                for run in p.findall(_q(HP, "run")):
                    for el in run:
                        n = _local(el)
                        if (n == "t" and "".join(el.itertext()).strip()) or (n == "tbl" and has_text(el)):
                            return True
    return False


def splittable(tbl) -> bool:
    pos = tbl.find(_q(HP, "pos"))
    return (pos is None or pos.get("treatAsChar") != "1") and tbl.get("pageBreak") in ("CELL", "TABLE")
