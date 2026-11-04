"""양식 저장소 시험(실제 브라우저 — Edge, Playwright).

사용: python -X utf8 tests/e2e_vault.py <양식A.hwpx> <양식B.hwpx> <문서> <결과 폴더> [--file]
  1 빈 저장소 → 양식 A를 올리고 [+ 양식 저장] → 목록 1개, 단추 '저장됨'
  2 새로 고침 → 목록 그대로 → 1번을 눌러 양식으로 → 문서를 올려 변환·다운로드(저장소의 양식으로 끝까지)
  3 양식 B 저장 → 목록 2개(번호 1·2) / 양식 A 파일을 다시 올리면 바로 '저장됨'(같은 내용을 알아봄)
  4 이름 바꾸기(Enter 저장·Esc 취소) / 지우기(확인) → 새로 고침 뒤에도 그대로
  5 다른 창에서 저장·지우면 이 창 목록도 바뀜
  화면 그림: 넓은 화면(1893×912)·노트북(1280×800)·휴대폰(390×844)·어두운 화면 → 결과 폴더
"""
import sys
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_web import DEFAULT, WEB, pick, serve  # noqa: E402

N = "document.querySelectorAll('#vault-list .vi').length"


def items(page):
    return page.eval_on_selector_all("#vault-list .vi", "els => els.map(e => e.innerText.replace(/\\s+/g, ' ').trim())")


def wait_count(page, n):
    page.wait_for_function(f"{N} === {n}", timeout=30000)


def load_template(page, path, change=False):
    if change:
        page.click("#tmpl-change")
    pick(page, "template", path)
    page.wait_for_selector("#template-card:not([hidden]), #template-error:not([hidden])", timeout=300000)
    if page.is_visible("#template-error"):
        raise SystemExit("양식 오류: " + page.inner_text("#template-error"))


def answer_survey(page):
    for name, v in DEFAULT.items():
        if name == "split" and page.is_hidden("#q-split"):
            continue
        page.check(f'input[name="{name}"][value="{v}"]')


