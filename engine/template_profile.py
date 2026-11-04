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


def body_roles(desc: Desc, rows):
    """본문 부분 역할 → 기준 문단(부분 안 번호). classify(원고 분석과 같은 규칙)로 정한다."""
    cls = []
    for k, r in enumerate(rows):
        c = ft.classify(desc, r["sec"], f"p{k}", r["p"], {})
        if c["역할"] == "그림 문단" and c.get("표") and c["표"]["그림수"] == 0 and not c.get("떠있는개체")                 and c["표"]["행"] >= 2 and c["표"]["열"] >= 2:  # 캡션 번호 종류가 '그림'이어도 글자 칸 표는 표
            c = {**c, "역할": "표 문단", "근거": c["근거"] + " → 그림 없는 여러 칸 표라 표로"}
        if c["역할"] in ("본문", "[판단 필요]") and CHAPTER.match(r["text"]) and len(r["text"].strip()) <= 40:
            c = {**c, "역할": "장 제목", "번호방식": "글자", "근거": "글자로 친 '제N장'"}
        cls.append(c)
    R = {"첫 문단": "p0"}
    T, notes, levels = {}, [], {}
    chap = next((k for k, c in enumerate(cls) if c["역할"] == "장 제목"), None)
    if chap is not None:
        T["장 제목"] = f"p{chap}"
    for k, c in enumerate(cls):
        if c["역할"].endswith("수준") and c.get("수준") is not None:
            levels.setdefault(c["수준"], k)
    for n, lvl in enumerate(sorted(levels), start=1):  # 실제 개요 수준 → 양식의 n번째 제목 단계
        if n <= 5:
            R[f"{n}수준"] = f"p{levels[lvl]}"
    body = Counter()  # 본문 모양: 글자 수로 가중(짧은 큰 제목 한 줄이 본문으로 뽑히지 않게)
    for k, c in enumerate(cls):
        if c["역할"] == "본문":
            body[sig(rows[k])] += len(rows[k]["text"].strip())
    if body:
        top = body.most_common(1)[0][0]
        R["본문"] = f"p{next(k for k, c in enumerate(cls) if c['역할'] == '본문' and sig(rows[k]) == top)}"
    blank = Counter(sig(rows[k]) for k, c in enumerate(cls) if c["역할"] == "빈 줄" and k > 0)
    if blank:
        top = blank.most_common(1)[0][0]
        R["빈 줄"] = f"p{next(k for k, c in enumerate(cls) if c['역할'] == '빈 줄' and k > 0 and sig(rows[k]) == top)}"
    def obj_key(kind, k):
        """예시로 쓸 표·그림 고르기: 캡션 있음 → (표) 3×2 이상·합친 셀 없음 / (그림) 1칸 틀 → 앞쪽."""
        tbl = next(o for o in ft.objects(rows[k]["p"]) if ft.local(o) == "tbl")
        cells = ft.direct_cells(tbl)
        merged = sum(1 for tc in cells if ft.cell_addr(tc)[2] > 1 or ft.cell_addr(tc)[3] > 1)
        has_cap = bool((cls[k].get("캡션") or {}).get("글자"))
        if kind == "표":
            ok = int(tbl.get("rowCnt")) >= 3 and int(tbl.get("colCnt")) >= 2
            return (not has_cap, not ok, merged, k)
        return (not has_cap, len(cells) != 1, k)
    for kind in ("표", "그림"):
        ks = [k for k, c in enumerate(cls) if c["역할"] == f"{kind} 문단"]
        if ks:
            T[kind] = f"p{min(ks, key=lambda k: obj_key(kind, k))}"
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
    typed = [k for k, c in enumerate(cls) if c["역할"] == "[판단 필요]" and c.get("직접기호")]
    if typed and not levels:
        notes.append(f"번호를 글자로 친 제목 {len(typed)}개(예: '{rows[typed[0]]['text'].strip()[:20]}') — 아직 자동 번호 제목만 양식 단계로 씀")
    return R, T, cls, notes


