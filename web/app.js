/* 보고서 양식 맞춤 — 화면 동작.
   변환 엔진(파이썬)은 Web Worker 안의 Pyodide에서 돈다. 파일은 브라우저 밖으로 나가지 않는다. */
"use strict";

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/";

/* ---------------------------------------------------------------- 작업자(Worker) */
function workerMain() {
  let py = null;
  const post = (msg) => self.postMessage(msg);
  self.onmessage = async (e) => {
    const m = e.data;
    try {
      if (m.type === "init") {
        post({ type: "progress", text: "파이썬 불러오는 중…" });
        importScripts(m.pyodide + "pyodide.js");
        py = await loadPyodide({ indexURL: m.pyodide });
        post({ type: "progress", text: "문서 도구 불러오는 중…" });
        await py.loadPackage("lxml");
        py.FS.mkdirTree("/app/engine");
        for (const [name, src] of Object.entries(m.files)) py.FS.writeFile("/app/engine/" + name, src);
        py.runPython(`
import sys, json, traceback
sys.path.insert(0, "/app/engine")
import service
def call(name, args_json):
    try:
        return json.dumps({"ok": True, "data": getattr(service, name)(*json.loads(args_json))}, ensure_ascii=False)
    except (service.UserError, SystemExit) as e:
        return json.dumps({"ok": False, "user": True, "error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "user": False, "error": f"{type(e).__name__}: {e}",
                           "trace": traceback.format_exc()[-3000:]}, ensure_ascii=False)
`);
        post({ type: "ready", version: py.version });
        return;
      }
      if (!py) throw new Error("엔진이 아직 준비되지 않았습니다.");
      let args;
      if (m.type === "template" || m.type === "document") {
        py.FS.mkdirTree("/in");
        const path = "/in/" + m.name.replace(/[\\/]/g, "_");
        py.FS.writeFile(path, new Uint8Array(m.bytes));
        args = [path, "/work"];
      } else if (m.type === "convert") {
        args = ["/work", m.options];
      }
      const fn = { template: "analyze_template", document: "inspect_document", convert: "convert" }[m.type];
      const res = JSON.parse(py.globals.get("call")(fn, JSON.stringify(args)));
      if (res.ok && m.type === "convert") {
        const bytes = py.FS.readFile(res.data["파일"]);
        post({ type: "result", id: m.id, res, bytes }, [bytes.buffer]);
        return;
      }
      post({ type: "result", id: m.id, res });
    } catch (err) {
      post({ type: "result", id: m.id, res: { ok: false, user: false, error: String(err && err.message || err) } });
    }
  };
}

const worker = new Worker(URL.createObjectURL(new Blob(["(" + workerMain.toString() + ")()"], { type: "text/javascript" })));
let engineReady = false;
const pending = new Map();
let seq = 0;

worker.onmessage = (e) => {
  const m = e.data;
  if (m.type === "progress") setEngine("wait", m.text);
  else if (m.type === "ready") { engineReady = true; setEngine("ready", "변환 엔진 준비 완료"); }
  else if (m.type === "result") {
    const p = pending.get(m.id);
    if (p) { pending.delete(m.id); p(m); }
  }
};
worker.onerror = (e) => setEngine("fail", "변환 엔진을 불러오지 못했습니다(인터넷 연결을 확인해 주세요)");
worker.postMessage({ type: "init", pyodide: PYODIDE, files: window.ENGINE_FILES });

function call(type, payload, transfer) {
  return new Promise((resolve) => {
    const id = ++seq;
    pending.set(id, resolve);
    worker.postMessage({ type, id, ...payload }, transfer || []);
  });
}

async function waitEngine() {
  if (engineReady) return;
  showBusy("변환 엔진을 준비하는 중입니다… (처음 한 번은 조금 걸려요)");
  while (!engineReady) {
    if (document.getElementById("engine").classList.contains("fail")) throw new Error("엔진을 불러오지 못했습니다.");
    await new Promise((r) => setTimeout(r, 200));
  }
}

/* ---------------------------------------------------------------- 화면 도우미 */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function setEngine(state, text) {
  const el = $("engine");
  el.classList.toggle("ready", state === "ready");
  el.classList.toggle("fail", state === "fail");
  $("engineText").textContent = text;
}
function showBusy(text) { $("busy-text").textContent = text; $("busy").hidden = false; }
function hideBusy() { $("busy").hidden = true; }
function showError(id, msg) { const el = $(id); el.textContent = msg; el.hidden = !msg; }
function lock(stepId, locked) {
  const el = $(stepId);
  el.classList.toggle("locked", locked);
  el.setAttribute("aria-disabled", locked ? "true" : "false");
}
function openModal(id) { $(id).hidden = false; const f = $(id).querySelector("input, button:not([disabled])"); if (f) f.focus(); }
function closeModal(id) { $(id).hidden = true; }
document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => closeModal(b.closest(".modal").id)));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") ["import-modal", "survey-modal"].forEach((id) => { if (!$(id).hidden) closeModal(id); });
});

