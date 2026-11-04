"""양식 자동 분석 시험: 양식 파일 하나 + 원고 설정(work/설정/*.json의 원고·역할매핑·역할판단·결정) → 결과 HWPX + 검증.

사용: python -I -X utf8 tests/try_template.py <양식.hwpx> <원고 설정.json> <작업 폴더> [--pdf] [--결정 '{"키": 값}']
  - 양식은 template_profile.analyze로 프로필을 만들고, 원고는 설정에 적힌 원고·역할매핑을 그대로 쓴다.
  - --pdf: 한글로 PDF까지(이 PC처럼 한글이 있을 때) — 엔진의 run과 같은 순서.
"""
import json
import shutil
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))
import format_transfer as ft  # noqa: E402
import template_profile as tp  # noqa: E402


def main(argv):
    tmpl, cfg_src, work = Path(argv[0]).resolve(), Path(argv[1]).resolve(), Path(argv[2]).resolve()
    extra = json.loads(argv[argv.index("--결정") + 1]) if "--결정" in argv else {}
    work.mkdir(parents=True, exist_ok=True)
    tcopy = work / ("양식" + tmpl.suffix)
    shutil.copy(tmpl, tcopy)
    prof = tp.analyze(tcopy, work / "양식프로필.json")
    src = json.loads(cfg_src.read_text(encoding="utf-8"))
    here = cfg_src.parent
    cfg = {"설명": f"시험: 양식 {tmpl.name} + 원고 {cfg_src.stem}", "양식프로필": "양식프로필.json",
           "원고": str((here / src["원고"]).resolve()), "역할매핑": str((here / src["역할매핑"]).resolve()),
           "출력": str(work / "out" / "결과.hwpx"), "버전정보": "본문양식", "결정": {**src.get("결정", {}), **extra}}
    if src.get("역할판단"):
        cfg["역할판단"] = str((here / src["역할판단"]).resolve())
    (work / "out").mkdir(exist_ok=True)
    for pat in ("차례쪽번호.json", "*.pdf", "미리보기.png"):  # 지난 시험의 PDF·차례 쪽 번호가 섞이지 않게
        for f in (work / "out").glob(pat):
            f.unlink()
    cpath = work / "설정.json"
    cpath.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    R = ft.Run(cpath)
    print("양식 부분:", {k: (v["범위"] if v else None) for k, v in prof["부분"].items()})
    if "--pdf" in argv:
        ft.cmd_apply(R)
        ft.cmd_pdf(R)
        ft.make_preview(R)
        ft.cmd_toc(R)
        ft.cmd_apply(R)
        ft.cmd_pdf(R)
    else:
        ft.cmd_apply(R)
    fails = ft.cmd_verify(R)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
