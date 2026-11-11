"""양식 맞춤 변환 — 웹(브라우저 안 파이썬)과 명령줄이 함께 쓰는 진행 순서.

  1. analyze_template(양식 파일, 작업 폴더)     → 양식 부분·역할 찾기(template_profile) + 요약
  2. inspect_document(원고 파일, 작업 폴더)      → 원고 정리(.docx 변환, 여러 구역 합치기) + 역할 매핑(사람 판단 없이 자동)
                                                 + 자동 제목 제안
  3. convert(작업 폴더, 설문 답)                 → 결과 .hwpx + 검증 요약

원칙: 입력 파일은 읽기만(작업 폴더에 사본). 원고 글자는 바꾸지 않는다 — 바뀌는 것은 서식과 번호·기호(승인 변경으로 기록).
"""
import copy
import functools
import json
import re
import shutil
import sys
import traceback
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_transfer as ft  # noqa: E402
import template_profile as tp  # noqa: E402
from format_transfer import q, local  # noqa: E402


class UserError(Exception):
    """사용자에게 그대로 보여 줄 오류(파일 형식 등). help: 화면에 자세히 보여 줄 안내 — 제목·어디서·이유·해 볼 것·기술 정보."""

    def __init__(self, msg, help=None):  # noqa: A002 — 화면 쪽 이름과 맞춘다
        super().__init__(msg)
        self.help = help


# ----------------------------------------------------------------------- 친절한 오류 안내
STAGE = {"양식": "양식을 분석하다가", "문서": "문서를 살펴보다가", "변환": "변환하다가"}
STAGE_TIP = {
    "양식": "양식 파일을 한글에서 열어 [파일] → [다른 이름으로 저장] → 파일 형식 'HWPX'로 다시 저장한 뒤 올려 보세요"
            "(한글이 파일 구조를 정리해 해결되는 경우가 많습니다).",
    "문서": "바꿀 문서를 한글(워드 문서는 워드)에서 열어 다시 저장한 뒤 올려 보세요(한글이면 형식 'HWPX').",
    "변환": "같은 양식으로 다른 문서도 안 되는지 확인해 보세요 — 다른 문서는 되면 이 문서의 위 부분이, 다 안 되면 양식이 원인입니다.",
}
# 엔진 함수(또는 모듈) → (하던 일, 이렇게 해 보세요). 안쪽 호출부터 처음 걸리는 것을 쓴다.
TASKS = [
    (("build_cover", "build_simple_cover", "cover_roles"), "표지를 만들던 중",
     "설정 1-1 '제목을 만들어 드릴까요?'를 '아니오'로 바꿔 다시 변환해 보세요(표지 없이 만들어집니다)."),
    (("build_toc", "build_simple_toc", "fit_right_tabs", "toc_roles"), "차례를 만들던 중",
     "설정 2 '목록을 만들어 드릴까요?'를 '아니오'로 바꿔 다시 변환해 보세요(차례 없이 만들어집니다)."),
    (("make_hfs", "make_hf", "put_header_text", "set_header_slots", "template_header", "other_header",
      "put_section_ctrls", "ms_header_text"), "머리말·꼬리말을 넣던 중",
     "설정 4-2에서 다른 머리말 방식을 고르거나, 4-1을 '아니오'로 바꿔 다시 변환해 보세요."),
    (("page_numbering",), "쪽 번호를 넣던 중", "설정 3에서 '페이지 번호 필요없음'을 골라 다시 변환해 보세요."),
    (("secure_tables", "table_plan", "page_height", "table_height", "table_rows", "cell_height"), "큰 표를 쪽에 맞게 나누던 중",
     "설정 5에서 다른 나누기 방식을 골라 다시 변환해 보세요."),
    (("build_object", "restyle_table", "restyle_frame", "set_shell", "build_caption", "chapter_caption_pp", "caption_para",
      "caption_paras", "empty_frame", "bare_picture_frame", "build_lone_caption", "fit_table_width", "table_border_spec",
      "keep_original", "object_role", "object_fallback", "caption_ts"), "표·그림을 양식 모양으로 바꾸던 중",
     "원고에서 위 표·그림을 찾아 확인해 보세요 — 표 안의 표, 합쳐진 셀, 글상자가 있으면 잠시 빼고 시도해 볼 수 있습니다."),
    (("write_package", "build_hpf", "build_rdf", "check_refs", "tostr"), "결과 파일을 저장하던 중", None),
    (("cmd_verify", "check_text", "check_format", "check_package", "check_tables"), "결과를 자동 검사하던 중", None),
    (("docx_hwpx",), "워드 문서를 한글 문서로 옮기던 중",
     "워드에서 문서를 열어 다시 저장하거나, 한글에서 열어 HWPX로 저장한 파일을 올려 보세요."),
    (("template_profile",), "양식의 표지·차례·본문과 제목·표·그림 모양을 찾던 중",
     "양식이 한글에서 제대로 열리는지, 본문(제목·본문 글·표·그림 예시)이 들어 있는 보고서인지 확인해 보세요."),
    (("cmd_analyze", "classify", "caption_info", "table_info", "heading", "number_all", "walk", "merge_sections",
      "auto_judge", "auto_title", "big_tables"), "문서의 문단·표·그림을 살펴보던 중", None),
    (("build_body", "heading_example", "doc_title_para", "build_first_para", "build_chapter_para", "setup_chapter_outline",
      "new_body_section", "attach_carrier", "chapter_outline_textlabel", "drop_typed_number"), "본문 문단을 양식 모양으로 바꾸던 중",
     "원고에서 위 문단을 찾아 확인해 보세요 — 번호·기호를 직접 친 제목이면 그 줄의 번호를 지우고 시도해 볼 수 있습니다."),
]
STEP_FN = {"표지": "build_cover", "차례": "build_toc", "쪽 번호": "page_numbering", "저장": "write_package",
           "큰 표": "secure_tables", "본문": "build_body", "본문 마무리": "build_body"}  # format_transfer.step() 이름 → TASKS
