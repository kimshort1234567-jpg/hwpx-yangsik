"""웹 페이지용 엔진 묶음 만들기: engine/*.py → web/engine_bundle.js (window.ENGINE_FILES = {파일 이름: 소스}).

사용: python tools/build_web.py
엔진 파이썬 파일을 JS 문자열로 넣어 두면 웹 페이지가 파일 하나씩 내려받지 않아도 되고,
index.html을 내 컴퓨터에서 바로(file://) 열어도 동작한다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["format_transfer.py", "table_fit.py", "docx_hwpx.py", "template_profile.py", "service.py"]


def main():
    files = {f: (ROOT / "engine" / f).read_text(encoding="utf-8") for f in FILES}
    js = ("// 자동 생성 파일 — 고치지 마세요(python tools/build_web.py로 다시 만듦).\n"
          "window.ENGINE_FILES = " + json.dumps(files, ensure_ascii=False) + ";\n")
    out = ROOT / "web" / "engine_bundle.js"
    out.write_text(js, encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: 파일 {len(files)}개, {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
