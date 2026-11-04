"""웹 화면 끝까지 시험(실제 브라우저 — Edge, Playwright): 양식 올리기 → 문서 올리기 → 설문 → 다운로드.

사용: python -X utf8 tests/e2e_web.py <양식.hwpx> <문서> <결과 폴더> [--file] [--설문 '{"title":"yes",...}']
  --file: 로컬 서버 없이 index.html을 file://로 연다(내려받아 바로 여는 경우).
  화면 그림(01_처음.png …)과 내려받은 파일을 결과 폴더에 남긴다.
"""
import functools
import http.server
import json
import sys
import threading
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DEFAULT = {"title": "yes", "titleMode": "auto", "toc": "yes", "pn": "본문부터", "header": "yes", "headerMode": "auto",
           "split": "셀 단위로 나눔"}


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/index.html"


def pick(page, kind, path):
    page.click(f'[data-import="{kind}"]')
    page.wait_for_selector("#import-modal:not([hidden])")
    with page.expect_file_chooser() as fc:
        page.click("#from-device")
    fc.value.set_files(str(path))


def main(argv):
    tmpl, doc, out = Path(argv[0]), Path(argv[1]), Path(argv[2])
    ans = {**DEFAULT, **(json.loads(argv[argv.index("--설문") + 1]) if "--설문" in argv else {})}
    out.mkdir(parents=True, exist_ok=True)
    srv, url = (None, (WEB / "index.html").as_uri()) if "--file" in argv else serve()
    logs = []
    with sync_playwright() as p:
        br = p.chromium.launch(channel="msedge", headless=True)
        page = br.new_page(viewport={"width": 1100, "height": 900}, accept_downloads=True)
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
        page.goto(url)
        page.screenshot(path=str(out / "01_처음.png"), full_page=True)
        page.wait_for_selector("#engine.ready", timeout=180000)
        print("엔진 준비:", page.inner_text("#engineText"))
        pick(page, "template", tmpl)
        page.wait_for_selector("#template-card:not([hidden]), #template-error:not([hidden])", timeout=300000)
        if page.is_visible("#template-error"):
            print("양식 오류:", page.inner_text("#template-error"))
            return 1
        page.screenshot(path=str(out / "02_양식.png"), full_page=True)
        pick(page, "document", doc)
        page.wait_for_selector("#survey-modal:not([hidden]), #document-error:not([hidden])", timeout=300000)
        if page.is_visible("#document-error"):
            print("문서 오류:", page.inner_text("#document-error"))
            return 1
        page.screenshot(path=str(out / "03_설문.png"))
        for name, v in ans.items():
            if name in ("titleText", "headerText", "pnStart"):
                continue
            if (name == "titleMode" and ans.get("title") != "yes") or (name == "headerMode" and ans.get("header") != "yes"):
                continue  # 위 질문이 '아니오'면 하위 질문은 숨겨진다
            if name == "split" and page.is_hidden("#q-split"):
                print("설문 5(큰 표 나누기): 안 보임 — 쪽 높이에 가까운 표 없음")
                continue
            if name == "split":
                print("설문 5(큰 표 나누기):", page.inner_text("#q-split legend"), "→", v)
            page.check(f'input[name="{name}"][value="{v}"]')
        if ans.get("titleText"):
            page.fill("#title-text", ans["titleText"])
        if ans.get("headerText"):
            page.fill("#header-text", ans["headerText"])
        if ans.get("pnStart"):
            page.fill("#pn-start", str(ans["pnStart"]))
        page.screenshot(path=str(out / "04_설문_답.png"))
        with page.expect_download(timeout=600000) as dl:
            page.click("#convert-btn")
        d = dl.value
        saved = out / d.suggested_filename
        d.save_as(str(saved))
        page.wait_for_selector("#done-card:not([hidden])")
        page.screenshot(path=str(out / "05_완성.png"), full_page=True)
        print("완성 화면:", page.inner_text("#done-card").replace("\n", " | ")[:400])
        br.close()
    if srv:
        srv.shutdown()
    z = zipfile.ZipFile(saved)
    first = z.infolist()[0]
    print(f"내려받은 파일: {saved.name} ({saved.stat().st_size:,} bytes), 첫 항목 {first.filename} "
          f"{'비압축' if first.compress_type == 0 else '압축'}, CRC {'정상' if z.testzip() is None else '오류'}, "
          f"구역 {len([n for n in z.namelist() if n.startswith('Contents/section')])}개")
    errs = [x for x in logs if x.startswith(("[error]", "[pageerror]"))]
    if errs:
        print("브라우저 오류:", *errs[:10], sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