ROLE_NAME = {"표 문단": "표", "그림 문단": "그림", "그림 문단(틀 없음)": "그림", "개체 문단(그대로)": "개체",
             "장 제목": "장 제목", "문서 제목": "문서 제목", "본문": "본문 문단", "빈 줄": "빈 줄"}
ENGINE = {"format_transfer", "template_profile", "service", "table_fit", "docx_hwpx"}


def where_text() -> str:
    """오류가 난 원고 자리(엔진이 step()으로 남긴 것) → 사람이 찾을 수 있는 말."""
    now = dict(ft.NOW)
    if now.get("작업") != "본문" or not now.get("문단"):
        return ""
    m = re.match(r"p(\d+)", now["문단"])
    role = now.get("역할", "")
    name = ROLE_NAME.get(role) or ("제목" if role.endswith("수준") else "캡션" if "캡션" in role else "문단")
    text = (now.get("글자") or "").strip()
    return f"원고 {int(m.group(1)) + 1}번째 문단({name})" + (f" — '{text}'" if text else "")


def reason_text(e: BaseException) -> str:
    s = f"{type(e).__name__}: {e}"
    if isinstance(e, MemoryError):
        return "파일이 커서 메모리가 모자랐습니다(그림이 아주 많거나 큰 문서)."
    if isinstance(e, (zipfile.BadZipFile, UnicodeDecodeError)) or type(e).__name__ == "XMLSyntaxError":
        return "파일 안의 내용 일부가 손상되었거나 한글이 쓰는 HWPX 형식과 다릅니다."
    if isinstance(e, KeyError) and "archive" in s:  # zipfile: 'There is no item named ... in the archive'
        return "HWPX 파일 안에 있어야 할 부분이 빠져 있습니다 — 파일이 손상되었거나 다른 프로그램이 만든 파일입니다."
    if isinstance(e, (AttributeError, TypeError)) and "NoneType" in s:
        return "있어야 할 부분(예: 표 제목, 셀, 서식 정보)을 찾지 못했습니다 — 이 파일이 프로그램이 예상한 구조와 조금 다릅니다."
    if isinstance(e, (KeyError, IndexError, StopIteration)):
        return "파일 안에서 가리키는 서식 정보(글자·문단 모양, 번호, 스타일 등) 하나를 찾지 못했습니다."
    if isinstance(e, SystemExit):
        return f"프로그램이 처리하지 못하는 구조를 만났습니다: {e}"
    return "이 파일 구조에서 프로그램이 처리하지 못한 부분이 있습니다."


def explain(stage: str, e: BaseException) -> dict:
    """예상하지 못한 오류 → 화면 안내(제목·어디서·이유·해 볼 것·기술 정보)."""
    frames = [f for f in traceback.extract_tb(e.__traceback__) if Path(f.filename).stem in ENGINE]
    task = tip = None
    for f in reversed(frames):
        for names, t, tp_ in TASKS:
            if f.name in names or Path(f.filename).stem in names:
                task, tip = t, tp_
                break
        if task:
            break
    if task is None:  # 호출 자리로 못 정하면 엔진이 남긴 '지금 하는 일'(step)로
        fn = STEP_FN.get(ft.NOW.get("작업"))
        task, tip = next(((t, tp_) for names, t, tp_ in TASKS if fn in names), (None, None))
    where = where_text() if stage == "변환" else ""
    damaged = isinstance(e, (zipfile.BadZipFile, UnicodeDecodeError)) or type(e).__name__ == "XMLSyntaxError" \
        or (isinstance(e, KeyError) and "archive" in str(e))
    tips = [x for x in ((None if damaged else tip), STAGE_TIP[stage]) if x]  # 파일 손상이면 다시 저장이 먼저
    tips.append("그래도 안 되면 아래 '오류 정보'를 복사해 알려 주세요 — 어디를 고쳐야 할지 바로 찾을 수 있습니다.")
    last = frames[-1] if frames else None
    detail = f"{type(e).__name__}: {e}" + (f"\n위치: {Path(last.filename).name} {last.lineno}행 {last.name}()" if last else "") \
        + (f"\n원고: {ft.NOW.get('문단')} {ft.NOW.get('역할', '')}" if ft.NOW.get("문단") else "") + f"\n단계: {stage}"
    return {"제목": f"{STAGE[stage]} 문제가 생겼습니다" + (f" — {task}" if task else ""), "어디서": where,
            "이유": reason_text(e), "해 볼 것": tips, "기술 정보": detail}