function errorText(res) {
  if (res.user) return res.error;
  console.error(res.error, res.trace || "");
  return "변환 중 문제가 생겼습니다: " + res.error + " (같은 파일로 계속 안 되면 알려 주세요)";
}

/* ---------------------------------------------------------------- 파일 받기 */
const state = { template: null, document: null, result: null, kind: "template" };
const ACCEPT = { template: ".hwpx", document: ".hwpx,.docx" };

document.querySelectorAll("[data-import]").forEach((b) =>
  b.addEventListener("click", () => { state.kind = b.dataset.import; openModal("import-modal"); }));
$("from-device").addEventListener("click", () => {
  closeModal("import-modal");
  const inp = $("file-input");
  inp.value = "";
  inp.accept = ACCEPT[state.kind];
  inp.click();
});
$("file-input").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) takeFile(state.kind, f); });

for (const kind of ["template", "document"]) {
  const zone = $("drop-" + kind);
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    const f = e.dataTransfer.files[0];
    if (f) takeFile(kind, f);
  });
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); state.kind = kind; openModal("import-modal"); } });
}
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => e.preventDefault());

function extOk(kind, name) {
  const ext = name.toLowerCase().split(".").pop();
  if (ext === "hwp") return "한글(.hwp) 파일은 먼저 한글에서 [파일] → [다른 이름으로 저장] → 파일 형식 'HWPX'로 저장한 뒤 올려 주세요.";
  if (kind === "template" && ext !== "hwpx") return "양식은 한글 .hwpx 파일만 받을 수 있습니다.";
  if (kind === "document" && !["hwpx", "docx"].includes(ext)) return "문서는 .docx 또는 .hwpx 파일만 받을 수 있습니다.";
  return "";
}

async function takeFile(kind, file) {
  const errId = kind + "-error";
  showError(errId, "");
  const bad = extOk(kind, file.name);
  if (bad) { showError(errId, bad); return; }
  try {
    await waitEngine();
    showBusy(kind === "template" ? "양식을 분석하는 중…" : "문서를 살펴보는 중…");
    const bytes = await file.arrayBuffer();
    const m = await call(kind, { name: file.name, bytes }, [bytes]);
    hideBusy();
    if (!m.res.ok) { showError(errId, errorText(m.res)); return; }
    if (kind === "template") onTemplate(file.name, m.res.data);
    else onDocument(file.name, m.res.data);
  } catch (err) {
    hideBusy();
    showError(errId, String(err.message || err));
  }
}

/* ---------------------------------------------------------------- 1. 양식 */
function onTemplate(name, data) {
  const s = data["요약"];
  state.template = { name, s };
  state.document = null;
  const has = (ok, text) => `<li class="${ok ? "" : "no"}">${ok ? "✓" : "✕"} ${esc(text)}</li>`;
  const levels = (s["제목 단계"] || []).map((h) => h["번호"]).filter(Boolean).join(" → ");
  const pn = s["쪽 번호"] ? `쪽 번호 ${s["쪽 번호"]["모양"]}` : "쪽 번호";
  const chips = [
    has(s["부분"]["표지"], "표지"), has(s["부분"]["차례"], "차례"), has(!!s["장 제목"], "장 제목"),
    has((s["제목 단계"] || []).length, "번호 단계" + (levels ? ` ${levels}` : "")), has(!!s["본문"], "본문"),
    has(!!s["표"], "표"), has(!!s["그림"], "그림"), has(s["머리말"] !== undefined, "머리말"), has(!!s["쪽 번호"], pn),
  ].join("");
  const notes = (s["알림"] || []).map((n) => `<li>${esc(n)}</li>`).join("");
  const font = s["본문"] ? `본문 글꼴: ${esc(s["본문"]["글꼴"])} ${s["본문"]["크기"]}pt` : "";
  $("template-card").innerHTML = `
    <div class="file"><span>📄 <b>${esc(name)}</b></span><button type="button" class="linkbtn" id="tmpl-change">다른 양식으로 바꾸기</button></div>
    <ul class="chips">${chips}</ul>
    <p class="hint" style="margin:6px 0 0">${font}${!s["부분"]["표지"] || !s["부분"]["차례"] ? " · 양식에 없는 표지·차례는 필요하면 간단한 모양으로 만들어 드려요." : ""}</p>
    ${notes ? `<ul class="notes">${notes}</ul>` : ""}`;
  $("template-card").hidden = false;
  $("drop-template").hidden = true;
  $("step1").classList.add("done");
  $("tmpl-change").addEventListener("click", resetTemplate);
  lock("step2", false);
  resetDocument();
  $("drop-document").focus();
}
function resetTemplate() {
  state.template = null;
  $("template-card").hidden = true;
  $("drop-template").hidden = false;
  $("step1").classList.remove("done");
  lock("step2", true);
  resetDocument();
}

