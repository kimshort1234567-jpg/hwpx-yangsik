"""여러 파일 양식 시험(실제 브라우저 — Edge, Playwright).

사용: python -X utf8 tests/e2e_multi.py <앞표지> <목차> <본문 스타일> <표그림 양식> <문서> <결과 폴더> [--file]
  1 양식 파일 4개를 한꺼번에 → 카드에 파일마다 맡은 부분(표지·차례·본문·표·그림), 표지·차례 ✓
  2 [+ 양식 저장] → 저장소에 '… 외 3개', '파일 4개' → 새로 고침 → 눌러서 문서 변환·다운로드까지
  3 같은 4개를 다른 순서로 올리면 바로 '저장됨'(묶음은 순서와 상관없이 같은 양식)
  4 본문 파일 하나만 올린 뒤 [+ 파일 더하기]로 앞표지 → 파일 2개, 표지 ✓, 새 양식이라 저장 단추 켜짐
"""
import sys
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_web import DEFAULT, WEB, serve  # noqa: E402


def pick(page, opener, paths):
    page.click(opener)
    page.wait_for_selector("#import-modal:not([hidden])")
    with page.expect_file_chooser() as fc:
        page.click("#from-device")
    fc.value.set_files([str(p) for p in paths])


def wait_card(page):
    page.wait_for_selector("#template-card:not([hidden]), #template-error:not([hidden])", timeout=300000)
    if page.is_visible("#template-error"):
        raise SystemExit("양식 오류: " + page.inner_text("#template-error"))


def main(argv):
    cover, toc, body, tg, doc, out = (Path(x) for x in argv[:6])
    out.mkdir(parents=True, exist_ok=True)
    srv, url = (None, (WEB / "index.html").as_uri()) if "--file" in argv else serve()
    logs, fails = [], []

    def check(cond, msg):
        print(("✅ " if cond else "❌ ") + msg)
        if not cond:
            fails.append(msg)

    def has_part(page, name):
        """양식 진단표에서 그 항목이 '있음'(✓)인가."""
        return page.evaluate("""(n) => [...document.querySelectorAll('#template-card .diag > li')]
            .some(li => li.querySelector('.d-name').innerText.trim() === n && li.classList.contains('ok'))""", name)

    def card_files(page):
        return page.eval_on_selector_all(".tfiles li", "els => els.map(e => e.innerText.replace(/\\s+/g, ' ').trim())")

    with sync_playwright() as p:
        br = p.chromium.launch(channel="msedge", headless=True)
        ctx = br.new_context(viewport={"width": 1600, "height": 950}, accept_downloads=True)
        page = ctx.new_page()
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
        page.goto(url)
        page.wait_for_selector("#engine.ready", timeout=180000)

        # 1. 4개 한꺼번에
        pick(page, '[data-import="template"]', [cover, toc, body, tg])
        wait_card(page)
        F = card_files(page)
        print("   파일:", F)
        role = {f.split(" ")[0]: f for f in F}
        ok = (len(F) == 4 and "표지" in next(f for f in F if cover.name in f) and "차례" in next(f for f in F if toc.name in f)
              and "본문" in next(f for f in F if body.name in f) and "표·그림" in next(f for f in F if tg.name in f))
        check(ok and has_part(page, "표지") and has_part(page, "차례"), "4개 한꺼번에: 파일마다 맡은 부분 표시, 표지·차례 ✓")
        page.screenshot(path=str(out / "01_여러파일.png"), full_page=True)

        # 2. 저장 → 새로 고침 → 골라서 변환
        page.click("#save-template")
        page.wait_for_function("document.querySelectorAll('#vault-list .vi').length === 1")
        item = page.inner_text("#vault-list .vi").replace("\n", " ")
        check(f"{body.stem} 외 3개" in item and "파일 4개" in item.replace("\xa0", " "), f"저장: '{item}'")
        page.reload()
        page.wait_for_selector("#engine.ready", timeout=180000)
        page.wait_for_function("document.querySelectorAll('#vault-list .vi').length === 1")
        page.click("#vault-list .vi .vi-main")
        wait_card(page)
        check(len(card_files(page)) == 4 and "저장됨" in page.inner_text("#save-template"), "새로 고침 뒤 저장소에서 고름: 파일 4개 그대로")
        pick(page, '[data-import="document"]', [doc])
        page.wait_for_selector("#survey-modal:not([hidden]), #document-error:not([hidden])", timeout=300000)
        if page.is_visible("#document-error"):
            raise SystemExit("문서 오류: " + page.inner_text("#document-error"))
        for name, v in DEFAULT.items():
            if name == "split" and page.is_hidden("#q-split"):
                continue
            page.check(f'input[name="{name}"][value="{v}"]')
        with page.expect_download(timeout=600000) as dl:
            page.click("#convert-btn")
        saved = out / dl.value.suggested_filename
        dl.value.save_as(str(saved))
        page.wait_for_selector("#done-card:not([hidden])")
        done = page.inner_text("#done-card")
        z = zipfile.ZipFile(saved)
        check("모두 통과" in done and "표지 + 차례 + 본문" in done and z.testzip() is None and z.infolist()[0].filename == "mimetype",
              f"여러 파일 양식으로 변환: {saved.name} ({saved.stat().st_size:,} bytes), 표지+차례+본문, 자동 검사 통과")
        page.screenshot(path=str(out / "02_완성.png"), full_page=True)

        # 3. 다른 순서로 다시
        page.click("#tmpl-change")
        pick(page, '[data-import="template"]', [tg, body, toc, cover])
        wait_card(page)
        check("저장됨" in page.inner_text("#save-template"), "같은 4개를 다른 순서로: 바로 '저장됨'")

        # 4. 하나 올린 뒤 파일 더하기
        page.click("#tmpl-change")
        pick(page, '[data-import="template"]', [body])
        wait_card(page)
        check(not page.is_visible(".tfiles") and not has_part(page, "표지"), "본문 파일 하나: 표지 없음")
        pick(page, "#tmpl-add", [cover])
        page.wait_for_function("document.querySelectorAll('.tfiles li').length === 2 || "
                               "!document.getElementById('template-error').hidden", timeout=300000)
        wait_card(page)
        F = card_files(page)
        check(len(F) == 2 and has_part(page, "표지")
              and "+ 양식 저장" in page.inner_text("#save-template") and page.is_enabled("#save-template"),
              f"[+ 파일 더하기]로 앞표지: 파일 2개 {F}, 표지 ✓, 새 묶음이라 저장 가능")
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(out / "03_휴대폰.png"), full_page=True)
        over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check(over <= 0, f"휴대폰 390px: 가로 넘침 없음({over})")
        ctx.close()
        br.close()
    if srv:
        srv.shutdown()
    errs = [x for x in logs if x.startswith(("[error]", "[pageerror]"))]
    if errs:
        print("브라우저 오류:", *errs[:10], sep="\n  ")
    print(f"결과: ❌ {len(fails)}개" + (f" — {fails}" if fails else ""))
    return 1 if fails or errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
