"""HWPX 서식 옮기기 엔진 — 원고 보고서(.hwpx)에 회사 양식(본문 스타일·표/그림·앞표지·차례)을 입혀 새 HWPX를 만든다.

사용: python -I -X utf8 format_transfer.py <명령> <설정.json>
  convert  설정의 '원본'(.hwp·.docx)을 한글로 열어 '원고'(.hwpx)로 저장(pyhwpx와 한글 필요, 원본은 그대로)
  analyze  원고 문단마다 역할을 붙인다 → <역할매핑>.json, <역할매핑>_분석.md        (B단계)
  apply    결과 HWPX를 만든다. 차례쪽번호.json이 있으면 차례 쪽 번호를 채운다        (C단계)
  pdf      결과를 한글로 열어 PDF로 저장한다(pyhwpx와 한글 필요)
  toc      PDF에서 차례 항목이 놓인 쪽을 찾아 차례쪽번호.json에 쓴다
  verify   패키지·글자 보존·서식 일치·PDF를 검사해 검증보고.md를 쓴다               (D단계)
  run      analyze(역할매핑이 없을 때) → apply → pdf → toc → apply → pdf → verify
  quick    한글 없이: 변환(.docx만) → analyze(없을 때) → apply → verify (PDF·차례 쪽 번호 없음 — 클로드 채팅용)

설정 파일(원고마다 하나, 경로는 설정 파일 폴더 기준)
  {"양식프로필": "양식프로필.json", "원고": "...hwpx", "역할매핑": "역할매핑.json", "역할판단": "역할_판단.json",
   "출력": "out/원고_양식적용.hwpx", "버전정보": "표그림양식", "결정": {...}}
  양식프로필(양식 묶음마다 하나): {"파일": {본문양식·표그림양식·표지양식·목차양식}, "양식역할": {역할 → 기준 문단}}
  출력 폴더에 적용로그.md, 차례항목.json, 차례쪽번호.json, 결과역할.json, 미리보기.png, <출력>.pdf, 검증보고.md가 생긴다.

결정(설정 '결정') — 기본값은 ()
  글자색 "검정"(양식 예시의 파랑·빨강 대신 스타일 글자색), 머리말글자 "원고"|"양식",
  표지 {"사업명": 글자|"원고 머리말"|"양식", "부제": 글자|"양식"}, 연속빈줄 (1), 본문쪽번호시작 (1),
  제목 다음 문단과 함께 (true), 장마다 새 쪽 (true),
  장마다 쪽 번호 새로 (false — 사용자 결정 2026-10-16: 한 파일 안에서는 쪽 번호를 이어 간다),
  장 번호 지정 ({} — 예: {"p102": 7}. 자동 번호와 다르면 그 장부터 새 구역에서 개요 번호를 새로 시작),
  캡션 직접 번호 삭제 (true — 자동 번호와 겹치는 '<그림 4-6>' 같은 글자), 캡션 앞뒤 공백 삭제 (false),
  캡션 안 본문 ("꺼냄" — 캡션 칸에 이어 친 번호 제목·긴 문단부터는 개체 뒤 본문으로. "둠"이면 캡션에 그대로),
  제목 직접 번호 삭제 (true — 번호 모양 없는 개요 문단에 글자로 친 '제4장'·'1.'·'(1)'을 지우고 양식 자동 번호로.
    글자로 친 장 번호는 '장 번호 지정'처럼 따른다), 개체 없는 캡션 ("빈 틀" — 옆에 그림이 없는 캡션 줄은 양식 빈 그림 틀 +
    아래 캡션, 표 캡션 줄은 양식 캡션 모양·번호 문단. "캡션 문단"이면 둘 다 문단. 다른 값이면 [판단 필요] — 사용자 결정 2026-10-19),
  원고 글자색 ("살림" — 원고에서 검정이 아닌 색 글자(자리표시 등)는 결과에서도 그 색. "검정"이면 모두 양식 글자색 — 사용자 결정 2026-10-19),
  줄 나눔 ("글자" — 결과의 모든 문단 모양을 '줄 나눔 기준' 한글 단위 '글자'·영어 단위 '글자'로. 어절·단어 단위면 긴 경로·주소가
    통째로 다음 줄로 넘어가 양쪽 정렬한 윗줄의 낱말 사이가 크게 벌어진다. "양식"이면 양식·원고 값 그대로 — 사용자 결정 2026-11-04)
  머리말: 원고 머리말이 한 칸에 '사업명 | 장 제목'(탭 또는 '|')이면 양식의 두 칸(사업명 ⇥ 장 제목)으로 나눠 넣는다(승인 변경으로 기록).
    원고 머리말이 없거나 공백뿐이면 '사업명 ⇥ 장 제목' — 머리말 사업명 ("양식" — "비움"이면 사업명 칸을 비움, 2026-10-26).

역할판단 파일에서 쓸 수 있는 것(문단마다): 역할, 근거, 붙일곳·캡션바꿈(캡션), 번호(장 제목 '제N장'),
  지울번호(없으면 제목으로 정한 문단의 친 번호·기호·앞 공백을 자동으로), 캡션추가(캡션 없는 표·그림에 새로 달 글자 — 사용자 승인),
  역할 "그림 문단(틀 없음)"(틀 없이 놓인 그림 → 양식 그림 틀 안, 캡션 없음).

규칙
  - 입력 파일은 읽기만 한다. XML은 lxml로만 다룬다(문자열 조합·치환·정규식으로 XML을 고치지 않는다).
  - 원고 글자는 바꾸지 않는다. 예외는 '결정'에 적힌 승인된 변경(캡션의 직접 친 번호·앞뒤 공백, 역할판단의 캡션바꿈)뿐.
  - 내용을 넣은 문단의 줄 배치 정보(linesegarray)는 지운다. 다시 압축할 때 mimetype을 첫 항목·비압축으로.
  - 원고는 구역이 하나인 것만 다룬다.

한글 동작에서 확인한 것(2026-10-16, 한글 2020)
  - 문단 여백·간격: hp:case(HwpUnitChar) 값이 실제 값, hp:default와 switch 없는 hh:margin은 2배로 저장된다.
  - 셀 안 문단에 매단 개체의 '문단 기준' 위치는 셀이 아니라 표를 담은 바깥 문단의 왼쪽 위에서 잰다.
  - 글자처럼 취급한 표는 쪽 경계에서 나뉘지 않는다 → 쪽보다 긴 표는 '자리 차지'로 바꾼다.
  - 상위 버전(version.xml)으로 적힌 파일은 열 때 경고 창이 뜨고 자동 PDF 저장이 멈출 수 있다.
  - 개요 번호는 앞 구역에서 이어 센다. 시작값은 문서 첫 구역이 가리키는 개요 번호 모양의 수준별 start에서 정해진다
    → 앞표지·차례도 본문의 개요 번호 모양을 가리키게. 구역 중간에서 새로 시작하려면 그 구역의 개요 번호 모양에
    hh:numbering@start = n(0이면 이어서) — 같은 구역 안에서는 새로 시작할 수 없다(노트 699·292).
  - pyhwpx: 숨김(visible=False)으로는 PDF 저장이 실패한다.
  - 줄 나눔 기준(2026-11-04): 한글 단위는 이름과 반대(breakNonLatinWord "KEEP_WORD" = 글자, "BREAK_WORD" = 어절),
    영어 단위는 이름대로(breakLatinWord "BREAK_WORD" = 글자, "KEEP_WORD" = 단어) — 같은 문단을 값만 바꿔 PDF로 비교.
"""
import copy
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

if str(Path(__file__).resolve().parent) not in sys.path:  # python -I로 돌려도 같은 폴더 모듈을 찾게
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import table_fit as tf  # noqa: E402