def main(argv):
    ta, tb, doc, out = (Path(x) for x in argv[:4])
    out.mkdir(parents=True, exist_ok=True)
    srv, url = (None, (WEB / "index.html").as_uri()) if "--file" in argv else serve()
    logs, fails = [], []

    def check(cond, msg):
        print(("✅ " if cond else "❌ ") + msg)
        if not cond:
            fails.append(msg)

    with sync_playwright() as p:
        br = p.chromium.launch(channel="msedge", headless=True)
        ctx = br.new_context(viewport={"width": 1893, "height": 912}, accept_downloads=True)
        page = ctx.new_page()
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
        page.goto(url)
        page.wait_for_selector("#engine.ready", timeout=180000)
        page.screenshot(path=str(out / "01_빈저장소.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(out / "01_빈저장소_휴대폰.png"))
        page.set_viewport_size({"width": 1893, "height": 912})
        check(page.is_visible("#vault-empty") and page.is_disabled("#save-template"),
              "처음: 빈 저장소 안내가 보이고 [+ 양식 저장]은 꺼져 있음")

        # 1. 양식 A를 올려 저장
        load_template(page, ta)
        check(page.is_enabled("#save-template") and "+ 양식 저장" in page.inner_text("#save-template"),
              "양식 A를 올림: [+ 양식 저장] 켜짐")
        page.click("#save-template")
        wait_count(page, 1)
        page.wait_for_function("document.getElementById('save-template').textContent.includes('저장됨')")
        L = items(page)
        print("   목록:", L, "/", page.inner_text("#vault-msg"))
        check(ta.stem in L[0] and "사용 중" in L[0] and page.is_hidden("#vault-empty"), "저장: 1번에 양식 A, '사용 중' 표시")
        page.screenshot(path=str(out / "02_저장.png"))

        # 2. 새로 고침 → 저장소에서 골라 변환까지
        page.reload()
        page.wait_for_selector("#engine.ready", timeout=180000)
        wait_count(page, 1)
        check(page.is_disabled("#save-template") and "사용 중" not in items(page)[0], "새로 고침: 목록 1개 그대로, 쓰는 양식 없음")
        page.click("#vault-list .vi .vi-main")
        page.wait_for_selector("#template-card:not([hidden])", timeout=300000)
        card = page.inner_text("#template-card")
        check("저장된 양식" in card and ta.stem in card and "저장됨" in page.inner_text("#save-template")
              and page.get_attribute("#step2", "aria-disabled") == "false",
              "저장소 1번을 누름: 양식으로 쓰임('저장된 양식', 단추 '저장됨', 2단계 열림)")
        pick(page, "document", doc)
        page.wait_for_selector("#survey-modal:not([hidden]), #document-error:not([hidden])", timeout=300000)
        if page.is_visible("#document-error"):
            raise SystemExit("문서 오류: " + page.inner_text("#document-error"))
        answer_survey(page)
        with page.expect_download(timeout=600000) as dl:
            page.click("#convert-btn")
        saved = out / dl.value.suggested_filename
        dl.value.save_as(str(saved))
        page.wait_for_selector("#done-card:not([hidden])")
        done = page.inner_text("#done-card")
        z = zipfile.ZipFile(saved)
        first = z.infolist()[0]
        check("모두 통과" in done and first.filename == "mimetype" and first.compress_type == 0 and z.testzip() is None,
              f"저장소의 양식으로 변환 끝까지: {saved.name} ({saved.stat().st_size:,} bytes), 자동 검사 통과, ZIP 정상")
        page.screenshot(path=str(out / "03_저장소양식으로_완성.png"), full_page=True)

        # 3. 양식 B 저장 → 2개, 양식 A를 다시 올리면 바로 '저장됨'
        load_template(page, tb, change=True)
        page.click("#save-template")
        wait_count(page, 2)
        L = items(page)
        print("   목록:", L)
        check(L[0].startswith("1") and L[1].startswith("2") and tb.stem in L[1] and "사용 중" in L[1], "양식 B 저장: 2번, '사용 중'")
        load_template(page, ta, change=True)
        L = items(page)
        check("저장됨" in page.inner_text("#save-template") and "사용 중" in L[0] and "사용 중" not in L[1] and len(L) == 2,
              "양식 A 파일을 다시 올림: 바로 '저장됨', 1번이 '사용 중'(같은 양식을 또 저장하지 않음)")

        # 4. 이름 바꾸기·지우기
        page.click('#vault-list .vi:nth-child(2) [data-act="rename"]')
        check(page.evaluate("document.activeElement.classList.contains('vi-input')"), "이름 바꾸기: 이름 칸에 바로 커서")
        page.fill("#vault-list .vi-input", "회사 표·그림 양식")
        page.keyboard.press("Enter")
        page.wait_for_function("document.querySelector('#vault-list .vi:nth-child(2)').innerText.includes('회사 표·그림 양식')")
        page.click('#vault-list .vi:nth-child(1) [data-act="rename"]')
        page.fill("#vault-list .vi-input", "바뀌면 안 됨")
        page.keyboard.press("Escape")
        L = items(page)
        check("회사 표·그림 양식" in L[1] and "바뀌면 안 됨" not in L[0] and ta.stem in L[0], "Enter는 저장, Esc는 취소")
        page.click('#vault-list .vi:nth-child(1) [data-act="delete"]')
        check(page.is_visible('#vault-list [data-act="delete-ok"]'), "지우기: 확인을 먼저 물음")
        page.screenshot(path=str(out / "04_지우기_확인.png"))
        page.click('#vault-list [data-act="delete-cancel"]')
        check(len(items(page)) == 2, "지우기 취소: 그대로 2개")
        page.click('#vault-list .vi:nth-child(1) [data-act="delete"]')
        page.click('#vault-list [data-act="delete-ok"]')
        wait_count(page, 1)
        check(not page.is_visible("#tmpl-tag") and "+ 양식 저장" in page.inner_text("#save-template")
              and page.is_enabled("#save-template"),
              "지금 쓰는 양식을 지움: 양식은 그대로 쓰고, 단추는 다시 '+ 양식 저장'")
        page.reload()
        page.wait_for_selector("#engine.ready", timeout=180000)
        wait_count(page, 1)
        L = items(page)
        check(L[0].startswith("1") and "회사 표·그림 양식" in L[0], f"새로 고침 뒤: 이름 바꾼 양식만 1번으로 남음 {L}")

        # 5. 다른 창과 맞춤
        page2 = ctx.new_page()
        page2.goto(url)
        page2.wait_for_selector("#engine.ready", timeout=180000)
        wait_count(page2, 1)
        load_template(page2, ta)
        page2.click("#save-template")
        wait_count(page2, 2)
        wait_count(page, 2)
        check(ta.stem in items(page)[1], "다른 창에서 저장: 이 창 목록에도 바로 나타남")
        page2.close()

        # 화면 그림(목록 2개, 1번 사용 중)
        page.click("#vault-list .vi:nth-child(2) .vi-main")
        page.wait_for_selector("#template-card:not([hidden])", timeout=300000)
        page.mouse.move(5, 300)  # 마우스가 목록 위에 남아 있으면 그림에 '가리킴' 색이 찍힌다
        for w, h, name in ((1893, 912, "넓은화면"), (1280, 800, "노트북"), (1100, 800, "경계1100"), (1099, 800, "경계1099"),
                           (390, 844, "휴대폰")):
            page.set_viewport_size({"width": w, "height": h})
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(out / f"05_{name}.png"))
            over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check(over <= 0, f"{name} {w}px: 가로 넘침 없음({over})")
        page.set_viewport_size({"width": 1893, "height": 912})
        page.emulate_media(color_scheme="dark")
        page.screenshot(path=str(out / "06_어두운화면.png"))
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