/* ---------------------------------------------------------------- 2. 문서 + 설문 */
function onDocument(name, data) {
  state.document = { name, data };
  const c = data["구성"];
  const notes = (data["알림"] || []).map((n) => `<li>${esc(n)}</li>`).join("");
  $("document-card").innerHTML = `
    <div class="file"><span>📝 <b>${esc(name)}</b></span><button type="button" class="linkbtn" id="doc-change">다른 문서로 바꾸기</button></div>
    <ul class="chips"><li>장 ${c["장"]}</li><li>제목 ${c["제목"]}</li><li>본문 ${c["본문"]}</li><li>표 ${c["표"]}</li><li>그림 ${c["그림"]}</li></ul>
    ${notes ? `<ul class="notes">${notes}</ul>` : ""}
    <div class="row-actions"><button type="button" class="btn" id="open-survey">변환 설정 다시 하기</button></div>`;
  $("document-card").hidden = false;
  $("drop-document").hidden = true;
  $("doc-change").addEventListener("click", resetDocument);
  $("open-survey").addEventListener("click", openSurvey);
  $("title-preview").textContent = data["자동 제목"] ? `예: ${data["자동 제목"]}` : "";
  $("header-preview").textContent = data["자동 머리말"] ? `예: ${data["자동 머리말"]}` : "";
  const big = data["큰 표"] || { "수": 0 };
  $("q-split").hidden = !(big["수"] > 0);  // 한 쪽보다 길 수 있는 표가 있을 때만 묻는다
  $("split-count").textContent = big["어림"] === false ? "(표가 있어 미리 여쭙니다)" : `(한 쪽을 넘는 표 ${big["수"]}개)`;
  openSurvey();
}
function resetDocument() {
  state.document = null;
  state.result = null;
  $("document-card").hidden = true;
  $("drop-document").hidden = false;
  $("step2").classList.remove("done");
  $("done-card").hidden = true;
  showError("document-error", "");
  showError("convert-error", "");
  lock("step3", true);
  $("step3").classList.remove("done");
}

const form = $("survey");
function val(name) { const el = form.querySelector(`input[name="${name}"]:checked`); return el ? el.value : ""; }
function syncSurvey() {
  form.querySelectorAll("[data-when]").forEach((el) => {
    const [k, v] = el.dataset.when.split("=");
    el.hidden = val(k) !== v;
  });
  const need = [];
  if (!val("title")) need.push("1-1");
  else if (val("title") === "yes") {
    if (!val("titleMode")) need.push("1-2");
    else if (val("titleMode") === "manual" && !$("title-text").value.trim()) need.push("1-2 제목 글자");
  }
  if (!val("toc")) need.push("2");
  if (!val("pn")) need.push("3");
  else if (val("pn") === "지정" && !(+$("pn-start").value >= 1)) need.push("3 시작 번호");
  if (!val("header")) need.push("4-1");
  else if (val("header") === "yes") {
    if (!val("headerMode")) need.push("4-2");
    else if (val("headerMode") === "manual" && !$("header-text").value.trim()) need.push("4-2 머리말 글자");
  }
  if (!$("q-split").hidden && !val("split")) need.push("5");
  $("survey-need").textContent = need.length ? `아직 답하지 않은 질문: ${need.join(", ")}` : "";
  $("convert-btn").disabled = need.length > 0;
}
form.addEventListener("input", syncSurvey);
form.addEventListener("change", syncSurvey);
$("title-text").addEventListener("focus", () => { form.querySelector('input[name="titleMode"][value="manual"]').checked = true; syncSurvey(); });
$("header-text").addEventListener("focus", () => { form.querySelector('input[name="headerMode"][value="manual"]').checked = true; syncSurvey(); });
$("pn-start").addEventListener("focus", () => { form.querySelector('input[name="pn"][value="지정"]').checked = true; syncSurvey(); });