NS = {
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "opf": "http://www.idpf.org/2007/opf/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}
NONE_ID = "4294967295"
LISTS = {"borderFill": "borderFills", "charPr": "charProperties", "tabPr": "tabProperties",
         "numbering": "numberings", "bullet": "bullets", "paraPr": "paraProperties", "style": "styles"}
FIRST_ID = {"borderFill": 1, "numbering": 1, "bullet": 1}  # 나머지 목록은 0부터
LANG_ATTR = {"hangul": "HANGUL", "latin": "LATIN", "hanja": "HANJA", "japanese": "JAPANESE",
             "other": "OTHER", "symbol": "SYMBOL", "user": "USER"}
OBJ = ("tbl", "pic", "container", "rect", "ellipse", "line", "arc", "polygon", "curve", "connectLine",
       "equation", "ole", "textart", "chart")
HEADING_ROLES = ("1수준", "2수준", "3수준", "4수준", "5수준")
TEMPLATE_NUM = {1: "1.", 2: "(1)", 3: "1)", 4: "가.", 5: "(가)"}
TYPED_CAP = re.compile(r"^\s*<\s*(그림|표)\s*(\d+)?\s*(?:-\s*(\d+)\s*)?>\s*")  # 글자로 친 캡션 번호('<표 1-2>'·'<표 1>'·'< 표 >')
CONT_WORD = re.compile(r"[(（]\s*계\s*속\s*[)）]")  # 이어지는 표·그림의 제목('… (계속)') — 번호를 늘리지 않는다
TYPED_HEAD = re.compile(r"^\s*(?:\(\d+\)|\d+\)|\d+\.|\([가-힣]\)|[가-힣]\)|[①-⑳]|[○●◦□■◇◆▶▷►•·ㅇ])\s*")  # 제목으로 정한 문단의 친 번호·기호
TYPED_CHAPTER = re.compile(r"^\s*제\s*(\d+)\s*장\s*")  # 글자로 친 장 번호(번호 모양 없는 개요 1수준 문단)
HEADER_SEP = re.compile(r"\t|\s*\|\s*")  # 머리말 '사업명 | 장 제목'의 구분(탭 또는 세로줄)
TYPED = [  # 글자로 친 번호·기호(분석용)
    (r"^\(\d+\)\s", "(1)"), (r"^\d+\)\s", "1)"), (r"^\d+\.\s", "1."), (r"^\([가-힣]\)\s", "(가)"),
    (r"^[가-힣]\)\s", "가)"), (r"^[가-힣]\.\s", "가."), (r"^[①-⑳]", "①"), (r"^※", "※"),
    (r"^[-–—]\s?", "-"), (r"^[○●◦]\s?", "○"), (r"^[□■]\s?", "□"), (r"^[◇◆]\s?", "◇"),
    (r"^[▶▷►]\s?", "▶"), (r"^[•·]\s?", "·"), (r"^ㅇ\s", "ㅇ"),
]
SYMBOL_ROLE = {"※": "본문", "-": "본문"}  # 양식에 없는 기호 문단 → 바탕글과 같게(체크포인트 1·2 결정)
ALIGN = {"JUSTIFY": "양쪽", "LEFT": "왼쪽", "RIGHT": "오른쪽", "CENTER": "가운데", "DISTRIBUTE": "배분",
         "DISTRIBUTE_SPACE": "나눔"}
LS_TYPE = {"PERCENT": "글자에 따라", "FIXED": "고정 값", "BETWEEN_LINES": "여백만 지정", "AT_LEAST": "최소"}
SAMPLE = {"DIGIT": "1", "HANGUL_SYLLABLE": "가", "CIRCLED_DIGIT": "①", "CIRCLED_HANGUL_SYLLABLE": "㉮",
          "ROMAN_SMALL": "i", "ROMAN_CAPITAL": "I", "LATIN_SMALL": "a", "LATIN_CAPITAL": "A"}
MM = 283.465


NOW = {}  # 지금 하는 일(오류가 나면 service가 '어디서'를 알려 주는 데 쓴다) — step()으로 바꾼다


def step(work: str, **where):
    """지금 하는 일 기록: 작업 이름(본문·표지·차례·쪽 번호·저장 …)과 원고 문단(본문일 때)."""
    NOW.clear()
    NOW.update({"작업": work, **where})


def q(tag: str) -> str:
    p, t = tag.split(":")
    return f"{{{NS[p]}}}{t}"


def local(el) -> str:
    return el.tag.split("}", 1)[-1] if isinstance(el.tag, str) else ""


def kids(el):
    return [c for c in el if isinstance(c.tag, str)]


def canon(el) -> bytes:
    c = copy.deepcopy(el)
    c.attrib.pop("id", None)
    return etree.tostring(c, method="c14n")


def s32(v: str) -> int:
    n = int(v)
    return n - (1 << 32) if n >= (1 << 31) else n


def u32(n: int) -> str:
    return str(n & 0xFFFFFFFF)


def fmt_num(v: int, kind: str) -> str:
    if kind == "HANGUL_SYLLABLE":
        return "가나다라마바사아자차카타파하"[(v - 1) % 14]
    if kind == "CIRCLED_DIGIT":
        return chr(0x2460 + v - 1)
    if kind == "LATIN_SMALL":
        return chr(ord("a") + v - 1)
    if kind == "LATIN_CAPITAL":
        return chr(ord("A") + v - 1)
    return str(v)


def head_text(numbering, level: int, counters: dict) -> str:
    """번호 정의의 수준 모양('(^3)')에 카운터를 넣은 글자."""
    heads = {int(ph.get("level")): ph for ph in numbering.findall(q("hh:paraHead"))}

    def rep(m):
        k = int(m.group(1))
        ph = heads.get(k)
        start = int(ph.get("start", "1")) if ph is not None else 1
        return fmt_num(counters.get(k, start), ph.get("numFormat") if ph is not None else "DIGIT")
    return re.sub(r"\^(\d)", rep, heads[level].text or "")


# ======================================================================= 글자

def text_ts(p):
    """문단 자체 글자(hp:t) 사본 — 개체 안 문단은 빼고, 빈 hp:t는 건너뛴다."""
    out = []
    for r in p.findall(q("hp:run")):
        for t in r.findall(q("hp:t")):
            if (t.text or "") or len(t):
                out.append(copy.deepcopy(t))
    return out


def text_segs(p):
    """문단 자체 글자를 원고 run별로 — [(원고 charPrIDRef, [hp:t 사본...]), ...]. 원고 글자색을 살릴 때 쓴다."""
    out = []
    for r in p.findall(q("hp:run")):
        ts = [copy.deepcopy(t) for t in r.findall(q("hp:t")) if (t.text or "") or len(t)]
        if ts:
            out.append((r.get("charPrIDRef"), ts))
    return out


KEEP_CTRL = ("footNote", "endNote", "bookmark", "fieldBegin", "fieldEnd", "hiddenComment", "indexmark")


def inline_segs(p, importer):
    """text_segs와 같되 각주·미주·책갈피·필드 컨트롤과 글자처럼 놓인 개체(그림·수식 등)도 순서대로 옮긴다(원고 ID → 결과 ID).
    구역·쪽 단위 컨트롤(구역 설정·머리말·쪽 번호 등)은 옮기지 않는다."""
    out = []
    for r in p.findall(q("hp:run")):
        items = []
        for c in r:
            n = local(c)
            if n == "t" and ((c.text or "") or len(c)):
                items.append(copy.deepcopy(c))
            elif n == "ctrl" and any(local(x) in KEEP_CTRL for x in c):
                items.append(importer.copy(c))
            elif n in OBJ and n != "tbl":
                items.append(importer.copy(c))
        if items:
            out.append((r.get("charPrIDRef"), items))
    return out


def flat(segs):
    return [t for _, ts in segs for t in ts]


def plain(ts) -> str:
    s = []
    for t in ts:
        s.append(t.text or "")
        for c in t:
            s.append("\t" if local(c) == "tab" else "")
            s.append(c.tail or "")
    return "".join(s)


def own_text(p) -> str:
    return plain(text_ts(p))


CAP_AUTONUM = ("PICTURE", "TABLE", "EQUATION")
LABEL_TAIL = re.compile(r"^[>\])}〉》】.:\-–·]*\s*")


def autonum_ctrl(el) -> bool:
    a = el.find(q("hp:autoNum")) if local(el) == "ctrl" else None
    return a is not None and a.get("numType") in CAP_AUTONUM


def caption_segs(p):
    """캡션 문단 글자 조각(text_segs와 같은 꼴). 한글 캡션 자동 번호(hp:autoNum)가 있으면 번호 표시 —
    번호 앞 글자('<그림 ')와 번호 바로 뒤 닫는 글자('> '·'. ')는 빼고 제목 글자만."""
    out, seen = [], False
    for r in p.findall(q("hp:run")):
        ts = []
        for c in r:
            if autonum_ctrl(c):
                out, ts, seen = [], [], True
            elif local(c) == "t" and ((c.text or "") or len(c)):
                ts.append(copy.deepcopy(c))
        if ts:
            out.append((r.get("charPrIDRef"), ts))
    if seen:
        for _, ts in out:
            t = ts[0]
            t.text = LABEL_TAIL.sub("", t.text or "", count=1)
            break
        out = [(cid, [t for t in ts if (t.text or "") or len(t)]) for cid, ts in out]
        out = [(cid, ts) for cid, ts in out if ts]
    return out


def caption_text(p) -> str:
    return plain(flat(caption_segs(p)))


def strip_layout(root):
    """줄 배치 정보(linesegarray) 삭제 — 한글이 열 때 다시 계산한다."""
    for ls in list(root.iter(q("hp:linesegarray"))):
        ls.getparent().remove(ls)


def text_run_cid(p) -> str:
    runs = p.findall(q("hp:run"))
    for r in runs:
        if r.find(q("hp:t")) is not None:
            return r.get("charPrIDRef")
    return runs[-1].get("charPrIDRef")


def set_runs(p, cid, ts):
    """문단의 run을 모두 지우고, 글자 모양 하나짜리 run에 글자(hp:t들)를 넣는다."""
    for r in p.findall(q("hp:run")):
        p.remove(r)
    strip_layout(p)
    run = etree.SubElement(p, q("hp:run"))
    run.set("charPrIDRef", cid)
    for t in ts:
        run.append(t)
    p.set("id", "0")
    return p


def caption_norm(s: str, D: dict):
    """캡션 글자의 승인된 변경 → (새 글자, 앞에서 뺀 글자 수, 뒤에서 뺀 글자 수, 바뀐 내용). 엔진·검증이 같이 쓴다."""
    lead, changes = 0, []
    m = TYPED_CAP.match(s)
    if m and D.get("캡션 직접 번호 삭제", True):
        lead = m.end()
        changes.append(f"직접 친 번호 '{m.group(0).strip()}' 삭제(자동 번호와 겹침)")
    rest = s[lead:]
    trail = 0
    if D.get("캡션 앞뒤 공백 삭제"):
        a, b = len(rest) - len(rest.lstrip()), len(rest) - len(rest.rstrip())
        if a or b:
            lead, trail = lead + a, b
            changes.append("앞뒤 공백 삭제")
    return s[lead:len(s) - trail], lead, trail, changes


def cut_ts(ts, lead: int, trail: int) -> bool:
    """hp:t 목록의 글자를 앞에서 lead, 뒤에서 trail 글자 뺀다(탭 같은 글자 안 요소는 넘지 않음)."""
    nodes = []
    for t in ts:
        if local(t) != "t":  # 각주·개체 같은 컨트롤은 글자로 세지 않는다
            continue
        nodes.append((t, "text"))
        for c in t:
            if local(c) == "tab":
                nodes.append((c, "tab"))
            nodes.append((c, "tail"))

    def take(seq, n, from_end):
        for el, kind in seq:
            if n <= 0:
                break
            if kind == "tab":
                return n
            txt = (el.text if kind == "text" else el.tail) or ""
            k = min(n, len(txt))
            new = txt[:len(txt) - k] if from_end else txt[k:]
            if kind == "text":
                el.text = new
            else:
                el.tail = new
            n -= k
        return n
    return take(nodes, lead, False) == 0 and take(list(reversed(nodes)), trail, True) == 0


# ======================================================================= 입력 파일

class Pkg:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.z = zipfile.ZipFile(self.path)
        self.header = etree.fromstring(self.z.read("Contents/header.xml"))
        names = [n for n in self.z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)]
        names.sort(key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        self.sections = [etree.fromstring(self.z.read(n)) for n in names]
        self.hpf = etree.fromstring(self.z.read("Contents/content.hpf"))
        self.bin = {it.get("id"): it.get("href") for it in self.hpf.iter(q("opf:item"))
                    if (it.get("href") or "").startswith("BinData/")}
        self.bin_type = {it.get("id"): (it.get("media-type"), it.get("isEmbeded", "1") == "1")
                         for it in self.hpf.iter(q("opf:item")) if (it.get("href") or "").startswith("BinData/")}

    def items(self, kind: str) -> dict:
        lst = self.header.find(f".//{q('hh:' + LISTS[kind])}")
        return {e.get("id"): e for e in kids(lst)} if lst is not None else {}

    def paras(self, i: int = 0):
        return self.sections[i].findall(q("hp:p"))

    def style_named(self, name: str):
        for st in self.items("style").values():
            if st.get("name") == name:
                return st
        raise KeyError(f"{self.path.name}: 스타일 '{name}' 없음")

    def page(self, i: int = 0):
        pg = self.sections[i].find(f".//{q('hp:pagePr')}")
        return pg, {k: int(v) for k, v in pg.find(q("hp:margin")).attrib.items()}


class PartPkg(Pkg):
    """양식 파일의 한 부분(표지·차례·본문)을 '구역 하나짜리 Pkg'처럼 쓴다 — 같은 header·그림을 쓰고 문단만 고른다.
    ranges: [(구역, 처음 문단, 끝 문단), ...](끝 포함, 여러 구역이면 이어 붙임).
    부분이 구역 중간(쪽 나누기 뒤)에서 시작하면 그 구역 첫 문단의 구역 설정(secPr)·단 설정을 첫 문단 앞에 붙인다."""

    def __init__(self, src: Pkg, ranges, name: str = ""):
        self.path, self.z, self.header, self.hpf = src.path, src.z, src.header, src.hpf
        self.bin, self.bin_type, self.name = src.bin, src.bin_type, name
        s0 = ranges[0][0]
        root = copy.deepcopy(src.sections[s0])
        for p in root.findall(q("hp:p")):
            root.remove(p)
        for s, a, b in ranges:
            for p in src.sections[s].findall(q("hp:p"))[a:b + 1]:
                root.append(copy.deepcopy(p))
        first = root.find(q("hp:p"))
        if first.find(f".//{q('hp:secPr')}") is None:
            carrier = src.sections[s0].find(q("hp:p"))
            run = etree.Element(q("hp:run"))
            run.set("charPrIDRef", (first.find(q("hp:run")) if first.find(q("hp:run")) is not None
                                    else carrier.find(q("hp:run"))).get("charPrIDRef"))
            run.append(copy.deepcopy(carrier.find(f".//{q('hp:secPr')}")))
            for ctrl in carrier.iter(q("hp:ctrl")):
                if ctrl.find(q("hp:colPr")) is not None:
                    run.append(copy.deepcopy(ctrl))
            first.insert(0, run)
        first.set("pageBreak", "0")
        self.sections = [root]


class Desc:
    """header.xml을 사람이 읽을 값으로(분석·검증용)."""

    def __init__(self, header):
        self.fonts = {ff.get("lang").lower(): {f.get("id"): f.get("face") for f in ff.findall(q("hh:font"))}
                      for ff in header.iter(q("hh:fontface"))}
        self.char_prs = {c.get("id"): c for c in header.iter(q("hh:charPr"))}
        self.para_prs = {p.get("id"): p for p in header.iter(q("hh:paraPr"))}
        self.styles = {s.get("id"): s for s in header.iter(q("hh:style"))}
        self.numberings = {n.get("id"): n for n in header.iter(q("hh:numbering"))}
        self.bullets = {b.get("id"): b for b in header.iter(q("hh:bullet"))}
        self.border_fills = {b.get("id"): b for b in header.iter(q("hh:borderFill"))}

    def margin(self, pid):
        """여백·간격(pt). hp:case 값이 실제, hp:default·switch 없는 값은 2배로 저장."""
        p = self.para_prs[pid]
        sw = p.find(q("hp:switch"))
        case = sw.find(q("hp:case")) if sw is not None else None
        src, scale = (case, 1.0) if case is not None else ((sw.find(q("hp:default")) if sw is not None else p), 0.5)
        m, ls = src.find(q("hh:margin")), src.find(q("hh:lineSpacing"))
        vals = {}
        for k in ("intent", "left", "right", "prev", "next"):
            e = m.find(q(f"hc:{k}")) if m is not None else None
            vals[k] = f"{int(e.get('value')) * scale / 100:g}pt" if e is not None and e.get("unit", "HWPUNIT") == "HWPUNIT" \
                else (f"{e.get('value')}{e.get('unit')}" if e is not None else "-")
        return vals, ls

    def para_desc(self, pid) -> dict:
        p = self.para_prs[pid]
        al, hd = p.find(q("hh:align")), p.find(q("hh:heading"))
        m, ls = self.margin(pid)
        ls_txt = "-"
        if ls is not None:
            t, v = ls.get("type"), ls.get("value")
            ls_txt = f"{LS_TYPE.get(t, t)} {v}%" if t == "PERCENT" else f"{LS_TYPE.get(t, t)} {int(v) / 100:g}pt"
        heading = "없음"
        if hd is not None and hd.get("type") != "NONE":
            heading = f"{hd.get('type')} idRef={hd.get('idRef')} level={hd.get('level')}"
        return {"정렬": ALIGN.get(al.get("horizontal"), al.get("horizontal")) if al is not None else "-",
                "왼쪽": m["left"], "오른쪽": m["right"], "첫줄": m["intent"], "위": m["prev"], "아래": m["next"],
                "줄간격": ls_txt, "번호": heading}

    def char_sig(self, cid):
        c = self.char_prs[cid]
        fr, ul = c.find(q("hh:fontRef")), c.find(q("hh:underline"))
        return (self.fonts["hangul"].get(fr.get("hangul")), self.fonts["latin"].get(fr.get("latin")), c.get("height"),
                c.find(q("hh:bold")) is not None, c.find(q("hh:italic")) is not None,
                ul.get("type") if ul is not None else "NONE",
                c.find(q("hh:ratio")).get("hangul"), c.find(q("hh:spacing")).get("hangul"))

    def para_sig(self, pid):
        d = self.para_desc(pid)
        return (d["정렬"], d["왼쪽"], d["오른쪽"], d["첫줄"], d["위"], d["아래"], d["줄간격"],
                re.sub(r"idRef=\d+ ", "", d["번호"]))


# ======================================================================= 설정

class Run:
    """설정 파일 하나(원고 하나)의 경로·결정 묶음."""

    def __init__(self, cfg_path):
        self.cfg_path = Path(cfg_path).resolve()
        self.cfg = json.loads(self.cfg_path.read_text(encoding="utf-8"))
        here = self.cfg_path.parent
        prof_path = (here / self.cfg["양식프로필"]).resolve()
        self.prof = json.loads(prof_path.read_text(encoding="utf-8"))
        self.R = self.prof["양식역할"]
        if self.prof.get("부분"):  # 자동 분석 프로필(template_profile.py): 보고서 파일 안의 표지·차례·본문 부분
            self.tfiles = [(prof_path.parent / v).resolve() for v in self.prof["양식파일"]]
            self.files = {}
        else:  # 손으로 만든 프로필: 부분마다 파일 하나
            self.tfiles = []
            self.files = {k: (prof_path.parent / v).resolve() for k, v in self.prof["파일"].items()}
        self._parts = None
        self.ms_path = (here / self.cfg["원고"]).resolve()
        self.src_path = (here / self.cfg["원본"]).resolve() if self.cfg.get("원본") else None  # .hwp·.docx → 변환
        self.map_path = (here / self.cfg["역할매핑"]).resolve()
        self.judge_path = (here / self.cfg["역할판단"]).resolve() if self.cfg.get("역할판단") else None
        self.out = (here / self.cfg["출력"]).resolve()
        self.out_dir = self.out.parent
        self.pdf = self.out.with_suffix(".pdf")
        self.D = self.cfg.get("결정", {})

    def f(self, name):
        return self.out_dir / name

    def parts(self) -> dict:
        """양식 부분 → Pkg: 본문양식·표그림양식·표지양식·목차양식(없는 부분은 None)."""
        if self._parts is None:
            if not self.prof.get("부분"):
                self._parts = {k: Pkg(v) for k, v in self.files.items()}
            else:
                pk = [Pkg(f) for f in self.tfiles]
                out = {}
                for key, name in (("본문양식", "본문"), ("표지양식", "표지"), ("목차양식", "차례"), ("표그림양식", "표그림")):
                    d = self.prof["부분"].get(name)
                    out[key] = PartPkg(pk[d["파일"]], [tuple(x) for x in d["범위"]], name) if d else None
                if out["표그림양식"] is None:  # 여러 파일 양식에서 표·그림을 다른 파일에서 가져올 때만 따로(그 밖에는 본문 부분)
                    out["표그림양식"] = out["본문양식"]
                self._parts = out
        return self._parts


# ======================================================================= B. 원고 분석

def heading(desc: Desc, sec, p):
    """(종류, 수준0, 표시) — 문단 모양의 번호 설정."""
    pp = desc.para_prs.get(p.get("paraPrIDRef"))
    hd = pp.find(q("hh:heading")) if pp is not None else None
    if hd is None or hd.get("type") == "NONE":
        return None
    t, lvl = hd.get("type"), int(hd.get("level"))
    if t == "BULLET":
        b = desc.bullets.get(hd.get("idRef"))
        return t, lvl, f"글머리표 {b.get('char') if b is not None else '?'}"
    nid = sec.find(f".//{q('hp:secPr')}").get("outlineShapeIDRef") if t == "OUTLINE" else hd.get("idRef")
    ph = [x for x in desc.numberings[nid].findall(q("hh:paraHead")) if x.get("level") == str(lvl + 1)][0]
    return t, lvl, re.sub(r"\^\d", SAMPLE.get(ph.get("numFormat"), "1"), ph.text or "")


def walk(sec_root):
    """(경로, hp:p, 문맥) — 최상위 문단과 표 셀·캡션·머리말·꼬리말·글상자 안의 문단."""
    def inner(p, path, ctx):
        yield path, p, ctx
        for run in p.findall(q("hp:run")):
            for obj in run:
                name = local(obj)
                if name == "ctrl":
                    for c in obj:
                        if local(c) in ("header", "footer", "footNote", "endNote"):
                            for i, sp in enumerate(c.find(q("hp:subList")).findall(q("hp:p"))):
                                yield from inner(sp, f"{path}>{local(c)}.p{i}", local(c))
                    continue
                cap = obj.find(q("hp:caption"))
                if cap is not None:
                    for i, sp in enumerate(cap.find(q("hp:subList")).findall(q("hp:p"))):
                        yield from inner(sp, f"{path}>{name}.캡션.p{i}", "캡션")
                if name == "tbl":
                    for tr in obj.findall(q("hp:tr")):
                        for tc in tr.findall(q("hp:tc")):
                            a = tc.find(q("hp:cellAddr"))
                            for i, sp in enumerate(tc.find(q("hp:subList")).findall(q("hp:p"))):
                                yield from inner(sp, f"{path}>표[{a.get('rowAddr')},{a.get('colAddr')}].p{i}", "표셀")
                elif name in ("rect", "ellipse", "polygon", "container"):
                    dt = obj.find(f".//{q('hp:drawText')}")
                    if dt is not None:
                        for i, sp in enumerate(dt.find(q("hp:subList")).findall(q("hp:p"))):
                            yield from inner(sp, f"{path}>{name}.글상자.p{i}", "글상자")
    for i, p in enumerate(sec_root.findall(q("hp:p"))):
        yield from inner(p, f"p{i}", "본문")


def number_all(desc: Desc, sec) -> dict:
    """문서 순서대로 문단 번호를 매긴다 → {경로: '<표 1-3>'}. 번호 정의마다 수준별 카운터를 센다."""
    outline = sec.find(f".//{q('hp:secPr')}").get("outlineShapeIDRef")
    counters, out = {}, {}
    for path, p, ctx in walk(sec):
        pp = desc.para_prs.get(p.get("paraPrIDRef"))
        hd = pp.find(q("hh:heading")) if pp is not None else None
        if hd is None or hd.get("type") not in ("NUMBER", "OUTLINE"):
            continue
        nid = outline if hd.get("type") == "OUTLINE" else hd.get("idRef")
        lv = int(hd.get("level")) + 1
        cs = counters.setdefault(nid, {})
        heads = {int(ph.get("level")): ph for ph in desc.numberings[nid].findall(q("hh:paraHead"))}
        cs[lv] = cs[lv] + 1 if lv in cs else int(heads[lv].get("start", "1"))
        for k in [k for k in cs if k > lv]:
            del cs[k]
        out[path] = head_text(desc.numberings[nid], lv, cs)
    return out


def objects(p):
    return [o for r in p.findall(q("hp:run")) for o in r if local(o) in OBJ]


def para_key(key: str):
    """'p53' 또는 'p53>tbl.캡션.p3'(캡션 안에서 꺼낸 문단) → (최상위 문단 번호, 개체 이름, 캡션 안 문단 번호)."""
    m = re.fullmatch(r"p(\d+)(?:>(\w+)\.캡션\.p(\d+))?", key)
    return int(m.group(1)), m.group(2), int(m.group(3)) if m.group(3) else None


def ms_para(paras, key: str):
    """역할매핑의 문단 이름 → 원고 hp:p."""
    i, name, j = para_key(key)
    if name is None:
        return paras[i]
    obj = next(o for o in objects(paras[i]) if local(o) == name)
    return obj.find(q("hp:caption")).find(q("hp:subList")).findall(q("hp:p"))[j]


CAP_BODY_LEN = 80  # 캡션 둘째 문단부터: 번호 붙은 제목이거나 이보다 긴 글이면 본문으로 본다


def caption_split(desc: Desc, sec, cap, D: dict):
    """캡션 문단 번호를 (캡션으로 둘 것, 본문으로 꺼낼 것)으로 나눈다. 원고에서 캡션 칸에 이어 친 본문
    (캡션 뒤 '다. 수직기준면 설정' 같은 번호 제목이나 긴 문단부터 끝까지)은 개체 뒤 본문으로 꺼낸다(결정 '캡션 안 본문')."""
    ps = cap.find(q("hp:subList")).findall(q("hp:p"))
    full = [j for j, p in enumerate(ps) if own_text(p).strip()]
    every = list(range(len(ps)))
    if not full or D.get("캡션 안 본문", "꺼냄") != "꺼냄":
        return every, []
    for j in full[1:]:
        h = heading(desc, sec, ps[j])
        numbered = bool(h) and h[0] in ("NUMBER", "OUTLINE") and "그림" not in h[2] and "표" not in h[2]
        if numbered or len(own_text(ps[j]).strip()) > CAP_BODY_LEN:
            start = j
            while start - 1 > full[0] and not own_text(ps[start - 1]).strip():
                start -= 1  # 꺼낼 글 바로 앞 빈 문단도 본문 쪽 빈 줄로
            return every[:start], every[start:]
    return every, []


def caption_info(desc: Desc, sec, obj, D=None):
    cap = obj.find(q("hp:caption"))
    if cap is None:
        return None
    keep, out = caption_split(desc, sec, cap, D or {})
    allp = cap.find(q("hp:subList")).findall(q("hp:p"))
    ps = [allp[j] for j in keep]
    kind = None
    for cp in ps:
        h = heading(desc, sec, cp)
        if h and ("그림" in h[2] or "표" in h[2]):
            kind = "그림" if "그림" in h[2] else "표"
            break
        for an in cp.iter(q("hp:autoNum")):
            if an.get("numType") in ("PICTURE", "TABLE"):
                kind = "그림" if an.get("numType") == "PICTURE" else "표"
    text = " / ".join(own_text(cp).strip() for cp in ps if own_text(cp).strip())
    m = TYPED_CAP.match(text)
    if kind is None and m:
        kind = m.group(1)
    return {"위치": cap.get("side"), "종류": kind, "글자": text, "직접번호": m.group(0).strip() if m else None,
            "번호": "", "캡션문단": keep, "꺼낼문단": out}


def table_info(o):
    sz, pos = o.find(q("hp:sz")), o.find(q("hp:pos"))
    rows = o.findall(q("hp:tr"))
    spans = [int(tc.find(q("hp:cellSpan")).get("rowSpan")) for tc in rows[0].findall(q("hp:tc"))] if rows else [1]
    return {"행": int(o.get("rowCnt")), "열": int(o.get("colCnt")), "폭mm": round(int(sz.get("width")) / MM, 1),
            "높이mm": round(int(sz.get("height")) / MM, 1), "글자처럼": pos.get("treatAsChar") == "1",
            "배치": o.get("textWrap"), "그림수": len(list(o.iter(q("hp:pic")))), "머리행수": max(spans),
            "제목셀": sum(tc.get("header") == "1" for tc in o.iter(q("hp:tc")))}


def typed_prefix(text: str):
    for pat, name in TYPED:
        m = re.match(pat, text)
        if m:
            return name, m.group(0)
    return None


def emphasis(desc: Desc, p):
    """문단 안 일부만 다른 강조(굵게·기울임·밑줄·색) — 1차는 목록만."""
    runs = [(r.get("charPrIDRef"), "".join(t.text or "" for t in r.findall(q("hp:t")))) for r in p.findall(q("hp:run"))]
    runs = [(c, t) for c, t in runs if t.strip()]
    if len(runs) < 2:
        return []

    def feat(cid):
        c = desc.char_prs[cid]
        ul = c.find(q("hh:underline"))
        return (c.find(q("hh:bold")) is not None, c.find(q("hh:italic")) is not None,
                ul is not None and ul.get("type") != "NONE", c.get("textColor"))
    weight = Counter()
    for c, t in runs:
        weight[feat(c)] += len(t)
    base = weight.most_common(1)[0][0]
    out = []
    for c, t in runs:
        f = feat(c)
        if f != base:
            what = [n for n, a, b in zip(("굵게", "기울임", "밑줄"), f[:3], base[:3]) if a != b]
            if f[3] != base[3]:
                what.append(f"색{f[3]}")
            out.append(f"'{t.strip()[:20]}'({','.join(what)})")
    return out


def classify(desc: Desc, sec, key: str, p, D=None):
    text = own_text(p).strip()
    objs = objects(p)
    names = [local(o) for o in objs]
    h = heading(desc, sec, p)
    info = {"문단": key, "앞30자": text[:30], "개체": names}
    tp = typed_prefix(text)
    if tp:
        info["직접기호"] = tp[1]
    if p.find(f".//{q('hp:secPr')}") is not None and not text and not names:
        return {**info, "역할": "빈 줄", "근거": "구역 설정만 있는 첫 문단"}
    if h and h[0] in ("NUMBER", "OUTLINE") and not h[2].strip():
        # 번호 모양이 빈 개요 문단(docx에서 옮긴 원고 등): 번호를 글자로 쳤다 → 직접 친 번호로 판정, 지울 번호로 기록
        lvl, raw = h[1], own_text(p)
        ws = len(raw) - len(raw.lstrip())
        m = TYPED_CHAPTER.match(raw)
        if lvl == 0:
            if not m:
                return {**info, "역할": "[판단 필요]", "근거": "개요 1수준 문단인데 '제N장' 번호가 없음"}
            return {**info, "역할": "장 제목", "근거": f"개요 1수준 문단 + 직접 친 장 번호 '{m.group(0).strip()}'",
                    "번호": f"제{m.group(1)}장", "지울번호": m.group(0)}
        why = f"개요 수준{lvl + 1} 문단(번호 모양 없음)"
        res = {**info, "역할": f"{lvl}수준" if lvl <= 5 else "[판단 필요]", "수준": lvl}
        if tp and tp[0] not in SYMBOL_ROLE:
            res["지울번호"] = raw[:ws] + tp[1]
            why += f", 직접 친 번호 '{tp[1].strip()}' → 지우고 양식 자동 번호('{TEMPLATE_NUM.get(lvl, '?')}' 꼴)"
        else:
            why += ", 직접 친 번호 없음"
        return {**res, "근거": why}
    if h and h[0] in ("NUMBER", "OUTLINE"):
        t, lvl, shown = h
        if lvl == 0 and "장" in shown:
            return {**info, "역할": "장 제목", "근거": f"문단 번호 1수준 '{shown}'", "번호": shown}
        if "그림" in shown or "표" in shown:
            kind = "그림" if "그림" in shown else "표"
            role = f"{kind} 캡션(따로 떨어진 문단)" if not names else f"{kind} 문단"
            return {**info, "역할": role, "근거": f"{kind} 캡션 번호(자동 문단 번호)가 걸린 문단", "번호": shown}
        return {**info, "역할": f"{lvl}수준" if lvl <= 5 else "[판단 필요]",
                "근거": f"문단 번호 수준{lvl + 1} '{shown}' → 양식 '{TEMPLATE_NUM.get(lvl, '?')}'", "번호": shown,
                "수준": lvl}
    if h and h[0] == "BULLET":
        return {**info, "역할": "[판단 필요]", "근거": h[2]}
    tbls = [o for o in objs if local(o) == "tbl"]
    if tbls:
        o = tbls[0]
        ti, cap = table_info(o), caption_info(desc, sec, o, D)
        floats = [n for n in names if n in ("container", "rect", "pic", "ellipse", "line")]
        if ti["그림수"] > 0 or floats:  # 그림 판정: 그림·떠 있는 개체 → 캡션 번호 종류 → 개체 번호 종류
            is_fig, basis = True, f"{ti['행']}×{ti['열']} 표 틀 안 그림 {ti['그림수']}장"
        elif cap and cap["종류"]:
            is_fig = cap["종류"] == "그림"
            basis = f"{ti['행']}×{ti['열']} 표, 캡션 번호 종류 '{cap['종류']}'" + (" (직접 친 번호)" if cap["직접번호"] else "")
        else:
            is_fig, basis = o.get("numberingType") == "PICTURE", f"{ti['행']}×{ti['열']} 표, 개체 번호 종류 {o.get('numberingType')}"
        info.update({"표": ti, "캡션": cap, "떠있는개체": floats})
        if cap and cap.get("직접번호"):
            info["직접기호"] = cap["직접번호"]
        if is_fig:
            why = basis + (", 그림 없는 빈 틀" if ti["그림수"] == 0 and not floats else "")
            if floats:
                why += f" + 떠 있는 개체 {len(floats)}개({', '.join(sorted(set(floats)))})"
            return {**info, "역할": "그림 문단", "근거": why + f", 캡션 {cap['위치'] if cap else '없음'}"}
        return {**info, "역할": "표 문단",
                "근거": f"{basis}, 폭 {ti['폭mm']}mm, 캡션 {cap['위치'] if cap else '없음(앞 문단)'}"}
    if names:
        return {**info, "역할": "[판단 필요]", "근거": f"표 밖 개체 {names}"}
    if not text:
        return {**info, "역할": "빈 줄", "근거": "글자 없음"}
    m = TYPED_CAP.match(text)
    if m:
        info["직접기호"] = m.group(0).strip()
        return {**info, "역할": f"{m.group(1)} 캡션(따로 떨어진 문단)", "근거": f"글자로 친 캡션 번호 '{m.group(0).strip()}'"}
    if tp and tp[0] in SYMBOL_ROLE:
        return {**info, "역할": SYMBOL_ROLE[tp[0]], "근거": f"'{tp[0]}' 문단 → 바탕글과 같게(체크포인트 결정)"}
    if tp:
        return {**info, "역할": "[판단 필요]", "근거": f"직접 친 기호/번호 '{tp[1].strip()}'"}
    return {**info, "역할": "본문", "근거": "번호·기호 없는 글"}


def cmd_analyze(R: Run):
    pk = Pkg(R.ms_path)
    if len(pk.sections) != 1:
        raise SystemExit(f"구역이 {len(pk.sections)}개인 원고는 아직 지원하지 않는다")
    desc, sec = Desc(pk.header), pk.sections[0]
    judge = json.loads(R.judge_path.read_text(encoding="utf-8")) if R.judge_path and R.judge_path.exists() else {}
    nums = number_all(desc, sec)
    rows = []

    def add(key, p, moved_from=None):
        r = classify(desc, sec, key, p, R.D)
        r["스타일"] = desc.styles[p.get("styleIDRef")].get("name")
        if nums.get(key) and r["역할"] != "본문":
            r["번호"] = nums[key]
        if moved_from:
            r["꺼냄"] = moved_from
        j = judge.get(key)
        if j:
            r["규칙판정"] = r["역할"]
            r.update({k: v for k, v in j.items()})
            r["판단"] = True
            if r["역할"] in HEADING_ROLES + ("장 제목",) and "지울번호" not in j:
                # 사람이 제목으로 정한 문단: 글자로 친 번호·기호('1. '·'8.'·' ○ ')나 앞 공백은 지우고 양식 자동 번호로
                raw = own_text(p)
                m = TYPED_HEAD.match(raw) if r["역할"] != "장 제목" else TYPED_CHAPTER.match(raw)
                pre = m.group(0) if m else raw[:len(raw) - len(raw.lstrip())]
                if pre:
                    r["지울번호"] = pre
        rows.append(r)
        return r
    paras = sec.findall(q("hp:p"))
    for i, p in enumerate(paras):
        r = add(f"p{i}", p)
        cap = r.get("캡션")
        if not cap:
            continue
        cap["번호"] = next((nums[k] for j in cap["캡션문단"] if (k := f"p{i}>tbl.캡션.p{j}") in nums), "")
        for j in cap["꺼낼문단"]:  # 캡션 칸에 이어 친 본문 → 개체 바로 뒤 본문 문단으로
            key = f"p{i}>tbl.캡션.p{j}"
            add(key, ms_para(paras, key), f"p{i} {cap['종류'] or ''} 캡션 안".replace("  ", " "))
    # 따로 떨어진 캡션 → 바로 옆(표는 다음→앞, 그림은 앞→다음) 같은 종류 개체 중 캡션이 없는 것에 붙인다
    for k, r in enumerate(rows):
        m = re.match(r"(표|그림) 캡션\(따로", r["역할"])
        if not m or r.get("붙일곳"):
            continue
        kind = m.group(1)
        order = (k + 1, k - 1) if kind == "표" else (k - 1, k + 1)
        cand = [rows[j] for j in order if 0 <= j < len(rows) and rows[j]["역할"] == f"{kind} 문단"]
        free = [c for c in cand if not (c.get("캡션") and c["캡션"]["글자"])]
        if free:
            r["붙일곳"] = free[0]["문단"]
            continue
        how = R.D.get("개체 없는 캡션", "빈 틀")
        if not cand and how in ("빈 틀", "캡션 문단"):  # 예: '【그림 삽입 예정】' 다음 캡션 줄
            r["원래역할"], r["역할"] = r["역할"], f"{kind} 캡션(개체 없음)"
            r["근거"] += (f" — 옆에 {kind}이 없어 " + ("양식 빈 그림 틀 + 아래 캡션으로" if kind == "그림" and how == "빈 틀"
                                                 else "양식 캡션 모양·번호의 문단으로") + "(결정 '개체 없는 캡션')")
            continue
        r["원래역할"], r["역할"] = r["역할"], "[판단 필요]"
        r["근거"] += (f" — 옆 {cand[0]['문단']} {kind}에 이미 캡션 '{cand[0]['캡션']['글자'][:30]}'가 있어 어느 쪽을 쓸지 정해야 함"
                     if cand else f" — 붙일 {kind}이 옆에 없음")
    emph = [(path, ctx, e) for path, p, ctx in walk(sec) if (e := emphasis(desc, p))]
    R.map_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    md = R.map_path.with_name(R.map_path.stem + "_분석.md")
    L = [f"# 역할 매핑(자동) — {R.ms_path.name}", "", "| 문단 | 앞 30자 | 역할 | 근거 |", "|---|---|---|---|"]
    for r in rows:
        head = (r.get("번호", "") + " " if r.get("번호") and not r.get("지울번호") else "") + r["앞30자"]
        if not head.strip() and r["개체"]:
            head = "[" + ",".join(dict.fromkeys(r["개체"])) + "]"
        why = r["근거"] + (f" → {r['붙일곳']}의 캡션(아래)으로" if r.get("붙일곳") else "")
        if r.get("꺼냄"):
            why = f"{r['꺼냄']}에 있던 문단 → 개체 뒤 본문으로 꺼냄; " + why
        L.append(f"| {r['문단']} | {head.replace('|', '/')} | {'[판단] ' if r.get('판단') else ''}"
                 f"{'[꺼냄] ' if r.get('꺼냄') else ''}{r['역할']} | {why.replace('|', '/')} |")
    for kind in ("표", "그림"):
        L += ["", f"## {kind} 목록", "", "| 번호 | 문단 | 행×열 | 원고 캡션 | 캡션 글자 |", "|---|---|---|---|---|"]
        for r in rows:
            if r["역할"] == f"{kind} 문단":
                cap = r.get("캡션") or {}
                sep = next((x for x in rows if x.get("붙일곳") == r["문단"]), None)
                num = cap.get("번호") or cap.get("직접번호") and f"{cap['직접번호']}(직접)" or (sep or {}).get("번호") \
                    or (sep or {}).get("직접기호") and f"{sep['직접기호']}(직접)" or ""
                where = (cap.get("위치") or "") + (f" {sep['문단']} 따로" if sep else "")
                if not where and r.get("캡션추가"):
                    where = "없음 → 새로 넣음(역할판단 '캡션추가')"
                L.append(f"| {num} | {r['문단']} | {r['표']['행']}×{r['표']['열']} | {where or '없음'} | "
                         f"{(cap.get('글자') or (sep or {}).get('앞30자', '') or r.get('캡션추가', ''))[:40]} |")
            elif r["역할"] == f"{kind} 문단(틀 없음)":
                L.append(f"| | {r['문단']} | 틀 없음 | 없음 | 양식 그림 틀에 넣음(캡션 없음) |")
            elif r["역할"] == f"{kind} 캡션(개체 없음)":
                L.append(f"| {r.get('직접기호', '')}(직접) | {r['문단']} | {kind} 없음 | 캡션 줄만 | {r['앞30자']} |")
    L += ["", f"## 문단 안 부분 강조 (글자색: 결정 '원고 글자색' {R.D.get('원고 글자색', '살림')} — 살림이면 결과에도 그 색, "
              "굵게·기울임·밑줄은 목록만)", ""] + ([f"- {a} ({b}): {', '.join(c)}" for a, b, c in emph] or ["- 없음"])
    moved = [r for r in rows if r.get("꺼냄")]
    if moved:
        L += ["", f"## 캡션 칸에서 꺼낸 문단 {len(moved)}개 (결정 '캡션 안 본문': "
              f"{R.D.get('캡션 안 본문', '꺼냄')} — 캡션에 그대로 두려면 '둠')", ""]
        L += [f"- {r['문단']} ({r['역할']}): {r['앞30자'] or '(빈 줄)'}" for r in moved]
    need = [r for r in rows if r["역할"] == "[판단 필요]"]
    L += ["", f"## 판단 필요 {len(need)}건", ""] + ([f"- {r['문단']}: {r['근거']}" for r in need] or ["- 없음"])
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    cnt = Counter(r["역할"] for r in rows)
    print(f"{len(rows)} 문단 → {R.map_path.name}, {md.name}: " + ", ".join(f"{k} {v}" for k, v in cnt.most_common()))
    return need


# ======================================================================= C. 적용 — 결과 헤더

def line_break(D: dict):
    """결정 '줄 나눔' → 결과의 모든 문단 모양에 넣을 (breakLatinWord, breakNonLatinWord). "양식"이면 None(그대로)."""
    how = D.get("줄 나눔", "글자")
    if how == "양식":
        return None
    if how != "글자":
        raise SystemExit(f"결정 '줄 나눔'은 \"글자\" 또는 \"양식\"이어야 한다: {how!r}")
    return tf.BREAK_LATIN["글자"], tf.BREAK_NON_LATIN["글자"]


class Dst:
    def __init__(self, base: Pkg, line_break=None):
        """line_break: (breakLatinWord, breakNonLatinWord) — 주면 결과 헤더의 문단 모양 모두(나중에 덧붙이는 것 포함)에 넣는다."""
        self.header = copy.deepcopy(base.header)
        self.line_break = line_break
        if line_break:
            for el in self.children("paraPr"):
                self.set_line_break(el)
        self.canon = {k: {} for k in LISTS}
        for k in LISTS:
            for el in self.children(k):
                self.canon[k].setdefault(canon(el), el.get("id"))
        self.fontfaces = {ff.get("lang"): ff for ff in self.header.iter(q("hh:fontface"))}
        self.added = Counter()

    def lst(self, kind):
        lst = self.header.find(f".//{q('hh:' + LISTS[kind])}")
        if lst is None:
            raise RuntimeError(f"결과 헤더에 {LISTS[kind]} 목록이 없다(새로 만드는 기능은 아직 없음)")
        return lst

    def children(self, kind):
        lst = self.header.find(f".//{q('hh:' + LISTS[kind])}")
        return kids(lst) if lst is not None else []

    def get(self, kind, iid):
        for e in self.children(kind):
            if e.get("id") == str(iid):
                return e
        raise KeyError((kind, iid))

    def ids(self, kind):
        return {e.get("id") for e in self.children(kind)}

    def set_line_break(self, pp):
        bs = pp.find(q("hh:breakSetting"))
        if bs is None:  # 한글이 쓴 파일에는 늘 있다 — 없으면 정렬·문단 머리 다음에 만든다
            bs = etree.Element(q("hh:breakSetting"), {"breakLatinWord": "", "breakNonLatinWord": "", "widowOrphan": "0",
                                                      "keepWithNext": "0", "keepLines": "0", "pageBreakBefore": "0",
                                                      "lineWrap": "BREAK"})
            before = [e for e in pp if local(e) in ("align", "heading")]
            pp.insert(pp.index(before[-1]) + 1 if before else 0, bs)
        bs.set("breakLatinWord", self.line_break[0])
        bs.set("breakNonLatinWord", self.line_break[1])

    def add(self, kind, el, dedupe=True) -> str:
        if kind == "paraPr" and self.line_break:
            self.set_line_break(el)
        c = canon(el)
        if dedupe and c in self.canon[kind]:
            return self.canon[kind][c]
        lst, cur = self.lst(kind), self.children(kind)
        new_id = str(len(cur) + FIRST_ID.get(kind, 0))
        if any(e.get("id") == new_id for e in cur):
            raise RuntimeError(f"{kind} id가 연속이 아니라 새 id {new_id}가 겹친다")
        el.set("id", new_id)
        lst.append(el)
        lst.set("itemCnt", str(len(cur) + 1))
        self.canon[kind].setdefault(c, new_id)
        self.added[kind] += 1
        return new_id

    def style_id(self, name, type_):
        for st in self.children("style"):
            if st.get("name") == name and st.get("type") == type_:
                return st.get("id")
        return None

    def font(self, lang, f) -> str:
        ff = self.fontfaces[lang]
        fonts = ff.findall(q("hh:font"))
        for x in fonts:
            if x.get("face") == f.get("face") and x.get("type") == f.get("type"):
                return x.get("id")
        n = copy.deepcopy(f)
        n.set("id", str(len(fonts)))
        ff.append(n)
        ff.set("fontCnt", str(len(fonts) + 1))
        self.added["font"] += 1
        return n.get("id")

    def variant(self, kind, iid, fn) -> str:
        """정의를 복사해 fn으로 고친 것(같으면 재사용)."""
        n = copy.deepcopy(self.get(kind, iid))
        if fn(n) is False:
            return str(iid)
        return self.add(kind, n)

    def black(self, cid) -> str:
        def fn(n):
            if n.get("textColor") == "#000000":
                return False
            n.set("textColor", "#000000")
        return self.variant("charPr", cid, fn)

    def keep_with_next(self, pid) -> str:
        def fn(n):
            bs = n.find(q("hh:breakSetting"))
            if bs is None or bs.get("keepWithNext") == "1":
                return False
            bs.set("keepWithNext", "1")
        return self.variant("paraPr", pid, fn)


class Bins:
    """결과 BinData — 같은 그림(내용 해시)은 하나로."""

    def __init__(self, dry=False):
        self.items, self.by_hash, self.dry = [], {}, dry

    def fake(self) -> str:
        """미리 보기(표 높이 어림 등)용 — 그림 내용은 읽지 않고 이름만."""
        self.items.append(None)
        return f"image{len(self.items)}"

    def add(self, data: bytes, ext: str, media=None, emb=True) -> str:
        h = hashlib.sha256(data).hexdigest()
        if h in self.by_hash:
            return self.by_hash[h]
        ext = ext.lower()
        iid = f"{'ole' if ext == 'ole' else 'image'}{len(self.items) + 1}"  # OLE 개체(원고 그대로 옮김)
        self.items.append({"id": iid, "href": f"BinData/{iid}.{ext}", "media": media or f"image/{ext}", "data": data,
                           "emb": emb})
        self.by_hash[h] = iid
        return iid


class Importer:
    """원본 파일의 글꼴·테두리·글자/문단 모양·번호·스타일·그림을 결과 쪽 ID로 옮긴다(같은 정의는 재사용).
    속성값 앞의 '@'는 '이미 결과 쪽 ID'라는 표시 — remap이 떼어 낸다."""
    REF = {"p": (("paraPrIDRef", "para_pr"), ("styleIDRef", "style")), "run": (("charPrIDRef", "char_pr"),),
           "tbl": (("borderFillIDRef", "border_fill"),), "tc": (("borderFillIDRef", "border_fill"),),
           "img": (("binaryItemIDRef", "bin"),), "ole": (("binaryItemIDRef", "bin"),),
           "secPr": (("outlineShapeIDRef", "numbering"),),
           "pageBorderFill": (("borderFillIDRef", "border_fill"),)}

    def __init__(self, dst: Dst, src: Pkg, bins: Bins, recolor=False):
        self.dst, self.src, self.bins, self.recolor = dst, src, bins, recolor
        self.items = {k: src.items(k) for k in LISTS}
        self.fonts = {ff.get("lang"): {f.get("id"): f for f in ff.findall(q("hh:font"))}
                      for ff in src.header.iter(q("hh:fontface"))}
        self.map = {k: {} for k in list(LISTS) + ["font", "bin"]}

    def _memo(self, kind, key, fn):
        if key not in self.map[kind]:
            self.map[kind][key] = fn()
        return self.map[kind][key]

    def font(self, lang, sid):
        return self._memo("font", (lang, sid), lambda: self.dst.font(lang, self.fonts[lang][sid]))

    def border_fill(self, sid):
        def do():
            el = copy.deepcopy(self.items["borderFill"][sid])
            for img in el.iter(q("hc:img")):
                img.set("binaryItemIDRef", self.bin(img.get("binaryItemIDRef")))
            return self.dst.add("borderFill", el)
        return self._memo("borderFill", sid, do)

    def char_pr(self, sid):
        def do():
            el = copy.deepcopy(self.items["charPr"][sid])
            fr = el.find(q("hh:fontRef"))
            for a, lang in LANG_ATTR.items():
                if fr is not None and fr.get(a) is not None:
                    fr.set(a, self.font(lang, fr.get(a)))
            if el.get("borderFillIDRef"):
                el.set("borderFillIDRef", self.border_fill(el.get("borderFillIDRef")))
            if self.recolor:
                el.set("textColor", "#000000")
            return self.dst.add("charPr", el)
        return self._memo("charPr", sid, do)

    def tab_pr(self, sid):
        return self._memo("tabPr", sid, lambda: self.dst.add("tabPr", copy.deepcopy(self.items["tabPr"][sid])))

    def _heads(self, el):
        for ph in el.iter(q("hh:paraHead")):
            c = ph.get("charPrIDRef")
            if c and c != NONE_ID:
                ph.set("charPrIDRef", self.char_pr(c))
        return el

    def numbering(self, sid):  # 번호 카운터가 섞이지 않게 항상 새로
        return self._memo("numbering", sid, lambda: self.dst.add(
            "numbering", self._heads(copy.deepcopy(self.items["numbering"][sid])), dedupe=False))

    def bullet(self, sid):
        return self._memo("bullet", sid, lambda: self.dst.add(
            "bullet", self._heads(copy.deepcopy(self.items["bullet"][sid])), dedupe=False))

    def para_pr(self, sid):
        def do():
            el = copy.deepcopy(self.items["paraPr"][sid])
            if el.get("tabPrIDRef") is not None:
                el.set("tabPrIDRef", self.tab_pr(el.get("tabPrIDRef")))
            for hd in el.iter(q("hh:heading")):
                if hd.get("type") == "NUMBER":
                    hd.set("idRef", self.numbering(hd.get("idRef")))
                elif hd.get("type") == "BULLET":
                    hd.set("idRef", self.bullet(hd.get("idRef")))
            for bd in el.iter(q("hh:border")):
                if bd.get("borderFillIDRef"):
                    bd.set("borderFillIDRef", self.border_fill(bd.get("borderFillIDRef")))
            return self.dst.add("paraPr", el)
        return self._memo("paraPr", sid, do)

    def style(self, sid):
        def do():
            st = self.items["style"][sid]
            hit = self.dst.style_id(st.get("name"), st.get("type"))
            if hit is not None:  # 같은 이름 스타일이 결과에 있으면 그것(문단 모양은 문단에 직접 붙음)
                return hit
            el = copy.deepcopy(st)
            el.set("paraPrIDRef", self.para_pr(el.get("paraPrIDRef")))
            el.set("charPrIDRef", self.char_pr(el.get("charPrIDRef")))
            tid = self.dst.add("style", el, dedupe=False)
            el.set("nextStyleIDRef", tid)  # 다음 스타일 = 자기 자신
            return tid
        return self._memo("style", sid, do)

    def bin(self, sid):
        if self.bins.dry:
            return self._memo("bin", sid, self.bins.fake)
        href = self.src.bin[sid]
        media, emb = self.src.bin_type.get(sid, (None, True))
        if media and media.startswith("image/"):
            media = None  # 그림은 확장자로(예전과 같은 결과)
        return self._memo("bin", sid, lambda: self.bins.add(self.src.z.read(href), href.rsplit(".", 1)[-1], media, emb))

    def remap(self, root):
        for el in root.iter():
            for attr, fn in self.REF.get(local(el), ()):
                v = el.get(attr)
                if v is None:
                    continue
                if v.startswith("@"):
                    el.set(attr, v[1:])
                elif fn == "numbering" and v not in self.items["numbering"]:
                    continue  # 개요 번호 없음(0)
                else:
                    el.set(attr, getattr(self, fn)(v))
        return root

    def copy(self, el):
        return self.remap(copy.deepcopy(el))


# ======================================================================= C. 적용 — 조립

class Ctx:
    def __init__(self, R: Run, dry=False):
        self.Rn, self.R, self.D = R, R.R, R.D
        P = R.parts()
        self.base, self.tgp, self.cvp, self.tocp = P["본문양식"], P["표그림양식"], P["표지양식"], P["목차양식"]
        self.msp = Pkg(R.ms_path)
        if not R.map_path.exists():
            raise SystemExit(f"역할매핑이 없다: {R.map_path} — 먼저 analyze")
        self.roles = json.loads(R.map_path.read_text(encoding="utf-8"))
        need = [r["문단"] for r in self.roles if r["역할"] == "[판단 필요]"]
        if need:
            raise SystemExit(f"[판단 필요] 문단이 남아 있다: {need} — 역할판단 파일에 정한 뒤 analyze를 다시")
        self.dst = Dst(self.base, line_break(self.D))
        self.bins = Bins(dry)
        self.tg = Importer(self.dst, self.tgp, self.bins)
        self.ms = Importer(self.dst, self.msp, self.bins)
        self.cv = Importer(self.dst, self.cvp, self.bins) if self.cvp is not None else None
        self.toc = Importer(self.dst, self.tocp, self.bins, recolor=(self.D.get("글자색", "검정") == "검정")) \
            if self.tocp is not None else None
        self.log, self.toc_entries, self.toc_anchor, self.out_roles, self.approved = [], [], {}, [], []
        if self.dst.line_break:
            self.log.append("줄 나눔 기준: 모든 문단 모양을 한글 단위 '글자'·영어 단위 '글자'로(결정 '줄 나눔' — "
                            "긴 경로·주소 때문에 양쪽 정렬한 줄의 낱말 사이가 벌어지지 않게)")
        self.cap_pp = {}
        self.cap_total = Counter()
        self.styled_tbls = []  # 양식 표 모양을 입힌 표(머리행을 제목 셀로 반복해도 되는 표)
        self.frame_tbls = []   # 양식 그림 틀을 입힌 표(사진 묶음 등)
        self.big_tables = []   # 쪽보다 길 수 있어 쪽 경계에서 나뉘게 한 표(secure_tables)
        self.tbl_names = []    # (표, 제목 글자) — 제목을 따로 문단으로 둔 표도 알림에 제목으로 부르게
        self.hf_id = 0
        self.ms_color = {c.get("id"): (c.get("textColor") or "").upper() for c in self.msp.items("charPr").values()}
        self.colored = Counter()

    def keep_color(self, cid: str, src_cid) -> str:
        """결과 글자 모양 cid에 원고 run의 글자색을 입힌 변형(결정 '원고 글자색': "살림", 사용자 결정 2026-10-19).
        검정이 아닌 색만 — 원고 자리표시(빨강 [ … 기재], 갈색 【 】) 같은 표시를 결과에서도 보이게."""
        if self.D.get("원고 글자색", "살림") != "살림" or not src_cid or src_cid.startswith("@"):
            return cid
        col = self.ms_color.get(src_cid, "")
        if col in ("", "#000000", "NONE"):
            return cid

        def fn(n):
            if (n.get("textColor") or "").upper() == col:
                return False
            n.set("textColor", col)
        self.colored[col] += 1
        return self.dst.variant("charPr", cid, fn)

    def seg_runs(self, p, cid, segs, run=None):
        """원고 글자 조각을 문단 끝 run으로 붙인다: 결과 글자 모양이 같으면 이어서, 색이 다르면 새 run.
        run(문단의 마지막 run)을 주면 거기에 먼저 이어 붙인다. 문단 끝에 줄 배치 정보가 없어야 한다."""
        prev = run
        for scid, ts in segs:
            c = self.keep_color(cid, scid)
            if prev is None or prev.get("charPrIDRef") != c:
                prev = etree.SubElement(p, q("hp:run"))
                prev.set("charPrIDRef", c)
            prev.extend(ts)
        return prev

    def set_seg_runs(self, p, cid, segs):
        """set_runs와 같되 원고 run별 글자색을 살린다(모두 검정이면 set_runs와 같은 결과)."""
        if not segs:
            return set_runs(p, cid, [])
        for r in p.findall(q("hp:run")):
            p.remove(r)
        strip_layout(p)
        self.seg_runs(p, cid, segs)
        p.set("id", "0")
        return p

    def tcolor(self, cid) -> str:
        """양식 예시 글자 모양 → 결정 '글자색'이 "검정"(손 프로필 기본)이면 검정, "양식"이면 그대로."""
        return self.dst.black(cid) if self.D.get("글자색", "검정") == "검정" else cid

    def tg_para(self, key):
        ref = self.R["표그림"].get(key)
        return self.tgp.paras()[int(ref[1:])] if ref else None

    def tmpl_tbl(self, kind):
        p = self.tg_para(kind)
        return p.find(f".//{q('hp:tbl')}") if p is not None else None

    def cap_mode(self, kind):
        """양식의 표·그림 제목 방식: '붙음'(개체 캡션) / '문단'(개체 위·아래 따로 문단) / None(제목 모양 없음)."""
        return tmpl_caption(self.R["표그림"], self.tgp, kind)[0]

    def cap_pos(self, kind) -> str:
        """따로 문단 제목의 자리: 양식에서 찾은 '위'·'아래'(못 찾았으면 표 위·그림 아래)."""
        return self.R["표그림"].get(f"{kind} 캡션 위치") or ("위" if kind == "표" else "아래")

    def cap_numbered(self, kind) -> bool:
        """양식 제목에 자동 번호가 있는가 — 없으면 원고에 친 번호를 지우지 않는다(번호가 사라지지 않게)."""
        head = caption_head(self, kind)
        if head is None:
            return False
        if is_inline(head):
            return True
        hd = self.tg.items["paraPr"][head.get("paraPrIDRef")].find(q("hh:heading"))
        return hd is not None and hd.get("type") in ("NUMBER", "OUTLINE")


# --- 앞표지

def ms_header_text(ctx: Ctx, hdr=None) -> str:
    hdr = hdr if hdr is not None else ctx.msp.sections[0].find(f".//{q('hp:header')}")
    if hdr is None:
        return ""
    return plain([t for p in hdr.find(q("hp:subList")).findall(q("hp:p")) for t in text_ts(p)])


def header_parts(s: str) -> list:
    """머리말 글자 → [사업명, 장 제목](구분: 탭 또는 '|', 앞뒤 빈칸 무시). 구분이 없으면 [글자]."""
    return [x.strip() for x in HEADER_SEP.split(s, maxsplit=1)]


def build_cover(ctx: Ctx):
    """앞표지: 양식 표지 부분을 그대로 쓰고 제목 줄(·부제 줄)만 바꾼다.
    결정 '표지' {"제목"(또는 예전 이름 "사업명"): 글자 | "원고 머리말" | "양식" | "비움", "부제": 같은 값}."""
    sec = ctx.cv.copy(ctx.cvp.sections[0])
    ps = sec.findall(q("hp:p"))
    want = ctx.D.get("표지", {})
    roles = ctx.R.get("표지", {})
    for key, alias in (("제목", "사업명"), ("부제", None)):
        ref = roles.get(key) or (roles.get(alias) if alias else None)
        if not ref:
            continue
        val = want.get(key, want.get(alias, "양식") if alias else "양식")
        p = ps[int(ref[1:])]
        ts = [t for r in p.findall(q("hp:run")) for t in r.findall(q("hp:t"))]
        old = plain(ts)
        if val == "원고 머리말":
            val = header_parts(ms_header_text(ctx))[0] or old
        if val in ("양식", old) or not ts:
            ctx.log.append(f"표지 {alias or key}: 양식 그대로 '{old}'")
            continue
        val = "" if val == "비움" else val
        for c in list(ts[0]):
            ts[0].remove(c)
        ts[0].text = val
        for t in ts[1:]:
            t.getparent().remove(t)
        ctx.log.append(f"표지 {alias or key}: '{old}' → '{val}'" + (" (비움)" if not val else ""))
    strip_layout(sec)
    return sec


# --- 장 제목 · 머리말

def chapter_no(row) -> int:
    m = re.search(r"\d+", row.get("번호", "") or "")
    return int(m.group()) if m else 1


def setup_chapter_outline(ctx: Ctx, first_chap: int) -> str:
    """장 제목을 바탕 양식 개요 1수준으로 — 장이 바뀌면 1.·(1) 번호가 다시 1부터 시작하게.
    개요 1수준 번호 모양은 표그림 양식 장 제목 번호('제^1장')를 그대로 쓰고 시작값 = 첫 장 번호.
    장 제목 문단 모양은 표그림 양식 것에서 번호 종류만 '개요 1수준'으로 바꾼 것."""
    tt = ctx.tg_para("장 제목")
    if tt is None:
        raise SystemExit("양식에 장 제목(큰 제목)이 없어 원고의 장 제목을 놓을 모양이 없다")
    src_pp = ctx.tg.items["paraPr"][tt.get("paraPrIDRef")]
    hd = src_pp.find(q("hh:heading"))
    if hd is None or hd.get("type") not in ("OUTLINE", "NUMBER"):
        return chapter_outline_textlabel(ctx, tt, first_chap)
    if hd.get("type") == "OUTLINE":
        src_num = ctx.tg.items["numbering"][ctx.tgp.sections[0].find(f".//{q('hp:secPr')}").get("outlineShapeIDRef")]
    else:
        src_num = ctx.tg.items["numbering"][hd.get("idRef")]
    src_lv1 = [x for x in src_num.findall(q("hh:paraHead")) if x.get("level") == "1"][0]
    num = ctx.dst.get("numbering", ctx.base.sections[0].find(f".//{q('hp:secPr')}").get("outlineShapeIDRef"))
    lv1 = [x for x in num.findall(q("hh:paraHead")) if x.get("level") == "1"][0]
    new = copy.deepcopy(src_lv1)
    if new.get("charPrIDRef") not in (None, NONE_ID):
        new.set("charPrIDRef", ctx.tg.char_pr(new.get("charPrIDRef")))
    new.set("start", str(first_chap))
    num.replace(lv1, new)

    def fn(n):
        h = n.find(q("hh:heading"))
        h.set("type", "OUTLINE")
        h.set("idRef", "0")
        h.set("level", "0")
    pid = ctx.dst.variant("paraPr", ctx.tg.para_pr(tt.get("paraPrIDRef")), fn)
    ctx.log.append(f"장 제목: 표그림 양식 모양 + 개요 1수준 번호('{new.text}', 시작 {first_chap}) — 장마다 1.·(1) 번호가 새로 시작")
    return pid


def chapter_outline_textlabel(ctx: Ctx, tt, first_chap: int) -> str:
    """양식 장 제목에 자동 번호가 없을 때(번호 없는 큰 제목·글자로 친 '제1장'): 장 번호는 원고 번호를 글자로 넣고,
    문단은 개요 1수준(번호 글자는 비움)으로 둬서 장마다 아래 번호(1.·(1))가 새로 시작하게 한다.
    양식의 1수준 제목이 이미 개요 1수준을 쓰면(장 없는 양식) 장 제목은 번호 없는 문단으로 둔다."""
    ctx.chapter_text_label = True
    ex1 = ctx.R["본문"].get("1수준")
    lv_used = None
    if ex1:
        h = ctx.dst.get("paraPr", ctx.base.paras()[int(ex1[1:])].get("paraPrIDRef")).find(q("hh:heading"))
        lv_used = int(h.get("level")) if h is not None and h.get("type") == "OUTLINE" else None
    pid0 = ctx.tg.para_pr(tt.get("paraPrIDRef"))
    if lv_used == 0:
        ctx.log.append("⚠ 양식 장 제목에 번호가 없고 1수준 제목이 개요 1수준을 써서, 장 제목은 번호 없는 문단으로 — "
                       "1.·(1) 번호가 장마다 새로 시작하지 않는다")
        return pid0
    num = ctx.dst.get("numbering", ctx.base.sections[0].find(f".//{q('hp:secPr')}").get("outlineShapeIDRef"))
    lv1 = [x for x in num.findall(q("hh:paraHead")) if x.get("level") == "1"][0]
    lv1.text = ""
    lv1.set("start", str(first_chap))

    def fn(n):
        h = n.find(q("hh:heading"))
        if h is None:
            h = etree.SubElement(n, q("hh:heading"))
        h.set("type", "OUTLINE")
        h.set("idRef", "0")
        h.set("level", "0")
    pid = ctx.dst.variant("paraPr", pid0, fn)
    ctx.log.append("장 제목: 양식 큰 제목 모양(자동 번호 없음) + 원고 장 번호를 글자로, 개요 1수준(번호 글자 비움)으로 "
                   "장마다 1.·(1) 번호가 새로 시작")
    return pid


def heading_example(ctx: Ctx, ex: dict, role: str):
    """제목 역할의 양식 예시 문단. 양식에 그 단계가 없으면 가장 가까운 윗단계 예시를 복사해 번호 수준만 내리고
    왼쪽 여백을 단계 차이만큼 더한다(양식 두 단계 여백 차이, 없으면 10 pt)."""
    if role in ex:
        return ex[role]
    n = int(role[0])
    have = sorted(int(k[0]) for k in ex if k in HEADING_ROLES)
    if not have:
        raise SystemExit("양식에 번호 제목 예시가 없다 — 원고의 제목을 놓을 모양이 없다")
    near = max([a for a in have if a < n], default=have[0])
    e = ex[f"{near}수준"]
    key = ("대체", role)
    if key not in ctx.cap_pp:
        def case_left(pid):
            m = ctx.dst.get("paraPr", pid).find(f".//{q('hp:case')}/{q('hh:margin')}/{q('hc:left')}")
            return int(m.get("value")) if m is not None else None
        prev = ex.get(f"{near - 1}수준")
        a, b = case_left(e.get("paraPrIDRef")), case_left(prev.get("paraPrIDRef")) if prev is not None else None
        step = (a - b) if a is not None and b is not None and a > b else 1000
        diff = n - near

        def fn(node):
            h = node.find(q("hh:heading"))
            if h is not None and h.get("type") in ("OUTLINE", "NUMBER"):
                h.set("level", str(int(h.get("level")) + diff))
            for case in node.iter(q("hp:case")):
                lf = case.find(f"{q('hh:margin')}/{q('hc:left')}")
                if lf is not None:
                    lf.set("value", str(int(lf.get("value")) + step * diff))
            for dflt in node.iter(q("hp:default")):
                lf = dflt.find(f"{q('hh:margin')}/{q('hc:left')}")
                if lf is not None:
                    lf.set("value", str(int(lf.get("value")) + 2 * step * diff))
        c = copy.deepcopy(e)
        c.set("paraPrIDRef", ctx.dst.variant("paraPr", e.get("paraPrIDRef"), fn))
        ctx.cap_pp[key] = c
        ctx.log.append(f"⚠ 양식에 {role} 제목이 없어 {near}수준 모양에서 번호 수준만 {diff}단계 내려 씀")
    return ctx.cap_pp[key]


def ms_headers_by_chapter(ctx: Ctx, chapters) -> dict:
    """원고 머리말 컨트롤 → 장 번호(0부터): 머리말이 있는 문단 앞에서 가장 가까운 장."""
    starts = [para_key(r["문단"])[0] for r in chapters]
    out = {}
    for i, p in enumerate(ctx.msp.paras()):
        for h in p.iter(q("hp:header")):
            k = max((n for n, s in enumerate(starts) if s <= i), default=0)
            out.setdefault(k, h)
    return out


def put_header_text(ctx: Ctx, hdr, ms_hdr, label_title: str):
    """양식 머리말(모양·선)에 원고 머리말 글자를 run 순서대로 넣는다. 원고 머리말이 없으면 '사업명 ⇥ 장 제목'."""
    tp0 = hdr.find(q("hp:subList")).findall(q("hp:p"))[0]
    truns = [r for r in tp0.findall(q("hp:run")) if r.find(q("hp:t")) is not None]
    if not truns:  # 양식 머리말이 비어 있음 → 첫 문단에 글자 자리(run)를 만든다
        r0 = tp0.find(q("hp:run"))
        run = etree.SubElement(tp0, q("hp:run"))
        run.set("charPrIDRef", r0.get("charPrIDRef") if r0 is not None else "0")
        etree.SubElement(run, q("hp:t"))
        truns = [run]
    old = plain([t for r in truns for t in r.findall(q("hp:t"))])
    tab = next(iter(truns[0].iter(q("hp:tab"))), None) if truns else None
    if ctx.D.get("머리말글자") == "지정":  # 설문: 머리말 글자를 정해 줌 → 왼쪽 칸 = 정한 글자, 오른쪽 칸 = 장 제목
        set_header_slots(ctx, truns, tab, ctx.D.get("머리말 내용", ""), label_title if ctx.D.get("머리말 장 제목", True) else "")
        return
    blank = ms_hdr is not None and not ms_header_text(ctx, ms_hdr).strip()
    if blank:  # 원고 머리말이 공백뿐 → 원고 머리말이 없을 때처럼 '사업명 ⇥ 장 제목'
        ms_hdr = None
    if ms_hdr is not None:
        mp0 = ms_hdr.find(q("hp:subList")).findall(q("hp:p"))[0]
        mruns = [r for r in mp0.findall(q("hp:run")) if r.find(q("hp:t")) is not None]
        mtext = plain([t for r in mruns for t in r.findall(q("hp:t"))])
        parts = header_parts(mtext)
        for r in truns:
            for t in r.findall(q("hp:t")):
                r.remove(t)
        if len(mruns) == len(truns):
            for tr, mr in zip(truns, mruns):
                tr.extend([copy.deepcopy(t) for t in mr.findall(q("hp:t"))])
        elif len(truns) == 2 and len(parts) == 2 and tab is not None:
            # 원고 머리말이 한 칸에 '사업명 | 장 제목' → 양식처럼 사업명(오른쪽 탭까지) / 장 제목 두 칸으로
            sep = HEADER_SEP.search(mtext).group(0)
            t0 = etree.SubElement(truns[0], q("hp:t"))
            t0.text = parts[0]
            t0.append(copy.deepcopy(tab))
            etree.SubElement(truns[1], q("hp:t")).text = parts[1]
            ctx.approved.append({"문단": "머리말", "내용": f"원고 머리말의 구분 '{sep}'을 양식의 두 칸(사업명 ⇥ 장 제목)으로 — "
                                                     f"'{parts[0]}' / '{parts[1]}'"})
        else:
            truns[0].extend([copy.deepcopy(t) for r in mruns for t in r.findall(q("hp:t"))])
            ctx.log.append(f"⚠ 머리말 run 수가 달라(양식 {len(truns)}, 원고 {len(mruns)}) 첫 run에 모두 넣음")
    else:
        biz = ctx.D.get("표지", {}).get("사업명")
        t0 = truns[0].find(q("hp:t"))
        if ctx.D.get("머리말 사업명") == "비움":  # 사업명 칸만 비우고 탭(오른쪽 장 제목 자리)은 둔다
            t0.text = ""
        elif biz and biz not in ("양식", "원고 머리말"):
            t0.text = biz
        if len(truns) > 1:
            for t in truns[1].findall(q("hp:t")):
                truns[1].remove(t)
            etree.SubElement(truns[1], q("hp:t")).text = label_title
        ctx.log.append(("원고 머리말이 비어 있어" if blank else "⚠ 원고에 머리말이 없어") + " '사업명 ⇥ 장 제목'으로 만듦"
                       + (" — 사업명 칸은 비움(결정 '머리말 사업명')" if ctx.D.get("머리말 사업명") == "비움" else ""))
    new = plain([t for r in truns for t in r.findall(q("hp:t"))])
    ctx.log.append(f"머리말 글자: '{old}' → '{new}'")


def set_header_slots(ctx: Ctx, truns, tab, left: str, right: str):
    """양식 머리말 글자 칸에 글자를 넣는다: 칸(run)이 둘이면 왼쪽·오른쪽, 하나면 '왼쪽 ⇥ 오른쪽'(탭이 있으면) 또는 왼쪽만."""
    old = plain([t for r in truns for t in r.findall(q("hp:t"))])
    for r in truns:
        for t in r.findall(q("hp:t")):
            r.remove(t)
    if len(truns) >= 2:
        t0 = etree.SubElement(truns[0], q("hp:t"))
        t0.text = left
        if tab is not None:
            t0.append(copy.deepcopy(tab))
        etree.SubElement(truns[-1], q("hp:t")).text = right
    else:
        t0 = etree.SubElement(truns[0], q("hp:t"))
        t0.text = left if not right or tab is None else left
        if right and tab is not None:
            tb = copy.deepcopy(tab)
            tb.tail = right
            t0.append(tb)
    new = plain([t for r in truns for t in r.findall(q("hp:t"))])
    ctx.log.append(f"머리말 글자(설문): '{old}' → '{new}'")


CHAPTER_HEAD = re.compile(r"^\s*(제\s*\d+\s*장|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]\s*[.\s])")  # 머리말의 장 제목 칸('제7장 …'·'Ⅶ. …')


def header_text_runs(hdr):
    """머리말 첫 문단의 글자 칸(run)과 탭 — put_header_text·template_header가 같이 쓴다."""
    tp0 = hdr.find(q("hp:subList")).findall(q("hp:p"))[0]
    truns = [r for r in tp0.findall(q("hp:run")) if r.find(q("hp:t")) is not None]
    tab = next(iter(truns[0].iter(q("hp:tab"))), None) if truns else None
    return tp0, truns, tab


def is_chapter_text(ctx: Ctx, text: str) -> bool:
    """양식 머리말 글자가 장 제목인가: '제N장 …'으로 시작하거나 양식 장 제목 글자(뒤의 '(… 20pt)' 같은 설명은 빼고)를 담았다."""
    if CHAPTER_HEAD.match(text or ""):
        return True
    tt = ctx.tg_para("장 제목")
    core = re.sub(r"\s*\([^)]*\)\s*$", "", own_text(tt)).strip() if tt is not None else ""
    return len(core) >= 4 and core in (text or "")


def template_header(ctx: Ctx, hdr, label_title: str):
    """결정 '머리말글자' = "양식"(설문 '양식에 있는 머리말 그대로'): 양식 머리말 글자를 그대로 두되 장 제목 칸만 원고 장 제목으로.
    장 제목 칸 = 두 칸 머리말('사업명 ⇥ 장 제목')의 오른쪽 칸, 또는 글자가 장 제목인 머리말(홀수 쪽 '제7장 …' 등).
    원고에 장이 없으면(label_title이 빔) 양식 글자 그대로 — 양식이 그 장의 양식이라고 본다."""
    _, truns, tab = header_text_runs(hdr)
    old = plain([t for r in truns for t in r.findall(q("hp:t"))])
    if label_title and truns:
        if len(truns) >= 2 and tab is not None:  # 두 칸: 왼쪽 '사업명 ⇥', 오른쪽 장 제목
            slot = truns[-1]
            for t in slot.findall(q("hp:t")):
                slot.remove(t)
            etree.SubElement(slot, q("hp:t")).text = label_title
        elif tab is not None and is_chapter_text(ctx, tab.tail or ""):  # 한 칸 안에 '사업명 ⇥ 장 제목'
            tab.tail = label_title
            for x in list(tab.itersiblings()):  # 장 제목 뒤에 이어진 글자 조각은 뺀다
                x.getparent().remove(x)
        elif is_chapter_text(ctx, old):  # 머리말 전체가 장 제목(홀수 쪽 '제7장 …' 등)
            for r in truns:
                for t in r.findall(q("hp:t")):
                    r.remove(t)
            etree.SubElement(truns[0], q("hp:t")).text = label_title
    new = plain([t for r in truns for t in r.findall(q("hp:t"))])
    ctx.log.append(f"머리말 글자(양식 그대로{' — 장 제목 칸은 이 장 제목' if new != old else ''}): '{old}' → '{new}'"
                   if new != old else f"머리말 글자(양식 그대로): '{old}'")


def other_header(ctx: Ctx, hdr, label_title: str):
    """쪽 종류가 여럿인 양식(짝수·홀수 쪽 머리말이 다름)의 둘째 머리말부터 — '원고'·'지정'일 때 양식 예시 글자가 남지 않게:
    장 제목 머리말(홀수 쪽 '제7장 …' 등)은 이 장 제목(장이 없으면 정한 머리말 글자), 그 밖은 첫 머리말과 같은 규칙."""
    _, truns, tab = header_text_runs(hdr)
    old = plain([t for r in truns for t in r.findall(q("hp:t"))])
    if truns and len(truns) == 1 and is_chapter_text(ctx, old):
        text = label_title or (ctx.D.get("머리말 내용", "") if ctx.D.get("머리말글자") == "지정" else "")
        if text:
            for t in truns[0].findall(q("hp:t")):
                truns[0].remove(t)
            etree.SubElement(truns[0], q("hp:t")).text = text
            ctx.log.append(f"머리말 글자({hdr.get('applyPageType')} 쪽, 장 제목 칸): '{old}' → '{text}'")
        return
    return "그대로"


def make_hfs(ctx: Ctx, kind, ms_hdr, label_title) -> list:
    """양식 머리말·꼬리말 사본들(머리말 글자는 결정대로) — 양식에 쪽 종류(모든 쪽·짝수·홀수)별로 여럿이면 모두.
    양식에 없거나 결정 '머리말 만들기'가 false면 []."""
    if kind == "header" and not ctx.D.get("머리말 만들기", True):
        return []
    hp = ctx.tg_para("머리말꼬리말")
    srcs = list(hp.iter(q("hp:" + kind))) if hp is not None else []
    out = []
    for n, src in enumerate(srcs):
        el = ctx.tg.copy(src)
        ctx.hf_id += 1
        el.set("id", str(ctx.hf_id))
        strip_layout(el)
        how = ctx.D.get("머리말글자", "원고")
        if kind == "header" and how == "양식":
            template_header(ctx, el, label_title)
        elif kind == "header" and how in ("원고", "지정"):
            if n == 0 or other_header(ctx, el, label_title) == "그대로":
                put_header_text(ctx, el, ms_hdr, label_title)
        out.append(el)
    return out


def make_hf(ctx: Ctx, kind, ms_hdr, label_title):
    """양식 머리말·꼬리말 첫 사본(예전 호출용) — 없으면 None."""
    els = make_hfs(ctx, kind, ms_hdr, label_title)
    return els[0] if els else None


def build_first_para(ctx: Ctx, title_segs, title_pp, ms_hdr, label_title):
    """본문 구역 첫 문단: 바탕 양식 첫 문단(구역 설정·쪽 번호·머리말·꼬리말 컨트롤)을 지우지 않고,
    장 제목 모양과 머리말·꼬리말·쪽 번호 위치(표그림 양식)로 바꾼 뒤 원고 장 제목을 넣는다."""
    first = copy.deepcopy(ctx.base.paras()[int(ctx.R["본문"]["첫 문단"][1:])])
    tt = ctx.tg_para("장 제목")
    first.set("paraPrIDRef", title_pp)
    first.set("styleIDRef", ctx.tg.style(tt.get("styleIDRef")))
    first.set("id", "0")
    cid = ctx.tg.char_pr(text_run_cid(tt))
    for r in first.findall(q("hp:run")):
        r.set("charPrIDRef", cid)
        for t in r.findall(q("hp:t")):
            r.remove(t)
    strip_layout(first)
    first.find(f".//{q('hp:secPr')}").find(q("hp:startNum")).set("page", str(ctx.D.get("본문쪽번호시작", 1)))
    put_section_ctrls(ctx, first, tt, ms_hdr, label_title)
    ctx.seg_runs(first, cid, title_segs, run=first.findall(q("hp:run"))[-1])
    return first


def put_section_ctrls(ctx: Ctx, first, tt, ms_hdr, label_title):
    """본문 첫 문단의 쪽 번호 위치·머리말·꼬리말을 양식 것으로. 손 프로필은 장 제목 문단의 쪽 번호와 '머리말꼬리말'
    문단의 것으로 바꾸고, 자동 분석 프로필은 '쪽번호'·'머리말꼬리말' 문단(없으면 뺌)의 것을 쓴다."""
    pn_src = ctx.tg_para("쪽번호") if ctx.R["표그림"].get("쪽번호") else tt
    pn_new = pn_src.find(f".//{q('hp:pageNum')}") if pn_src is not None else None
    run0 = first.findall(q("hp:run"))[0]
    for kind, news in [("pageNum", [ctx.tg.copy(pn_new)] if pn_new is not None else [])] + \
                      [(k, make_hfs(ctx, k, ms_hdr, label_title)) for k in ("header", "footer")]:
        olds = list(first.iter(q("hp:" + kind)))
        # 쪽 종류(모든 쪽·짝수·홀수)가 같은 것끼리 바꾼다 — 양식이 짝수·홀수 쪽 머리말을 따로 두면 둘 다
        for old in olds:
            new = next((n for n in news if n.get("applyPageType") == old.get("applyPageType")), None) \
                if len(olds) > 1 or len(news) > 1 else (news[0] if news else None)
            if new is not None:
                old.getparent().replace(old, new)
                news.remove(new)
            else:  # 양식에 없음 → 첫 문단(양식 본문 첫 문단)에 있던 것도 뺀다
                ctrl = old.getparent()
                ctrl.getparent().remove(ctrl) if len(ctrl) == 1 else ctrl.remove(old)
        for new in news:  # 양식에는 있는데 첫 문단에 없음(다른 문단에 있던 것) → 첫 문단에 붙인다
            etree.SubElement(run0, q("hp:ctrl")).append(new)


def attach_carrier(ctx: Ctx, p, ms_hdr, label_title):
    """장 제목이 아닌 글로 시작하는 본문: 양식 본문 첫 문단의 구역 설정·단·쪽 번호·머리말·꼬리말을 첫 문단 앞에 붙인다."""
    first = copy.deepcopy(ctx.base.paras()[int(ctx.R["본문"]["첫 문단"][1:])])
    strip_layout(first)
    first.find(f".//{q('hp:secPr')}").find(q("hp:startNum")).set("page", str(ctx.D.get("본문쪽번호시작", 1)))
    put_section_ctrls(ctx, first, ctx.tg_para("장 제목"), ms_hdr, label_title)
    runs = [r for r in first.findall(q("hp:run")) if r.find(q("hp:secPr")) is not None or r.find(q("hp:ctrl")) is not None]
    for r in runs:
        for x in [x for x in r if local(x) not in ("secPr", "ctrl")]:
            r.remove(x)
    for i, r in enumerate(runs):
        p.insert(i, r)
    p.set("pageBreak", "0")


def segs_of(src):
    return text_segs(src)


def doc_title_para(ctx: Ctx, src, segs):
    """원고 맨 앞의 문서 제목 줄 → 양식 장 제목(없으면 1수준) 모양, 번호 없이."""
    ex = ctx.tg_para("장 제목")
    if ex is None and ctx.R["본문"].get("1수준"):
        ex = ctx.base.paras()[int(ctx.R["본문"]["1수준"][1:])]
    if ex is None:
        ex = ctx.base.paras()[int(ctx.R["본문"]["본문"][1:])]

    def fn(n):
        h = n.find(q("hh:heading"))
        if h is None or h.get("type") == "NONE":
            return False
        h.set("type", "NONE")
        h.set("idRef", "0")
        h.set("level", "0")
    pid = ctx.dst.variant("paraPr", ctx.tg.para_pr(ex.get("paraPrIDRef")), fn)
    p = etree.Element(q("hp:p"))
    for k, v in (("id", "0"), ("paraPrIDRef", pid), ("styleIDRef", ctx.tg.style(ex.get("styleIDRef"))), ("pageBreak", "0"),
                 ("columnBreak", "0"), ("merged", "0")):
        p.set(k, v)
    ctx.seg_runs(p, ctx.tcolor(ctx.tg.char_pr(text_run_cid(ex))), segs)
    deco = [local(o) for o in objects(src) if not "".join(o.itertext()).strip()]
    if deco:
        ctx.log.append(f"문서 제목 줄의 글자 없는 꾸밈 개체 {deco} → 뺌")
    return p


def new_body_section(ctx: Ctx, title_segs, title_pp, ms_hdr, label_title, chap: int):
    """장 번호를 건너뛸 때(예: 제5장 다음 제7장): 개요 번호는 같은 구역 안에서 새로 시작할 수 없어(노트 699·292)
    새 구역을 만들고 그 구역의 개요 번호 모양을 '새 번호로 시작, 1수준 시작 번호 = chap'으로 둔다.
    구역 첫 문단은 본문 첫 문단처럼 구역 설정·단·쪽 번호 위치·머리말·꼬리말을 갖는다. 쪽 번호는 설정대로(기본 이어서)."""
    sec = copy.deepcopy(ctx.base.sections[0])
    for p in sec.findall(q("hp:p")):
        sec.remove(p)
    first = build_first_para(ctx, title_segs, title_pp, ms_hdr, label_title)
    sp = first.find(f".//{q('hp:secPr')}")
    sp.find(q("hp:startNum")).set("page", "1" if ctx.D.get("장마다 쪽 번호 새로", False) else "0")
    num = copy.deepcopy(ctx.dst.get("numbering", ctx.base.sections[0].find(f".//{q('hp:secPr')}").get("outlineShapeIDRef")))
    num.set("start", str(chap))  # 0 = 앞 구역에 이어서, n = n부터 새로 시작(2026-10-16 PDF로 확인)
    [x for x in num.findall(q("hh:paraHead")) if x.get("level") == "1"][0].set("start", str(chap))
    sp.set("outlineShapeIDRef", ctx.dst.add("numbering", num, dedupe=False))
    sec.append(first)
    ctx.log.append(f"{label_title.split(' ')[0]}: 장 번호를 건너뛰어 새 구역에서 개요 번호를 {chap}부터 새로 시작")
    return sec


def build_chapter_para(ctx: Ctx, sec, title_segs, title_pp, ms_hdr, label_title):
    """둘째 장부터: 새 쪽 + (원고에 머리말이 있으면) 머리말·꼬리말 (+ 설정하면 쪽 번호 1부터)."""
    tt = ctx.tg_para("장 제목")
    p = etree.SubElement(sec, q("hp:p"))
    for k, v in (("id", "0"), ("paraPrIDRef", title_pp), ("styleIDRef", ctx.tg.style(tt.get("styleIDRef"))),
                 ("pageBreak", "1" if ctx.D.get("장마다 새 쪽", True) else "0"), ("columnBreak", "0"), ("merged", "0")):
        p.set(k, v)
    run = etree.SubElement(p, q("hp:run"))
    run.set("charPrIDRef", ctx.tg.char_pr(text_run_cid(tt)))
    if ms_hdr is not None:
        for kind in ("header", "footer"):
            for el in make_hfs(ctx, kind, ms_hdr, label_title):  # 짝수·홀수 쪽 머리말이 따로면 둘 다
                etree.SubElement(run, q("hp:ctrl")).append(el)
    if ctx.D.get("장마다 쪽 번호 새로", False):
        nn = etree.SubElement(etree.SubElement(run, q("hp:ctrl")), q("hp:newNum"))
        nn.set("num", "1")
        nn.set("numType", "PAGE")
    ctx.seg_runs(p, run.get("charPrIDRef"), title_segs, run=run)
    return p


class InlineNum:
    """양식 캡션 번호가 문단 번호가 아니라 캡션 글자 안 자동 번호(hp:autoNum)일 때 — '<그림 ' + 번호 + '> '."""

    def __init__(self, head):
        before, after, self.fmt, hit = [], [], "DIGIT", False
        for r in head.findall(q("hp:run")):
            for c in r:
                if autonum_ctrl(c):
                    hit = True
                    f = c.find(f"{q('hp:autoNum')}/{q('hp:autoNumFormat')}")
                    self.fmt = f.get("type", "DIGIT") if f is not None else "DIGIT"
                elif local(c) == "t":
                    (after if hit else before).append(plain([c]))
            if hit:
                break
        self.before = "".join(before)
        m = LABEL_TAIL.match("".join(after))
        self.after = m.group(0) if m else ""

    def label(self, n: int) -> str:
        return f"{self.before}{fmt_num(n, self.fmt)}{self.after}".strip()


class ParaNum:
    """양식 캡션 번호가 문단 번호일 때 — 번호 정의와 캡션이 쓰는 수준(위성 양식 '<그림 1-^1>'은 1수준,
    '<표 ^1-^7>'처럼 7수준을 쓰는 양식도 있다). fixed: 다른 수준 자리에 넣을 값(개요 번호 캡션의 장 번호)."""

    def __init__(self, num, lv: int, fixed=None):
        self.num, self.lv, self.fixed = num, lv, dict(fixed or {})

    def label(self, n: int) -> str:
        return head_text(self.num, self.lv, {**self.fixed, self.lv: n})


def chapter_in_label(text: str, lv: int, chap: int, no_chapters: bool) -> str:
    """캡션 번호 모양의 장 번호 자리 → 이 장 번호(글자로). 장 번호 자리는 세는 번호(^lv) 바로 앞의 '숫자-' 또는 '^n-'
    ('<그림 1-^1>' → '<그림 3-^1>', '<표 ^1-^7>' → '<표 3-^7>'). 장 없는 원고는 장 번호 자리를 뺀다('<표 ^7>')."""
    i = text.find(f"^{lv}")
    if i < 0:
        return text
    m = re.search(r"(\d+|\^\d)(\s*[-–.·]\s*)$", text[:i])
    if not m:
        return text
    return text[:m.start()] + ("" if no_chapters else f"{chap}{m.group(2)}") + text[i:]


def cap_label(num, n_chap: int, n_total: int) -> str:
    """캡션 번호 글자: 문단 번호 정의면 장별 번호, 글자 안 자동 번호면 문서 전체 번호."""
    if num is None:
        return ""
    if isinstance(num, InlineNum):
        return num.label(n_total)
    if isinstance(num, ParaNum):
        return num.label(n_chap)
    return head_text(num, 1, {1: n_chap})


def tmpl_caption(T: dict, tgp, kind: str):
    """양식 표·그림 제목(캡션) → (방식, 제목 문단): ('붙음', 개체 캡션의 첫 문단) / ('문단', 개체 위·아래에 따로 놓인
    제목 문단 — template_profile이 찾은 '표 캡션'·'그림 캡션') / (None, None) — 양식에 제목 모양이 없음."""
    ref = T.get(kind)
    p = tgp.paras()[int(ref[1:])] if ref else None
    tbl = p.find(f".//{q('hp:tbl')}") if p is not None else None
    cap = tbl.find(q("hp:caption")) if tbl is not None else None
    if cap is not None:
        return "붙음", cap.find(q("hp:subList")).find(q("hp:p"))
    if T.get(f"{kind} 캡션"):
        return "문단", tgp.paras()[int(T[f"{kind} 캡션"][1:])]
    return None, None


def caption_head(ctx: Ctx, kind: str):
    """양식 제목(캡션) 문단 — 개체에 붙은 캡션의 첫 문단 또는 따로 놓인 제목 문단(없으면 None)."""
    return tmpl_caption(ctx.R["표그림"], ctx.tgp, kind)[1]


def is_inline(head) -> bool:
    return head is not None and any(autonum_ctrl(c) for r in head.findall(q("hp:run")) for c in r)


def inline_caption_para(ctx: Ctx, head, segs, kind: str):
    """글자 안 자동 번호 캡션 문단: 양식 문단의 번호 부분('<그림 '·번호·'> ')만 남기고 원고 캡션 글자를 붙인다.
    head는 결과 ID로 옮긴 양식 캡션 문단. 번호 종류는 개체 종류대로(양식이 표 캡션에 '그림' 번호를 쓴 경우도 표로)."""
    np = copy.deepcopy(head)
    strip_layout(np)
    runs = np.findall(q("hp:run"))
    k = next(i for i, r in enumerate(runs) if any(autonum_ctrl(c) for c in r))
    title_cid = runs[k + 1].get("charPrIDRef") if k + 1 < len(runs) else runs[k].get("charPrIDRef")
    for r in runs[k + 1:]:
        np.remove(r)
    run, hit, tail_done = runs[k], False, False
    for c in list(run):
        if autonum_ctrl(c):
            hit = True
            a = c.find(q("hp:autoNum"))
            want = {"표": "TABLE", "그림": "PICTURE"}.get(kind, a.get("numType"))
            if a.get("numType") != want:
                old = a.get("numType")
                a.set("numType", want)
                if not getattr(ctx, "numtype_fixed", False):
                    ctx.numtype_fixed = True
                    ctx.log.append(f"⚠ 양식 {kind} 캡션의 자동 번호 종류가 '{old}'여서 '{want}'로 — 표·그림 번호를 따로 센다")
        elif hit and local(c) == "t":
            if tail_done:
                run.remove(c)
            else:
                m = LABEL_TAIL.match(plain([c]))
                for x in list(c):
                    c.remove(x)
                c.text = m.group(0) if m else ""
                tail_done = True
    np.set("id", "0")
    ctx.seg_runs(np, title_cid, segs)
    return np


def chapter_caption_pp(ctx: Ctx, kind: str, chap: int):
    """장마다 캡션 번호를 따로: 장 번호 자리를 이 장 번호로 바꾼 번호 정의 + 그것을 쓰는 제목(캡션) 문단 모양.
    돌려주는 값 (결과 문단 모양 ID, 번호):
      - 문단 번호(NUMBER): (새 문단 모양, ParaNum) — 캡션이 쓰는 수준이 1수준이 아니어도 된다('<표 ^1-^7>' 꼴)
      - 개요 번호(OUTLINE): (양식 문단 모양 그대로, ParaNum — 장 번호는 결과 개요 번호가 센다)
      - 글자 안 자동 번호: (None, InlineNum) — 문단 모양은 양식 캡션 그대로
      - 번호 없음: (양식 문단 모양 그대로, None) — 원고에 친 번호를 그대로 둔다
      - 양식에 제목 모양이 없음: (None, None)"""
    head = caption_head(ctx, kind)
    if head is None:
        return None, None
    if is_inline(head):
        return None, InlineNum(head)
    key = (kind, chap)
    if key not in ctx.cap_pp:
        base_pid = ctx.tg.para_pr(head.get("paraPrIDRef"))
        pp = copy.deepcopy(ctx.dst.get("paraPr", base_pid))
        hd = pp.find(q("hh:heading"))
        if hd is None or hd.get("type") not in ("NUMBER", "OUTLINE"):
            ctx.cap_pp[key] = (base_pid, None)
        elif hd.get("type") == "OUTLINE":
            lv = int(hd.get("level")) + 1
            outline = ctx.dst.get("numbering", ctx.base.sections[0].find(f".//{q('hp:secPr')}").get("outlineShapeIDRef"))
            ctx.cap_pp[key] = (base_pid, ParaNum(outline, lv, {1: chap}))
        else:
            lv = int(hd.get("level")) + 1
            num = copy.deepcopy(ctx.dst.get("numbering", hd.get("idRef")))
            ph = next(x for x in num.findall(q("hh:paraHead")) if x.get("level") == str(lv))
            # 장 없는 원고: '<표 1-^1>' → '<표 ^1>'(없는 장 번호를 찍지 않게)
            ph.text = chapter_in_label(ph.text or "", lv, chap, getattr(ctx, "no_chapters", False))
            hd.set("idRef", ctx.dst.add("numbering", num, dedupe=False))
            ctx.cap_pp[key] = (ctx.dst.add("paraPr", pp), ParaNum(num, lv))
    return ctx.cap_pp[key]


def caption_para(ctx: Ctx, kind: str, segs, pp, cont=None):
    """따로 놓인 제목(캡션) 문단: 양식 제목 문단 모양 + 원고 캡션 글자. pp: 이 장의 번호를 쓰는 문단 모양(결과 ID).
    cont: 이어지는 표·그림('(계속)')의 번호 글자 — 번호를 늘리지 않게 번호 없는 모양에 번호를 글자로 넣는다
    (양식에 '(계속)' 제목 문단이 있으면 그 모양)."""
    head = caption_head(ctx, kind)
    if cont is not None:
        t = etree.Element(q("hp:t"))
        t.text = cont + " "
        segs = [(None, [t])] + list(segs)
        ex = ctx.tg_para(f"{kind} 계속")
        if ex is not None:
            pid = ctx.tg.para_pr(ex.get("paraPrIDRef"))
        else:
            ex = head
            pid = no_number(ctx, pp or ctx.tg.para_pr(head.get("paraPrIDRef")))
    elif is_inline(head):
        return inline_caption_para(ctx, ctx.tg.copy(head), segs, kind)
    else:
        ex, pid = head, pp or ctx.tg.para_pr(head.get("paraPrIDRef"))
    p = etree.Element(q("hp:p"))
    for k, v in (("id", "0"), ("paraPrIDRef", pid), ("styleIDRef", ctx.tg.style(ex.get("styleIDRef"))), ("pageBreak", "0"),
                 ("columnBreak", "0"), ("merged", "0")):
        p.set(k, v)
    ctx.set_seg_runs(p, ctx.tg.char_pr(text_run_cid(ex)), segs)
    return p


# --- 표 · 그림

def cell_addr(tc):
    a, s = tc.find(q("hp:cellAddr")), tc.find(q("hp:cellSpan"))
    return int(a.get("rowAddr")), int(a.get("colAddr")), int(s.get("rowSpan")), int(s.get("colSpan"))


def direct_cells(tbl):
    return [tc for tr in tbl.findall(q("hp:tr")) for tc in tr.findall(q("hp:tc"))]


def make_inline(obj):
    pos = obj.find(q("hp:pos"))
    for k, v in (("treatAsChar", "1"), ("affectLSpacing", "0"), ("flowWithText", "1"), ("allowOverlap", "0"),
                 ("vertRelTo", "PARA"), ("horzRelTo", "PARA"), ("vertAlign", "TOP"), ("horzAlign", "LEFT"),
                 ("vertOffset", "0"), ("horzOffset", "0")):
        pos.set(k, v)
    obj.set("textWrap", "TOP_AND_BOTTOM")


def cell_format(ctx: Ctx, ttc, style_name=None):
    sl = ttc.find(q("hp:subList"))
    if style_name:
        st = ctx.tgp.style_named(style_name)
        pp, sid, cp = st.get("paraPrIDRef"), st.get("id"), st.get("charPrIDRef")
    else:
        p = sl.find(q("hp:p"))
        pp, sid, cp = p.get("paraPrIDRef"), p.get("styleIDRef"), text_run_cid(p)
    return {"pp": ctx.tg.para_pr(pp), "st": ctx.tg.style(sid), "cp": ctx.tg.char_pr(cp),
            "margin": dict(ttc.find(q("hp:cellMargin")).attrib), "valign": sl.get("vertAlign")}


def apply_cell_format(ctx: Ctx, tc, f):
    """셀에 양식 셀의 여백·세로 정렬·문단/글자 모양을 입힌다(원고 run의 글자색은 결정대로 살림)."""
    tc.set("hasMargin", "0")
    cm = tc.find(q("hp:cellMargin"))
    for k, v in f["margin"].items():
        cm.set(k, v)
    sl = tc.find(q("hp:subList"))
    sl.set("vertAlign", f["valign"])
    for p in sl.findall(q("hp:p")):
        p.set("paraPrIDRef", "@" + f["pp"])
        p.set("styleIDRef", "@" + f["st"])
        for run in p.findall(q("hp:run")):
            run.set("charPrIDRef", "@" + ctx.keep_color(f["cp"], run.get("charPrIDRef")))


def table_border_spec(ctx: Ctx, tmpl):
    """양식 표 셀 테두리에서 바깥선·안쪽선·머리행 구분선·머리행 배경을 뽑는다."""
    bfs = ctx.tgp.items("borderFill")
    cells = {cell_addr(tc)[:2]: tc for tc in direct_cells(tmpl)}
    head_rows = max(cell_addr(tc)[2] for tc in tmpl.find(q("hp:tr")).findall(q("hp:tc")))
    corner = cells[(0, 0)]
    mid = cells.get((2, 1))
    if mid is None:
        mid = next((tc for (r, c), tc in sorted(cells.items()) if r >= head_rows and c >= 1), None)
    if mid is None:
        raise RuntimeError("양식 표가 3×2보다 작아 안쪽 선을 알 수 없다")

    def side(tc, name):
        return bfs[tc.get("borderFillIDRef")].find(q("hh:" + name))
    return {"outer": side(corner, "leftBorder"), "inner": side(mid, "leftBorder"),
            "head_sep": side(corner, "bottomBorder"),
            "head_fill": bfs[corner.get("borderFillIDRef")].find(q("hc:fillBrush")),
            "body_fill": bfs[mid.get("borderFillIDRef")].find(q("hc:fillBrush")),
            "base": bfs[mid.get("borderFillIDRef")], "cells": cells, "head_rows": head_rows}


def cell_border(ctx: Ctx, spec, left, right, top, bottom, head, below_head, above_body) -> str:
    el = copy.deepcopy(spec["base"])

    def put(name, src):
        new = copy.deepcopy(src)
        new.tag = q("hh:" + name)
        el.replace(el.find(q("hh:" + name)), new)
    put("leftBorder", spec["outer"] if left else spec["inner"])
    put("rightBorder", spec["outer"] if right else spec["inner"])
    put("topBorder", spec["outer"] if top else (spec["head_sep"] if below_head else spec["inner"]))
    put("bottomBorder", spec["outer"] if bottom else (spec["head_sep"] if above_body else spec["inner"]))
    old = el.find(q("hc:fillBrush"))
    if old is not None:
        el.remove(old)
    fill = spec["head_fill"] if head else spec["body_fill"]
    if fill is not None:
        el.append(copy.deepcopy(fill))
    return ctx.dst.add("borderFill", el)


def set_table_attrs(ctx: Ctx, tbl, tmpl):
    for a in ("numberingType", "textWrap", "textFlow", "lock", "dropcapstyle", "pageBreak", "repeatHeader",
              "cellSpacing", "noAdjust"):
        if tmpl.get(a) is not None:
            tbl.set(a, tmpl.get(a))
    tbl.set("borderFillIDRef", "@" + ctx.tg.border_fill(tmpl.get("borderFillIDRef")))
    for cz in tbl.findall(q("hp:cellzoneList")):
        tbl.remove(cz)
        ctx.log.append("⚠ 표의 셀 영역 테두리(cellzoneList) 삭제")


def restyle_table(ctx: Ctx, tbl, tmpl, pno):
    rows = tbl.findall(q("hp:tr"))
    R_, C_ = int(tbl.get("rowCnt")), int(tbl.get("colCnt"))
    H = max(cell_addr(tc)[2] for tc in rows[0].findall(q("hp:tc")))
    spec = table_border_spec(ctx, tmpl)
    cells, hr = spec["cells"], spec["head_rows"]
    t_head = cells[(0, 0)]
    t_body = next((cells[a] for a in ((1, 1), (1, 0)) if a in cells and hr == 1), None)
    if t_body is None:
        t_body = next((cells[a] for a in ((hr, 1), (hr, 0)) if a in cells), None)
    if t_body is None:
        t_body = next(tc for (r, c), tc in sorted(cells.items()) if r >= hr)
    fh, fb = cell_format(ctx, t_head), cell_format(ctx, t_body)
    min_h = {True: int(t_head.find(q("hp:cellSz")).get("height")),
             False: int(t_body.find(q("hp:cellSz")).get("height"))}
    raised = 0
    for tc in direct_cells(tbl):
        r, c, rs, cs = cell_addr(tc)
        bf = cell_border(ctx, spec, left=c == 0, right=c + cs == C_, top=r == 0, bottom=r + rs == R_,
                         head=r < H, below_head=(r == H), above_body=(r + rs == H))
        tc.set("borderFillIDRef", "@" + bf)
        apply_cell_format(ctx, tc, fh if r < H else fb)
        sz = tc.find(q("hp:cellSz"))
        if int(sz.get("height")) < 0.9 * min_h[r < H] * rs:  # 양식보다 확실히 낮은 행만
            sz.set("height", str(min_h[r < H] * rs))
            raised += 1
    if raised:
        ctx.log.append(f"{pno} 표 셀 {raised}개의 높이를 양식 행 높이({min_h[False]})로 올림")
    set_table_attrs(ctx, tbl, tmpl)


def body_height(ctx: Ctx) -> int:
    pg, m = ctx.base.page()
    return int(pg.get("height")) - m["top"] - m["bottom"] - m["header"] - m["footer"]


def body_width(ctx: Ctx) -> int:
    pg, m = ctx.base.page()
    return int(pg.get("width")) - m["left"] - m["right"] - m["gutter"]


def fit_table_width(ctx: Ctx, tbl, pno):
    """본문 폭보다 넓은 표 → 열 너비를 같은 비율로 줄여 본문 폭에 맞춘다(열 비율·행 높이·글자는 그대로)."""
    width, limit = int(tbl.find(q("hp:sz")).get("width")), body_width(ctx)
    if width <= limit + MM:  # 1 mm 안쪽 차이는 그대로(양식 여백 안에서 보이지 않음)
        return
    C_ = int(tbl.get("colCnt"))
    col = {}
    for tc in direct_cells(tbl):
        r, c, rs, cs = cell_addr(tc)
        if cs == 1:
            col.setdefault(c, int(tc.find(q("hp:cellSz")).get("width")))
    if len(col) != C_:  # 한 칸짜리 셀이 없는 열이 있으면 줄이지 않는다
        ctx.log.append(f"⚠ {pno} 표 폭 {width / MM:.0f} mm > 본문 폭 {limit / MM:.0f} mm인데 열 너비를 못 정해 그대로 둠")
        return
    total = sum(col.values())
    new = {c: col[c] * limit // total for c in range(C_)}
    new[C_ - 1] += limit - sum(new.values())  # 반올림 차이는 마지막 열에
    for tc in direct_cells(tbl):
        r, c, rs, cs = cell_addr(tc)
        tc.find(q("hp:cellSz")).set("width", str(sum(new[k] for k in range(c, c + cs))))
    tbl.find(q("hp:sz")).set("width", str(limit))
    ctx.log.append(f"{pno} 표 폭 {width / MM:.1f} mm > 본문 폭 {limit / MM:.0f} mm → 열 너비를 같은 비율로 줄여 {limit / MM:.0f} mm")


def repeat_header_rows(tbl):
    """쪽 경계에서 나뉘는 표: 머리행(첫 행에 걸친 행)을 제목 셀로 — 다음 쪽에서 머리행이 반복된다."""
    H = max(cell_addr(tc)[2] for tc in tbl.find(q("hp:tr")).findall(q("hp:tc")))
    tbl.set("repeatHeader", "1")
    n = 0
    for tc in direct_cells(tbl):
        if cell_addr(tc)[0] < H and tc.get("header") != "1":
            tc.set("header", "1")
            n += 1
    return n


def make_floating_block(tbl):
    """쪽보다 긴 표: 글자처럼 취급을 끄고 '자리 차지'로 둬서 쪽 경계에서 나뉘게 한다."""
    pos = tbl.find(q("hp:pos"))
    for k, v in (("treatAsChar", "0"), ("affectLSpacing", "0"), ("flowWithText", "1"), ("allowOverlap", "0"),
                 ("holdAnchorAndSO", "0"), ("vertRelTo", "PARA"), ("horzRelTo", "COLUMN"), ("vertAlign", "TOP"),
                 ("horzAlign", "CENTER"), ("vertOffset", "0"), ("horzOffset", "0")):
        pos.set(k, v)
    tbl.set("textWrap", "TOP_AND_BOTTOM")


def table_label(tbl, n=24) -> str:
    """알림용 표 이름: 캡션 글자, 없으면 첫 칸들 글자."""
    cap = tbl.find(q("hp:caption"))
    src = cap if cap is not None else tbl
    t = re.sub(r"\s+", " ", " ".join("".join(x.itertext()) for x in src.iter(q("hp:t")))).strip()
    return t[:n] + ("…" if len(t) > n else "")


def table_split_mode(ctx: Ctx, tbl) -> str:
    """결정 '표 나누기'(설문 — 한글 메뉴 이름 "나눔"/"셀 단위로 나눔") → pageBreak 값.
    결정이 없으면 표에 있던 값(CELL·TABLE), 그것도 아니면 "CELL"(나눔 — 한 행이 길어도 넘치지 않음)."""
    want = ctx.D.get("표 나누기")
    if want in tf.PAGE_BREAK:
        return tf.PAGE_BREAK[want]
    return tbl.get("pageBreak") if tbl.get("pageBreak") in ("CELL", "TABLE") else "CELL"


def secure_tables(ctx: Ctx, secs):
    """한 쪽을 넘는 본문 표 → 글자처럼 취급을 끄고 '자리 차지'로, 쪽 경계에서 나뉘게, 머리행은 쪽마다 반복.
    글자처럼 취급인 표는 쪽을 넘지 못해 아래가 꼬리말 쪽으로 넘친다(사용자 보고 2026-11-03, 한글 PDF로 확인).
    한 쪽 안에 드는 표는 양식대로 둔다 — 쪽 끝에 걸리면 통째로 다음 쪽으로 넘어간다(사용자 결정 2026-11-03).
    원고 셀 높이 값은 최소 높이일 뿐이라 높이는 셀 글자로 어림한다(table_fit — 쪽에서 차지할 높이가
    본문 높이의 99 %를 넘으면 나눔: 어림 오차 여유).
    표는 설문 답(결정 '표 나누기'), 그림 틀(사진 묶음)은 사진과 설명이 갈리지 않게 늘 '셀 단위로 나눔'.
    '셀 단위로 나눔'(행을 통째로 넘김)은 반복 머리행 + 한 행이 쪽보다 길면 그 행이 넘치므로 그 표만 '나눔'으로."""
    M = tf.Metrics(ctx.dst.header)
    limit = body_height(ctx)
    for sec in secs:
        for tbl in tf.top_tables(sec):
            if not tf.has_text(tbl):  # 그림만 담은 틀 — 나눠도 소용없다
                continue
            total, rows = M.page_height(tbl)
            if total <= tf.FIT * limit:
                continue
            was = "글자처럼 취급" if tbl.find(q("hp:pos")).get("treatAsChar") == "1" else "자리 차지"
            make_floating_block(tbl)
            frame = any(t is tbl for t in ctx.frame_tbls)
            styled = any(t is tbl for t in ctx.styled_tbls)
            n = repeat_header_rows(tbl) if styled else 0
            if not styled and any(tc.get("header") == "1" for tc in direct_cells(tbl)):
                tbl.set("repeatHeader", "1")  # 원고 표는 원고가 정한 제목 셀만 반복
            rep = tf.repeats_header(tbl)
            mode, note = ("TABLE" if frame else table_split_mode(ctx, tbl)), ""  # 그림 틀은 사진 줄을 통째로
            if mode == "TABLE" and tf.row_too_tall(rows, tf.head_rows(tbl), rep, limit):
                mode = "CELL"
                note = f"한 행이 쪽 높이에 가까워({max(rows) / MM:.0f}mm) '셀 단위로 나눔' 대신 '나눔'(행이 넘치지 않게)"
            tbl.set("pageBreak", mode)
            info = {"표": table_label(tbl), "종류": "그림" if frame else "표", "높이mm": round(total / MM),
                    "본문높이mm": round(limit / MM), "나누기": tf.PAGE_BREAK_NAME[mode], "전": was, "머리행반복": rep,
                    "알림": note}
            if tbl.find(q("hp:caption")) is None:  # 제목을 따로 문단으로 둔 표 → 그 제목으로 부른다
                name = next((t for x, t in ctx.tbl_names if x is tbl and t), "")
                if name:
                    info["표"] = name[:24] + ("…" if len(name) > 24 else "")
            ctx.big_tables.append(info)
            ctx.log.append(f"표 '{info['표']}' 쪽에서 차지할 높이 어림 {total / MM:.0f}mm > 본문 높이 {limit / MM:.0f}mm → "
                           f"{was}을 끄고 자리 차지, 쪽 경계에서 '{info['나누기']}'"
                           + (f", 머리행 셀 {n}개를 제목 셀로(쪽마다 반복)" if n else ""))
            if note:
                ctx.log.append(f"⚠ 표 '{info['표']}': {note}")


def table_plan(R: Run) -> list:
    """설문 전(역할매핑 뒤): 결과에서 한 쪽을 넘는 표를 미리 어림한다(그림 내용은 읽지 않음, 파일도 쓰지 않음)."""
    ctx = Ctx(R, dry=True)
    build_body(ctx)
    return ctx.big_tables


def para_geom(pkg: Pkg, pid):
    """문단 정렬과 왼쪽·오른쪽 여백(HWPUNIT, case 그대로·default/plain 반)."""
    pp = pkg.items("paraPr")[pid]
    al = pp.find(q("hh:align")).get("horizontal")
    sw = pp.find(q("hp:switch"))
    case = sw.find(q("hp:case")) if sw is not None else None
    src, scale = (case, 1.0) if case is not None else ((sw.find(q("hp:default")) if sw is not None else pp), 0.5)
    m = src.find(q("hh:margin"))

    def val(k):
        e = m.find(q("hc:" + k)) if m is not None else None
        return int(int(e.get("value")) * scale) if e is not None else 0
    return al, val("left"), val("right")


def border_hwpunit(ctx: Ctx, tmpl) -> int:
    bf = ctx.tgp.items("borderFill")[direct_cells(tmpl)[0].get("borderFillIDRef")]
    widths = [float(re.match(r"[\d.]+", e.get("width", "0")).group()) for e in bf
              if local(e) in ("leftBorder", "topBorder") and e.get("type") != "NONE"]
    return round(max(widths, default=0) * MM)


def anchor_in_cell(ctx: Ctx, objs, tbl_src, tmpl, src_p, pno, border=0):
    """그림 위에 떠 있던 개체(종이 기준)를 그림 틀 셀 안 문단에 매달아 틀과 함께 움직이게 한다.
    한글은 셀 안 개체의 '문단 기준' 위치를 표를 담은 바깥 문단 왼쪽 위에서 잰다 → 원고의 '틀에 대한 위치'를
    결과의 틀 위치에 더한다. 틀 선에 걸치는 개체는 선 바깥쪽 반만큼 안으로."""
    pg, mg = ctx.msp.page()
    if pg.get("gutterType") == "LEFT_RIGHT" and mg["gutter"]:
        ctx.log.append(f"⚠ {pno} 원고가 맞쪽 제본이라 가로 위치 환산이 쪽마다 다를 수 있음")
    col_left = mg["left"] + (mg["gutter"] if pg.get("gutterType") == "LEFT_ONLY" else 0)
    col_w = int(pg.get("width")) - mg["left"] - mg["right"] - mg["gutter"]
    ls = src_p.find(f"{q('hp:linesegarray')}/{q('hp:lineseg')}")
    para_top = mg["top"] + mg["header"] + (int(ls.get("vertpos")) if ls is not None else 0)
    al, pl, pr = para_geom(ctx.msp, src_p.get("paraPrIDRef"))
    om = {k: int(v) for k, v in tbl_src.find(q("hp:outMargin")).attrib.items()}
    frame_w = int(tbl_src.find(q("hp:sz")).get("width")) + om["left"] + om["right"]
    avail = col_w - pl - pr
    x0 = pl + {"CENTER": (avail - frame_w) // 2, "RIGHT": avail - frame_w}.get(al, 0)
    frame_x, frame_y = col_left + x0 + om["left"], para_top + om["top"]
    bpg, bm = ctx.base.page()
    out_w = int(bpg.get("width")) - bm["left"] - bm["right"] - bm["gutter"]
    nom = {k: int(v) for k, v in tmpl.find(q("hp:outMargin")).attrib.items()}
    nframe_w = int(tbl_src.find(q("hp:sz")).get("width")) + nom["left"] + nom["right"]
    nx, ny = (out_w - nframe_w) // 2 + nom["left"], nom["top"]
    lim = {"vertOffset": ny + border // 2, "horzOffset": nx + border // 2}
    out, clamped = [], 0
    for o in objs:
        c = copy.deepcopy(o)
        pos = c.find(q("hp:pos"))
        for rel, off, src0, dst0 in (("vertRelTo", "vertOffset", frame_y, ny), ("horzRelTo", "horzOffset", frame_x, nx)):
            if pos.get(rel) == "PAPER":
                v = s32(pos.get(off)) - src0 + dst0
                if v < lim[off]:
                    v, clamped = lim[off], clamped + 1
                pos.set(off, u32(v))
                pos.set(rel, "PARA")
        out.append(c)
    ctx.log.append(f"{pno} 떠 있는 개체 {len(out)}개 → 그림 틀 셀 안에 매닮(틀과 함께 움직임, 틀에 대한 위치 유지)"
                   + (f", 틀 선에 걸친 위치 {clamped}곳은 선 안쪽으로" if clamped else ""))
    return out


def cell_empty(tc) -> bool:
    for p in tc.find(q("hp:subList")).findall(q("hp:p")):
        if own_text(p).strip() or any(local(o) in OBJ for r in p.findall(q("hp:run")) for o in r):
            return False
    return True


def restyle_frame(ctx: Ctx, tbl, tmpl, floats, pno):
    """그림 틀(표)에 양식 틀의 선·여백과 '그림 틀 안' 문단 모양을 입힌다. 빈 틀 안으로 옮긴 떠 있는 개체를 돌려준다."""
    ttc = direct_cells(tmpl)[0]
    f = cell_format(ctx, ttc, ctx.R["표그림"].get("그림 틀 안 스타일"))
    bf = ctx.tg.border_fill(ttc.get("borderFillIDRef"))
    cells = direct_cells(tbl)
    for tc in cells:
        tc.set("borderFillIDRef", "@" + bf)
        apply_cell_format(ctx, tc, f)
    ml, mr = int(f["margin"]["left"]), int(f["margin"]["right"])
    for tc in cells:  # 셀 높이에 자리가 안 잡힌 떠 있는 그림 → 셀 폭 안에 들어가면 글자처럼 취급
        inner_w = int(tc.find(q("hp:cellSz")).get("width")) - ml - mr
        cell_h = int(tc.find(q("hp:cellSz")).get("height"))
        for p in tc.find(q("hp:subList")).findall(q("hp:p")):
            for run in p.findall(q("hp:run")):
                for pic in run.findall(q("hp:pic")):
                    pos, sz = pic.find(q("hp:pos")), pic.find(q("hp:sz"))
                    if pos.get("treatAsChar") == "0" and cell_h < int(sz.get("height")) and int(sz.get("width")) <= inner_w:
                        make_inline(pic)
                        ctx.log.append(f"{pno} 그림 틀 안 떠 있는 그림(셀 높이 {cell_h} < 그림 높이 {sz.get('height')}) → 글자처럼 취급")
    moved = []
    if floats and len(cells) == 1 and cell_empty(cells[0]):
        cp = cells[0].find(q("hp:subList")).find(q("hp:p"))
        run = cp.find(q("hp:run"))
        if run is None:
            run = etree.SubElement(cp, q("hp:run"))
            run.set("charPrIDRef", "@" + f["cp"])
        for i, fl in enumerate(o for o in floats if local(o) in ("container", "pic")):
            c = copy.deepcopy(fl)
            make_inline(c)
            run.insert(i, c)
            moved.append(fl)
            ctx.log.append(f"{pno} 빈 그림 틀 위에 떠 있던 {local(fl)} → 틀 안에 글자처럼 취급으로 넣음")
    set_table_attrs(ctx, tbl, tmpl)
    return moved


def reposition_float(ctx: Ctx, obj, src_p, pno):
    """(틀 밖) 종이 기준 위치 → 문단·단 기준. 원고 줄 배치 정보로 거리를 환산."""
    pos = obj.find(q("hp:pos"))
    if pos.get("treatAsChar") == "1":
        return
    pg, mg = ctx.msp.page()
    ls = src_p.find(f"{q('hp:linesegarray')}/{q('hp:lineseg')}")
    para_top = mg["top"] + mg["header"] + (int(ls.get("vertpos")) if ls is not None else 0)
    col_left = mg["left"] + (mg["gutter"] if pg.get("gutterType") == "LEFT_ONLY" else 0)
    if pos.get("vertRelTo") == "PAPER":
        pos.set("vertOffset", u32(s32(pos.get("vertOffset")) - para_top))
        pos.set("vertRelTo", "PARA")
    if pos.get("horzRelTo") == "PAPER":
        pos.set("horzOffset", u32(s32(pos.get("horzOffset")) - col_left))
        pos.set("horzRelTo", "COLUMN")
    ctx.log.append(f"{pno} 떠 있는 {local(obj)} 위치 기준: 종이 → 문단/단")


def no_number(ctx: Ctx, pid) -> str:
    """문단 번호를 뺀 문단 모양(캡션 둘째 문단부터 — 같은 모양이면 번호가 또 붙는다)."""
    def fn(n):
        hd = n.find(q("hh:heading"))
        if hd is None or hd.get("type") == "NONE":
            return False
        hd.set("type", "NONE")
        hd.set("idRef", "0")
        hd.set("level", "0")
    return ctx.dst.variant("paraPr", pid, fn)


def build_caption(ctx: Ctx, tmpl, cap_ps, width, pp, kind="그림", cont=None):
    """개체에 붙는 캡션. cont: 이어지는 표·그림('(계속)')의 번호 글자 — 자동 번호 대신 글자로 넣어 번호를 늘리지 않는다."""
    tcap = tmpl.find(q("hp:caption"))
    if tcap is None or not cap_ps:
        return None
    cap = ctx.tg.copy(tcap)
    cap.set("lastWidth", width)
    sl = cap.find(q("hp:subList"))
    tps = sl.findall(q("hp:p"))
    head, tail = tps[0], [p for p in tps[1:] if not own_text(p).strip()]
    cid = text_run_cid(head)
    inline = is_inline(head)
    for p in tps:
        sl.remove(p)
    for k, segs in enumerate(cap_ps):
        if cont is not None and k == 0:  # 번호를 글자로(번호 없는 모양) — 글자 안 자동 번호도 넣지 않는다
            t = etree.Element(q("hp:t"))
            t.text = cont + " "
            np = ctx.set_seg_runs(copy.deepcopy(head), cid, [(None, [t])] + list(segs))
            if not inline:
                np.set("paraPrIDRef", no_number(ctx, pp))
        elif inline:  # 양식 캡션 번호가 글자 안 자동 번호 → 첫 문단에 번호 부분, 둘째부터는 글자만
            np = inline_caption_para(ctx, head, segs, kind) if k == 0 else ctx.set_seg_runs(copy.deepcopy(head), cid, segs)
        else:
            np = ctx.set_seg_runs(copy.deepcopy(head), cid, segs)
            np.set("paraPrIDRef", pp if k == 0 else no_number(ctx, pp))  # 번호는 첫 문단에만(이 장의 캡션 번호)
        sl.append(np)
    for p in tail:
        p.set("id", "0")
        sl.append(p)
    strip_layout(cap)
    return cap


def set_shell(ctx: Ctx, tbl, tmpl, cap_ps, pp, kind="그림", cont=None):
    """표 개체의 위치·바깥 여백·캡션·안 여백을 양식 것으로(크기·행·셀은 원고 그대로).
    양식 개체에 캡션이 없으면(제목을 따로 문단으로 두는 양식) 캡션을 달지 않는다."""
    for name in ("pos", "outMargin", "caption", "inMargin"):
        old = tbl.find(q("hp:" + name))
        if old is not None:
            tbl.remove(old)
    sz = tbl.find(q("hp:sz"))
    new = [ctx.tg.copy(tmpl.find(q("hp:pos"))), ctx.tg.copy(tmpl.find(q("hp:outMargin")))]
    cap = build_caption(ctx, tmpl, cap_ps, sz.get("width"), pp, kind, cont)
    if cap is not None:
        new.append(cap)
    new.append(ctx.tg.copy(tmpl.find(q("hp:inMargin"))))
    at = list(tbl).index(sz) + 1
    for k, el in enumerate(new):
        tbl.insert(at + k, el)


def center_no_indent(n):
    """문단 모양 변형: 가운데 정렬, 왼쪽·오른쪽 여백과 첫 줄 들여쓰기 0(표·그림을 담는 문단)."""
    changed = False
    for al in n.iter(q("hh:align")):
        if al.get("horizontal") != "CENTER":
            al.set("horizontal", "CENTER")
            changed = True
    for m in n.iter(q("hh:margin")):
        for k in ("intent", "left", "right"):
            e = m.find(q("hc:" + k))
            if e is not None and e.get("value") != "0":
                e.set("value", "0")
                changed = True
    return None if changed else False


def object_paragraph(ctx: Ctx, sec, objs, kind="표"):
    """표·그림을 담는 문단 — 손 프로필은 양식 스타일 「본문그림」 정의값(가운데, 여백 0). 예시 문단의 들여쓰기는 쓰지 않는다.
    자동 분석 프로필은 양식에서 표(그림)를 담은 문단 모양을 가운데 정렬·여백 0으로 바꿔 쓴다."""
    name = ctx.R["표그림"].get("개체 문단 스타일")
    if name:
        st = ctx.tgp.style_named(name)
        pp, sid, cid = ctx.tg.para_pr(st.get("paraPrIDRef")), ctx.tg.style(st.get("id")), ctx.tg.char_pr(st.get("charPrIDRef"))
    else:
        ex = ctx.tg_para(kind) if ctx.tg_para(kind) is not None else ctx.tg_para("그림" if kind == "표" else "표")
        pp = ctx.dst.variant("paraPr", ctx.tg.para_pr(ex.get("paraPrIDRef")), center_no_indent)
        sid, cid = ctx.tg.style(ex.get("styleIDRef")), ctx.tg.char_pr(text_run_cid(ex))
    p = etree.SubElement(sec, q("hp:p"))
    for k, v in (("id", "0"), ("paraPrIDRef", pp), ("styleIDRef", sid), ("pageBreak", "0"), ("columnBreak", "0"),
                 ("merged", "0")):
        p.set(k, v)
    run = etree.SubElement(p, q("hp:run"))
    run.set("charPrIDRef", cid)
    for o in objs:
        run.append(o)
    etree.SubElement(run, q("hp:t"))
    return p


def caption_ts(ctx: Ctx, r, tbl_src, numbered=True, mode="붙음"):
    """캡션 글자(문단마다 text_segs 글자 조각): 개체에 붙은 캡션, 따로 떨어진 캡션 문단, 또는 역할판단의 '캡션바꿈'.
    승인된 변경(직접 친 번호·앞뒤 공백)을 적용한다 — 양식 제목에 자동 번호가 없으면(numbered=False) 친 번호를 그대로 둔다."""
    mp = ctx.msp.paras()
    cap_src = tbl_src.find(q("hp:caption"))
    sep = next((x for x in ctx.roles if x.get("붙일곳") == r["문단"]), None)
    if sep and (cap_src is None or sep.get("캡션바꿈")):
        if cap_src is not None:
            old = " / ".join(own_text(p).strip() for p in cap_src.iter(q("hp:p")) if own_text(p).strip())
            ctx.approved.append({"문단": r["문단"], "내용": f"기존 캡션 '{old}' 대신 {sep['문단']} 글자를 캡션으로(역할판단)"})
            ctx.log.append(f"{r['문단']} 기존 캡션 '{old}' 버림 → {sep['문단']} 글자를 캡션으로(역할판단)")
        else:
            ctx.log.append(f"{sep['문단']} 따로 떨어진 캡션 → {r['문단']}의 캡션(아래)으로")
        ps = [caption_segs(ms_para(mp, sep["문단"]))]
    elif cap_src is not None:
        allp = cap_src.find(q("hp:subList")).findall(q("hp:p"))
        keep = (r.get("캡션") or {}).get("캡션문단")
        ps = [caption_segs(allp[j]) for j in (keep if keep is not None else range(len(allp)))]
        if keep is not None and len(keep) < len(allp):
            ctx.log.append(f"{r['문단']} 캡션 칸 문단 {len(allp)}개 중 {len(allp) - len(keep)}개는 본문으로 꺼냄(역할매핑 '꺼냄')")
        if cap_src.get("side") != "BOTTOM" and mode == "붙음":
            ctx.log.append(f"{r['문단']} 캡션 위치 {cap_src.get('side')} → BOTTOM")
    elif r.get("캡션추가"):  # 원고에 캡션이 없는 개체 — 사용자가 승인한 캡션 글자를 새로 단다(역할판단 '캡션추가')
        t = etree.Element(q("hp:t"))
        t.text = r["캡션추가"]
        ctx.approved.append({"문단": r["문단"], "내용": f"캡션 없던 개체에 캡션 '{r['캡션추가']}' 새로 넣음(사용자 승인)"})
        ctx.log.append(f"{r['문단']} 캡션 없음 → '{r['캡션추가']}' 새로 넣음(역할판단 '캡션추가', 사용자 승인)")
        return [[(None, [t])]]
    else:
        ps = []
    ps = [segs for segs in ps if plain(flat(segs)).strip()]
    if ps and numbered:
        ps[0] = norm_caption_segs(ctx, r, ps[0])
    return ps


def raw_caption(ctx: Ctx, r, tbl_src) -> str:
    """원고 캡션 글자 그대로(번호 다듬기 없이) — 붙은 캡션(꺼낸 문단 빼고), 없으면 따로 떨어진 캡션 문단."""
    cap = tbl_src.find(q("hp:caption")) if tbl_src is not None else None
    if cap is not None:
        keep = (r.get("캡션") or {}).get("캡션문단")
        ps = cap.find(q("hp:subList")).findall(q("hp:p"))
        return " / ".join(s for s in (caption_text(p).strip() for j, p in enumerate(ps) if keep is None or j in keep) if s)
    sep = next((x for x in ctx.roles if x.get("붙일곳") == r["문단"]), None)
    return caption_text(ms_para(ctx.msp.paras(), sep["문단"])).strip() if sep else ""


def ms_copy(ctx: Ctx, el):
    """원고 요소를 결과 ID로 옮긴 사본(줄 배치 정보 없이)."""
    c = ctx.ms.copy(el)
    strip_layout(c)
    return c


def keep_original(ctx: Ctx, sec, r, src, kind, why):
    """원고 개체 문단을 원고 모양 그대로(개체·캡션 그대로, 결과 ID로만 옮김) — 양식 모양을 입히지 못할 때.
    따로 떨어진 원고 캡션 문단도 원래 자리(위·아래)에 그대로 둔다. 캡션 칸에서 본문으로 꺼낸 문단은 캡션에서 뺀다.
    돌려주는 값: 결과 문단 순서(out_roles를 맞추는 데)."""
    sep = next((x for x in ctx.roles if x.get("붙일곳") == r["문단"]), None)
    above = sep is not None and para_key(sep["문단"])[0] < para_key(r["문단"])[0]
    order = []

    def put_sep():
        c = ms_copy(ctx, ms_para(ctx.msp.paras(), sep["문단"]))
        c.set("id", "0")
        sec.append(c)
        order.append(("캡션", 0))
    if sep and above:
        put_sep()
    keep = []
    for o in objects(src):
        c = ms_copy(ctx, o)
        cap, out = c.find(q("hp:caption")), (r.get("캡션") or {}).get("꺼낼문단") or []
        if cap is not None and out and local(c) == "tbl":
            ps = cap.find(q("hp:subList")).findall(q("hp:p"))
            for j in sorted(out, reverse=True):
                ps[j].getparent().remove(ps[j])
        keep.append(c)
    object_paragraph(ctx, sec, keep, kind)
    order.append("개체")
    if sep and not above:
        put_sep()
    ctx.log.append(f"⚠ {r['문단']} {kind} '{raw_caption(ctx, r, next((o for o in objects(src) if local(o) == 'tbl'), None))[:30]}'"
                   f" — {why} 원고 모양 그대로 둠(한글에서 확인해 주세요)")
    return order


def caption_paras(ctx: Ctx, kind, cap_ps, pp, cont=None) -> list:
    """따로 놓인 제목 문단들: 첫 문단은 양식 제목(번호) 모양, 둘째부터는 번호 없는 같은 모양."""
    out = []
    for k, segs in enumerate(cap_ps):
        if k == 0:
            out.append(caption_para(ctx, kind, segs, pp, cont))
        elif is_inline(caption_head(ctx, kind)):
            head = ctx.tg.copy(caption_head(ctx, kind))
            out.append(ctx.set_seg_runs(head, text_run_cid(head), segs))
        else:
            out.append(caption_para(ctx, kind, segs, no_number(ctx, pp or ctx.tg.para_pr(caption_head(ctx, kind).get("paraPrIDRef")))))
    return out


def build_object(ctx: Ctx, sec, r, kind, chap, counts=None):
    """원고 표·그림 문단 → 양식 표 모양·그림 틀 + 양식 제목(캡션).
    제목은 양식 방식대로: 개체에 붙은 캡션('붙음') 또는 개체 위·아래에 따로 놓인 제목 문단('문단').
    '(계속)'이 붙은 제목은 앞 표·그림과 같은 번호를 글자로 넣는다(번호를 늘리지 않음 — counts: 이 장에서 센 번호).
    돌려주는 값 (캡션 글자, 번호, 정보) — 정보 '순서': 결과 문단 순서('개체'·('캡션', k)), '계속': 글자로 넣은 번호,
    '원고 그대로': 개체·캡션 모두 원고 모양, '원고 캡션': 캡션만 원고 것, '번호 둠': 원고에 친 번호를 지우지 않음."""
    src = ms_para(ctx.msp.paras(), r["문단"])
    objs = objects(src)
    tbl_src = next(o for o in objs if local(o) == "tbl")
    floats = [o for o in objs if o is not tbl_src]
    tmpl = ctx.tmpl_tbl(kind)
    if tmpl is None:  # 양식에 이 종류(표·그림) 예시가 없음 → 원고 개체 모양을 그대로(캡션도 원고 것)
        order = keep_original(ctx, sec, r, src, kind, f"양식에 {kind} 예시가 없어")
        return raw_caption(ctx, r, tbl_src), None, {"순서": order, "원고 그대로": True}
    mode, numbered = ctx.cap_mode(kind), ctx.cap_numbered(kind)
    cap_ps = caption_ts(ctx, r, tbl_src, numbered, mode) if mode else []
    tbl = copy.deepcopy(tbl_src)
    old_cap = tbl.find(q("hp:caption"))
    if old_cap is not None:
        tbl.remove(old_cap)
    if tbl.find(q("hp:pos")).get("treatAsChar") != "1":
        ctx.log.append(f"{r['문단']} {kind} 글자처럼 취급 아님(배치 {tbl.get('textWrap')}) → 글자처럼 취급")
    moved = []
    if kind == "표":
        restyle_table(ctx, tbl, tmpl, r["문단"])
        fit_table_width(ctx, tbl, r["문단"])
    else:
        moved = restyle_frame(ctx, tbl, tmpl, floats, r["문단"])
        left = [o for o in floats if o not in moved]
        cells = direct_cells(tbl)
        if left and len(cells) == 1:
            run = cells[0].find(q("hp:subList")).find(q("hp:p")).find(q("hp:run"))
            for k, c in enumerate(anchor_in_cell(ctx, left, tbl_src, tmpl, src, r["문단"], border_hwpunit(ctx, tmpl))):
                run.insert(k, c)
            moved += left
    ctx.ms.remap(tbl)
    pp, num = chapter_caption_pp(ctx, kind, chap)
    text = " ".join(plain(flat(segs)).strip() for segs in cap_ps)
    info = {"순서": ["개체"]}
    if counts is not None and cap_ps and num is not None and counts.get(kind, 0) > 0 and CONT_WORD.search(text):
        info["계속"] = cap_label(num, counts[kind], ctx.cap_total[kind])  # 앞 표·그림과 같은 번호
    if not numbered:
        info["번호 둠"] = True
    set_shell(ctx, tbl, tmpl, cap_ps if mode == "붙음" else [], pp, kind, info.get("계속"))
    if mode is None:  # 양식에 제목 모양이 없음 → 원고 캡션을 원고 모양 그대로(번호도 원고 것)
        info["원고 캡션"] = True
        text = raw_caption(ctx, r, tbl_src)
        cap_src = tbl_src.find(q("hp:caption"))
        if cap_src is not None:
            cap = ms_copy(ctx, cap_src)
            for j in sorted((r.get("캡션") or {}).get("꺼낼문단") or [], reverse=True):
                p = cap.find(q("hp:subList")).findall(q("hp:p"))[j]
                p.getparent().remove(p)
            tbl.insert(list(tbl).index(tbl.find(q("hp:inMargin"))), cap)
        if text:
            ctx.log.append(f"⚠ {r['문단']} 양식에 {kind} 제목(캡션) 모양이 없어 원고 제목을 원고 모양·번호 그대로 둠")
    if kind == "표":  # 쪽보다 길면 secure_tables가 쪽 경계에서 나뉘게 한다(머리행 반복 포함)
        ctx.styled_tbls.append(tbl)
    else:  # 그림 틀(사진 묶음 등): 쪽보다 길면 사진 줄이 잘리지 않게 행 단위로 나눈다
        ctx.frame_tbls.append(tbl)
    ctx.tbl_names.append((tbl, text))
    rest = []
    for fl in floats:
        if fl in moved:
            continue
        c = copy.deepcopy(fl)
        reposition_float(ctx, c, src, r["문단"])
        ctx.ms.remap(c)
        rest.append(c)
    sep = next((x for x in ctx.roles if x.get("붙일곳") == r["문단"]), None)
    if mode == "문단" and cap_ps:  # 제목을 개체 위(표)·아래(그림)에 따로 문단으로 — 개체와 같은 쪽에 오게 한다
        caps = caption_paras(ctx, kind, cap_ps, pp, info.get("계속"))
        above = ctx.cap_pos(kind) == "위"
        for c in (caps if above else caps[:-1]):
            c.set("paraPrIDRef", ctx.dst.keep_with_next(c.get("paraPrIDRef")))
        blank = []
        if above and ctx.out_roles and ctx.out_roles[-1]["역할"] in ("표 문단", "그림 문단", "개체 문단", "캡션 문단") \
                and ctx.R["본문"].get("빈 줄"):  # 앞 표·그림 바로 밑에 제목이 붙지 않게 — 양식처럼 표 뒤 빈 줄 하나
            ex = ctx.base.paras()[int(ctx.R["본문"]["빈 줄"][1:])]
            blank = [set_runs(copy.deepcopy(ex), ctx.tcolor(text_run_cid(ex)), [])]
            ctx.log.append(f"{r['문단']} 앞 {ctx.out_roles[-1]['원고']}의 표·그림 바로 뒤라 제목 앞에 빈 줄 하나(양식처럼)")
        if above:
            sec.extend(blank + caps)
        op = object_paragraph(ctx, sec, rest + [tbl], kind)
        if not above:
            op.set("paraPrIDRef", ctx.dst.keep_with_next(op.get("paraPrIDRef")))
            sec.extend(caps)
        ctx.log.append(f"{r['문단']} {kind} 제목 → 양식처럼 {kind} {'위' if above else '아래'}에 따로 문단으로"
                       + (f"(원고 {sep['문단']} 글자)" if sep else ""))
        info["순서"] = (["빈 줄"] * len(blank) + [("캡션", k) for k in range(len(caps))] + ["개체"]) if above else \
            (["개체"] + [("캡션", k) for k in range(len(caps))])
    elif mode is None and sep:  # 따로 떨어진 원고 제목 문단을 원래 자리에 원고 모양 그대로
        above = para_key(sep["문단"])[0] < para_key(r["문단"])[0]
        c = ms_copy(ctx, ms_para(ctx.msp.paras(), sep["문단"]))
        c.set("id", "0")
        if above:
            sec.append(c)
        object_paragraph(ctx, sec, rest + [tbl], kind)
        if not above:
            sec.append(c)
        info["순서"] = [("캡션", 0), "개체"] if above else ["개체", ("캡션", 0)]
    else:
        object_paragraph(ctx, sec, rest + [tbl], kind)
    return text, num, info


def typed_value(s: str):
    """직접 친 번호 글자의 값('3.'→3, '(2)'→2, '다.'→3, '③'→3). 모르면 None."""
    s = (s or "").strip()
    m = re.search(r"\d+", s)
    if m:
        return int(m.group())
    for ch in s:
        if ch in "가나다라마바사아자차카타파하":
            return "가나다라마바사아자차카타파하".index(ch) + 1
        if "①" <= ch <= "⑳":
            return ord(ch) - 0x2460 + 1
    return None


def typed_cap_same(typed: str, chap: int, n: int) -> bool:
    """글자로 친 캡션 번호가 결과 자동 번호와 같은가('<표 1-2>'는 장·번호, '<표 2>'는 번호만, '< 표 >'는 비교할 번호 없음)."""
    m = TYPED_CAP.match(typed or "")
    if not m:
        return False
    if m.group(3):
        return (int(m.group(2)), int(m.group(3))) == (chap, n)
    return not m.group(2) or int(m.group(2)) == n


def check_typed(ctx: Ctx, r, typed: str, auto: str, same: bool):
    if typed and typed.strip() and not same:
        ctx.log.append(f"⚠ {r['문단']} 원고에 친 번호 '{typed.strip()}'와 결과 자동 번호 '{auto}'가 다름 — 원고 번호를 확인")


def drop_typed_number(ctx: Ctx, r, segs):
    """제목·장 제목에 글자로 친 번호(역할매핑 '지울번호')를 뺀다 — 양식 자동 번호와 겹치므로
    (결정 '제목 직접 번호 삭제', 기본 true). 승인된 변경으로 기록. segs: text_segs 결과(글자 조각을 직접 고침)."""
    pre = r.get("지울번호")
    if not pre or not ctx.D.get("제목 직접 번호 삭제", True):
        return segs
    orig = copy.deepcopy(segs)
    if plain(flat(segs)).startswith(pre) and cut_ts(flat(segs), len(pre), 0):
        ctx.approved.append({"문단": r["문단"], "내용": f"직접 친 번호 '{pre.strip()}' 삭제(양식 자동 번호와 겹침)" if pre.strip()
                             else "제목 앞 공백 삭제(자동 번호 뒤 공백과 겹침)"})
        return segs
    ctx.log.append(f"⚠ {r['문단']} 직접 친 번호 '{pre.strip()}'를 지우지 못함(탭 등) — 그대로 둠")
    return orig


def norm_caption_segs(ctx: Ctx, r, segs):
    """캡션 글자의 승인된 다듬기(직접 친 번호·앞뒤 공백, caption_norm)를 글자 조각에 적용."""
    s = plain(flat(segs))
    _, lead, trail, changes = caption_norm(s, ctx.D)
    if not changes:
        return segs
    orig = copy.deepcopy(segs)
    if cut_ts(flat(segs), lead, trail):
        ctx.approved.append({"문단": r["문단"], "내용": f"캡션 '{s.strip()[:40]}' — {', '.join(changes)}"})
        ctx.log.append(f"{r['문단']} 캡션: {', '.join(changes)}")
        return segs
    ctx.log.append(f"⚠ {r['문단']} 캡션 글자 다듬기 실패(탭 등을 넘어감) — 그대로 둠")
    return orig


def drop_caption(tbl):
    """양식 예시 개체의 캡션을 뺀다(있을 때만 — 제목을 따로 문단으로 두는 양식의 개체에는 캡션이 없다)."""
    cap = tbl.find(q("hp:caption"))
    if cap is not None:
        tbl.remove(cap)


def empty_frame(ctx: Ctx, sec, r, segs, chap, src=None):
    """그림이 아직 없는 캡션 줄 → 양식 그림 틀(크기 그대로, 안은 비움) + 그 아래 캡션(이 장의 캡션 번호).
    사용자 결정(2026-10-19): '빈 그림 틀을 만들고 그 아래 캡션'. 틀 위의 '【그림 삽입 예정】' 같은 줄은 본문 그대로.
    제목을 따로 문단으로 두는 양식이면 틀 + 양식 제목 문단(양식 자리). 돌려주는 값 (번호, 결과 문단 순서, 정보)."""
    tmpl = ctx.tmpl_tbl("그림")
    tbl = copy.deepcopy(tmpl)
    drop_caption(tbl)  # 양식 예시 캡션은 버리고 set_shell이 새로 단다
    ctx.frame_id = getattr(ctx, "frame_id", 1300000000) + 1
    tbl.set("id", str(ctx.frame_id))  # 같은 양식 틀을 여러 번 쓰므로 개체 id는 따로
    f = cell_format(ctx, direct_cells(tmpl)[0], ctx.R["표그림"].get("그림 틀 안 스타일"))
    for tc in direct_cells(tbl):
        sl = tc.find(q("hp:subList"))
        for p in sl.findall(q("hp:p")):
            sl.remove(p)
        p = etree.SubElement(sl, q("hp:p"))
        for k, v in (("id", "0"), ("paraPrIDRef", "@" + f["pp"]), ("styleIDRef", "@" + f["st"]), ("pageBreak", "0"),
                     ("columnBreak", "0"), ("merged", "0")):
            p.set(k, v)
        run = etree.SubElement(p, q("hp:run"))
        run.set("charPrIDRef", "@" + f["cp"])
        etree.SubElement(run, q("hp:t"))
    restyle_frame(ctx, tbl, tmpl, [], r["문단"])
    ctx.tg.remap(tbl)
    pp, num = chapter_caption_pp(ctx, "그림", chap)
    mode = ctx.cap_mode("그림")
    set_shell(ctx, tbl, tmpl, [segs] if segs and mode == "붙음" else [], pp)
    strip_layout(tbl)
    caps, info = [], {}
    if segs and mode == "문단":
        caps = caption_paras(ctx, "그림", [segs], pp)
    elif segs and mode is None and src is not None:  # 양식에 제목 모양이 없음 → 원고 캡션 줄을 원고 모양 그대로
        c = ms_copy(ctx, src)
        c.set("id", "0")
        caps, info = [c], {"원고 캡션": True}
    above = ctx.cap_pos("그림") == "위" and mode == "문단"
    for c in (caps if above else caps[:-1]):
        c.set("paraPrIDRef", ctx.dst.keep_with_next(c.get("paraPrIDRef")))
    if above:
        sec.extend(caps)
    op = object_paragraph(ctx, sec, [tbl], "그림")
    if not above:
        if caps:
            op.set("paraPrIDRef", ctx.dst.keep_with_next(op.get("paraPrIDRef")))
        sec.extend(caps)
    sz = tmpl.find(q("hp:sz"))
    ctx.log.append(f"{r['문단']} 옆에 그림 없는 캡션 줄 → 양식 그림 틀(빈 틀 {int(sz.get('width')) / MM:.0f}×"
                   f"{int(sz.get('height')) / MM:.0f} mm) + {'위' if above else '아래'} 캡션(결정 '개체 없는 캡션': 빈 틀)")
    order = ([("캡션", k) for k in range(len(caps))] + ["개체"]) if above else (["개체"] + [("캡션", k) for k in range(len(caps))])
    return num, order, info


def fit_pic(pic, width: int):
    """그림 크기를 폭 width(HWPUNIT)에 맞춰 비율대로 바꾼다(sz·curSz·회전 중심·배율 행렬)."""
    sz, cur, org = pic.find(q("hp:sz")), pic.find(q("hp:curSz")), pic.find(q("hp:orgSz"))
    w, h = int(sz.get("width")), int(sz.get("height"))
    nw, nh = width, round(h * width / w)
    for el in (sz, cur):
        el.set("width", str(nw))
        el.set("height", str(nh))
    ri = pic.find(q("hp:rotationInfo"))
    if ri is not None:
        ri.set("centerX", str(nw // 2))
        ri.set("centerY", str(nh // 2))
    sca = pic.find(f"{q('hp:renderingInfo')}/{q('hc:scaMatrix')}")
    if sca is not None and org is not None:
        sca.set("e1", f"{nw / int(org.get('width')):.6f}")
        sca.set("e5", f"{nh / int(org.get('height')):.6f}")
    return nw, nh


def bare_picture_frame(ctx: Ctx, sec, r, src):
    """틀 없이 놓인 그림(캡션 없음) → 양식 그림 틀(폭·선·안 여백 그대로) 안에 글자처럼 넣는다. 틀 안 폭보다 넓으면
    비율대로 줄이고, 틀 높이는 그림에 맞춘다. 캡션·번호는 달지 않는다(사용자 결정 2026-10-26)."""
    tmpl = ctx.tmpl_tbl("그림")
    if tmpl is None or len(direct_cells(tmpl)) != 1:  # 양식에 한 칸짜리 그림 틀이 없음 → 그림을 원고 모양 그대로
        keep = [ms_copy(ctx, o) for o in objects(src)]
        object_paragraph(ctx, sec, keep, "그림")
        ctx.log.append(f"⚠ {r['문단']} 틀 없는 그림 {len(keep)}개 — 양식에 한 칸짜리 그림 틀이 없어 원고 모양 그대로 둠")
        return False
    tbl = copy.deepcopy(tmpl)
    drop_caption(tbl)
    ctx.frame_id = getattr(ctx, "frame_id", 1300000000) + 1
    tbl.set("id", str(ctx.frame_id))
    f = cell_format(ctx, direct_cells(tmpl)[0], ctx.R["표그림"].get("그림 틀 안 스타일"))
    cells = direct_cells(tbl)
    tc = cells[0]
    sl = tc.find(q("hp:subList"))
    for p in sl.findall(q("hp:p")):
        sl.remove(p)
    p = etree.SubElement(sl, q("hp:p"))
    for k, v in (("id", "0"), ("paraPrIDRef", "@" + f["pp"]), ("styleIDRef", "@" + f["st"]), ("pageBreak", "0"),
                 ("columnBreak", "0"), ("merged", "0")):
        p.set(k, v)
    run = etree.SubElement(p, q("hp:run"))
    run.set("charPrIDRef", "@" + f["cp"])
    restyle_frame(ctx, tbl, tmpl, [], r["문단"])
    ctx.tg.remap(tbl)  # 양식 쪽 ID → 결과 ID(원고 그림을 넣기 전에)
    m = {k: int(v) for k, v in f["margin"].items()}
    csz = tc.find(q("hp:cellSz"))
    inner_w = int(csz.get("width")) - m["left"] - m["right"]
    pics, hmax = [], 0
    for o in objects(src):
        if local(o) not in ("pic", "container"):
            continue
        c = copy.deepcopy(o)
        make_inline(c)
        w0 = int(c.find(q("hp:sz")).get("width"))
        if w0 > inner_w and local(c) == "pic":
            nw, nh = fit_pic(c, inner_w)
            ctx.log.append(f"{r['문단']} 틀 없는 그림 폭 {w0 / MM:.0f} mm > 틀 안 폭 {inner_w / MM:.0f} mm → {nw / MM:.0f}×{nh / MM:.0f} mm로 줄임")
        hmax = max(hmax, int(c.find(q("hp:sz")).get("height")))
        ctx.ms.remap(c)
        pics.append(c)
    run.extend(pics)
    etree.SubElement(run, q("hp:t"))
    h = hmax + m["top"] + m["bottom"]
    csz.set("height", str(h))
    tbl.find(q("hp:sz")).set("height", str(h))
    set_shell(ctx, tbl, tmpl, [], None)
    strip_layout(tbl)
    object_paragraph(ctx, sec, [tbl], "그림")
    ctx.log.append(f"{r['문단']} 틀 없이 놓인 그림 {len(pics)}개 → 양식 그림 틀 안에(캡션·번호 없음, 사용자 결정 2026-10-26)")
    return True


MARKER = re.compile(r"^\s*[【\[][^】\]]{0,40}[】\]]\s*$")  # '【그림 삽입 예정】' 같은 자리표시 한 줄


def keep_marker_with_frame(ctx: Ctx, sec):
    """빈 그림 틀 바로 앞의 자리표시 한 줄은 틀과 같은 쪽에 오게 한다(다음 문단과 함께 — 서식만)."""
    ps = sec.findall(q("hp:p"))
    if not ps or not ctx.out_roles or ctx.out_roles[-1]["역할"] != "본문" or not MARKER.match(own_text(ps[-1])):
        return
    ps[-1].set("paraPrIDRef", ctx.dst.keep_with_next(ps[-1].get("paraPrIDRef")))
    ctx.log.append(f"{ctx.out_roles[-1]['원고']} 자리표시 줄 '{own_text(ps[-1]).strip()}' → 빈 그림 틀과 같은 쪽에(다음 문단과 함께)")


def build_lone_caption(ctx: Ctx, sec, r, src, kind, chap):
    """옆에 표·그림이 없는 캡션 줄(예: '【그림 삽입 예정】' 다음 줄). 결정 '개체 없는 캡션'이 "빈 틀"(기본)이고 그림이면
    양식 빈 그림 틀 + 아래 캡션, 아니면 양식 캡션 문단 모양 + 이 장의 캡션 번호. 직접 친 번호·공백은 캡션과 같은 규칙.
    돌려주는 값: (캡션 글자, 번호 정의, 빈 틀을 만들었는지, 결과 문단 순서, 정보 — build_object와 같은 꼴)."""
    numbered = ctx.cap_numbered(kind)
    segs = norm_caption_segs(ctx, r, text_segs(src)) if numbered else text_segs(src)
    cap = plain(flat(segs)).strip()
    info = {} if numbered else {"번호 둠": True}
    if kind == "그림" and ctx.D.get("개체 없는 캡션", "빈 틀") == "빈 틀" and ctx.tmpl_tbl("그림") is not None:
        keep_marker_with_frame(ctx, sec)
        num, order, more = empty_frame(ctx, sec, r, segs, chap, src)
        return cap, num, True, order, {**info, **more}
    if caption_head(ctx, kind) is None:  # 양식에 제목 모양이 없음 → 원고 줄을 원고 모양 그대로
        c = ms_copy(ctx, src)
        c.set("id", "0")
        sec.append(c)
        ctx.log.append(f"⚠ {r['문단']} 옆에 {kind} 없는 제목 줄 — 양식에 {kind} 제목 모양이 없어 원고 모양 그대로 둠")
        return cap, None, False, ["개체"], {"원고 그대로": True}
    pp, num = chapter_caption_pp(ctx, kind, chap)
    sec.append(caption_para(ctx, kind, segs, pp))
    ctx.log.append(f"{r['문단']} 옆에 {kind} 없는 캡션 줄 → 양식 캡션 모양·번호 문단(결정 '개체 없는 캡션')")
    return cap, num, False, ["개체"], info


def put_roles(ctx: Ctx, info, ent: dict, kind: str):
    """결과 문단 순서대로 역할 기록 — 개체 문단(ent)과 따로 놓인 제목 문단('캡션 문단'). 검증(check_text·check_format)이 쓴다."""
    if info.get("원고 그대로"):
        ent["원고 그대로"] = True
    if info.get("원고 그대로") or info.get("원고 캡션") or info.get("번호 둠"):
        ent["번호 둠"] = True
    caps = [x for x in info["순서"] if x not in ("개체", "빈 줄")]
    if info.get("계속") and not caps:  # 개체에 붙은 캡션 안에 글자로 넣은 번호
        ent["글자번호"] = info["계속"] + " "
    for x in info["순서"]:
        if x == "개체":
            ctx.out_roles.append(ent)
            continue
        if x == "빈 줄":  # 앞 표·그림과 띄우려고 넣은 빈 줄(양식처럼)
            ctx.out_roles.append({"역할": "빈 줄", "원고": ent["원고"]})
            continue
        c = {"역할": "캡션 문단", "원고": ent["원고"], "종류": kind}
        if x[1] == 0 and info.get("계속"):
            c["글자번호"] = info["계속"] + " "
        if info.get("원고 그대로") or info.get("원고 캡션"):
            c["원고 그대로"] = True
        ctx.out_roles.append(c)


OBJECT_ROLES = ("표 문단", "그림 문단", "그림 문단(틀 없음)", "개체 문단(그대로)", "표 캡션(개체 없음)", "그림 캡션(개체 없음)")


def object_role(ctx: Ctx, sec, r, src, role, chap, cap_count):
    """표·그림·개체 문단 하나를 결과에 넣는다(build_body가 부른다 — 실패하면 object_fallback)."""
    if role in ("표 문단", "그림 문단"):
        kind = "표" if role.startswith("표") else "그림"
        cap, num, info = build_object(ctx, sec, r, kind, chap, cap_count)
        sep = next((x for x in ctx.roles if x.get("붙일곳") == r["문단"]), None)
        put_roles(ctx, info, {"역할": role, "원고": r["문단"], "캡션원고": sep["문단"] if sep else None}, kind)
        if not cap:  # 캡션 없는 개체는 번호가 붙지 않는다 → 세지 않고 차례에도 넣지 않음
            ctx.log.append(f"{r['문단']} {kind}: 원고에 캡션 없음 → 캡션·번호 없이")
            return
        if num is None:  # 양식에 예시·번호가 없어 원고 캡션(번호 포함)을 그대로 둔 것
            ctx.toc_entries.append((kind, cap))
            return
        typed = (sep or {}).get("직접기호") or (r.get("캡션") or {}).get("직접번호")
        if info.get("계속"):  # 이어지는 표·그림: 앞과 같은 번호(글자), 세지 않고 차례에도 넣지 않음
            check_typed(ctx, r, typed, info["계속"], isinstance(num, InlineNum) or typed_cap_same(typed, chap, cap_count[kind]))
            ctx.approved.append({"문단": r["문단"], "내용": f"이어지는 {kind}('(계속)')의 번호 '{info['계속']}'를 글자로 넣음"
                                                         f"(앞 {kind}{'와' if kind == '표' else '과'} 같은 번호 — 번호를 늘리지 않음)"})
            ctx.log.append(f"{r['문단']} {kind} 제목에 '(계속)' → 앞 {kind}{'와' if kind == '표' else '과'} 같은 번호 '{info['계속']}'를 글자로(번호를 늘리지 않음, 차례에 넣지 않음)")
            return
        cap_count[kind] += 1
        ctx.cap_total[kind] += 1
        auto = cap_label(num, cap_count[kind], ctx.cap_total[kind])
        check_typed(ctx, r, typed, auto, isinstance(num, InlineNum) or typed_cap_same(typed, chap, cap_count[kind]))
        ctx.toc_entries.append((kind, f"{auto} {cap}"))
        if kind == "표":  # 캡션이 아래라 긴 표는 캡션 쪽 ≠ 시작 쪽 → 첫 본문 행 글자로 시작 쪽을 찾는다
            rows = src.find(f".//{q('hp:tbl')}").findall(q("hp:tr"))
            if len(rows) > 1:
                ctx.toc_anchor[len(ctx.toc_entries) - 1] = " ".join(
                    own_text(p) for tc in rows[1].findall(q("hp:tc")) for p in tc.find(q("hp:subList")).findall(q("hp:p")))
    elif role.endswith("캡션(개체 없음)"):
        kind = "표" if role.startswith("표") else "그림"
        cap, num, framed, order, info = build_lone_caption(ctx, sec, r, src, kind, chap)
        # 빈 틀을 만들었으면 결과에서는 그림 문단(틀 + 캡션) — 검증도 그림 문단처럼
        put_roles(ctx, {**info, "순서": order}, {"역할": "그림 문단", "원고": r["문단"], "빈 틀": True} if framed
                  else {"역할": role, "원고": r["문단"]}, kind)
        if num is None:
            if cap:
                ctx.toc_entries.append((kind, cap))
            return
        cap_count[kind] += 1
        ctx.cap_total[kind] += 1
        auto = cap_label(num, cap_count[kind], ctx.cap_total[kind])
        check_typed(ctx, r, r.get("직접기호"), auto, isinstance(num, InlineNum) or typed_cap_same(r.get("직접기호"), chap, cap_count[kind]))
        ctx.toc_entries.append((kind, f"{auto} {cap}"))
    elif role == "그림 문단(틀 없음)":
        framed = bare_picture_frame(ctx, sec, r, src)
        ctx.out_roles.append({"역할": "그림 문단", "원고": r["문단"], "틀 없음": True, **({} if framed else {"원고 그대로": True})})
    elif role == "개체 문단(그대로)":
        keep = [copy.deepcopy(o) for o in objects(src)]
        for o in keep:
            ctx.ms.remap(o)
            strip_layout(o)
        object_paragraph(ctx, sec, keep, "그림")
        ctx.out_roles.append({"역할": "개체 문단", "원고": r["문단"]})
        ctx.log.append(f"{r['문단']} 표 밖 개체 {[local(o) for o in keep]} → 원고 모양 그대로 가운데 문단에")


def object_fallback(ctx: Ctx, sec, r, src, role, e):
    """표·그림 하나를 양식 모양으로 바꾸다 오류가 나면: 그 개체만 원고 모양 그대로 두고(글자·그림 보존) 알림을 남긴다 —
    낯선 구조의 양식·원고 하나 때문에 변환 전체가 멈추지 않게."""
    why = "양식 모양으로 바꾸다 문제가 생겨"
    ctx.log.append(f"{r['문단']} 오류 자세히: {type(e).__name__}: {e}")
    if role in ("표 문단", "그림 문단"):
        kind = "표" if role.startswith("표") else "그림"
        order = keep_original(ctx, sec, r, src, kind, why)
        put_roles(ctx, {"순서": order, "원고 그대로": True}, {"역할": role, "원고": r["문단"]}, kind)
        cap = raw_caption(ctx, r, next((o for o in objects(src) if local(o) == "tbl"), None))
        if cap:
            ctx.toc_entries.append((kind, cap))
    elif role.endswith("캡션(개체 없음)"):
        c = ms_copy(ctx, src)
        c.set("id", "0")
        sec.append(c)
        ctx.out_roles.append({"역할": role, "원고": r["문단"], "원고 그대로": True, "번호 둠": True})
        ctx.log.append(f"⚠ {r['문단']} 제목 줄 '{own_text(src).strip()[:30]}' — {why} 원고 모양 그대로 둠(한글에서 확인해 주세요)")
    else:
        keep = [ms_copy(ctx, o) for o in objects(src)]
        object_paragraph(ctx, sec, keep, "그림")
        ctx.out_roles.append({"역할": "그림 문단", "원고": r["문단"], "틀 없음": True, "원고 그대로": True}
                             if role == "그림 문단(틀 없음)" else {"역할": "개체 문단", "원고": r["문단"]})
        ctx.log.append(f"⚠ {r['문단']} 그림·개체 {len(keep)}개 — {why} 원고 모양 그대로 둠(한글에서 확인해 주세요)")


def snapshot(ctx: Ctx, sec, counts) -> dict:
    """object_role 앞의 상태 — 실패하면 되돌린다(반쯤 만든 문단·기록이 남지 않게)."""
    return {"p": len(sec.findall(q("hp:p"))), "roles": len(ctx.out_roles), "toc": len(ctx.toc_entries),
            "ap": len(ctx.approved), "st": len(ctx.styled_tbls), "fr": len(ctx.frame_tbls), "names": len(ctx.tbl_names),
            "counts": dict(counts), "total": Counter(ctx.cap_total)}


def restore(ctx: Ctx, sec, s: dict, counts):
    for p in sec.findall(q("hp:p"))[s["p"]:]:
        sec.remove(p)
    del ctx.out_roles[s["roles"]:], ctx.toc_entries[s["toc"]:], ctx.approved[s["ap"]:]
    del ctx.styled_tbls[s["st"]:], ctx.frame_tbls[s["fr"]:], ctx.tbl_names[s["names"]:]
    for k in [k for k in ctx.toc_anchor if k >= s["toc"]]:
        del ctx.toc_anchor[k]
    counts.clear()
    counts.update(s["counts"])
    ctx.cap_total = s["total"]


def build_body(ctx: Ctx):
    """본문 구역(들). 장 번호를 건너뛰면(설정 '장 번호 지정' 또는 글자로 친 장 번호) 그 장부터 새 구역."""
    bp, mp = ctx.base.paras(), ctx.msp.paras()
    ex = {k: bp[int(v[1:])] for k, v in ctx.R["본문"].items()}
    sec = copy.deepcopy(ctx.base.sections[0])
    for p in sec.findall(q("hp:p")):
        sec.remove(p)
    secs = [sec]
    chapters = [r for r in ctx.roles if r["역할"] == "장 제목"]
    assigned = {k: int(v) for k, v in ctx.D.get("장 번호 지정", {}).items()}
    if chapters:
        for r in chapters:  # 장 번호를 글자로 쳤으면(예: docx 원고 '제7장') 그 번호를 따른다
            if r.get("지울번호"):
                assigned.setdefault(r["문단"], chapter_no(r))
        first_chap = assigned.get(chapters[0]["문단"], chapter_no(chapters[0]))
        nums = [chapter_no(r) for r in chapters]
        if nums != list(range(nums[0], nums[0] + len(nums))):
            ctx.log.append(f"⚠ 원고 장 번호가 연속이 아님 {nums}")
        title_pp = setup_chapter_outline(ctx, first_chap)
        hdrs = ms_headers_by_chapter(ctx, chapters)
    else:
        first_chap, title_pp, hdrs = 1, None, {}
        ctx.log.append("원고에 장 제목이 없음 → 장 없이 본문만")
    if ctx.D.get("머리말글자") in ("지정", "양식"):  # 설문으로 머리말을 정함 → 장마다 새 머리말(장 제목 칸 = 그 장 제목)
        hdrs = {i: ctx.D["머리말글자"] for i in range(max(1, len(chapters)))}
    doc_label = ctx.D.get("문서 제목", "")
    started = False
    outline = ctx.dst.get("numbering", ctx.base.sections[0].find(f".//{q('hp:secPr')}").get("outlineShapeIDRef"))
    limit = int(ctx.D.get("연속빈줄", 1))
    k, chap, blanks, hcount, cap_count = -1, first_chap, 0, {}, {"표": 0, "그림": 0}
    ctx.no_chapters = not chapters
    for r in ctx.roles:
        role, src = r["역할"], ms_para(mp, r["문단"])
        step("본문", 문단=r["문단"], 역할=role, 글자=(r.get("앞30자") or (r.get("캡션") or {}).get("글자") or "")[:40])
        if role == "장 제목":
            k += 1
            prev, chap = chap, (first_chap if k == 0 else assigned.get(r["문단"], chap + 1))
            segs = drop_typed_number(ctx, r, text_segs(src))
            deco = [local(o) for o in objects(src) if not "".join(o.itertext()).strip()]
            if deco:
                ctx.log.append(f"{r['문단']} 장 제목 문단의 글자 없는 꾸밈 개체 {deco} → 뺌(양식 장 제목 모양으로)")
            hcount = {1: chap}
            label = head_text(outline, 1, hcount)
            if getattr(ctx, "chapter_text_label", False):  # 양식 장 제목에 자동 번호가 없음 → 원고 장 번호를 글자로
                label = (r.get("번호") if r.get("번호") and "장" in r.get("번호", "") else f"제{chap}장")
                t = etree.Element(q("hp:t"))
                t.text = f"{label} "
                segs = [(segs[0][0] if segs else None, [t])] + segs
                ctx.approved.append({"문단": r["문단"], "내용": f"장 번호 '{label}'를 글자로 넣음(양식 장 제목에 자동 번호가 없음)"})
            label_title = f"{label} {plain(flat(segs)).strip()}" if not getattr(ctx, "chapter_text_label", False)                 else plain(flat(segs)).strip()
            if chap != chapter_no(r):
                ctx.log.append(f"{r['문단']} 장 번호: 원고 자동 번호 제{chapter_no(r)}장 → {label}(설정 '장 번호 지정')")
            if not started:
                sec.append(build_first_para(ctx, segs, title_pp, hdrs.get(0), label_title))
                started = True
            elif k > 0 and chap != prev + 1:
                sec = new_body_section(ctx, segs, title_pp, hdrs.get(k), label_title, chap)
                secs.append(sec)
            else:
                build_chapter_para(ctx, sec, segs, title_pp, hdrs.get(k), label_title)
                ctx.log.append(f"{r['문단']} {label}: 새 쪽" + (" + 머리말·꼬리말" if hdrs.get(k) is not None else "")
                               + (" + 쪽 번호 1부터" if ctx.D.get("장마다 쪽 번호 새로", False) else ""))
            ctx.out_roles.append({"역할": "장 제목", "원고": r["문단"]})
            ctx.toc_entries.append(("장", label_title))
            cap_count, blanks = {"표": 0, "그림": 0}, 0
            continue
        if not started and role == "빈 줄":
            ctx.log.append(f"{r['문단']} 첫 장 제목 앞 빈 줄 → 뺌" if chapters else f"{r['문단']} 본문 첫 빈 줄 → 뺌")
            continue
        n_before = len(sec.findall(q("hp:p")))
        if "따로 떨어진" in role:
            if not r.get("붙일곳"):
                raise SystemExit(f"{r['문단']} 캡션을 붙일 표·그림을 못 찾음")
            continue
        if role == "빈 줄":
            blanks += 1
            if blanks > limit:
                ctx.log.append(f"{r['문단']} 연속 빈 줄 → 뺌")
                continue
            sec.append(set_runs(copy.deepcopy(ex["빈 줄"]), ctx.tcolor(text_run_cid(ex["빈 줄"])), []))
            ctx.out_roles.append({"역할": "빈 줄", "원고": r["문단"]})
            continue
        blanks = 0
        if role in HEADING_ROLES or role == "본문":
            e = heading_example(ctx, ex, role) if role in HEADING_ROLES else ex[role]
            src_segs = inline_segs(src, ctx.ms) if ctx.D.get("인라인 개체 살림", False) else text_segs(src)
            segs = drop_typed_number(ctx, r, src_segs) if role in HEADING_ROLES else src_segs
            if r.get("앞기호"):  # 원고 글머리표(문단 모양의 기호)를 글자로 — 양식 본문 모양에는 글머리표가 없으므로
                t = etree.Element(q("hp:t"))
                t.text = r["앞기호"]
                segs = [(segs[0][0] if segs else None, [t])] + segs
                ctx.approved.append({"문단": r["문단"], "내용": f"글머리표 '{r['앞기호'].strip()}'를 글자로 넣음"})
            np = ctx.set_seg_runs(copy.deepcopy(e), ctx.tcolor(text_run_cid(e)), segs)
            if role in HEADING_ROLES and ctx.D.get("제목 다음 문단과 함께", True):
                np.set("paraPrIDRef", ctx.dst.keep_with_next(np.get("paraPrIDRef")))
            sec.append(np)
            ctx.out_roles.append({"역할": role, "원고": r["문단"]})
            if role in HEADING_ROLES:
                lv = int(ctx.dst.get("paraPr", e.get("paraPrIDRef")).find(q("hh:heading")).get("level")) + 1
                hcount[lv] = hcount.get(lv, 0) + 1
                for kk in [kk for kk in hcount if kk > lv]:
                    del hcount[kk]
                auto = head_text(outline, lv, hcount)
                check_typed(ctx, r, r.get("지울번호"), auto, typed_value(r.get("지울번호")) in (None, hcount[lv]))
                ctx.toc_entries.append((role, f"{auto} {plain(flat(segs)).strip()}"))
        elif role in OBJECT_ROLES:
            snap = snapshot(ctx, sec, cap_count)
            try:
                object_role(ctx, sec, r, src, role, chap, cap_count)
            except Exception as e:  # noqa: BLE001 — 개체 하나 때문에 변환 전체가 멈추지 않게(원고 모양 그대로 + 알림)
                if ctx.D.get("개체 오류 멈춤"):  # 시험용: 오류를 그대로 보고 싶을 때
                    raise
                restore(ctx, sec, snap, cap_count)
                object_fallback(ctx, sec, r, src, role, e)
        elif role == "문서 제목":
            sec.append(doc_title_para(ctx, src, segs_of(src)))
            ctx.out_roles.append({"역할": "문서 제목", "원고": r["문단"]})
        else:
            raise SystemExit(f"{r['문단']} 처리 못 하는 역할: {role}")
        if not started and len(sec.findall(q("hp:p"))) > n_before:
            attach_carrier(ctx, sec.find(q("hp:p")), hdrs.get(0), "")  # 장 앞: 머리말 오른쪽 칸(장 제목)은 비움
            started = True
    step("본문 마무리")
    for s in secs:
        strip_layout(s)
    if any(is_inline(caption_head(ctx, k)) for k in ("표", "그림")):
        fix_numbering_types(ctx, secs)
    step("큰 표")
    secure_tables(ctx, secs)
    return secs


NUMBERED = ("tbl", "pic", "container", "ole", "equation", "rect", "ellipse", "arc", "polygon", "curve", "line",
            "connectLine", "textart", "chart")


def fix_numbering_types(ctx: Ctx, secs):
    """글자 안 자동 번호 캡션(hp:autoNum)은 같은 '번호 종류'의 개체를 모두 센다 — 틀 안 그림, 캡션 없는 표까지.
    → 캡션이 있는 개체만 캡션 번호 종류(표·그림)로 두고 나머지는 '없음'(NONE). 2026-11-03 PDF로 확인(1→3→6 건너뜀)."""
    n_none, n_set = 0, 0
    for sec in secs:
        for el in sec.iter():
            if local(el) not in NUMBERED or el.get("numberingType") is None:
                continue
            cap = el.find(q("hp:caption"))
            head = cap.find(q("hp:subList")).find(q("hp:p")) if cap is not None else None
            a = next((c.find(q("hp:autoNum")) for r in head.findall(q("hp:run")) for c in r if autonum_ctrl(c)), None) \
                if head is not None else None
            # 자동 번호가 없는 캡션('(계속)' 표의 글자 번호 등)도 번호를 차지하지 않게 '없음'
            want = a.get("numType") if a is not None else "NONE"
            if el.get("numberingType") != want:
                el.set("numberingType", want)
                n_none += want == "NONE"
                n_set += want != "NONE"
    if n_none or n_set:
        ctx.log.append(f"캡션 자동 번호가 건너뛰지 않게: 캡션 없는 개체 {n_none}개의 번호 종류 → 없음, "
                       f"캡션 있는 개체 {n_set}개 → 캡션 번호 종류")


# --- 차례

def fit_right_tabs(ctx: Ctx, sec):
    """오른쪽 탭이 본문 폭 밖이면 본문 오른쪽 끝으로(목차 양식 탭 160 mm > 차례 쪽 본문 폭 150 mm)."""
    pg = sec.find(f".//{q('hp:pagePr')}")
    m = {k: int(v) for k, v in pg.find(q("hp:margin")).attrib.items()}
    width = int(pg.get("width")) - m["left"] - m["right"] - m["gutter"]
    cache, fixed = {}, []
    for p in sec.findall(q("hp:p")):
        if p.find(f".//{q('hp:tab')}") is None:
            continue
        pid = p.get("paraPrIDRef")
        if pid not in cache:
            pp = copy.deepcopy(ctx.dst.get("paraPr", pid))
            tp = copy.deepcopy(ctx.dst.get("tabPr", pp.get("tabPrIDRef")))
            changed = False
            for it in tp.iter(q("hh:tabItem")):
                limit = width * 2 if it.getparent().tag == q("hp:default") else width
                if it.get("type") == "RIGHT" and int(it.get("pos")) > limit:
                    fixed.append((int(it.get("pos")), limit))
                    it.set("pos", str(limit))
                    changed = True
            if changed:
                pp.set("tabPrIDRef", ctx.dst.add("tabPr", tp))
                cache[pid] = ctx.dst.add("paraPr", pp)
            else:
                cache[pid] = pid
        p.set("paraPrIDRef", cache[pid])
    if fixed:
        a, b = fixed[0]
        ctx.log.append(f"차례 쪽 번호 오른쪽 탭 {a / MM:.0f}mm → {b / MM:.0f}mm(차례 쪽 본문 폭 끝)")


def bare_copy(p):
    """양식 예시 문단 사본에서 구역 설정·컨트롤(필드 시작·끝, 책갈피 등)을 뺀다 — 글자 모양 틀로만 쓴다."""
    c = copy.deepcopy(p)
    for r in c.findall(q("hp:run")):
        for el in [x for x in r if local(x) in ("secPr", "ctrl")]:
            r.remove(el)
    return c


def simple_section(ctx: Ctx):
    """양식 본문 구역 설정만 가진 빈 구역(첫 문단: 구역 설정·단 설정만, 머리말·꼬리말·쪽 번호 없음)."""
    sec = copy.deepcopy(ctx.base.sections[0])
    for p in sec.findall(q("hp:p")):
        sec.remove(p)
    first = copy.deepcopy(ctx.base.paras()[int(ctx.R["본문"]["첫 문단"][1:])])
    strip_layout(first)
    for r in first.findall(q("hp:run")):
        for x in list(r):
            if local(x) == "secPr" or (local(x) == "ctrl" and x.find(q("hp:colPr")) is not None):
                continue
            r.remove(x)
    first.find(f".//{q('hp:secPr')}").find(q("hp:startNum")).set("page", "0")
    first.set("pageBreak", "0")
    bl = ctx.base.paras()[int(ctx.R["본문"]["빈 줄"][1:])] if ctx.R["본문"].get("빈 줄") else first
    first.set("paraPrIDRef", bl.get("paraPrIDRef"))
    sec.append(first)
    return sec


def simple_para(ctx: Ctx, ex, text: str, size=None, bold=False, center=False, left_pt=0, tab=None, tail=None):
    """양식 예시 문단 모양을 바탕으로 한 간단한 문단(가운데·크기·굵게·왼쪽 여백·오른쪽 탭)."""
    def pfn(n):
        h = n.find(q("hh:heading"))
        if h is not None and h.get("type") != "NONE":
            h.set("type", "NONE")
            h.set("idRef", "0")
            h.set("level", "0")
        if center:
            center_no_indent(n)
        else:
            for case in n.iter(q("hp:case")):
                for k, v in (("left", left_pt * 100), ("intent", 0)):
                    e = case.find(f"{q('hh:margin')}/{q('hc:' + k)}")
                    if e is not None:
                        e.set("value", str(v))
            for d in n.iter(q("hp:default")):
                for k, v in (("left", left_pt * 200), ("intent", 0)):
                    e = d.find(f"{q('hh:margin')}/{q('hc:' + k)}")
                    if e is not None:
                        e.set("value", str(v))
        if tab is not None:
            n.set("tabPrIDRef", tab)
    pid = ctx.dst.variant("paraPr", ctx.tg.para_pr(ex.get("paraPrIDRef")), pfn)

    def cfn(n):
        if size:
            n.set("height", str(int(size * 100)))
        if bold and n.find(q("hh:bold")) is None:
            etree.SubElement(n, q("hh:bold"))
    cid = ctx.dst.variant("charPr", ctx.tcolor(ctx.tg.char_pr(text_run_cid(ex))), cfn)
    p = etree.Element(q("hp:p"))
    for k, v in (("id", "0"), ("paraPrIDRef", pid), ("styleIDRef", ctx.tg.style(ex.get("styleIDRef"))), ("pageBreak", "0"),
                 ("columnBreak", "0"), ("merged", "0")):
        p.set(k, v)
    run = etree.SubElement(p, q("hp:run"))
    run.set("charPrIDRef", cid)
    t = etree.SubElement(run, q("hp:t"))
    t.text = text
    if tail is not None:
        tb = etree.SubElement(t, q("hp:tab"))
        tb.set("width", "4000")
        tb.set("leader", "3")
        tb.set("type", "2")
        tb.tail = tail
    return p


def body_example(ctx: Ctx, *keys):
    for k in keys:
        ref = ctx.R["본문"].get(k) if k in ctx.R["본문"] else ctx.R["표그림"].get(k)
        if ref:
            return (ctx.base if k in ctx.R["본문"] else ctx.tgp).paras()[int(ref[1:])]
    return None


def build_simple_cover(ctx: Ctx):
    """양식에 표지가 없을 때: 양식 글꼴로 만든 간단한 표지(가운데 큰 제목). 결정 '표지'의 '제목' 글자."""
    sec = simple_section(ctx)
    title = ctx.D.get("표지", {}).get("제목") or ctx.D.get("문서 제목", "")
    blank = body_example(ctx, "빈 줄", "본문")
    for _ in range(9):
        sec.append(set_runs(copy.deepcopy(blank), ctx.tcolor(text_run_cid(blank)), []))
    ex = body_example(ctx, "장 제목", "1수준", "본문")
    sec.append(simple_para(ctx, ex, title, size=26, bold=True, center=True))
    strip_layout(sec)
    ctx.log.append(f"양식에 표지가 없어 간단한 표지를 만듦(제목 '{title}', 양식 글꼴·26pt·가운데)")
    return sec


def simple_tab(ctx: Ctx) -> str:
    """본문 폭 오른쪽 끝 탭(채움 선) — 간단한 차례의 쪽 번호 자리."""
    pg, m = ctx.base.page()
    pos = int(pg.get("width")) - m["left"] - m["right"] - m["gutter"]
    el = etree.Element(q("hh:tabPr"))
    el.set("autoTabLeft", "0")
    el.set("autoTabRight", "0")
    sw = etree.SubElement(el, q("hp:switch"))
    case = etree.SubElement(sw, q("hp:case"))
    case.set(f"{{{NS['hp']}}}required-namespace", "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar")
    for parent, v, unit in ((case, pos, True), (etree.SubElement(sw, q("hp:default")), pos * 2, False)):
        ti = etree.SubElement(parent, q("hh:tabItem"))
        ti.set("pos", str(v))
        ti.set("type", "RIGHT")
        ti.set("leader", "DASH")
        if unit:
            ti.set("unit", "HWPUNIT")
    return ctx.dst.add("tabPr", el)


def build_simple_toc(ctx: Ctx):
    """양식에 차례가 없을 때: 양식 글꼴로 만든 간단한 차례(제목 + 단계별 들여쓰기 + 오른쪽 탭 쪽 번호)."""
    sec = simple_section(ctx)
    ex_t = body_example(ctx, "장 제목", "1수준", "본문")
    ex_b = body_example(ctx, "본문")
    blank = body_example(ctx, "빈 줄", "본문")
    sec.append(simple_para(ctx, ex_t, "목  차", size=18, bold=True, center=True))
    sec.append(set_runs(copy.deepcopy(blank), ctx.tcolor(text_run_cid(blank)), []))
    tab = simple_tab(ctx)
    pages = []
    pf = ctx.Rn.f("차례쪽번호.json")
    if pf.exists():
        data = json.loads(pf.read_text(encoding="utf-8"))
        if [d["항목"] for d in data] == [t for _, t in ctx.toc_entries]:
            pages = [d.get("쪽") for d in data]
    rows = [(kind, text, pages[n] if n < len(pages) else None) for n, (kind, text) in enumerate(ctx.toc_entries)]
    rows = [x for x in rows if x[0] not in ("표", "그림")] + [x for x in rows if x[0] == "표"] + \
           [x for x in rows if x[0] == "그림"]
    seen = set()
    for kind, text, page in rows:
        if kind in ("표", "그림") and kind not in seen:
            seen.add(kind)
            sec.append(set_runs(copy.deepcopy(blank), ctx.tcolor(text_run_cid(blank)), []))
            sec.append(simple_para(ctx, ex_t, f"{kind} 차례", size=14, bold=True, center=True))
        lv = {"장": 0, "표": 0, "그림": 0}.get(kind, int(kind[0]) if kind[0].isdigit() else 1)
        sec.append(simple_para(ctx, ex_b, text, bold=(kind == "장"), left_pt=lv * 10, tab=tab, tail=str(page) if page else ""))
    strip_layout(sec)
    ctx.log.append(f"양식에 차례가 없어 간단한 차례를 만듦({len(rows)}항목, 쪽 번호 {'채움' if pages else '비움'})")
    return sec


def build_toc(ctx: Ctx):
    tp, R = ctx.tocp.paras(), ctx.R["목차"]
    sec = copy.deepcopy(ctx.tocp.sections[0])
    for p in sec.findall(q("hp:p")):
        sec.remove(p)
    for key in R.get("머리", ["p0"]):  # 첫 문단(구역 설정)부터 차례 제목까지
        sec.append(copy.deepcopy(tp[int(key[1:])]))

    def ex(key):
        return bare_copy(tp[int(R[key][1:])])
    for key in R["제목 뒤 빈 줄"]:
        sec.append(bare_copy(tp[int(key[1:])]))
    pages = []
    pf = ctx.Rn.f("차례쪽번호.json")
    if pf.exists():
        data = json.loads(pf.read_text(encoding="utf-8"))
        if [d["항목"] for d in data] == [t for _, t in ctx.toc_entries]:
            pages = [d.get("쪽") for d in data]
            ctx.log.append(f"차례 쪽 번호: {pf.name}에서 {sum(1 for x in pages if x)}개 채움")
        else:
            ctx.log.append(f"⚠ {pf.name}의 항목이 지금 차례와 달라 쪽 번호를 비움")
    rows = [(kind, text, pages[n] if n < len(pages) else None) for n, (kind, text) in enumerate(ctx.toc_entries)]
    rows = [x for x in rows if x[0] not in ("표", "그림")] + [x for x in rows if x[0] == "표"] + \
           [x for x in rows if x[0] == "그림"]
    seen, chaps = set(), 0
    for kind, text, page in rows:
        if kind in ("표", "그림") and kind not in seen:
            seen.add(kind)
            sec.append(copy.deepcopy(ex(f"{kind} 차례 제목")))
        if kind == "장":
            chaps += 1
            if chaps > 1 and R.get("장 사이 빈 줄"):
                bl = copy.deepcopy(ex("장 사이 빈 줄"))
                bl.set("id", "0")
                sec.append(bl)
        key = {"장": "장", "표": "표 항목", "그림": "그림 항목"}.get(kind, kind)
        if key not in R:
            ctx.log.append(f"⚠ 차례 양식에 '{key}' 줄이 없어 '{text[:20]}'를 차례에서 뺌")
            continue
        p = copy.deepcopy(ex(key))
        p.set("id", "0")
        t0 = p.find(f".//{q('hp:t')}")
        tab = t0.find(q("hp:tab")) if t0 is not None else None
        runs = p.findall(q("hp:run"))
        for rr in runs[1:]:
            p.remove(rr)
        for t in runs[0].findall(q("hp:t")):
            runs[0].remove(t)
        t = etree.SubElement(runs[0], q("hp:t"))
        t.text = text
        if tab is not None:
            tb = copy.deepcopy(tab)
            tb.tail = str(page) if page else None
            t.append(tb)
        sec.append(p)
    strip_layout(sec)
    ctx.toc.remap(sec)
    fit_right_tabs(ctx, sec)
    return sec


# --- 패키지

def check_refs(ctx: Ctx, sections):
    ids = {k: ctx.dst.ids(k) for k in LISTS}
    bins = {b["id"] for b in ctx.bins.items}
    want = {"paraPrIDRef": "paraPr", "styleIDRef": "style", "charPrIDRef": "charPr", "borderFillIDRef": "borderFill"}
    bad = []
    for n, sec in enumerate(sections):
        for el in sec.iter():
            for a, v in el.attrib.items():
                if isinstance(v, str) and v.startswith("@"):
                    bad.append((n, local(el), a, v))
                if a in want and v not in ids[want[a]] and v != NONE_ID:
                    bad.append((n, local(el), a, v))
                if a == "binaryItemIDRef" and v and v not in bins:
                    bad.append((n, local(el), a, v))
    if bad:
        raise RuntimeError(f"없는 정의를 가리키는 속성 {len(bad)}개: {bad[:8]}")


def tostr(root) -> bytes:
    etree.cleanup_namespaces(root, top_nsmap=root.nsmap, keep_ns_prefixes=list(root.nsmap))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def build_hpf(ctx: Ctx, n_sec: int, title: str) -> bytes:
    hpf = copy.deepcopy(ctx.base.hpf)
    man, spine = hpf.find(q("opf:manifest")), hpf.find(q("opf:spine"))
    for el in list(man) + list(spine):
        el.getparent().remove(el)

    def item(iid, href, media, emb=False):
        e = etree.SubElement(man, q("opf:item"))
        e.set("id", iid)
        e.set("href", href)
        e.set("media-type", media)
        if emb:
            e.set("isEmbeded", "1")
    item("header", "Contents/header.xml", "application/xml")
    for k in range(n_sec):
        item(f"section{k}", f"Contents/section{k}.xml", "application/xml")
    for b in ctx.bins.items:
        item(b["id"], b["href"], b["media"], b.get("emb", True))
    item("settings", "settings.xml", "application/xml")
    for iid in ["header"] + [f"section{k}" for k in range(n_sec)]:
        e = etree.SubElement(spine, q("opf:itemref"))
        e.set("idref", iid)
        e.set("linear", "yes")
    t = hpf.find(f".//{q('opf:metadata')}/{{{NS['opf']}}}title")
    if t is not None:
        t.text = title
    return tostr(hpf)


def build_rdf(ctx: Ctx, n_sec: int) -> bytes:
    rdf = etree.fromstring(ctx.base.z.read("META-INF/container.rdf"))
    res, about = f"{{{NS['rdf']}}}resource", f"{{{NS['rdf']}}}about"
    part = next(d for d in rdf if any(c.get(res) == "Contents/section0.xml" for c in d))
    desc = next(d for d in rdf if d.get(about) == "Contents/section0.xml")
    at = list(rdf).index(desc) + 1
    for k in range(1, n_sec):
        p2, d2 = copy.deepcopy(part), copy.deepcopy(desc)
        for c in p2:
            c.set(res, f"Contents/section{k}.xml")
        d2.set(about, f"Contents/section{k}.xml")
        rdf.insert(at, p2)
        rdf.insert(at + 1, d2)
        at += 2
    return tostr(rdf)


def write_package(ctx: Ctx, sections):
    out = ctx.Rn.out
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx.dst.header.set("secCnt", str(len(sections)))
    vkey = ctx.Rn.cfg.get("버전정보")
    vpkg = {"본문양식": ctx.base, "표그림양식": ctx.tgp, "표지양식": ctx.cvp, "목차양식": ctx.tocp}.get(vkey) or ctx.base
    if vpkg is not ctx.base:  # 사용자 한글보다 높은 버전으로 적히면 '상위 버전' 경고가 뜬다
        ctx.dst.header.set("version", vpkg.header.get("version"))
        ctx.log.append(f"버전 정보: {vkey}의 것(header version {vpkg.header.get('version')})")
    title = ctx.toc_entries[0][1] if ctx.toc_entries else ""
    prv = "\r\n".join(s for sec in sections for p in sec.findall(q("hp:p")) if (s := own_text(p).strip()))[:1000]
    parts = [("version.xml", vpkg.z.read("version.xml"), False),
             ("Contents/header.xml", tostr(ctx.dst.header), False)]
    parts += [(f"Contents/section{k}.xml", tostr(s), False) for k, s in enumerate(sections)]
    parts += [(b["href"], b["data"], False) for b in ctx.bins.items]
    parts.append(("Preview/PrvText.txt", prv.encode("utf-8"), False))
    img = ctx.Rn.f("미리보기.png")
    if img.exists():
        parts.append(("Preview/PrvImage.png", img.read_bytes(), True))
    parts += [("settings.xml", ctx.base.z.read("settings.xml"), False),
              ("META-INF/container.rdf", build_rdf(ctx, len(sections)), False),
              ("Contents/content.hpf", build_hpf(ctx, len(sections), title), False),
              ("META-INF/container.xml", ctx.base.z.read("META-INF/container.xml"), False),
              ("META-INF/manifest.xml", ctx.base.z.read("META-INF/manifest.xml"), False)]
    now = time.localtime()[:6]
    tmp = out.with_name(out.name + ".tmp")
    with zipfile.ZipFile(tmp, "w") as zo:
        zo.writestr(zipfile.ZipInfo("mimetype", date_time=now), ctx.base.z.read("mimetype"),
                    compress_type=zipfile.ZIP_STORED)  # 첫 항목·비압축
        for name, data, store in parts:
            zo.writestr(zipfile.ZipInfo(name, date_time=now), data,
                        compress_type=zipfile.ZIP_STORED if store else zipfile.ZIP_DEFLATED)
    try:
        tmp.replace(out)
    except PermissionError:
        tmp.unlink()
        raise SystemExit(f"결과 파일이 한글 등에 열려 있어 바꿀 수 없다: {out}\n  → 그 파일을 닫고 다시 실행")
    return out


def page_numbering(ctx: Ctx, sections, front):
    """결정 '쪽 번호': "본문부터"(본문 첫 쪽 = 본문쪽번호시작, 기본) / "제목부터"(맨 앞 쪽 = 1, 이어서 셈 — 표지·차례에는
    양식대로 번호를 찍지 않음) / "없음"(쪽 번호 컨트롤과 머리말·꼬리말 안 쪽 번호를 뺀다)."""
    how = ctx.D.get("쪽 번호", "본문부터")
    if how == "제목부터" and front:
        for n, sec in enumerate(sections):
            sn = sec.find(f".//{q('hp:secPr')}").find(q("hp:startNum"))
            sn.set("page", "1" if n == 0 else "0")
        ctx.log.append("쪽 번호: 맨 앞 쪽(표지)부터 1로 세어 본문까지 이어 감(설문)")
    elif how == "없음":
        n = 0
        for sec in sections:
            for el in list(sec.iter(q("hp:pageNum"))) + [a for a in sec.iter(q("hp:autoNum")) if a.get("numType") == "PAGE"]:
                ctrl = el.getparent()
                para = ctrl.getparent().getparent() if ctrl is not None and ctrl.getparent() is not None else None
                ctrl.getparent().remove(ctrl) if local(ctrl) == "ctrl" else ctrl.remove(el)
                n += 1
                if para is not None and local(para) == "p" and not own_text(para).strip("-–— \t()<>[]"):
                    for t in para.iter(q("hp:t")):  # '- 1 -'의 양옆 줄표만 남지 않게
                        t.text = ""
                        for c in list(t):
                            t.remove(c)
        ctx.log.append(f"쪽 번호 없음(설문): 쪽 번호 {n}곳 뺌")


def cmd_apply(R: Run):
    R.out.parent.mkdir(parents=True, exist_ok=True)  # 결과구성·로그 JSON을 결과 파일보다 먼저 쓴다(새 작업 폴더)
    step("준비")
    ctx = Ctx(R)
    bodies = build_body(ctx)
    # 앞표지·차례: 양식에 그 부분이 있고 결정 '표지 만들기'·'차례 만들기'(기본 true)일 때만
    want_cover, want_toc = ctx.D.get("표지 만들기", True), ctx.D.get("차례 만들기", True)
    step("표지")
    cover = (build_cover(ctx) if ctx.cvp is not None else build_simple_cover(ctx) if want_cover == "간단" else None) \
        if want_cover else None
    step("차례")
    toc = (build_toc(ctx) if ctx.tocp is not None else build_simple_toc(ctx) if want_toc == "간단" else None) \
        if want_toc else None
    front = [s for s in (cover, toc) if s is not None]
    sections = front + bodies
    step("쪽 번호")
    page_numbering(ctx, sections, front)
    step("저장")
    # 한글은 개요 번호를 앞 구역에서 이어 센다 — 앞표지·차례가 다른 개요 번호 모양을 가리키면 본문 장 번호가
    # 1부터 매겨짐(2026-10-16 PDF로 확인) → 앞표지·차례도 본문(첫 구역)의 개요 번호 모양을 가리키게 한다.
    oid = bodies[0].find(f".//{q('hp:secPr')}").get("outlineShapeIDRef")
    for s in front:
        s.find(f".//{q('hp:secPr')}").set("outlineShapeIDRef", oid)
    R.f("결과구성.json").write_text(json.dumps({"앞구역": len(front), "표지": cover is not None, "차례": toc is not None,
                                              "본문구역": len(bodies)}, ensure_ascii=False), encoding="utf-8")
    check_refs(ctx, sections)
    out = write_package(ctx, sections)
    added = ", ".join(f"{k} {v}" for k, v in ctx.dst.added.items() if v)
    L = [f"# 적용 로그 — {out.name}", "", f"- 원고: `{R.ms_path.name}`", f"- 만든 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}",
         f"- 구역: {' / '.join([n for n, x in (('앞표지', cover), ('차례', toc)) if x is not None] + ['본문'])}, 그림 파일 {len(ctx.bins.items)}개", f"- 결과 헤더에 덧붙인 정의: {added}",
         f"- 차례 항목 {len(ctx.toc_entries)}개, 승인된 글자 변경 {len(ctx.approved)}건",
         "- 원고 글자색 살림(결정 '원고 글자색'): " + (", ".join(f"{c} {n}곳" for c, n in ctx.colored.items()) or "없음(모두 검정)"),
         "", "## 처리 내역", ""]
    L += [f"- {x}" for x in ctx.log]
    L += ["", "## 승인된 글자 변경", ""] + ([f"- {a['문단']}: {a['내용']}" for a in ctx.approved] or ["- 없음"])
    L += ["", "## 차례 항목", ""] + [f"- [{k}] {t}" for k, t in ctx.toc_entries]
    R.f("적용로그.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    entries = [[k, t, ctx.toc_anchor.get(n)] for n, (k, t) in enumerate(ctx.toc_entries)]
    R.f("차례항목.json").write_text(json.dumps(entries, ensure_ascii=False, indent=0), encoding="utf-8")
    R.f("결과역할.json").write_text(json.dumps(ctx.out_roles, ensure_ascii=False, indent=0), encoding="utf-8")
    R.f("승인변경.json").write_text(json.dumps(ctx.approved, ensure_ascii=False, indent=0), encoding="utf-8")
    R.f("표나눔.json").write_text(json.dumps(ctx.big_tables, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"결과: {out} ({out.stat().st_size:,} bytes) — 처리 {len(ctx.log)}건, 차례 {len(ctx.toc_entries)}항목, "
          f"승인 변경 {len(ctx.approved)}건")


# ======================================================================= PDF (한글 필요)

def hwp_pids() -> set:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Hwp.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, encoding="cp949", errors="replace").stdout
    return {int(r[1]) for r in csv.reader(io.StringIO(out)) if len(r) > 1 and r[1].isdigit()}


def snap_extra_windows(pids, png: Path) -> list:
    try:
        import win32gui
        import win32process
        from PIL import ImageGrab
    except ImportError:
        return []
    found = []

    def enum(h, _):
        _, pid = win32process.GetWindowThreadProcessId(h)
        if pid in pids and win32gui.IsWindowVisible(h) and not win32gui.GetWindowText(h).endswith("- 한글"):
            found.append((win32gui.GetWindowText(h), win32gui.GetWindowRect(h)))
        return True
    win32gui.EnumWindows(enum, None)
    if found:
        ImageGrab.grab(bbox=found[0][1], all_screens=True).save(png)
    return found


OPEN_ARG = "versionwarning:false;forceopen:true;suspendpassword:true;lock:false"
IN_FORMAT = {".hwp": "HWP", ".hwpx": "HWPX", ".docx": "OOXML", ".doc": "MSWORD"}


def hwp_child(src: str, dst: str, fmt_out: str) -> None:
    """(자식 프로세스) 한글로 src를 열어 dst로 저장 — fmt_out 'PDF'(결과 확인) 또는 'HWPX'(.hwp·.docx 변환).
    대화상자가 뜨면(이번에 띄운 한글 창만) 그림으로 남기고 기본 단추(Enter)를 누른다."""
    import threading
    from pyhwpx import Hwp
    t0 = time.time()
    before = hwp_pids()
    hwp = Hwp(new=True, visible=True)  # 숨김이면 PDF 저장 실패
    mine = hwp_pids() - before
    stop, seen = threading.Event(), []

    def watch():
        try:
            import win32con
            import win32gui
            import win32process
            from PIL import ImageGrab
        except ImportError:
            return
        while not stop.is_set():
            def enum(h, _):
                _, pid = win32process.GetWindowThreadProcessId(h)
                title = win32gui.GetWindowText(h)
                if pid in mine and win32gui.IsWindowVisible(h) and title and not title.endswith("- 한글") and h not in seen:
                    seen.append(h)
                    png = Path(dst).with_name(Path(dst).stem + f"_대화상자{len(seen)}.png")
                    try:
                        ImageGrab.grab(bbox=win32gui.GetWindowRect(h), all_screens=True).save(png)
                    except Exception:
                        pass
                    win32gui.PostMessage(h, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                    win32gui.PostMessage(h, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
                    print(f"대화상자 '{title}' → Enter(그림 {png.name})", flush=True)
                return True
            try:
                win32gui.EnumWindows(enum, None)
            except Exception:
                pass
            stop.wait(0.5)
    threading.Thread(target=watch, daemon=True).start()
    try:
        fmt_in = IN_FORMAT.get(Path(src).suffix.lower(), "")
        tries = [(fmt_in, OPEN_ARG), ("", ""), (fmt_in, "")] + ([("MSWORD", ""), ("DOCX", "")] if fmt_in == "OOXML" else [])
        for k, (f_in, arg) in enumerate(dict.fromkeys(tries)):
            if hwp.open(src, f_in, arg):
                if k:
                    print(f"열기: 형식 '{f_in}', 옵션 '{arg}'로 성공", flush=True)
                break
        else:
            raise SystemExit(f"한글에서 열기 실패: {src} (시도 {list(dict.fromkeys(tries))})")
        pages = hwp.PageCount
        ok = hwp.save_as(dst, format=fmt_out)
        size = Path(dst).stat().st_size if Path(dst).exists() else 0
        print(f"열기 성공, {pages}쪽 → {fmt_out} 저장 {'성공' if ok and size else '실패'} ({size:,} bytes, {time.time() - t0:.1f}초)")
        if not (ok and size):
            raise SystemExit(3)
    finally:
        stop.set()
        hwp.clear(1)  # 연 문서는 저장하지 않음(원본 그대로)
        hwp.quit()


def run_hwp_job(src: Path, dst: Path, fmt_out: str, limit=120, tries=3):
    """한글 작업은 자식 프로세스로. 제한 시간을 넘기면 멈춘 창을 그림으로 남기고, 이번에 띄운 한글만 끄고 다시 시도."""
    for attempt in range(1, tries + 1):
        if dst.exists():
            dst.unlink()
        before = hwp_pids()
        try:
            r = subprocess.run([sys.executable, "-I", "-X", "utf8", __file__, "_hwp_child", str(src), str(dst), fmt_out],
                               timeout=limit, capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(r.stdout.strip() or r.stderr.strip()[-500:])
            ok = r.returncode == 0 and dst.exists() and dst.stat().st_size > 0
        except subprocess.TimeoutExpired:
            png = dst.with_name(dst.stem + f"_멈춤창{attempt}.png")
            wins = snap_extra_windows(hwp_pids() - before, png)
            print(f"{attempt}차: {limit:.0f}초 안에 안 끝남. 떠 있던 창: {[w[0] for w in wins]}" + (f" → {png.name}" if wins else ""))
            ok = False
        time.sleep(1.5)
        for pid in hwp_pids() - before:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        if ok:
            return
        time.sleep(3)
    raise SystemExit(f"{fmt_out} 저장 실패({tries}번 시도): {src.name}")


def cmd_pdf(R: Run):
    run_hwp_job(R.out, R.pdf, "PDF")


def cmd_convert(R: Run):
    """원본을 원고 .hwpx로 → 설정의 '원고' 경로. 원본은 그대로.
    .hwp는 한글로 열어 저장(pyhwpx). .docx는 한글 2020 자동화가 열지 못해(2026-10-19 확인) docx_hwpx.py로 직접 옮긴다
    (설정 'docx 변환': "한글"이면 한글로 시도)."""
    if not R.src_path:
        raise SystemExit("설정에 '원본'이 없다(.hwpx 원고는 변환이 필요 없음)")
    R.ms_path.parent.mkdir(parents=True, exist_ok=True)
    h0 = hashlib.sha256(R.src_path.read_bytes()).hexdigest()
    if R.src_path.suffix.lower() == ".docx" and R.cfg.get("docx 변환", "파이썬") != "한글":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import docx_hwpx
        vkey = R.cfg.get("버전정보")
        P = R.parts()
        rep = docx_hwpx.convert(R.src_path, R.ms_path, P["본문양식"], P.get(vkey))
        log = R.ms_path.with_name(R.ms_path.stem + "_변환기록.md")
        log.write_text(docx_hwpx.report_md(R.src_path, R.ms_path, rep), encoding="utf-8")
        print(f"docx 변환: 구역 {rep['구역']}, 블록 {rep['블록']}, 문단 {rep['문단(셀 안 포함)']}, 그림 {rep['그림']}, "
              f"글자 대조 차이 {len(rep['글자 대조 차이'])} → {log.name}")
    else:
        run_hwp_job(R.src_path, R.ms_path, "HWPX", limit=300)
    if hashlib.sha256(R.src_path.read_bytes()).hexdigest() != h0:
        raise SystemExit(f"⚠ 원본이 바뀌었다: {R.src_path}")
    print(f"변환: {R.src_path.name} → {R.ms_path} (원본 해시 그대로)")


CHAP_PREFIX = r"(?:(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]|[IVXL]{1,5}|\d{1,2})\s*[-–.]\s*)?"  # 장 번호가 붙은 쪽 번호('Ⅶ - 4'·'7-4')
FOOT = re.compile(r"^\s*" + CHAP_PREFIX + r"[-–(<\[]?\s*(\d{1,4})\s*[-–)>\]]?\s*$", re.M)  # '- 1 -'·'1'·'(1)'·'Ⅶ - 1' 같은 쪽 번호 줄


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def printed_number(page):
    h = page.rect.height
    for b in page.get_text("blocks"):
        if b[1] > h * 0.88:
            m = FOOT.search(b[4])
            if m:
                return int(m.group(1))
    return None


def toc_pages(pdf: Path, entries) -> list:
    import pymupdf
    doc = pymupdf.open(str(pdf))
    body = [(i, printed_number(p), norm(p.get_text())) for i, p in enumerate(doc)]
    body = [b for b in body if b[1] is not None]

    def first(needle, start):
        for j in range(start, len(body)):
            if needle and needle in body[j][2]:
                return j
        return None
    res, k = [], 0
    for ent in entries:
        text = ent[1]
        anchor = norm(ent[2]) if len(ent) > 2 and ent[2] else None
        key = norm(text)
        found = first(key, k)
        if found is None:
            found = first(norm(text.split(" ", 1)[1]) if " " in text else key, k)
        if found is None:
            res.append({"항목": text, "쪽": None})
            continue
        start = first(anchor, k) if anchor else None
        if start is not None and start < found:
            found = start
        k = found
        res.append({"항목": text, "쪽": body[found][1]})
    return res


def cmd_toc(R: Run):
    entries = json.loads(R.f("차례항목.json").read_text(encoding="utf-8"))
    res = toc_pages(R.pdf, entries)
    R.f("차례쪽번호.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    miss = [r["항목"] for r in res if r["쪽"] is None]
    print(f"차례 {len(res)}항목, 못 찾음 {len(miss)} {miss[:5]}")


def make_preview(R: Run):
    import pymupdf
    doc = pymupdf.open(str(R.pdf))
    z = 724 / doc[0].rect.width
    doc[0].get_pixmap(matrix=pymupdf.Matrix(z, z)).save(str(R.f("미리보기.png")))


# ======================================================================= D. 검증

def frags(el, skip_caption=True):
    out = []
    for p in el.iter(q("hp:p")):
        anc, under = p.getparent(), False
        while anc is not None and anc is not el:
            if local(anc) == "caption":
                under = True
                break
            anc = anc.getparent()
        if skip_caption and under:
            continue
        s = own_text(p).strip()
        if s:
            out.append(s)
    return sorted(out)


def object_unit(p, keep=None):
    """(캡션 글자, 개체 안 글자 조각) — keep: 캡션으로 남긴 캡션 문단 번호(나머지는 본문으로 꺼낸 것).
    표가 없는 문단(원고 모양 그대로 둔 그림 등)은 캡션 없이 개체 안 글자만."""
    tbl = next((o for r in p.findall(q("hp:run")) for o in r if local(o) == "tbl"), None)
    others = [o for r in p.findall(q("hp:run")) for o in r if local(o) in ("rect", "container", "pic")]
    cap = tbl.find(q("hp:caption")) if tbl is not None else None
    cps = [] if cap is None else list(cap.iter(q("hp:p"))) if keep is None else \
        [x for j, x in enumerate(cap.find(q("hp:subList")).findall(q("hp:p"))) if j in keep]
    ctext = " / ".join(s for s in (caption_text(x).strip() for x in cps) if s)
    return ctext, sorted((frags(tbl) if tbl is not None else []) + [f for o in others for f in frags(o)])


def cut_label(text: str, label) -> str:
    """'(계속)' 표 제목 앞에 글자로 넣은 번호(승인 변경)를 비교에서 뺀다."""
    lab = (label or "").strip()
    return text[len(lab):].strip() if lab and text.startswith(lab) else text


def front_count(R: Run) -> int:
    """결과 앞쪽 구역 수(앞표지·차례) — apply가 남긴 결과구성.json, 없으면 2(예전 결과)."""
    f = R.f("결과구성.json")
    return json.loads(f.read_text(encoding="utf-8"))["앞구역"] if f.exists() else 2


def check_text(R: Run, out_pkg: Pkg):
    ms = Pkg(R.ms_path)
    roles = json.loads(R.map_path.read_text(encoding="utf-8"))
    out_roles = json.loads(R.f("결과역할.json").read_text(encoding="utf-8"))
    mp, body = ms.paras(), [p for s in out_pkg.sections[front_count(R):] for p in s.findall(q("hp:p"))]  # 본문 구역(들)
    if len(body) != len(out_roles):
        return 0, [f"결과 문단 수 {len(body)} ≠ 역할 기록 {len(out_roles)}"], 0, 0
    sep = {r["붙일곳"]: r for r in roles if r.get("붙일곳")}
    framed = {o["원고"] for o in out_roles if o.get("빈 틀")}  # 그림 없는 캡션 줄 → 빈 그림 틀 + 캡션으로 만든 것
    raw = {o["원고"] for o in out_roles if o.get("번호 둠")}  # 원고 캡션 번호를 지우지 않은 것(양식에 자동 번호 없음·원고 그대로)
    units_ms, units_out, approved = [], [], 0
    for r in roles:
        role, src = r["역할"], ms_para(mp, r["문단"])
        if role == "빈 줄" or "따로 떨어진" in role:
            continue
        if role in ("표 문단", "그림 문단"):
            cap, fs = object_unit(src, (r.get("캡션") or {}).get("캡션문단"))
            s = sep.get(r["문단"])
            if s and (not cap or s.get("캡션바꿈")):
                cap = caption_text(ms_para(mp, s["문단"])).strip()
                approved += bool(s.get("캡션바꿈"))
            elif not cap and r.get("캡션추가"):  # 사용자가 승인해 새로 단 캡션
                units_ms.append((r["문단"], role, r["캡션추가"], fs))
                approved += 1
                continue
            new, _, _, ch = caption_norm(cap, R.D) if r["문단"] not in raw else (cap, 0, 0, [])
            approved += bool(ch)
            units_ms.append((r["문단"], role, new.strip(), fs))
        elif role == "그림 문단(틀 없음)":  # 양식 그림 틀 안에 넣은 그림(글자 없음)
            units_ms.append((r["문단"], role, "", []))
        else:
            s = own_text(src)
            pre = r.get("지울번호")
            if pre and R.D.get("제목 직접 번호 삭제", True) and s.startswith(pre):
                s = s[len(pre):]
            if role.endswith("캡션(개체 없음)") and r["문단"] not in raw:
                s = caption_norm(s, R.D)[0]
            if r.get("앞기호") and role in HEADING_ROLES + ("본문",):  # 글머리표를 글자로 넣은 것(승인 변경)
                s = r["앞기호"] + s
                approved += 1
            units_ms.append((r["문단"], role, s.strip(), [] if r["문단"] in framed else None))
    ap = json.loads(R.f("승인변경.json").read_text(encoding="utf-8")) if R.f("승인변경.json").exists() else []
    added_label = {}  # 양식 장 제목에 자동 번호가 없어 글자로 넣은 장 번호(승인 변경) → 비교에서 뺀다
    for a in ap:
        m = re.match(r"장 번호 '(.+?)'를 글자로 넣음", a["내용"])
        if m:
            added_label[a["문단"]] = m.group(1) + " "
    capt = {}  # 개체 위·아래에 따로 놓인 제목 문단 → 그 개체의 캡션 글자로 모은다
    for p, o in zip(body, out_roles):
        if o["역할"] == "캡션 문단":
            t = cut_label(caption_text(p).strip(), o.get("글자번호"))
            if t:
                capt[o["원고"]] = f"{capt[o['원고']]} / {t}" if o["원고"] in capt else t
    for p, o in zip(body, out_roles):
        if o["역할"] in ("빈 줄", "캡션 문단"):
            continue
        if o["역할"] in ("표 문단", "그림 문단"):
            cap, fs = object_unit(p)
            cap = cut_label(cap, o.get("글자번호")) or capt.get(o["원고"], "")
            units_out.append((o["원고"], o["역할"], cap, fs))
        elif o["역할"].endswith("캡션(개체 없음)"):  # 글자 안 자동 번호의 번호 부분('<그림 '·'> ')은 빼고 비교
            units_out.append((o["원고"], o["역할"], caption_text(p).strip(), None))
        else:
            t = own_text(p)
            lab = added_label.get(o["원고"]) if o["역할"] == "장 제목" else None
            if lab and t.lstrip().startswith(lab):
                t = t.lstrip()[len(lab):]
                approved += 1
            units_out.append((o["원고"], o["역할"], t.strip(), None))
    diffs, chars = [], 0
    if len(units_ms) != len(units_out):
        diffs.append(f"단위 수가 다름: 원고 {len(units_ms)}, 결과 {len(units_out)}")
    for a, b in zip(units_ms, units_out):
        chars += len(a[2]) + sum(len(x) for x in (a[3] or []))
        if a[0] != b[0] or a[2] != b[2] or a[3] != b[3]:
            diffs.append(f"{a[0]}({a[1]}): 원고 '{a[2][:40]}' / 결과 '{b[2][:40]}'"
                         + ("" if a[3] == b[3] else f" — 개체 안 글자 {len(a[3] or [])}조각 vs {len(b[3] or [])}조각"))
    if R.D.get("머리말글자", "원고") == "원고" and R.D.get("머리말 만들기", True):  # 설문으로 정한 머리말은 비교하지 않음
        def htext(h):
            return plain([t for p in h.find(q("hp:subList")).findall(q("hp:p")) for t in text_ts(p)]).strip()
        mh = [htext(h) for h in ms.sections[0].iter(q("hp:header"))]
        oh = [htext(h) for s in out_pkg.sections[front_count(R):] for h in s.iter(q("hp:header"))]
        if any(mh) and [header_parts(x) for x in mh] != [header_parts(x) for x in oh]:  # 구분(탭·'|')은 양식 칸 나눔으로
            diffs.append(f"머리말: 원고 {mh} / 결과 {oh}")
    return len(units_ms), diffs, chars, approved


def check_format(R: Run, out_pkg: Pkg):
    Rr = R.R
    P = R.parts()
    base, tg = P["본문양식"], P["표그림양식"]
    HB, HT, HO = Desc(base.header), Desc(tg.header), Desc(out_pkg.header)
    bp, tp = base.paras(), tg.paras()
    want = {k: (HB, bp[int(v[1:])]) for k, v in Rr["본문"].items() if k != "첫 문단" and v}
    if Rr["표그림"].get("장 제목"):
        want["장 제목"] = (HT, tp[int(Rr["표그림"]["장 제목"][1:])])

    def tpara(kind):
        ref = Rr["표그림"].get(kind)
        return tp[int(ref[1:])] if ref else None

    def obj_exp(kind):
        name = Rr["표그림"].get("개체 문단 스타일")
        if name:
            st = tg.style_named(name)
            return HT.para_sig(st.get("paraPrIDRef")), HT.char_sig(st.get("charPrIDRef"))
        ex = tpara(kind) if tpara(kind) is not None else tpara("그림" if kind == "표" else "표")
        ps = HT.para_sig(ex.get("paraPrIDRef"))  # object_paragraph: 가운데 정렬, 왼쪽·오른쪽·첫 줄 0
        return ("가운데", "0pt", "0pt", "0pt") + ps[4:], HT.char_sig(text_run_cid(ex))

    def cap_exp(kind, cont=False):
        """양식 제목(캡션) 문단 모양 — 붙은 캡션의 첫 문단이나 따로 놓인 제목 문단. cont: '(계속)' 제목(번호 없는 모양)."""
        cp = tmpl_caption(Rr["표그림"], tg, kind)[1]
        if cont:
            c = tpara(f"{kind} 계속")
            if c is not None:
                return HT.para_sig(c.get("paraPrIDRef")), HT.char_sig(text_run_cid(c))
            if cp is not None:
                return HT.para_sig(cp.get("paraPrIDRef"))[:-1] + ("없음",), HT.char_sig(text_run_cid(cp))
        if cp is None:
            return None, None
        return HT.para_sig(cp.get("paraPrIDRef")), HT.char_sig(text_run_cid(cp))

    def exp(o):
        role = o["역할"]
        if o.get("원고 그대로"):  # 양식 모양을 입히지 못해 원고 모양 그대로 둔 것(적용로그 ⚠) — 비교하지 않음
            return None, None
        if role in ("표 문단", "그림 문단"):
            return obj_exp(role[0] if role.startswith("표") else "그림")
        if role == "캡션 문단":  # 개체 위·아래에 따로 놓인 제목
            return cap_exp(o["종류"], bool(o.get("글자번호")))
        if role.endswith("캡션(개체 없음)"):  # 양식 표·그림 캡션 문단과 같게(번호 정의만 장마다 다름)
            return cap_exp("표" if role.startswith("표") else "그림")
        if role not in want:  # 양식에 없는 제목 단계 — 가까운 단계 모양을 바꿔 씀(적용로그 ⚠), 비교하지 않음
            return None, None
        H, p = want[role]
        ps = H.para_sig(p.get("paraPrIDRef"))
        if role == "장 제목":  # 번호 방식만 개요 1수준으로 바꿈(모양은 같음)
            ps = ps[:-1] + ("OUTLINE level=0",)
        return ps, H.char_sig(text_run_cid(p))
    out_roles = json.loads(R.f("결과역할.json").read_text(encoding="utf-8"))
    body = [p for s in out_pkg.sections[front_count(R):] for p in s.findall(q("hp:p"))]
    stat, bad, colors = Counter(), [], Counter()
    for p, o in zip(body, out_roles):
        ep, ec = exp(o)
        if ep is None:
            stat[(o["역할"] + (" (원고 모양 그대로 — 알림 참고)" if o.get("원고 그대로") else " (양식에 없는 단계 — 대체)"), True)] += 1
            continue
        ap = HO.para_sig(p.get("paraPrIDRef"))
        cids = {r.get("charPrIDRef") for r in p.findall(q("hp:run"))}
        ok = ap == ep and all(HO.char_sig(c) == ec for c in cids)
        for c in cids:
            colors[HO.char_prs[c].get("textColor")] += 1
        stat[(o["역할"], ok)] += 1
        if not ok:
            bad.append(f"{o['원고']}({o['역할']}): 문단 {ap if ap != ep else '같음'} / 글자 "
                       f"{[HO.char_sig(c) for c in cids if HO.char_sig(c) != ec][:1] or '같음'}")
    t_tbl = tpara("표").find(f".//{q('hp:tbl')}") if tpara("표") is not None else None
    t_fr = tpara("그림").find(f".//{q('hp:tbl')}") if tpara("그림") is not None else None
    tcells = {cell_addr(tc)[:2]: tc for tc in direct_cells(t_tbl)} if t_tbl is not None else {}

    def cell_exp(tc, style_name=None):
        if style_name:
            s = tg.style_named(style_name)
            return HT.para_sig(s.get("paraPrIDRef")), HT.char_sig(s.get("charPrIDRef"))
        p = tc.find(q("hp:subList")).find(q("hp:p"))
        return HT.para_sig(p.get("paraPrIDRef")), HT.char_sig(text_run_cid(p))
    e_head = cell_exp(tcells[(0, 0)]) if tcells else None
    e_body = cell_exp(tcells.get((1, 1), tcells.get((1, 0), tcells[(0, 0)]))) if tcells else None
    fname = Rr["표그림"].get("그림 틀 안 스타일")
    e_frame = cell_exp(None, fname) if fname else (cell_exp(direct_cells(t_fr)[0]) if t_fr is not None else None)
    e_cap = {}
    for k, t in (("표", t_tbl), ("그림", t_fr)):
        if t is not None and t.find(q("hp:caption")) is not None:
            cp = t.find(q("hp:caption")).find(q("hp:subList")).find(q("hp:p"))
            e_cap[k] = (HT.para_sig(cp.get("paraPrIDRef")), HT.char_sig(text_run_cid(cp)))
    cstat, cbad, fills = Counter(), [], Counter()
    for p, o in zip(body, out_roles):
        if o["역할"] not in ("표 문단", "그림 문단") or o.get("원고 그대로"):
            continue
        kind = "표" if o["역할"].startswith("표") else "그림"
        tbl = p.find(f".//{q('hp:tbl')}")
        if tbl is None:
            continue
        cap = tbl.find(q("hp:caption"))
        if cap is not None and kind in e_cap:
            cp = cap.find(q("hp:subList")).find(q("hp:p"))
            want_c = e_cap[kind] if not o.get("글자번호") else (e_cap[kind][0][:-1] + ("없음",), e_cap[kind][1])  # '(계속)': 번호 없음
            okc = (HO.para_sig(cp.get("paraPrIDRef")), HO.char_sig(text_run_cid(cp))) == want_c
            cstat[("캡션", okc)] += 1
            if not okc:
                cbad.append(f"{o['원고']} 캡션")
        H = max(cell_addr(tc)[2] for tc in tbl.find(q("hp:tr")).findall(q("hp:tc")))
        for tc in direct_cells(tbl):
            r = cell_addr(tc)[0]
            e = e_frame if kind == "그림" else (e_head if r < H else e_body)
            name = "그림 틀 셀" if kind == "그림" else ("표 머리행 셀" if r < H else "표 본문 셀")
            if e is None:  # 양식에 그 개체가 없어 원고 모양을 그대로 둔 것
                continue
            wb = HO.border_fills[tc.get("borderFillIDRef")].find(f".//{q('hc:winBrush')}")
            fills[(name, wb.get("faceColor") if wb is not None else "없음")] += 1
            for cpp in tc.find(q("hp:subList")).findall(q("hp:p")):
                ok = (HO.para_sig(cpp.get("paraPrIDRef")), HO.char_sig(text_run_cid(cpp))) == e
                cstat[(name, ok)] += 1
                if not ok:
                    cbad.append(f"{o['원고']} {name} r{r}")
    return stat, bad, cstat, cbad, fills, colors


def check_package(path: Path):
    z = zipfile.ZipFile(path)
    infos = z.infolist()
    rows = [("첫 항목이 mimetype", infos[0].filename == "mimetype"),
            ("mimetype 비압축", infos[0].compress_type == zipfile.ZIP_STORED),
            ("mimetype 내용", z.read("mimetype") == b"application/hwp+zip"), ("CRC(testzip)", z.testzip() is None)]
    bad = []
    for i in infos:
        if i.filename.endswith((".xml", ".hpf", ".rdf")):
            try:
                etree.fromstring(z.read(i.filename))
            except etree.XMLSyntaxError as e:
                bad.append(f"{i.filename}: {e}")
    rows.append(("XML 파싱", not bad))
    hpf = etree.fromstring(z.read("Contents/content.hpf"))
    items = {it.get("id"): it.get("href") for it in hpf.iter(q("opf:item"))}
    missing = [h for h in items.values() if h not in z.namelist()]
    rows.append(("매니페스트 파일이 모두 있음", not missing))
    secs = [n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)]
    head = etree.fromstring(z.read("Contents/header.xml"))
    rows.append((f"구역 수(secCnt={head.get('secCnt')}, 파일 {len(secs)})", head.get("secCnt") == str(len(secs))))
    refs = {img.get("binaryItemIDRef") for s in secs for img in etree.fromstring(z.read(s)).iter(q("hc:img"))}
    rows.append((f"그림 참조 {len(refs)}개가 매니페스트에 있음", refs <= set(items)))
    return rows, bad + missing


def body_limit(R: Run, out_pkg: Pkg) -> int:
    pg, m = out_pkg.page(front_count(R))
    return int(pg.get("height")) - m["top"] - m["bottom"] - m["header"] - m["footer"]


def check_tables(R: Run, out_pkg: Pkg) -> list:
    """한 쪽을 넘는 본문 표(쪽에서 차지할 높이 어림 > 본문 높이의 99 %)가 쪽 경계에서 나뉘게 되어 있는가
    — 한글 없이 하는 검사. [(표 이름, 어림 높이, 통과, 설명)]"""
    M = tf.Metrics(out_pkg.header)
    limit = body_limit(R, out_pkg)
    out = []
    for s in out_pkg.sections[front_count(R):]:
        for tbl in tf.top_tables(s):
            if not tf.has_text(tbl):
                continue
            total, rows = M.page_height(tbl)
            if total <= tf.FIT * limit:
                continue
            if not tf.splittable(tbl):
                why, ok = "쪽 경계에서 나뉘지 않음(글자처럼 취급이거나 '나누지 않음') → 쪽 아래로 넘친다", False
            elif tbl.get("pageBreak") == "TABLE" and tf.row_too_tall(rows, tf.head_rows(tbl), tf.repeats_header(tbl), limit):
                why, ok = "'셀 단위로 나눔'인데 쪽 높이에 가까운 행이 있어 그 행이 넘친다", False
            else:
                why, ok = f"쪽 경계에서 '{tf.PAGE_BREAK_NAME[tbl.get('pageBreak')]}'" + \
                          (", 제목 줄 반복" if tf.repeats_header(tbl) else ""), True
            out.append((table_label(tbl), total, ok, why))
    return out


OVER_IGNORE = re.compile(CHAP_PREFIX + r"[-–—(<\[]?\s*\d{1,4}(\s*/\s*\d{1,4})?\s*[-–—)>\]]?")


def pdf_overflow(R: Run, out_pkg: Pkg, doc) -> list:
    """한글 PDF에서 본문 영역 아래(꼬리말 자리)로 내려온 글자 — 쪽을 넘친 표 등. [(쪽, 글자 예)]
    본문 쪽(찍힌 쪽 번호가 있는 쪽, 없으면 첫 본문 글이 나온 쪽부터)만 보고, 머리말·꼬리말 글자와 쪽 번호는 뺀다."""
    pg, m = out_pkg.page(front_count(R))
    hf = norm("".join("".join(t.itertext()) for s in out_pkg.sections for el in s.iter(q("hp:header"), q("hp:footer"))
                      for t in el.iter(q("hp:t"))))
    pages = [i for i, p in enumerate(doc) if printed_number(p) is not None]
    if not pages:
        first = next((norm(own_text(p))[:10] for s in out_pkg.sections[front_count(R):] for p in s.findall(q("hp:p"))
                      if norm(own_text(p))), "")
        start = next((i for i, p in enumerate(doc) if first and first in norm(p.get_text())), 0)
        pages = list(range(start, len(doc)))
    out = []
    for i in pages:
        p = doc[i]
        lim = p.rect.height * (int(pg.get("height")) - m["bottom"] - m["footer"]) / int(pg.get("height")) + 2  # 2pt 여유
        hits = []
        for b in p.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln["spans"]:
                    t = norm(sp["text"])
                    if t and sp["bbox"][3] > lim and not OVER_IGNORE.fullmatch(t) and t not in hf:
                        hits.append(t)
        if hits:
            out.append((i + 1, " ".join(hits[:4])[:40]))
    return out


def check_pdf(R: Run, n_chapters: int, out_pkg: Pkg = None):
    import pymupdf
    doc = pymupdf.open(str(R.pdf))
    nums = [n for n in (printed_number(p) for p in doc) if n is not None]
    segs = []
    for n in nums:
        if segs and n == segs[-1][-1] + 1:
            segs[-1].append(n)
        else:
            segs.append([n])
    want = n_chapters if R.D.get("장마다 쪽 번호 새로", False) else 1
    rows = [(f"PDF {len(doc)}쪽 (앞표지·차례 {len(doc) - len(nums)}쪽 + 본문 {len(nums)}쪽)", True),
            (f"본문 쪽 번호 " + ", ".join(f"{s[0]}~{s[-1]}" for s in segs) + f" (장 {n_chapters}개)",
             len(segs) == want and all(s[0] == (R.D.get("본문쪽번호시작", 1) if k == 0 else 1) for k, s in enumerate(segs)))]
    entries = json.loads(R.f("차례항목.json").read_text(encoding="utf-8"))
    diff = []
    made = json.loads(R.f("결과구성.json").read_text(encoding="utf-8")) if R.f("결과구성.json").exists() else {"차례": True}
    if made.get("차례", True):
        toc = json.loads(R.f("차례쪽번호.json").read_text(encoding="utf-8"))
        real = toc_pages(R.pdf, entries)
        diff = [(a["항목"], a["쪽"], b["쪽"]) for a, b in zip(toc, real) if a["쪽"] != b["쪽"]]
        rows.append((f"차례 쪽 번호 {len(toc)}개가 PDF 위치와 같음", not diff and len(toc) == len(real)))
    else:
        rows.append(("차례 없음(만들지 않음) — 차례 쪽 번호 검사 건너뜀", True))
    # 본문에 찍힌 장 제목(자동 번호 포함) — 머리말 영역 아래 글 묶음에서 찾는다
    want_titles = [norm(e[1]) for e in entries if e[0] == "장"]
    shown = []
    for p in doc:
        if printed_number(p) is None:
            continue
        bs = [norm(b[4]) for b in p.get_text("blocks") if b[1] > p.rect.height * 0.075]
        shown += ["".join(bs[j:j + 3]) for j in range(len(bs))]  # 긴 제목은 두 줄로 나뉘어 글 묶음이 갈린다
    miss = [t for t in want_titles if not any(s.startswith(t) for s in shown)]
    rows.append((f"본문에 찍힌 장 제목 {len(want_titles) - len(miss)}/{len(want_titles)}개가 차례와 같음(자동 번호 포함)", not miss))
    diff += [(t, "본문에 없음", "") for t in miss]
    if out_pkg is not None:
        over = pdf_overflow(R, out_pkg, doc)
        rows.append(("본문 영역 아래(꼬리말 자리)로 넘친 글자 없음" if not over else
                     f"본문 영역 아래로 넘친 글자 — {len(over)}쪽: " + ", ".join(f"{n}쪽 '{t}'" for n, t in over[:5]), not over))
    return rows, diff


REF = re.compile(r"(?<![가-힣])(표|그림)\s*(\d+)\s*-\s*(\d+)")


def body_refs(R: Run, out_pkg: Pkg):
    """본문 글자에서 언급한 '표 2-4'·'<그림 4-1>' 번호들과, 이 파일 캡션 번호들(차례항목.json)."""
    text = "\n".join(own_text(p) for s in out_pkg.sections[front_count(R):] for p in s.findall(q("hp:p")))
    refs = list(dict.fromkeys(f"{k} {a}-{b}" for k, a, b in REF.findall(text)))
    entries = json.loads(R.f("차례항목.json").read_text(encoding="utf-8"))
    have = {f"{m.group(1)} {m.group(2)}-{m.group(3)}" for e in entries if e[0] in ("표", "그림")
            for m in [REF.search(e[1])] if m}
    return refs, have


def check_line_break(R: Run, out_pkg: Pkg):
    """결정 '줄 나눔'대로 결과의 문단 모양이 모두 바뀌었는지 → (문단 모양 수, 다른 id 목록). "양식"이면 None."""
    want = line_break(R.D)
    if not want:
        return None
    pps = list(out_pkg.header.iter(q("hh:paraPr")))
    bad = []
    for pp in pps:
        bs = pp.find(q("hh:breakSetting"))
        if bs is None or (bs.get("breakLatinWord"), bs.get("breakNonLatinWord")) != want:
            bad.append(pp.get("id"))
    return len(pps), bad


def cmd_verify(R: Run):
    out_pkg = Pkg(R.out)
    roles = json.loads(R.map_path.read_text(encoding="utf-8"))
    n_ch = sum(1 for r in roles if r["역할"] == "장 제목")
    L = [f"# 검증 보고 — {R.out.name}", "", f"- 원고: `{R.ms_path.name}`",
         f"- 다시 만들기: `python -I -X utf8 scripts/format_transfer.py verify {R.cfg_path.name}`", ""]
    pk, pk_bad = check_package(R.out)
    L += ["## 1. 패키지 무결성", ""] + [f"- {'✅' if ok else '❌'} {n}" for n, ok in pk] + [f"  - {x}" for x in pk_bad]
    n_units, diffs, chars, approved = check_text(R, out_pkg)
    ap = json.loads(R.f("승인변경.json").read_text(encoding="utf-8")) if R.f("승인변경.json").exists() else []
    L += ["", "## 2. 글자 보존", "",
          f"- 비교 단위 {n_units}개(장 제목·번호 문단·본문 문단, 표·그림은 캡션 + 칸 안 글자 조각, 머리말), 글자 {chars:,}자",
          f"- {'✅ 차이 0' if not diffs else f'❌ 차이 {len(diffs)}건'} (빈 줄·자동 번호는 글자가 아니라 제외)",
          f"- 승인된 변경 {len(ap)}건(설정 '결정'·역할판단에 따른 것만)"]
    L += [f"  - {a['문단']}: {a['내용']}" for a in ap] + [f"  - ❌ {d}" for d in diffs[:30]]
    stat, bad, cstat, cbad, fills, colors = check_format(R, out_pkg)
    L += ["", "## 3. 서식 일치 (양식 기준 문단과 글자·문단 모양 비교, 글자색 제외)", "", "| 역할 | 일치 | 다름 |", "|---|---|---|"]
    L += [f"| {role} | {stat[(role, True)]} | {stat[(role, False)]} |" for role in dict.fromkeys(k[0] for k in stat)]
    L += [f"| {n} (문단) | {cstat[(n, True)]} | {cstat[(n, False)]} |" for n in dict.fromkeys(k[0] for k in cstat)]
    L += [f"- 다름: {x}" for x in (bad + cbad)[:30]] or ["- 다른 곳 없음"]
    L += ["- 셀 배경: " + ", ".join(f"{n} {c} {v}개" for (n, c), v in fills.items()),
          "- 본문 글자색: " + ", ".join(f"{c} {v}" for c, v in colors.items())]
    lb = check_line_break(R, out_pkg)
    if lb:
        n, bad_ids = lb
        L.append(f"- {'❌' if bad_ids else '✅'} 줄 나눔 기준 한글 단위 '글자'·영어 단위 '글자'(결정 '줄 나눔'): 문단 모양 {n}개 중 "
                 + (f"다른 것 {len(bad_ids)}개(id {', '.join(bad_ids[:10])})" if bad_ids else "모두"))
    big = check_tables(R, out_pkg)
    L += ["", f"## 3-1. 한 쪽을 넘는 표 (셀 글자로 어림한 '쪽에서 차지할 높이'가 본문 높이 {body_limit(R, out_pkg) / MM:.0f}mm의 "
              f"{tf.FIT:.0%}를 넘는 표 — 글자처럼 취급이면 쪽 아래로 넘친다)", ""]
    L += [f"- {'✅' if ok else '❌'} '{name}' 높이 어림 {total / MM:.0f}mm — {why}" for name, total, ok, why in big] \
        or ["- ✅ 없음(모든 표가 한 쪽 안에 들어가는 높이 — 양식대로 둠)"]
    refs, have = body_refs(R, out_pkg)
    miss = [x for x in refs if x not in have]
    L += ["", "## 참고: 본문에서 언급한 표·그림 번호", "",
          f"- 언급 {len(refs)}개(서로 다른 번호), 이 파일 캡션 번호 {len(have)}개"
          + (f" — ⚠ 이 파일에 없는 번호 {len(miss)}개(다른 장이면 정상, 이 장이면 원고 확인): {', '.join(miss)}" if miss else " — 모두 있음")]
    if R.pdf.exists():
        pr, pdiff = check_pdf(R, n_ch, out_pkg)
        L += ["", "## 4. PDF(한글에서 열어 PDF로 저장한 결과)", ""] + [f"- {'✅' if ok else '❌'} {n}" for n, ok in pr]
        L += [f"  - {a}: 차례 {b} / 실제 {c}" for a, b, c in pdiff]
    else:
        L += ["", "## 4. PDF", "", "- ⏭ PDF 없음(한글 없이 만듦) — 쪽 모양 검사를 못 했고 차례의 쪽 번호가 비어 있다. "
              "한글에서 열어 확인하거나, 한글이 있는 PC에서 `run`으로 다시 만든다."]
    memo = R.f("눈확인메모.md")
    if memo.exists():
        L += ["", memo.read_text(encoding="utf-8").strip()]
    R.f("검증보고.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    fails = sum(x.count("❌") for x in L)
    print(f"검증보고: {R.f('검증보고.md')} — ❌ {fails}개")
    return fails


# ======================================================================= 실행

def cmd_run(R: Run):
    if R.src_path and not R.ms_path.exists():
        cmd_convert(R)
    if not R.map_path.exists():
        need = cmd_analyze(R)
        if need:
            raise SystemExit(f"[판단 필요] {len(need)}건 — {R.map_path.stem}_분석.md를 보고 역할판단 파일을 채운 뒤 다시 run")
    for f in ("차례쪽번호.json",):
        if R.f(f).exists():
            R.f(f).unlink()
    cmd_apply(R)
    cmd_pdf(R)
    make_preview(R)
    cmd_toc(R)
    cmd_apply(R)
    cmd_pdf(R)
    return cmd_verify(R)


def cmd_quick(R: Run):
    """한글 없이(클로드 채팅 등): 변환(.docx만) → analyze(역할매핑이 없을 때) → apply → verify.
    PDF 저장·차례 쪽 번호 채우기는 빠진다(한글이 있는 PC에서는 run)."""
    if R.src_path and not R.ms_path.exists():
        if R.src_path.suffix.lower() != ".docx":
            raise SystemExit(f"{R.src_path.suffix} 원본은 한글이 있어야 .hwpx로 바뀐다 — "
                             "한글에서 [파일] → [다른 이름으로 저장] → 형식 'HWPX'로 저장한 파일을 받는다")
        cmd_convert(R)
    if not R.map_path.exists():
        need = cmd_analyze(R)
        if need:
            raise SystemExit(f"[판단 필요] {len(need)}건 — {R.map_path.stem}_분석.md를 보고 역할판단 파일을 채운 뒤 다시 quick")
    cmd_apply(R)
    return cmd_verify(R)


def cmd_tables(R: Run):
    """한 쪽을 넘는 표 미리 보기(analyze 뒤, 결과 파일은 쓰지 않음) — 있으면 사용자에게 나누는 방식을 묻고
    설정 '결정'의 "표 나누기"("나눔" = 쪽 경계에서 나눔 / "셀 단위로 나눔")에 적는다."""
    plan = table_plan(R)
    tables = [x for x in plan if x["종류"] == "표"]
    for x in plan:
        print(f"- [{x['종류']}] '{x['표']}' 쪽에서 차지할 높이 어림 {x['높이mm']}mm > 본문 높이 {x['본문높이mm']}mm"
              + (" — 그림 묶음은 늘 '셀 단위로 나눔'" if x["종류"] == "그림" else ""))
    if tables:
        now = R.D.get("표 나누기")
        print(f"한 쪽을 넘는 표 {len(tables)}개 → " + (f"설정 '표 나누기' = {now}" if now else
              "사용자에게 묻는다: 쪽 경계에서 나눔 / 셀 단위로 나눔 → 설정 '결정'의 \"표 나누기\"에 \"나눔\" 또는 \"셀 단위로 나눔\""))
    else:
        print("한 쪽을 넘는 표 없음 — 표는 양식대로(한 쪽 안에 들어감), 나누기를 묻지 않아도 된다")
    return plan


def main(argv):
    if argv[0] == "_hwp_child":
        return hwp_child(argv[1], argv[2], argv[3])
    cmd, R = argv[0], Run(argv[1])
    {"convert": cmd_convert, "analyze": cmd_analyze, "apply": cmd_apply, "pdf": cmd_pdf, "toc": cmd_toc,
     "verify": cmd_verify, "run": cmd_run, "quick": cmd_quick, "tables": cmd_tables}[cmd](R)


if __name__ == "__main__":
    main(sys.argv[1:])