def describe(desc: Desc, rows, cls, R, T, cover_lines, toc_R, parts):
    def para(ref, kind="본문"):
        if not ref:
            return None
        r = rows[int(ref[1:])]
        cid = text_run_cid(r["p"])
        fonts = desc.char_sig(cid)
        return {"보기": r["text"].strip()[:40], "글꼴": fonts[0], "크기": pt(desc, cid), "굵게": fonts[3]}
    heads = []
    for n in range(1, 6):
        ref = R.get(f"{n}수준")
        if ref:
            c = cls[int(ref[1:])]
            heads.append({"단계": n, "번호": c.get("번호", ""), **para(ref)})
    caps = {}
    for kind in ("표", "그림"):
        ref = T.get(kind)
        if ref:
            cap = cls[int(ref[1:])].get("캡션") or {}
            caps[kind] = {"캡션": (cap.get("번호", "") + " " + (cap.get("글자") or "")).strip(), "위치": cap.get("위치") or "없음"}
    hf = {}
    if T.get("머리말꼬리말"):
        p = rows[int(T["머리말꼬리말"][1:])]["p"]
        for tag, name in (("header", "머리말"), ("footer", "꼬리말")):
            el = p.find(f".//{q('hp:' + tag)}")
            if el is not None:
                hf[name] = " ".join(own_text(x) for x in el.iter(q("hp:p"))).replace("\t", " ⇥ ").strip()
    pn = None
    if T.get("쪽번호"):
        el = rows[int(T["쪽번호"][1:])]["p"].find(f".//{q('hp:pageNum')}")
        side = el.get("sideChar", "")
        pn = {"위치": el.get("pos"), "모양": f"{side} 1 {side}".strip() if side else "1"}
    missing = [k for k in ("본문", "빈 줄", "1수준") if k not in R] + [k for k in ("표", "그림") if k not in T]
    return {"부분": {k: bool(parts.get(k)) for k in ("표지", "차례", "본문")},
            "표지 줄": cover_lines, "장 제목": para(T.get("장 제목")), "제목 단계": heads, "본문": para(R.get("본문")),
            "표": caps.get("표"), "그림": caps.get("그림"), **hf, "쪽 번호": pn,
            "차례 항목": sorted(k for k in toc_R if k not in ("머리", "제목 뒤 빈 줄")), "없는 것": missing}


def analyze(path, profile_path=None) -> dict:
    """양식 파일 → 프로필(dict). profile_path를 주면 JSON으로 쓰고 양식 파일 경로는 그 폴더 기준 상대 경로로."""
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
    if body_from >= len(groups):
        raise ValueError("본문을 찾지 못했다(표지·차례 뒤에 쪽이 없음)")
    parts, part_rows, notes = {}, {}, []
    if cover_i is not None:
        parts["표지"], part_rows["표지"] = part_of([groups[cover_i]])
    if first_toc is not None:
        parts["차례"], part_rows["차례"] = part_of(groups[first_toc:last_toc + 1])
    parts["본문"], part_rows["본문"] = part_of(groups[body_from:])
    if first_toc is not None and cover_i is None and first_toc > 0:
        notes.append(f"차례 앞 {first_toc}쪽은 표지로 보지 않음(제출문·요약 등)")
    R, T, cls, bnotes = body_roles(desc, part_rows["본문"])
    notes += bnotes
    roles = {"본문": R, "표그림": T}
    cover_lines = []
    if "표지" in parts:
        roles["표지"], cover_lines = cover_roles(desc, part_rows["표지"])
    toc_R = {}
    if "차례" in parts:
        toc_R, tnotes = toc_roles(desc, part_rows["차례"])
        roles["목차"] = toc_R
        notes += tnotes
    prof = {
        "버전": 2,
        "설명": f"{path.name}에서 자동으로 찾은 양식(template_profile.py)",
        "양식파일": [path.name if profile_path is None else str(Path(path).resolve().relative_to(Path(profile_path).resolve().parent))
                 if Path(path).resolve().is_relative_to(Path(profile_path).resolve().parent) else str(Path(path).resolve())],
        "부분": {k: ({"파일": 0, "범위": v} if v else None) for k, v in parts.items()},
        "양식역할": roles,
    }
    prof["요약"] = describe(desc, part_rows["본문"], cls, R, T, cover_lines, toc_R, parts)
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