def friendly(stage: str):
    """서비스 함수에서 예상하지 못한 오류가 나면 UserError(친절한 안내)로 바꾼다 — 화면·명령줄이 같이 쓴다."""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **k):
            ft.step(stage)
            try:
                return fn(*a, **k)
            except UserError:
                raise
            except (Exception, SystemExit) as e:  # noqa: BLE001
                h = explain(stage, e)
                raise UserError(h["제목"] + (f" ({h['어디서']})" if h["어디서"] else ""), help=h) from e
        return wrap
    return deco


DEFAULTS = {
    "글자색": "양식", "원고 글자색": "살림", "연속빈줄": 1, "본문쪽번호시작": 1, "제목 다음 문단과 함께": True,
    "장마다 새 쪽": True, "장마다 쪽 번호 새로": False, "캡션 직접 번호 삭제": True, "캡션 앞뒤 공백 삭제": False,
    "캡션 안 본문": "꺼냄", "제목 직접 번호 삭제": True, "개체 없는 캡션": "빈 틀", "인라인 개체 살림": True,
    "줄 나눔": "글자",  # 모든 문단 모양 줄 나눔 기준 한글·영어 단위 '글자'(사용자 결정 2026-11-04)
}
SENTENCE_END = re.compile(r"(다|요|음|함|임|됨|것)\s*[.。]?\s*$")
TYPED_HEAD_NO_SPACE = re.compile(r"^\s*(\d{1,2})\.(?=\S)(?!\d)")  # '8.속초' 처럼 번호 뒤 빈칸이 없는 것


JOSA = {"양식": ("이", "은"), "문서": ("가", "는")}  # 받침 따라 조사(양식이·양식은 / 문서가·문서는)


def check_ext(path, what):
    ext = Path(path).suffix.lower()
    i_ga, eun_neun = JOSA.get(what, ("이(가)", "은(는)"))
    if ext == ".hwp":
        raise UserError(f"{what}{i_ga} .hwp 파일입니다. 한글에서 [파일] → [다른 이름으로 저장] → 파일 형식 'HWPX'로 저장한 뒤 올려 주세요.")
    if ext not in (".hwpx", ".docx") or (what == "양식" and ext != ".hwpx"):
        raise UserError(f"{what}{eun_neun} .hwpx" + (" 또는 .docx" if what == "문서" else "") + " 파일만 받을 수 있습니다.")
    if not zipfile.is_zipfile(path):
        raise UserError(f"{what} 파일을 열 수 없습니다(손상되었거나 암호가 걸린 파일).")


# ======================================================================= 1. 양식

