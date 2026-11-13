"""양식 자동 분석 — 보고서 .hwpx 하나를 읽어 표지·차례·본문 부분과 역할별 기준 문단(양식 프로필)을 찾는다.

사용(명령줄): python template_profile.py <양식.hwpx> [프로필.json]
  → 프로필(format_transfer.py의 '자동 분석 프로필')과 요약을 쓴다. 프로필의 문단 번호는 '부분' 안에서 센 번호.

찾는 방법
  - 쪽: 구역이 바뀌거나 '쪽 나누기'가 걸린 문단에서 나눈다.
  - 차례: '목차·차례' 제목 줄이나, 탭 뒤에 쪽 번호가 붙은 줄이 반을 넘는 쪽.
  - 표지: 차례 앞(차례가 없으면 첫 쪽)에서 번호 제목·긴 문단 없이 큰 글자가 있는 쪽.
  - 본문: 차례(없으면 표지) 다음부터 끝까지. 역할은 엔진의 원고 분석(classify)과 같은 규칙으로 정한다.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_transfer as ft  # noqa: E402
from format_transfer import q, own_text, text_run_cid, Pkg, Desc  # noqa: E402

TOC_TITLE = re.compile(r"^[<〈《\[【(]?(목차|차례|목록|contents|tableofcontents)[>〉》\]】)]?$", re.I)
TOC_SUB = re.compile(r"^[<〈《\[【(]?(표|그림|사진|도표)(목차|차례|목록)[>〉》\]】)]?$")
TOC_ENTRY = re.compile(r"(\t|\.{3,}|…{2,}|·{3,}|ㆍ{3,})\s*[-–]?\s*\d+\s*[-–]?\s*$")
GENERIC_COVER = re.compile(r"^(연구|최종|중간|착수|결과|완료|사업|과업|용역|기술|실적|성과|조사|분석)*"
                           r"(보고서|계획서|제안서|지시서|요약서|결과서)$")
DATE = re.compile(r"^\d{4}\s*[.년]\s*(\d{1,2}\s*[.월]?)?\s*(\d{1,2}\s*[.일]?)?$")
PAREN = re.compile(r"^[(<〈\[【-].*[)>〉\]】-]?$")
CAP_TBL = re.compile(r"^\s*[<〈\[(【]?\s*표\s*\d")
CAP_FIG = re.compile(r"^\s*[<〈\[(【]?\s*(그림|사진)\s*\d")
CHAPTER = re.compile(r"^\s*제\s*\d+\s*장")
CONT_CAP = re.compile(r"^\s*[<〈\[【(]?\s*(표|그림|사진)\s*[\d\s\-–.]*[(（]\s*계\s*속\s*[)）]")  # '<표 7-2(계속)> 표제목'


def squeeze(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def pt(desc: Desc, cid) -> float:
    c = desc.char_prs.get(cid)
    return int(c.get("height")) / 100 if c is not None else 0.0


def left_pt(desc: Desc, pid) -> float:
    vals, _ = desc.margin(pid)
    try:
        return float(vals["left"].replace("pt", ""))
    except ValueError:
        return 0.0


def flatten(pk: Pkg):
    rows = []
    for s, sec in enumerate(pk.sections):
        for i, p in enumerate(sec.findall(q("hp:p"))):
            rows.append({"s": s, "i": i, "p": p, "sec": sec, "text": own_text(p)})
    return rows


def pages(rows):
    """쪽 묶음: 구역이 바뀌거나 '쪽 나누기' 문단에서 새 쪽."""
    out = [[]]
    for r in rows:
        if out[-1] and ((r["i"] == 0 and r["s"] > 0) or r["p"].get("pageBreak") == "1"):
            out.append([])
        out[-1].append(r)
    return out


def is_toc_page(g) -> bool:
    texts = [r["text"] for r in g if r["text"].strip()]
    if not texts:
        return False
    title = any(TOC_TITLE.match(squeeze(t)) or TOC_SUB.match(squeeze(t)) for t in texts)
    entries = sum(1 for t in texts if TOC_ENTRY.search(t))
    return (title and entries >= 1) or (entries >= 3 and entries >= 0.5 * len(texts))


def has_heading(desc: Desc, r) -> bool:
    h = ft.heading(desc, r["sec"], r["p"])
    return bool(h and h[0] in ("OUTLINE", "NUMBER")) or bool(CHAPTER.match(r["text"]))


def is_cover_page(desc: Desc, g) -> bool:
    texts = [r for r in g if r["text"].strip()]
    if not texts or any(len(r["text"]) > 120 for r in texts):
        return False
    if any(has_heading(desc, r) for r in texts):
        return False
    if any(ft.objects(r["p"]) and any(ft.local(o) == "tbl" and int(o.get("rowCnt", 1)) > 3 for o in ft.objects(r["p"]))
           for r in g):
        return False
    return max(pt(desc, text_run_cid(r["p"])) for r in texts) >= 15


def part_of(g_list):
    """쪽 묶음들 → 부분 범위 [(구역, 처음, 끝), ...] (구역마다 하나)."""
    rows = [r for g in g_list for r in g]
    out = []
    for r in rows:
        if out and out[-1][0] == r["s"] and out[-1][2] == r["i"] - 1:
            out[-1][2] = r["i"]
        else:
            out.append([r["s"], r["i"], r["i"]])
    return out, rows


def cover_roles(desc: Desc, rows):
    lines = []
    for k, r in enumerate(rows):
        t = r["text"].strip()
        if not t:
            continue
        s = squeeze(t)
        kind = ("문서 종류" if GENERIC_COVER.match(s) else "날짜" if DATE.match(s) else
                "부제 후보" if PAREN.match(t) and (t[0] in "(<〈[【-") else "")
        lines.append({"문단": f"p{k}", "글자": t, "크기": pt(desc, text_run_cid(r["p"])), "역할": kind, "k": k})
    cands = [x for x in lines if not x["역할"]]
    title = max(cands, key=lambda x: (x["크기"], -x["k"])) if cands else None
    sub = None
    if title:
        title["역할"] = "제목"
        subs = [x for x in lines if x["역할"] == "부제 후보"]
        if subs:
            sub = min(subs, key=lambda x: abs(x["k"] - title["k"]))
            sub["역할"] = "부제"
    for x in lines:
        if x["역할"] == "부제 후보":
            x["역할"] = ""
    roles = {}
    if title:
        roles["제목"] = title["문단"]
    if sub:
        roles["부제"] = sub["문단"]
    return roles, [{k: v for k, v in x.items() if k != "k"} for x in lines]


def toc_roles(desc: Desc, rows):
    roles, notes = {"제목 뒤 빈 줄": []}, []
    title_k = next((k for k, r in enumerate(rows) if TOC_TITLE.match(squeeze(r["text"]))), None)
    roles["머리"] = [f"p{k}" for k in range(0, (title_k or 0) + 1)]
    start = (title_k if title_k is not None else 0) + 1
    k = start
    while k < len(rows) and not rows[k]["text"].strip() and not ft.objects(rows[k]["p"]):
        roles["제목 뒤 빈 줄"].append(f"p{k}")
        k += 1
    sub, heads, kinds = None, [], []
    for j in range(start, len(rows)):
        r = rows[j]
        t = r["text"]
        s = squeeze(t)
        if TOC_SUB.match(s):
            sub = "그림" if s.lstrip("<〈《[【(").startswith(("그림", "사진")) else "표"
            roles.setdefault(f"{sub} 차례 제목", f"p{j}")
            kinds.append((j, "부제목"))
            continue
        if not TOC_ENTRY.search(t):
            kinds.append((j, "빈 줄" if not s else "기타"))
            continue
        head = t.rsplit("\t", 1)[0] if "\t" in t else re.sub(r"[.…·ㆍ]{2,}.*$", "", t)
        if sub == "표" or CAP_TBL.match(head):
            kind = "표 항목"
        elif sub == "그림" or CAP_FIG.match(head):
            kind = "그림 항목"
        elif CHAPTER.match(head):
            kind = "장"
        else:
            kind = "제목"
            heads.append((j, left_pt(desc, r["p"].get("paraPrIDRef"))))
        kinds.append((j, kind))
        if kind != "제목":
            roles.setdefault(kind, f"p{j}")
    levels = sorted({x for _, x in heads})
    for j, x in heads:
        lv = levels.index(x) + 1
        if lv <= 5:
            roles.setdefault(f"{lv}수준", f"p{j}")
    for n, (j, kind) in enumerate(kinds):  # 장 사이 빈 줄: 항목 다음, 다음 '장' 항목 앞의 빈 줄
        if kind == "빈 줄" and 0 < n < len(kinds) - 1 and kinds[n + 1][1] == "장" and kinds[n - 1][1] not in ("빈 줄", "부제목"):
            roles.setdefault("장 사이 빈 줄", f"p{j}")
    if title_k is None:
        notes.append("차례 제목 줄('목차'·'차례')을 못 찾아 첫 문단을 머리로 씀")
    return roles, notes


def sig(r):
    return r["p"].get("paraPrIDRef"), text_run_cid(r["p"])


def vsig(desc: Desc, r):
    """눈에 보이는 모양(문단 모양 값, 글자 모양 값) — 한글은 같은 모양에도 ID를 여러 개 만들므로 ID가 아니라 값으로 견준다."""
    return desc.para_sig(r["p"].get("paraPrIDRef")), desc.char_sig(text_run_cid(r["p"]))


CAPTION_LIKE = re.compile(r"^\s*[<〈\[(【]?\s*(표|그림|사진|도표|fig\.?|figure|table)\s*[\d<\[(]", re.I)  # 제목처럼 보여도 표·그림 제목
NOTE_LIKE = re.compile(r"^\s*(자료|출처|주|비고|단위)\s*[:：)]")
STYLE_HINT = re.compile(r"제목|개요|heading|title", re.I)  # 스타일 이름이 제목임을 알려 줄 때
HEAD_LEN, HEAD_LEN_PLAIN = 60, 40  # 제목으로 볼 길이(번호·기호 뒤 글자 수) / 번호 없는 제목은 더 짧게


def is_auto(c) -> bool:
    """자동 번호(개요·문단 번호)가 걸린 제목 문단인가."""
    return c["역할"].endswith("수준") and c.get("수준") is not None


def kind_of(desc: Desc, rows, cls, k) -> dict:
    """문단 k를 제목 예시로 쓸 때의 번호 방식: 자동(개요·문단 번호) / 글자(직접 친 번호·기호) / 없음."""
    c, text = cls[k], rows[k]["text"]
    if is_auto(c) or (c["역할"] == "장 제목" and c.get("번호방식") != "글자"):
        return {"방식": "자동", "모양": c.get("번호", "")}
    t = text.strip()
    tpx = ft.typed_prefix(t)
    if tpx and tpx[0] not in ft.SYMBOL_ROLE:
        rest = t[len(tpx[1]):]
        lit = tpx[1].rstrip()
        gap = tpx[1][len(lit):] + rest[:len(rest) - len(rest.lstrip())]  # 번호 뒤 빈칸(양식에 친 그대로)
        return {"방식": "글자", "모양": tpx[0], "글자": lit, "뒤": gap}
    return {"방식": "없음", "모양": ""}


def heading_kinds(desc: Desc, rows, cls, body_k, skip, mixed: bool):
    """글자로 친 번호·기호 제목과 번호 없는 제목(굵거나 큰 짧은 줄)을 찾는다 → [(처음 나온 문단 번호, 정보)].
    같은 (번호 모양, 문단·글자 모양)끼리 묶어 판단한다(번호 모양 하나에 단계 하나):
      - 본문과 모양이 다르고 대부분 짧다(60자 이하) → 제목. 예시 글이 '제목을 입력하세요' 같은 문장이어도 된다.
      - 본문과 모양이 같아도 번호가 붙고 대부분 짧은 '문장 아닌 줄'이면 제목(자동 번호 제목이 없는 양식에서만).
      - 번호·기호가 없는 줄은 본문보다 굵거나 크고(또는 스타일 이름이 제목), 짧고, 문장이 아니고, 줄줄이 이어지지 않을 때만
        (자동 번호 제목이 없는 양식에서만 — 표·그림 제목, '자료:' 같은 줄은 뺀다).
    mixed: 자동 번호 제목이 함께 있는 양식(이때는 본문과 모양이 다른 '글자 번호' 제목만 더한다)."""
    body_cid = text_run_cid(rows[body_k]["p"]) if body_k is not None else None
    body_sig = vsig(desc, rows[body_k]) if body_k is not None else None
    b_size = pt(desc, body_cid) if body_cid else 0.0
    b_bold = bool(desc.char_sig(body_cid)[3]) if body_cid else False
    groups = {}
    for k, c in enumerate(cls):
        t = rows[k]["text"].strip()
        if not t or k in skip:
            continue
        if c["역할"] == "[판단 필요]" and "직접 친 기호/번호" in c.get("근거", ""):
            tpx = ft.typed_prefix(t)
            rest = t[len(tpx[1]):].strip()
            key = (tpx[0], vsig(desc, rows[k]))
        elif c["역할"] == "본문" and not c.get("직접기호") and not CAPTION_LIKE.match(t) and not NOTE_LIKE.match(t):
            rest, key = t, ("", vsig(desc, rows[k]))
        else:
            continue
        groups.setdefault(key, []).append((k, len(rest), ft.is_sentence(rest)))

    def next_sig(k):
        for j in range(k + 1, len(rows)):
            if rows[j]["text"].strip() or ft.objects(rows[j]["p"]):
                return vsig(desc, rows[j])
        return None
    best = {}  # 번호 모양(번호 없는 줄은 모양마다) → 그 묶음의 문단들
    for (shape, sg), ms in groups.items():
        short = sum(1 for _, n, _ in ms if n <= HEAD_LEN) / len(ms)
        plain_ = sum(1 for _, n, s in ms if n <= 50 and not s) / len(ms)
        differs = sg != body_sig
        if shape and ft.is_number_shape(shape):
            ok = (differs and short >= 0.6) or (not mixed and plain_ >= 0.6)
        elif shape:  # 기호('□'·'○' …): 본문과 모양이 다를 때만
            ok = differs and short >= 0.6
        else:  # 번호·기호 없는 줄
            st = desc.styles.get(rows[ms[0][0]]["p"].get("styleIDRef"))
            look = (bool(sg[1][3]) and not b_bold) or int(sg[1][2]) / 100 >= b_size * 1.1 or \
                bool(st is not None and STYLE_HINT.search(st.get("name") or ""))
            tight = sum(1 for _, n, s in ms if n <= HEAD_LEN_PLAIN and not s) / len(ms)
            ok = not mixed and differs and look and tight >= 0.6 and any(next_sig(k) != sg for k, _, _ in ms)
        key = shape or ("", sg)
        if ok and (key not in best or len(ms) > len(best[key])):
            best[key] = ms
    return sorted(((ms[0][0], kind_of(desc, rows, cls, ms[0][0])) for ms in best.values()), key=lambda x: x[0])


def order_levels(kinds):
    """제목 단계 순서: 처음 나온 순서. 자동 번호 제목끼리는 개요 수준 순서를 지키고, 여러 단 번호('1.1')는 윗단('1.') 바로 아래."""
    kinds = sorted(kinds, key=lambda x: x[0])
    autos = sorted((x for x in kinds if x[1]["방식"] == "자동"), key=lambda x: x[2])
    it = iter(autos)
    kinds = [next(it) if x[1]["방식"] == "자동" else x for x in kinds]
    moved = True
    while moved:
        moved = False
        shapes = [x[1].get("모양") if x[1]["방식"] == "글자" else None for x in kinds]
        for i, s in enumerate(shapes):
            par = ft.multi_parent_shape(s) if s else None
            if par in shapes and shapes.index(par) > i:
                x = kinds.pop(i)
                kinds.insert(kinds.index(next(y for y in kinds if y[1].get("모양") == par and y[1]["방식"] == "글자")) + 1, x)
                moved = True
                break
    return kinds


def body_roles(desc: Desc, rows, picks=None):
    """본문 부분 역할 → 기준 문단(부분 안 번호). classify(원고 분석과 같은 규칙)로 정한다.
    picks: 사용자가 고친 것 {"제목": ["p3", "p21", …](1단계부터), "본문": "p4"} — 있으면 자동으로 찾은 것 대신 쓴다.
    돌려주는 값: (본문 역할 R, 표·그림 역할 T, 문단 분류, 알림, 제목 번호 방식 N, 고를 수 있는 줄 후보)"""
    picks = picks or {}
    cls = []
    for k, r in enumerate(rows):
        c = ft.classify(desc, r["sec"], f"p{k}", r["p"], {})
        if c["역할"] == "그림 문단" and c.get("표") and c["표"]["그림수"] == 0 and not c.get("떠있는개체")                 and c["표"]["행"] >= 2 and c["표"]["열"] >= 2:  # 캡션 번호 종류가 '그림'이어도 글자 칸 표는 표
            c = {**c, "역할": "표 문단", "근거": c["근거"] + " → 그림 없는 여러 칸 표라 표로"}
        if c["역할"] in ("본문", "[판단 필요]") and CHAPTER.match(r["text"]) and len(r["text"].strip()) <= 40:
            c = {**c, "역할": "장 제목", "번호방식": "글자", "근거": "글자로 친 '제N장'"}
        cls.append(c)

    def sep_kind(c):
        """따로 떨어진 표·그림 제목(캡션) 문단의 종류 — 개체에 붙은 캡션이 아니라 개체 위·아래에 따로 놓인 문단."""
        m = re.match(r"(표|그림) 캡션\(따로", c["역할"])
        return m.group(1) if m else None
    for k, c in enumerate(cls):  # 그림 제목 문단 옆의 글자 없는 표 = 빈 그림 틀(양식의 그림 자리)
        if sep_kind(c) != "그림":
            continue
        for j in (k - 1, k + 1):
            if 0 <= j < len(cls) and cls[j]["역할"] == "표 문단":
                tbl = next(o for o in ft.objects(rows[j]["p"]) if ft.local(o) == "tbl")
                if not ft.tf.has_text(tbl):
                    cls[j] = {**cls[j], "역할": "그림 문단", "근거": cls[j]["근거"] + " → 옆 문단이 그림 제목이라 빈 그림 틀"}

    def sep_near(kind, k):
        """개체 문단 k 바로 앞·뒤의 따로 떨어진 제목 문단 → (문단 번호, '위'/'아래'). 표는 위부터, 그림은 아래부터 본다."""
        for j in ((k - 1, k + 1) if kind == "표" else (k + 1, k - 1)):
            if 0 <= j < len(cls) and sep_kind(cls[j]) == kind:
                return j, ("위" if j < k else "아래")
        return None
    R = {"첫 문단": "p0"}
    T, notes, levels = {}, [], {}
    chap = next((k for k, c in enumerate(cls) if c["역할"] == "장 제목"), None)
    if chap is not None:
        T["장 제목"] = f"p{chap}"
    for k, c in enumerate(cls):
        if is_auto(c):
            levels.setdefault(c["수준"], k)

    def bodyish(k):
        """본문 모양 후보: 번호·기호 없는 글, 그리고 번호·기호로 시작해도 긴 글·문장(개조식 '○ …' 항목)."""
        c, t = cls[k], rows[k]["text"].strip()
        if c["역할"] == "본문":
            return True
        if c["역할"] == "[판단 필요]" and "직접 친 기호/번호" in c.get("근거", ""):
            rest = t[len(ft.typed_prefix(t)[1]):].strip()
            return len(rest) > HEAD_LEN or ft.is_sentence(rest)
        return False
    body = Counter()  # 본문 모양: 글자 수로 가중(짧은 큰 제목 한 줄이 본문으로 뽑히지 않게)
    for k in range(len(cls)):
        if bodyish(k):
            body[sig(rows[k])] += len(rows[k]["text"].strip())
    body_sig = None
    if body:
        body_sig = body.most_common(1)[0][0]
        R["본문"] = f"p{next(k for k in range(len(cls)) if bodyish(k) and sig(rows[k]) == body_sig)}"
    blank = Counter(sig(rows[k]) for k, c in enumerate(cls) if c["역할"] == "빈 줄" and k > 0)
    if blank:
        top = blank.most_common(1)[0][0]
        R["빈 줄"] = f"p{next(k for k, c in enumerate(cls) if c['역할'] == '빈 줄' and k > 0 and sig(rows[k]) == top)}"
    def obj_key(kind, k):
        """예시로 쓸 표·그림 고르기: 캡션 있음 → (표) 3×2 이상·합친 셀 없음 / (그림) 1칸 틀 → 앞쪽."""
        tbl = next(o for o in ft.objects(rows[k]["p"]) if ft.local(o) == "tbl")
        cells = ft.direct_cells(tbl)
        merged = sum(1 for tc in cells if ft.cell_addr(tc)[2] > 1 or ft.cell_addr(tc)[3] > 1)
        has_cap = bool((cls[k].get("캡션") or {}).get("글자")) or sep_near(kind, k) is not None
        if kind == "표":
            ok = int(tbl.get("rowCnt")) >= 3 and int(tbl.get("colCnt")) >= 2
            return (not has_cap, not ok, merged, k)
        return (not has_cap, len(cells) != 1, k)
    for kind in ("표", "그림"):
        ks = [k for k, c in enumerate(cls) if c["역할"] == f"{kind} 문단"]
        if not ks:
            continue
        e = min(ks, key=lambda k: obj_key(kind, k))
        T[kind] = f"p{e}"
        if (cls[e].get("캡션") or {}).get("글자"):
            continue  # 개체에 붙은 캡션(예전 방식) — 아래는 제목을 따로 문단으로 쓰는 양식만
        near = sep_near(kind, e)
        seps = [k for k, c in enumerate(cls) if sep_kind(c) == kind]
        if near is None and seps:  # 예시 개체 옆에는 없지만 양식 안에 제목 문단이 있음 → 첫 것, 위치는 관례
            near = (seps[0], "위" if kind == "표" else "아래")
            notes.append(f"{kind} 제목 문단이 예시 {kind} 바로 옆에 없어 {('위' if kind == '표' else '아래')}에 둠(관례)")
        if near is not None:
            T[f"{kind} 캡션"], T[f"{kind} 캡션 위치"] = f"p{near[0]}", near[1]
            for k, r in enumerate(rows):  # '(계속)' 제목 문단(번호를 늘리지 않는 이어지는 표·그림의 제목)
                st = desc.styles.get(r["p"].get("styleIDRef"))
                name = (st.get("name") or "") if st is not None else ""
                m = CONT_CAP.match(r["text"])
                kk = ("그림" if m.group(1) in ("그림", "사진") else "표") if m else \
                    (("그림" if "그림" in name else "표" if "표" in name else None) if "계속" in name else None)
                if kk == kind and k != near[0]:
                    T[f"{kind} 계속"] = f"p{k}"
                    break
    if "장 제목" not in T and R.get("본문"):  # 번호 없는 큰 제목(문서 제목) → 장 제목 모양으로(장 번호는 글자로)
        body_pt = pt(desc, text_run_cid(rows[int(R["본문"][1:])]["p"]))
        for k, c in enumerate(cls[:6]):
            t = rows[k]["text"].strip()
            size = pt(desc, text_run_cid(rows[k]["p"]))
            if t and c["역할"] == "본문" and len(t) <= 60 and size >= max(14.0, body_pt * 1.3):
                T["장 제목"] = f"p{k}"
                notes.append(f"'제N장' 장 제목이 없어 큰 제목 '{t[:20]}'(크기 {size:g}pt)를 장 제목 모양으로 씀 — 장 번호는 글자로")
                break
    for key, tags in (("머리말꼬리말", ("header", "footer")), ("쪽번호", ("pageNum",))):
        k = next((k for k, r in enumerate(rows) if any(r["p"].find(f".//{q('hp:' + t)}") is not None for t in tags)), None)
        if k is not None:
            T[key] = f"p{k}"
    # 제목 단계: 자동 번호 제목 + 글자로 친 번호·기호 제목 + (자동 번호 제목이 없는 양식) 번호 없는 굵은·큰 제목 — 처음 나온 순서
    skip = {int(T[k][1:]) for k in ("장 제목", "표 계속", "그림 계속", "표 캡션", "그림 캡션") if T.get(k)}
    kinds = [(k, {"방식": "자동", "모양": cls[k].get("번호", "")}, lvl) for lvl, k in levels.items()]
    body_k = int(R["본문"][1:]) if R.get("본문") else None
    kinds += [(k, info, None) for k, info in heading_kinds(desc, rows, cls, body_k, skip, mixed=bool(levels))]
    kinds = order_levels(kinds)
    N = {}
    for n, (k, info, _) in enumerate(kinds[:5], start=1):
        R[f"{n}수준"] = f"p{k}"
        N[f"{n}수준"] = info
    typed = [info["글자"] for _, info, _ in kinds[:5] if info["방식"] == "글자"]
    plain_n = sum(1 for _, info, _ in kinds[:5] if info["방식"] == "없음")
    if typed:
        notes.append("번호·기호를 직접 친 제목을 제목 단계로 씀: " + ", ".join(f"'{x}'" for x in typed)
                     + " — 문서의 제목 번호도 이 모양으로 글자로 넣습니다")
    if plain_n:
        notes.append(f"번호 없는 굵은(큰) 줄 {plain_n}가지를 제목 단계로 씀 — 틀렸으면 [제목·본문 줄 고치기]에서 바꿔 주세요")
    if len(kinds) > 5:
        notes.append(f"제목 단계는 5단계까지만 씀(양식에서 찾은 것 {len(kinds)}가지)")
    # 사용자가 고친 것(제목 단계·본문 줄)
    def valid(ref):
        m = re.fullmatch(r"p(\d+)", str(ref or ""))
        return bool(m) and int(m.group(1)) < len(rows) and bool(rows[int(m.group(1))]["text"].strip()) \
            and not ft.objects(rows[int(m.group(1))]["p"])
    if picks.get("제목") is not None:
        good = [ref for ref in picks["제목"] if valid(ref)][:5]
        if len(good) == len(list(picks["제목"])[:5]):
            for key in [key for key in R if key.endswith("수준")]:
                del R[key]
            N = {}
            for n, ref in enumerate(good, start=1):
                R[f"{n}수준"] = ref
                N[f"{n}수준"] = kind_of(desc, rows, cls, int(ref[1:]))
            notes = [x for x in notes if "제목 단계로 씀" not in x and "5단계까지만" not in x]
            notes.append(f"제목 단계 {len(good)}가지는 직접 고르신 줄을 씁니다" if good else "제목 단계는 쓰지 않기로 하셨습니다")
        else:
            notes.append("고르신 제목 줄 일부를 이 양식에서 찾지 못해 자동으로 찾은 제목 단계를 씁니다")
    if picks.get("본문"):
        if valid(picks["본문"]):
            R["본문"] = picks["본문"]
            notes.append("본문 모양은 직접 고르신 줄을 씁니다")
        else:
            notes.append("고르신 본문 줄을 이 양식에서 찾지 못해 자동으로 찾은 본문 모양을 씁니다")
    return R, T, cls, notes, N, candidates(desc, rows, cls, R, T, N)


def candidates(desc: Desc, rows, cls, R, T, N, limit=40):
    """사용자가 제목·본문 줄을 고칠 때 고를 수 있는 줄: 글이 있는 본문 부분 문단을 (번호 방식·모양, 문단·글자 모양)으로 묶어
    묶음마다 첫 줄 하나(표·그림 제목과 개체 문단은 뺀다). 지금 맡은 역할도 함께."""
    role_of = {int(v[1:]): k for k, v in R.items() if k != "첫 문단" and k != "빈 줄"}
    if T.get("장 제목"):
        role_of[int(T["장 제목"][1:])] = "장 제목"
    groups, order = {}, []
    for k, c in enumerate(cls):
        t = rows[k]["text"].strip()
        if not t or ft.objects(rows[k]["p"]) or "캡션" in c["역할"] or CAPTION_LIKE.match(t):
            continue
        info = kind_of(desc, rows, cls, k)
        key = ("자동", c.get("수준"), c["역할"]) if info["방식"] == "자동" else (info["방식"], info.get("모양"), vsig(desc, rows[k]))
        if key not in groups:
            groups[key] = {"k": k, "n": 0, "info": info, "role": ""}
            order.append(key)
        g = groups[key]
        g["n"] += 1
        if k in role_of:  # 이 묶음의 줄이 역할을 맡고 있으면 그 줄을 보여 준다
            g["k"], g["role"], g["info"] = k, role_of[k], (N.get(role_of[k]) or info)
    out = []
    for key in order[:limit]:
        g = groups[key]
        r = rows[g["k"]]
        cid = text_run_cid(r["p"])
        fonts = desc.char_sig(cid)
        out.append({"문단": f"p{g['k']}", "보기": r["text"].strip()[:40], "글꼴": fonts[0], "크기": pt(desc, cid),
                    "굵게": bool(fonts[3]), "방식": g["info"]["방식"], "번호": g["info"].get("모양") or "", "수": g["n"],
                    "역할": g["role"]})
    return out


def describe(desc: Desc, rows, cls, R, T, cover_lines, toc_R, parts, tg=None, N=None):
    """요약. tg=(desc, rows, cls): 표·그림 역할(T)을 다른 파일에서 가져왔을 때 그 파일의 것(없으면 본문 파일).
    N: 제목 단계의 번호 방식(자동·글자·없음)."""
    t_desc, t_rows, t_cls = tg or (desc, rows, cls)
    N = N or {}

    def para(ref, kind="본문", d=desc, rs=rows):
        if not ref:
            return None
        r = rs[int(ref[1:])]
        cid = text_run_cid(r["p"])
        fonts = d.char_sig(cid)
        return {"보기": r["text"].strip()[:40], "글꼴": fonts[0], "크기": pt(d, cid), "굵게": fonts[3]}
    heads = []
    for n in range(1, 6):
        ref = R.get(f"{n}수준")
        if ref:
            c = cls[int(ref[1:])]
            info = N.get(f"{n}수준") or {"방식": "자동", "모양": c.get("번호", "")}
            shown = info.get("글자") or info.get("모양") or ""
            heads.append({"단계": n, "번호": shown if info["방식"] != "자동" else c.get("번호", ""), "방식": info["방식"], **para(ref)})
    caps = {}
    for kind in ("표", "그림"):
        ref = T.get(kind)
        if ref:
            cap = t_cls[int(ref[1:])].get("캡션") or {}
            caps[kind] = {"캡션": (cap.get("번호", "") + " " + (cap.get("글자") or "")).strip(), "위치": cap.get("위치") or "없음"}
            if T.get(f"{kind} 캡션"):  # 제목을 개체 위·아래에 따로 문단으로 두는 양식
                sr = t_rows[int(T[f"{kind} 캡션"][1:])]
                shown = ft.number_all(t_desc, sr["sec"]).get(f"p{sr['i']}") or (t_cls[int(T[f"{kind} 캡션"][1:])].get("번호") or "")
                caps[kind] = {"캡션": f"{shown} {sr['text'].strip()[:40]}".strip(),
                              "위치": f"{T[f'{kind} 캡션 위치']}(따로 문단)",
                              **({"계속": t_rows[int(T[f'{kind} 계속'][1:])]["text"].strip()[:40]} if T.get(f"{kind} 계속") else {})}
    hf = {}
    if T.get("머리말꼬리말"):
        p = t_rows[int(T["머리말꼬리말"][1:])]["p"]
        for tag, name in (("header", "머리말"), ("footer", "꼬리말")):
            el = p.find(f".//{q('hp:' + tag)}")
            if el is not None:
                hf[name] = " ".join(own_text(x) for x in el.iter(q("hp:p"))).replace("\t", " ⇥ ").strip()
        hdrs = list(p.iter(q("hp:header")))
        if hdrs:  # 쪽 종류별 머리말(설문 '양식에 있는 머리말 그대로'의 미리 보기)
            side = {"BOTH": "모든 쪽", "EVEN": "짝수 쪽", "ODD": "홀수 쪽"}
            hf["머리말 쪽"] = [{"쪽": side.get(h.get("applyPageType"), h.get("applyPageType") or ""),
                              "글자": " ".join(own_text(x) for x in h.iter(q("hp:p"))).replace("\t", " ⇥ ").strip()}
                             for h in hdrs]
    pn = None
    if T.get("쪽번호"):
        el = t_rows[int(T["쪽번호"][1:])]["p"].find(f".//{q('hp:pageNum')}")
        side = el.get("sideChar", "")
        pn = {"위치": el.get("pos"), "모양": f"{side} 1 {side}".strip() if side else "1"}
    missing = [k for k in ("본문", "빈 줄", "1수준") if k not in R] + [k for k in ("표", "그림") if k not in T]
    return {"부분": {k: bool(parts.get(k)) for k in ("표지", "차례", "본문")},
            "표지 줄": cover_lines, "장 제목": para(T.get("장 제목"), d=t_desc, rs=t_rows), "제목 단계": heads,
            "본문": para(R.get("본문")),
            "표": caps.get("표"), "그림": caps.get("그림"), **hf, "쪽 번호": pn,
            "차례 항목": sorted(k for k in toc_R if k not in ("머리", "제목 뒤 빈 줄")), "없는 것": missing}


def scan(path) -> dict:
    """파일 하나 → 찾은 부분(표지·차례·본문)과 그 문단. 본문이 없어도 된다(표지만·차례만 든 파일)."""
    path = Path(path)
    pk = Pkg(path)
    desc = Desc(pk.header)
    rows = flatten(pk)
    groups = pages(rows)
    kinds = ["차례" if is_toc_page(g) else "" for g in groups]
    first_toc = kinds.index("차례") if "차례" in kinds else None
    last_toc = max(i for i, x in enumerate(kinds) if x == "차례") if first_toc is not None else None
    cover_i = None
    for i in range(0, first_toc if first_toc is not None else 1):
        if is_cover_page(desc, groups[i]):
            cover_i = i
            break
    body_from = (last_toc + 1) if last_toc is not None else ((cover_i + 1) if cover_i is not None else 0)
    parts, part_rows, notes = {}, {}, []
    if cover_i is not None:
        parts["표지"], part_rows["표지"] = part_of([groups[cover_i]])
    if first_toc is not None:
        parts["차례"], part_rows["차례"] = part_of(groups[first_toc:last_toc + 1])
    if body_from < len(groups):
        parts["본문"], part_rows["본문"] = part_of(groups[body_from:])
    if first_toc is not None and cover_i is None and first_toc > 0:
        notes.append(f"차례 앞 {first_toc}쪽은 표지로 보지 않음(제출문·요약 등)")
    return {"path": path, "desc": desc, "parts": parts, "rows": part_rows, "notes": notes}


def body_score(sc) -> tuple:
    """본문 모양을 가져올 파일: 본문 문단이 있고, 제목 단계가 많고, 본문 글이 긴 파일."""
    R = sc["R"]
    levels = sum(1 for k in R if k.endswith("수준"))
    text = sum(len(r["text"].strip()) for r in sc["rows"]["본문"])
    return (bool(R.get("본문")), levels, text)


def tg_score(sc) -> int:
    """표·그림·장 제목·머리말 모양을 가져올 파일: 표·그림 예시(2점씩), 진짜 '제N장' 장 제목(2점 — 큰 제목으로 대신한 것은 1점),
    머리말꼬리말·쪽 번호(1점씩)."""
    T, cls = sc["T"], sc["cls"]
    s = 2 * bool(T.get("표")) + 2 * bool(T.get("그림")) + bool(T.get("머리말꼬리말")) + bool(T.get("쪽번호"))
    if T.get("장 제목"):
        s += 2 if cls[int(T["장 제목"][1:])]["역할"] == "장 제목" else 1
    return s


def diagnose(s: dict) -> dict:
    """양식 진단: 요약(describe) → 항목마다 있음·없음과, 없을 때 어떻게 처리하는지·한글에서 고치는 법.
    구분: 필수(없으면 양식으로 못 씀 — 여기 오기 전에 걸러진다) / 권장(없으면 그 부분만 다르게 처리) / 선택(없어도 됨)."""
    def font(p):
        return f"{p['글꼴']} {p['크기']:g}pt" + (" 굵게" if p.get("굵게") else "")
    items = []

    def add(name, kind, found, missing="", fix=""):
        items.append({"이름": name, "구분": kind, "상태": "있음" if found else "없음", "찾은 것": found or "",
                      "없으면": "" if found else missing, "고치는 법": "" if found else fix})
    b = s.get("본문")
    add("본문", "필수", f"{font(b)} — '{b['보기']}'" if b else "")
    heads = s.get("제목 단계") or []
    how = {"자동": "자동 번호", "글자": "직접 친 번호", "없음": "번호 없음"}
    add("제목 단계", "권장",
        " → ".join(f"{h['단계']}단계 {h['번호'] or '(번호 없음)'}" for h in heads) if heads else "",
        "문서에 제목이 있으면 변환할 때 여쭤봅니다(양식 본문 글꼴로 굵게 / 문서의 원래 모양 그대로).",
        "양식 본문에 '1. 제목'처럼 제목 줄을 단계마다 한 줄씩 넣어 주세요. 번호는 직접 쳐도, 자동 번호여도 됩니다.")
    items[-1]["단계"] = [{"단계": h["단계"], "번호": h["번호"], "방식": how.get(h.get("방식"), ""), "모양": font(h), "보기": h["보기"]}
                        for h in heads]
    ch = s.get("장 제목")
    add("장 제목", "권장", f"{font(ch)} — '{ch['보기']}'" if ch else "",
        "문서에 장(제1장 …)이 있으면 변환할 때 여쭤봅니다(양식 1단계 제목으로 / 문서의 원래 모양 그대로).",
        "양식 본문 맨 앞에 '제1장 제목' 줄을 넣어 주세요.")
    for kind, tip in (("표", "제목이 달린 표를 하나 넣어 주세요(3줄×2칸 이상이면 테두리·머리행 모양을 정확히 읽습니다)."),
                      ("그림", "그림(또는 그림을 넣는 틀)과 그림 제목을 하나 넣어 주세요.")):
        c = s.get(kind)
        add(kind, "권장", (f"제목 '{c['캡션']}' · 위치 {c['위치']}" if c.get("캡션") else "제목(캡션) 없는 예시") if c else "",
            f"문서의 {kind}{'는' if kind == '표' else '은'} 원래 모양 그대로 둡니다.", tip)
    has_hf = "머리말" in s or "꼬리말" in s
    add("머리말·꼬리말", "권장", " / ".join(f"{k} '{s[k]}'" if s[k] else f"{k}(글자 없음)" for k in ("머리말", "꼬리말") if k in s)
        if has_hf else "", "머리말·꼬리말 없이 만듭니다.", "[쪽] → [머리말/꼬리말]로 머리말을 넣어 주세요.")
    pn = s.get("쪽 번호")
    add("쪽 번호", "권장", f"모양 {pn['모양']}" if pn else "", "쪽 번호 없이 만듭니다.", "[쪽] → [쪽 번호 매기기]로 쪽 번호를 넣어 주세요.")
    for part in ("표지", "차례"):
        add(part, "선택", "양식의 것을 씁니다" if s["부분"].get(part) else "", f"원하시면 간단한 {part}를 만들어 드립니다.", "")
    lacking = [x["이름"] for x in items if x["상태"] == "없음" and x["구분"] == "권장"]
    return {"판정": "주의" if lacking else "통과", "없는 것": lacking, "항목": items}


def analyze(path, profile_path=None, picks=None) -> dict:
    """양식 파일(하나 또는 여러 개) → 프로필(dict). profile_path를 주면 JSON으로 쓰고 양식 파일 경로는 그 폴더 기준 상대 경로로.
    picks: 사용자가 고친 제목 단계·본문 줄(body_roles 참고) — 본문을 가져올 파일에만 쓴다.

    여러 파일이면(회사 양식이 앞표지·목차·본문 스타일·표 그림 양식처럼 나뉜 경우) 부분마다 알맞은 파일을 고른다.
      - 본문(본문·제목 단계·빈 줄, 쪽 설정·글꼴의 바탕): 본문 문단이 있고 제목 단계가 가장 많은 파일
      - 표·그림·장 제목·머리말·쪽 번호: tg_score가 가장 높은 파일(같으면 본문 파일)
      - 표지·차례: 그 부분만 든 파일 → 본문 파일 안의 것 → 다른 파일 안의 것 순서(앞에 올린 파일 먼저)"""
    paths = [Path(p) for p in path] if isinstance(path, (list, tuple)) else [Path(path)]
    scans = [scan(p) for p in paths]
    for sc in scans:
        if "본문" in sc["parts"]:
            sc["R"], sc["T"], sc["cls"], sc["bnotes"], sc["N"], sc["cands"] = body_roles(sc["desc"], sc["rows"]["본문"])
    bodies = [i for i, sc in enumerate(scans) if "본문" in sc["parts"]]
    if not bodies:
        raise ValueError("본문을 찾지 못했다(표지·차례 뒤에 쪽이 없음)")
    bi = max(bodies, key=lambda i: (body_score(scans[i]), -i))
    ti = max(bodies, key=lambda i: (tg_score(scans[i]), i == bi, -i))
    B, TG = scans[bi], scans[ti]
    if picks:  # 사용자가 고친 줄은 본문을 가져오는 파일의 문단 번호
        B["R"], _, B["cls"], B["bnotes"], B["N"], B["cands"] = body_roles(B["desc"], B["rows"]["본문"], picks)

    def pick_part(name):
        own = [i for i, sc in enumerate(scans) if name in sc["parts"] and "본문" not in sc["parts"]]
        if own:
            return own[0]
        if name in B["parts"]:
            return bi
        return next((i for i, sc in enumerate(scans) if name in sc["parts"]), None)
    ci, oi = pick_part("표지"), pick_part("차례")
    used = sorted({i for i in (bi, ti, ci, oi) if i is not None})
    fidx = {i: n for n, i in enumerate(used)}  # 프로필 '양식파일' 안 번호(쓰는 파일만)

    # 장 제목 알림은 표·그림 역할(T)을 가져온 파일의 것, 나머지(제목 단계 등)는 본문 파일의 것
    notes = list(B["notes"]) + [x for x in B["bnotes"] if "장 제목" not in x] + [x for x in TG["bnotes"] if "장 제목" in x]
    if ti == bi:
        notes = list(B["notes"]) + list(B["bnotes"])  # 파일 하나: 예전 순서 그대로
    R, T, cls = B["R"], TG["T"], B["cls"]
    roles = {"본문": R, "표그림": T, "제목 번호": B["N"]}
    parts = {}
    cover_lines = []
    if ci is not None:
        parts["표지"] = {"파일": fidx[ci], "범위": scans[ci]["parts"]["표지"]}
        roles["표지"], cover_lines = cover_roles(scans[ci]["desc"], scans[ci]["rows"]["표지"])
    toc_R = {}
    if oi is not None:
        parts["차례"] = {"파일": fidx[oi], "범위": scans[oi]["parts"]["차례"]}
        toc_R, tnotes = toc_roles(scans[oi]["desc"], scans[oi]["rows"]["차례"])
        roles["목차"] = toc_R
        notes += tnotes
    parts["본문"] = {"파일": fidx[bi], "범위": B["parts"]["본문"]}
    if ti != bi:
        parts["표그림"] = {"파일": fidx[ti], "범위": TG["parts"]["본문"]}

    def rel(p):
        if profile_path is None:
            return p.name
        here = Path(profile_path).resolve().parent
        return str(p.resolve().relative_to(here)) if p.resolve().is_relative_to(here) else str(p.resolve())
    names = [p.name for p in paths]
    prof = {
        "버전": 2,
        "설명": (f"{names[0]}에서" if len(paths) == 1 else f"{len(paths)}개 파일({', '.join(names)})에서") + " 자동으로 찾은 양식(template_profile.py)",
        "양식파일": [rel(paths[i]) for i in used],
        "부분": parts,
        "양식역할": roles,
    }
    prof["요약"] = describe(B["desc"], B["rows"]["본문"], cls, R, T, cover_lines, toc_R, parts,
                          tg=(TG["desc"], TG["rows"]["본문"], TG["cls"]) if ti != bi else None, N=B["N"])
    prof["요약"]["후보"] = B["cands"]
    prof["요약"]["진단"] = diagnose(prof["요약"])
    if len(paths) > 1:
        unused = [names[i] for i in range(len(paths)) if i not in used]
        prof["요약"]["파일"] = {"본문": names[bi], "표·그림": names[ti], "표지": names[ci] if ci is not None else None,
                             "차례": names[oi] if oi is not None else None, "안 씀": unused}
        if unused:
            notes.append(f"쓰지 않은 파일: {', '.join(unused)} — 같은 부분을 다른 파일에서 가져왔습니다")
    prof["요약"]["알림"] = notes
    if profile_path:
        Path(profile_path).write_text(json.dumps(prof, ensure_ascii=False, indent=1), encoding="utf-8")
    return prof


def main(argv):
    prof = analyze(argv[0], argv[1] if len(argv) > 1 else None)
    s = prof["요약"]
    print(f"부분: {', '.join(k for k, v in s['부분'].items() if v)}")
    for k, v in prof["부분"].items():
        print(f"  {k}: {v['범위'] if v else '-'}")
    print("역할:", json.dumps(prof["양식역할"], ensure_ascii=False))
    print("요약:", json.dumps({k: v for k, v in s.items() if k != "표지 줄"}, ensure_ascii=False, indent=1))
    if s["표지 줄"]:
        print("표지 줄:", [(x["글자"][:20], x["크기"], x["역할"]) for x in s["표지 줄"]])


if __name__ == "__main__":
    main(sys.argv[1:])