function openSurvey() { syncSurvey(); openModal("survey-modal"); }

function options() {
  return {
    "표지": { "만들기": val("title") === "yes", "제목": val("titleMode") === "manual" ? $("title-text").value.trim() : "" },
    "차례": { "만들기": val("toc") === "yes" },
    "쪽번호": { "방식": val("pn"), "시작": val("pn") === "지정" ? +$("pn-start").value : 1 },
    "머리말": { "만들기": val("header") === "yes", "글자": val("headerMode") === "manual" ? $("header-text").value.trim() : "" },
    "표": { "나누기": $("q-split").hidden ? "" : val("split") },
  };
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if ($("convert-btn").disabled) return;
  closeModal("survey-modal");
  showError("convert-error", "");
  lock("step3", false);
  try {
    await waitEngine();
    showBusy("양식에 맞게 바꾸는 중…");
    const m = await call("convert", { options: options() });
    hideBusy();
    if (!m.res.ok) { showError("convert-error", errorText(m.res)); return; }
    onResult(m.res.data, m.bytes);
  } catch (err) {
    hideBusy();
    showError("convert-error", String(err.message || err));
  }
});

/* ---------------------------------------------------------------- 3. 결과 */
function download(name, bytes) {
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/hwp+zip" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function onResult(data, bytes) {
  state.result = { name: data["이름"], bytes };
  download(data["이름"], bytes);
  const made = data["구성"];
  const parts = [made["표지"] ? "표지" : "", made["차례"] ? "차례" : "", "본문"].filter(Boolean).join(" + ");
  const warn = (data["알림"] || []).map((n) => `<li class="warn">${esc(n)}</li>`).join("");
  const tocNote = made["차례"] ? `<li>차례의 쪽 번호는 아직 비어 있습니다 — 한글에서 열어 쪽을 확인해 주세요(다음 판에서 채울 예정).</li>` : "";
  const all = data["표 나눔"] || [];
  const split = all.filter((x) => x["종류"] !== "그림");
  const frames = all.length - split.length;
  const modes = [...new Set(split.map((x) => (x["나누기"] === "나눔" ? "쪽 경계에서 나눔" : "셀 단위로 나눔")))];
  const rep = split.filter((x) => x["머리행반복"]).length;
  const splitNote = (split.length
    ? `<li>한 쪽보다 긴 표 ${split.length}개: ${esc(modes.join(", "))} — 쪽 아래로 넘치지 않게 다음 쪽으로 이어집니다`
      + (rep ? `(표 머리행은 다음 쪽에도 나옵니다${rep < split.length ? ` — ${rep}개` : ""})` : "") + ".</li>" : "")
    + (frames ? `<li>한 쪽을 넘는 그림 묶음 ${frames}개는 사진과 설명이 갈리지 않게 줄 단위로 다음 쪽에 이어집니다.</li>` : "");
  const ok = data["검증 실패"] === 0;
  $("done-card").innerHTML = `
    <p class="done-msg">✓ 완성했습니다</p>
    <p style="margin:0">📥 <b>${esc(data["이름"])}</b> 파일을 <b>다운로드 폴더</b>에 저장했습니다.</p>
    <ul class="notes">
      <li>구성: ${esc(parts)}</li>
      <li>바뀐 번호·기호: ${data["바뀐 글자"]}곳 (글자는 그대로이고, 직접 친 번호를 양식 번호로 바꾼 곳 등)</li>
      <li>${ok ? "자동 검사: 문서 구조·글자 보존·서식 모두 통과" : `자동 검사에서 ${data["검증 실패"]}곳이 다릅니다 — 한글에서 열어 확인해 주세요`}</li>
      ${splitNote}${tocNote}${warn}
    </ul>
    <div class="row-actions">
      <button type="button" class="btn primary" id="again-dl">다시 다운로드</button>
      <button type="button" class="btn" id="again-survey">설정 바꿔서 다시 만들기</button>
      <button type="button" class="btn ghost" id="next-doc">다른 문서도 이 양식으로</button>
    </div>`;
  $("done-card").hidden = false;
  $("step2").classList.add("done");
  $("step3").classList.add("done");
  $("again-dl").addEventListener("click", () => download(state.result.name, state.result.bytes));
  $("again-survey").addEventListener("click", openSurvey);
  $("next-doc").addEventListener("click", () => { resetDocument(); $("drop-document").scrollIntoView({ behavior: "smooth" }); });
}