@friendly("양식")
def analyze_template(src, work) -> dict:
    """양식 파일 하나(src) 또는 여러 개(목록 — 앞표지·목차·본문 스타일·표 그림 양식처럼 나뉜 회사 양식)를 분석한다."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    srcs = [Path(s) for s in src] if isinstance(src, (list, tuple)) else [Path(src)]
    if not srcs:
        raise UserError("양식 파일을 올려 주세요.")
    for s in srcs:
        check_ext(s, "양식")
    for old in work.glob("양식*.hwpx"):  # 지난번 양식 사본(파일 수가 달랐을 수 있다)
        if all(old.resolve() != s.resolve() for s in srcs):
            old.unlink()
    dsts = [work / "양식.hwpx"] if len(srcs) == 1 else [work / f"양식_{n + 1}.hwpx" for n in range(len(srcs))]
    for s, d in zip(srcs, dsts):
        if s.resolve() != d.resolve():
            shutil.copy(s, d)
    try:
        prof = tp.analyze(dsts[0] if len(dsts) == 1 else dsts, work / "양식프로필.json")
    except ValueError:
        raise UserError("양식에서 본문 쪽을 찾지 못했습니다. 표지나 차례만 있는 파일이 아니라 본문이 들어 있는 보고서를 "
                        + ("함께 " if len(srcs) > 1 else "") + "올려 주세요.")
    s = prof["요약"]
    if len(srcs) > 1:  # 요약의 파일 이름을 사용자가 올린 이름으로
        names = {d.name: x.name for d, x in zip(dsts, srcs)}
        f = s["파일"]
        s["파일"] = {k: ([names.get(n, n) for n in v] if isinstance(v, list) else names.get(v, v) if v else v) for k, v in f.items()}
        s["알림"] = [re.sub(r"양식_\d+\.hwpx", lambda m: names.get(m.group(0), m.group(0)), x) for x in s["알림"]]
    if not prof["양식역할"]["본문"].get("본문"):
        raise UserError("양식에서 본문 문단(긴 글)을 찾지 못했습니다. 본문이 들어 있는 보고서 파일을 올려 주세요.")
    return {"요약": s, "이름": srcs[0].name if len(srcs) == 1 else f"{srcs[0].name} 외 {len(srcs) - 1}개"}


# ======================================================================= 2. 원고

def merge_sections(src: Path, dst: Path) -> int:
    """여러 구역 원고 → 한 구역(둘째 구역부터는 첫 문단에 쪽 나누기, 구역 설정·쪽 단위 컨트롤은 뺀다). 구역 수를 돌려준다."""
    pk = ft.Pkg(src)
    if len(pk.sections) <= 1:
        if src.resolve() != dst.resolve():
            shutil.copy(src, dst)
        return len(pk.sections)
    root = copy.deepcopy(pk.sections[0])
    drop = ("secPr",)
    drop_ctrl = ("colPr", "pageNum", "header", "footer", "pageHiding", "newNum", "pageNumCtrl")
    for sec in pk.sections[1:]:
        for i, p in enumerate(sec.findall(q("hp:p"))):
            c = copy.deepcopy(p)
            if i == 0:
                for r in c.findall(q("hp:run")):
                    for x in list(r):
                        if local(x) in drop or (local(x) == "ctrl" and any(local(y) in drop_ctrl for y in x)):
                            r.remove(x)
                c.set("pageBreak", "1")
            root.append(c)
    names = [n for n in pk.z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)]
    with zipfile.ZipFile(dst, "w") as zo:
        for info in pk.z.infolist():
            if info.filename in names and info.filename != "Contents/section0.xml":
                continue
            data = ft.tostr(root) if info.filename == "Contents/section0.xml" else pk.z.read(info.filename)
            zo.writestr(info, data, compress_type=zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED)
    return len(pk.sections)


def write_config(work: Path, decisions=None) -> Path:
    st = json.loads((work / "상태.json").read_text(encoding="utf-8"))
    cfg = {"설명": "양식 맞춤 변환(service.py)", "양식프로필": "양식프로필.json", "원고": "원고.hwpx",
           "역할매핑": "역할매핑.json", "역할판단": "역할판단.json", "출력": f"out/{st['결과 이름']}",
           "버전정보": "본문양식", "결정": {**DEFAULTS, **(decisions or {})}}
    if st.get("원본"):
        cfg["원본"] = st["원본"]
    path = work / "설정.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def para_size(desc, p) -> float:
    return tp.pt(desc, ft.text_run_cid(p))


def auto_judge(rows, paras, desc, prof) -> tuple:
    """규칙으로 못 정한 문단([판단 필요])과 제목 단계를 사람 없이 정한다 → (역할판단 dict, 알림 목록)."""
    J, notes = {}, []
    roles_t = prof["양식역할"]
    has_chapter_style = bool(roles_t["표그림"].get("장 제목"))
    has_frame = bool(roles_t["표그림"].get("그림"))

    def text_of(key):
        return ft.own_text(ft.ms_para(paras, key))
    # 개요 1수준인데 '제N장'이 없는 문단(워드 '제목 1' 등) → 양식에 장 제목이 있으면 장 제목
    chap_n = 0
    for r in rows:
        if r["역할"] == "장 제목":
            chap_n += 1
        elif r["역할"] == "[판단 필요]" and "'제N장' 번호가 없음" in r.get("근거", ""):
            if has_chapter_style:
                chap_n += 1
                J[r["문단"]] = {"역할": "장 제목", "번호": f"제{chap_n}장", "근거": "자동: 개요 1수준 큰 제목 → 장 제목(장 번호 자동)"}
            else:
                J[r["문단"]] = {"역할": "1수준", "근거": "자동: 개요 1수준 큰 제목 → 양식에 장이 없어 1수준"}
    # 글자로 친 번호·기호 제목: 짧고 문장이 아닌 줄만 제목, 기호 종류가 처음 나온 순서로 단계.
    # 여러 단 번호('2-1)'·'1.1')는 윗단 모양('1)'·'1.')보다 한 단계 아래 — 2026-11-11 사용자: '2-1)'은 하위 제목이니
    # 양식 번호('1)')로 깔끔하게. 개요 번호 제목이 있는 원고에서는 여러 단 번호만, 윗제목 번호와 맞을 때 그 아래 단계로
    auto_levels = sorted({r["수준"] for r in rows if r["역할"].endswith("수준") and r.get("수준") is not None
                          and r["역할"] != "[판단 필요]"})
    cands, multi = [], {}
    for r in rows:
        if r["역할"] != "[판단 필요]" or "직접 친 기호/번호" not in r.get("근거", ""):
            continue
        t = text_of(r["문단"])
        tp_ = ft.typed_prefix(t.strip())
        name = tp_[0] if tp_ else None
        body = t.strip()[len(tp_[1]):] if tp_ else t.strip()
        short = bool(name) and len(body) <= 50 and not SENTENCE_END.search(body)
        if short and not auto_levels:
            cands.append((r, name, tp_[1]))
        elif short and ft.multi_parent_shape(name):
            multi[r["문단"]] = (name, tp_[1])
        else:
            J[r["문단"]] = {"역할": "본문", "근거": "자동: 번호·기호로 시작하는 문장 → 본문(기호 그대로)"}
    # 닫는 기호 없는 여러 단 번호('1.1'·'10-20')는 숫자 범위·소수·날짜일 수 있어, 윗단 모양 제목이 있으면 그 번호와 맞을 때만
    # ('1.' 3 아래 '3.2'), 윗단 모양이 없으면 두 번 넘게 나올 때만 제목
    seen = {name for _, name, _ in cands}
    count = {name: sum(1 for _, n, _ in cands if n == name) for name in seen}
    last, keep = {}, []
    for r, name, pre in cands:
        par = ft.multi_parent_shape(name)
        if par and name[-1] not in ".)":
            if not (last.get(par) == ft.multi_parts(pre)[-2] if par in seen else count[name] >= 2):
                J[r["문단"]] = {"역할": "본문", "근거": f"자동: '{pre.strip()}'은 윗제목 번호와 맞지 않는 숫자 → 본문(글자 그대로)"}
                continue
        last[name] = ft.typed_value(pre)
        keep.append((r, name, pre))
    cands, order, example = keep, [], {}
    for r, name, pre in cands:
        if name not in order:
            order.append(name)
            example[name] = pre.strip()
    moved = True  # 여러 단 번호가 윗단 모양보다 먼저 나왔어도('1-1)' 다음에 '2)') 윗단 바로 아래 단계로
    while moved:
        moved = False
        for name in list(order):
            par = ft.multi_parent_shape(name)
            if par in order and order.index(par) > order.index(name):
                order.remove(name)
                order.insert(order.index(par) + 1, name)
                moved = True
    for r, name, pre in cands:
        lv = order.index(name) + 1
        if lv <= 5:
            J[r["문단"]] = {"역할": f"{lv}수준", "근거": f"자동: 글자로 친 '{example[name]}' 꼴 제목 → {lv}수준"
                                                     + ("(윗단 번호 아래)" if ft.multi_parent_shape(name) in order else "(처음 나온 순서)")}
        else:
            J[r["문단"]] = {"역할": "본문", "근거": "자동: 제목 단계가 5단계를 넘어 본문"}
    if cands:
        tnum = {h.get("단계"): h.get("번호", "") for h in (prof.get("요약") or {}).get("제목 단계") or []}
        notes.append("글자로 친 제목 번호를 양식 제목 단계로: " + ", ".join(
            f"'{example[n]}' → " + (f"'{tnum[i + 1]}'" if tnum.get(i + 1) else f"{i + 1}단계") for i, n in enumerate(order[:5])))
    if multi:  # 개요 번호 제목 + 글자로 친 여러 단 번호('2.'(개요) 아래 '2-1)'): 윗제목 번호가 맞으면 그 다음 단계
        rank = {x: i + 1 for i, x in enumerate(auto_levels)}
        open_, shown, shape_lv = [], [], {}  # 열려 있는 제목들 (번호 값, 단계), 모양마다 처음 정한 단계
        for r in rows:
            if r["역할"] == "장 제목":
                open_ = [(ft.typed_value(r.get("번호")), 0)]
            elif r["역할"].endswith("수준") and r.get("수준") in rank and r["문단"] not in J:
                lv = rank[r["수준"]]
                open_ = [x for x in open_ if x[1] < lv] + [(ft.typed_value(r.get("번호")), lv)]
            elif r["문단"] in multi:
                name, pre = multi[r["문단"]]
                want = ft.multi_parts(pre)[-2]
                par = next((x for x in reversed(open_) if x[0] == want), None)
                lv, why = (par[1] + 1, f"윗제목 번호 {want} 아래") if par else (None, "")
                if lv is None and name[-1] in ".)" and (name in shape_lv or open_):  # 닫는 기호가 있으면 번호가 어긋나도 제목
                    lv, why = (shape_lv[name], "같은 꼴 제목과 같은 단계(윗번호는 다름)") if name in shape_lv else \
                        (open_[-1][1] + 1, "바로 앞 제목 아래(윗번호는 다름)")
                if lv is None or lv > 5:
                    J[r["문단"]] = {"역할": "본문", "근거": f"자동: 글자로 친 '{pre.strip()}'의 윗번호와 맞는 제목이 없음 → 본문(번호 그대로)"}
                    continue
                shape_lv.setdefault(name, lv)
                J[r["문단"]] = {"역할": f"{lv}수준", "근거": f"자동: 글자로 친 '{pre.strip()}' → {why} {lv}수준"}
                open_ = [x for x in open_ if x[1] < lv] + [(ft.multi_parts(pre)[-1], lv)]
                if pre.strip() not in shown:
                    shown.append(pre.strip())
        if shown:
            notes.append("개요 번호 제목 아래 글자로 친 여러 단 번호를 하위 제목으로: " + ", ".join(f"'{s}'" for s in shown[:5]))
    # 번호 뒤 빈칸 없는 '8.속초' 같은 줄: 같은 기호 종류 제목이 있으면 그 단계
    if "1." in order:
        lv = order.index("1.") + 1
        for r in rows:
            if r["역할"] == "본문" and r["문단"] not in J:
                t = text_of(r["문단"])
                if TYPED_HEAD_NO_SPACE.match(t) and len(t.strip()) <= 40 and not SENTENCE_END.search(t):
                    J[r["문단"]] = {"역할": f"{lv}수준", "지울번호": TYPED_HEAD_NO_SPACE.match(t).group(0),
                                   "근거": "자동: 번호 뒤 빈칸 없는 '1.' 제목"}
    # 나머지 판단 필요
    for r in rows:
        if r["역할"] != "[판단 필요]" or r["문단"] in J:
            continue
        why = r.get("근거", "")
        if why.startswith("표 밖 개체"):
            names = r.get("개체") or []
            if text_of(r["문단"]).strip():
                J[r["문단"]] = {"역할": "본문", "근거": "자동: 글과 개체가 같이 있는 문단 → 본문(개체는 문단 안에 그대로)"}
            elif names and all(n in ("pic", "container") for n in names) and has_frame:
                J[r["문단"]] = {"역할": "그림 문단(틀 없음)", "근거": "자동: 틀 없는 그림 → 양식 그림 틀(캡션 없음)"}
            else:
                J[r["문단"]] = {"역할": "개체 문단(그대로)", "근거": "자동: 표 밖 개체 → 원고 모양 그대로"}
        elif why.startswith("글머리표"):
            ch = why.replace("글머리표", "").strip()
            J[r["문단"]] = {"역할": "본문", "근거": "자동: 글머리표 문단 → 본문(기호는 글자로)",
                           **({"앞기호": ch + " "} if ch and ch != "?" else {})}
        else:
            J[r["문단"]] = {"역할": "본문", "근거": f"자동: 정하지 못한 문단 → 본문({why[:30]})"}
    # 제목 단계 정규화: 원고 개요 수준(0부터) → 1..n 단계
    lv = sorted({r["수준"] for r in rows if r["역할"].endswith("수준") and r.get("수준") is not None
                 and r["역할"] not in ("[판단 필요]",) and r["문단"] not in J})
    rank = {x: i + 1 for i, x in enumerate(lv)}
    for r in rows:
        if r["문단"] in J or not r["역할"].endswith("수준") or r.get("수준") is None:
            continue
        n = rank[r["수준"]]
        if f"{n}수준" != r["역할"]:
            J[r["문단"]] = {"역할": f"{n}수준" if n <= 5 else "본문", "근거": f"자동: 원고 제목 단계 {r['역할']} → {n}수준"}
    # 문서 제목: 첫 글이 제목처럼 보이면(짧고, 문장이 아니고, 크거나 가운데·굵게)
    first = next((r for r in rows if r["역할"] != "빈 줄"), None)
    if first is not None and (J.get(first["문단"], {}).get("역할", first["역할"]) == "본문"):
        p = ft.ms_para(paras, first["문단"])
        t = ft.own_text(p).strip()
        sizes = sorted(para_size(desc, ft.ms_para(paras, r["문단"])) for r in rows if r["역할"] == "본문"
                       and ft.own_text(ft.ms_para(paras, r["문단"])).strip())
        body_pt = sizes[len(sizes) // 2] if sizes else 10.0
        pp = desc.para_prs.get(p.get("paraPrIDRef"))
        al = pp.find(q("hh:align")).get("horizontal") if pp is not None and pp.find(q("hh:align")) is not None else ""
        bold = desc.char_prs[ft.text_run_cid(p)].find(q("hh:bold")) is not None
        if t and len(t) <= 60 and not SENTENCE_END.search(t) and (para_size(desc, p) >= body_pt * 1.2 or al == "CENTER" or bold):
            J[first["문단"]] = {"역할": "문서 제목", "근거": "자동: 맨 앞 짧은 큰 글 → 문서 제목(양식 큰 제목 모양)"}
    return J, notes


def auto_title(rows, paras, stem: str) -> str:
    def text(r):
        t = ft.own_text(ft.ms_para(paras, r["문단"])).strip()
        pre = r.get("지울번호")
        if pre and t.startswith(pre.strip()):
            t = t[len(pre.strip()):].strip()
        return re.sub(r"^\s*제\s*\d+\s*장\s*", "", t).strip()
    for role in ("문서 제목", "장 제목", "1수준"):
        r = next((x for x in rows if x["역할"] == role and text(x)), None)
        if r is not None:
            return text(r)[:60]
    s = re.sub(r"[_]+", " ", stem)
    s = re.sub(r"\((초안|최종|수정|v?\d+(\.\d+)*)\)|\b(초안|최종본?|수정본?)\b", "", s)
    return re.sub(r"\s{2,}", " ", s).strip() or "보고서"


@friendly("문서")
def inspect_document(src, work) -> dict:
    work = Path(work)
    check_ext(src, "문서")
    if not (work / "양식프로필.json").exists():
        raise UserError("먼저 양식을 올려 주세요.")
    for old in ("원고.hwpx", "역할매핑.json", "역할판단.json", "역할매핑_분석.md"):
        if (work / old).exists():
            (work / old).unlink()
    src = Path(src)
    stem = src.stem
    st = {"원고 이름": src.name, "결과 이름": f"{stem}_양식적용.hwpx"}
    notes = []
    if src.suffix.lower() == ".docx":
        dcopy = work / ("원본" + src.suffix)
        shutil.copy(src, dcopy)
        st["원본"] = dcopy.name
        (work / "상태.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        R = ft.Run(write_config(work))
        ft.cmd_convert(R)
        notes.append("워드 문서를 한글 문서로 옮긴 뒤 변환합니다(옮긴 내용은 변환기록에).")
    else:
        n = merge_sections(src, work / "원고.hwpx")
        if n > 1:
            notes.append(f"구역 {n}개를 하나로 이어 붙여 분석했습니다(구역이 바뀌던 곳은 새 쪽).")
        (work / "상태.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    R = ft.Run(write_config(work))
    prof = json.loads((work / "양식프로필.json").read_text(encoding="utf-8"))
    pk = ft.Pkg(R.ms_path)
    desc = ft.Desc(pk.header)
    judge = {}
    for _ in range(3):  # 자동 판단 → 다시 분석(캡션 붙이기 등이 새 역할을 보고 다시 정해진다)
        (work / "역할판단.json").write_text(json.dumps(judge, ensure_ascii=False, indent=1), encoding="utf-8")
        R = ft.Run(write_config(work))
        ft.cmd_analyze(R)
        rows = json.loads(R.map_path.read_text(encoding="utf-8"))
        add, n2 = auto_judge(rows, pk.paras(), desc, prof)
        new = {k: v for k, v in add.items() if k not in judge}
        if not new:
            break
        judge.update(new)
        notes += [x for x in n2 if x not in notes]
    rows = json.loads(R.map_path.read_text(encoding="utf-8"))
    left = [r["문단"] for r in rows if r["역할"] == "[판단 필요]"]
    if left:
        for k in left:
            judge[k] = {"역할": "본문", "근거": "자동: 끝까지 정하지 못한 문단 → 본문"}
        (work / "역할판단.json").write_text(json.dumps(judge, ensure_ascii=False, indent=1), encoding="utf-8")
        ft.cmd_analyze(R)
        rows = json.loads(R.map_path.read_text(encoding="utf-8"))
    title = auto_title(rows, pk.paras(), stem)
    st["자동 제목"] = title
    (work / "상태.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    cnt = {}
    for r in rows:
        k = r["역할"]
        k = "제목" if k.endswith("수준") else k
        cnt[k] = cnt.get(k, 0) + 1
    big = big_tables(R, cnt.get("표 문단", 0) + sum(1 for t in pk.sections[0].iter(q("hp:tbl"))) > 0)
    return {"원고": src.name, "자동 제목": title, "자동 머리말": title,
            "구성": {"장": cnt.get("장 제목", 0), "제목": cnt.get("제목", 0), "본문": cnt.get("본문", 0),
                   "표": cnt.get("표 문단", 0), "그림": cnt.get("그림 문단", 0) + cnt.get("그림 문단(틀 없음)", 0)},
            "큰 표": big, "자동 판단": len(judge), "알림": notes}


def big_tables(R, has_table: bool) -> dict:
    """설문 5(표 나누기)를 물을지: 양식 모양을 입힌 결과에서 한 쪽을 넘는 표(쪽에서 차지할 높이 어림 > 본문 높이의 99 %).
    미리 어림하다 실패하면 표가 하나라도 있을 때 묻는다(쪽을 넘는 표는 절대 안 됨 — 사용자 2026-11-03)."""
    try:
        plan = [x for x in ft.table_plan(R) if x["종류"] == "표"]  # 그림 틀(사진 묶음)은 늘 행 단위로 나눠 묻지 않는다
        return {"수": len(plan), "표": [x["표"] for x in plan][:5], "어림": True}
    except (Exception, SystemExit) as e:  # noqa: BLE001 — 미리 보기 실패가 문서 올리기를 막지 않게
        return {"수": 1 if has_table else 0, "표": [], "어림": False, "오류": str(e)[:200]}


# ======================================================================= 3. 변환

def decisions_from(options: dict, st: dict, prof: dict) -> dict:
    """설문 답 → 엔진 결정."""
    D = {}
    title = (options.get("표지", {}).get("제목") or "").strip() or st.get("자동 제목", "")
    cover = options.get("표지", {}).get("만들기", True)
    has_cover, has_toc = bool(prof["부분"].get("표지")), bool(prof["부분"].get("차례"))
    D["표지 만들기"] = (True if has_cover else "간단") if cover else False
    D["표지"] = {"제목": title, "부제": "비움"}
    D["문서 제목"] = title
    toc = options.get("차례", {}).get("만들기", True)
    D["차례 만들기"] = (True if has_toc else "간단") if toc else False
    pn = options.get("쪽번호", {})
    how = pn.get("방식", "본문부터")
    if how == "지정":
        D["쪽 번호"], D["본문쪽번호시작"] = "본문부터", max(1, int(pn.get("시작") or 1))
    else:
        D["쪽 번호"] = {"제목부터": "제목부터", "없음": "없음"}.get(how, "본문부터")
    hd = options.get("머리말", {})
    if not hd.get("만들기", True):
        D["머리말 만들기"] = False
    elif hd.get("방식") == "양식":  # 4-2 '양식에 있는 머리말 그대로' — 장 제목 칸만 원고 장 제목으로(장이 없으면 양식 글자 그대로)
        D["머리말글자"] = "양식"
    else:  # 직접 작성 / 본문 분석 자동(글자를 비우면 자동 제목)
        D["머리말글자"] = "지정"
        D["머리말 내용"] = (hd.get("글자") or "").strip() or title
    split = options.get("표", {}).get("나누기")  # 설문 5: 한쪽보다 긴 표 — "나눔"(쪽 경계에서 나눔) / "셀 단위로 나눔"
    if split in ft.tf.PAGE_BREAK:
        D["표 나누기"] = split
    return D


@friendly("변환")
def convert(work, options: dict) -> dict:
    work = Path(work)
    st = json.loads((work / "상태.json").read_text(encoding="utf-8"))
    prof = json.loads((work / "양식프로필.json").read_text(encoding="utf-8"))
    D = decisions_from(options, st, prof)
    R = ft.Run(write_config(work, D))
    out_dir = R.out.parent
    if out_dir.exists():
        for f in out_dir.iterdir():
            if f.is_file():
                f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    ft.cmd_apply(R)
    try:
        fails = ft.cmd_verify(R)
        check_note = []
    except Exception as e:  # noqa: BLE001 — 검사가 멈춰도 만든 결과 파일은 준다
        fails = None
        check_note = [f"자동 검사를 끝내지 못했습니다({type(e).__name__}) — 결과 파일은 만들었으니 한글에서 열어 확인해 주세요."]
    log = R.f("적용로그.md").read_text(encoding="utf-8")
    warns = check_note + [re.sub(r"^⚠\s*(p\d+(>\S+)?\s+)?", "", x[2:].strip()) for x in log.splitlines() if x.startswith("- ⚠")]
    seen = {}  # 같은 알림이 여러 문단에서 나오면 한 줄로('… (4곳)') — 이어지는 표('(계속)')마다 같은 번호 알림이 되풀이됨
    for w in warns:
        seen[w] = seen.get(w, 0) + 1
    warns = [w + (f" ({n}곳)" if n > 1 else "") for w, n in seen.items()]
    made = json.loads(R.f("결과구성.json").read_text(encoding="utf-8"))
    ap = json.loads(R.f("승인변경.json").read_text(encoding="utf-8"))
    split = json.loads(R.f("표나눔.json").read_text(encoding="utf-8"))
    return {"파일": str(R.out), "이름": R.out.name, "검증 실패": fails, "구성": made, "알림": warns[:20],
            "바뀐 글자": len(ap), "표 나눔": split, "설정": D}


def run_all(template, document, work, options) -> dict:
    """명령줄·시험용: 1~3을 한 번에."""
    analyze_template(template, work)
    inspect_document(document, work)
    return convert(work, options)


USAGE = """사용:
  python3 service.py inspect <양식.hwpx> <원고.hwpx|.docx> <작업 폴더>   # 1·2단계: 양식 분석 + 원고 살펴보기(설문 전)
    양식이 여러 파일(앞표지·목차·본문 스타일·표 그림 양식 등)이면 <양식.hwpx> 자리에 '|'로 이어 적는다: "앞표지.hwpx|목차.hwpx|본문.hwpx"
  python3 service.py convert <작업 폴더> '<설문 답 JSON>'               # 3단계: 결과 .hwpx + 검증
  python3 service.py <양식> <원고> <작업 폴더> ['<설문 답 JSON>']        # 한 번에
설문 답 JSON: {"표지":{"만들기":true,"제목":""},"차례":{"만들기":true},"쪽번호":{"방식":"본문부터","시작":1},
              "머리말":{"만들기":true,"글자":"","방식":"자동"},"표":{"나누기":"나눔"}}
  쪽번호 방식: 제목부터 / 본문부터 / 없음 / 지정(시작 = 본문 첫 쪽 번호). 제목·글자를 비우면 자동(원고에서 뽑은 제목).
  머리말 방식: 직접(글자) / 자동(원고에서 뽑은 제목) / 양식(양식 머리말 그대로 — 장 제목 칸만 원고 장 제목, 장이 없으면 양식 글자).
  표 나누기: 한 쪽을 넘는 표가 있을 때(inspect의 '큰 표' 수 > 0)만 — "나눔"(쪽 경계에서 나눔) / "셀 단위로 나눔"."""


def cli(a) -> int:
    """결과 JSON만 표준 출력으로(엔진 진행 글은 표준 오류로) — 읽어서 바로 쓸 수 있게."""
    import contextlib
    try:
        with contextlib.redirect_stdout(sys.stderr):
            if a and a[0] == "inspect" and len(a) == 4:
                tm = a[1].split("|") if "|" in a[1] else a[1]
                out = {"양식": analyze_template(tm, a[3]), "원고": inspect_document(a[2], a[3])}
            elif a and a[0] == "convert" and len(a) in (2, 3):
                out = convert(a[1], json.loads(a[2]) if len(a) > 2 else {})
            elif len(a) in (3, 4) and a[0] not in ("inspect", "convert"):
                out = run_all(a[0].split("|") if "|" in a[0] else a[0], a[1], a[2], json.loads(a[3]) if len(a) > 3 else {})
            else:
                out = None
    except UserError as e:
        print(json.dumps({"사용자에게 알릴 것": str(e), **({"도움말": e.help} if e.help else {})}, ensure_ascii=False, indent=1))
        return 1
    if out is None:
        print(USAGE)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
