/* 보고서 양식 맞춤 — 화면 동작.
   변환 엔진(파이썬)은 Web Worker 안의 Pyodide에서 돈다. 파일은 브라우저 밖으로 나가지 않는다. */
"use strict";

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/";

/* ---------------------------------------------------------------- 작업자(Worker) */
function workerMain() {
  let py = null;
  let tpaths = null; // 마지막으로 올린 양식 파일 경로(제목·본문 줄을 고쳐 다시 분석할 때 쓴다)
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
        return json.dumps({"ok": False, "user": True, "error": str(e), "help": getattr(e, "help", None)}, ensure_ascii=False)
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
        // 양식은 여러 파일일 수 있다(앞표지·목차·본문 스타일 등) — 이름이 같아도 겹치지 않게 번호 폴더에
        const paths = m.list.map((f, i) => {
          const dir = m.type === "document" ? "/in" : `/in/t${i}`;
          py.FS.mkdirTree(dir);
          const path = dir + "/" + f.name.replace(/[\\/]/g, "_");
          py.FS.writeFile(path, new Uint8Array(f.bytes));
          return path;
        });
        args = [paths.length === 1 ? paths[0] : paths, "/work"];
        if (m.type === "template") { tpaths = paths; args.push(m.picks || null); } // picks: 저장해 둔 '고친 줄'
      } else if (m.type === "repick") {
        // 같은 양식 파일을 사용자가 고친 제목·본문 줄(picks)로 다시 분석한다(picks가 없으면 자동으로 찾은 대로)
        if (!tpaths) throw new Error("양식을 먼저 올려 주세요.");
        args = [tpaths.length === 1 ? tpaths[0] : tpaths, "/work", m.picks || null];
      } else if (m.type === "convert") {
        args = ["/work", m.options];
      }
      const fn = { template: "analyze_template", repick: "analyze_template", document: "inspect_document", convert: "convert" }[m.type];
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
  if (e.key === "Escape") ["import-modal", "survey-modal", "pick-modal"].forEach((id) => { if (!$(id).hidden) closeModal(id); });
});

function errorText(res) {
  if (res.user) return res.error;
  console.error(res.error, res.trace || "");
  return "변환 중 문제가 생겼습니다: " + res.error + " (같은 파일로 계속 안 되면 알려 주세요)";
}

/* 엔진 오류 안내: 무엇을 하다가 · 원고 어디서 · 왜 · 이렇게 해 보세요 + 오류 정보(복사). help가 없으면 한 줄 글자 */
function showProblem(id, res) {
  const h = res.help;
  if (!h) { showError(id, errorText(res)); return; }
  const el = $(id);
  const tips = (h["해 볼 것"] || []).map((t) => `<li>${esc(t)}</li>`).join("");
  const detail = h["기술 정보"] || res.error || "";
  el.innerHTML = `
    <p class="err-title">${esc(h["제목"])}</p>
    ${h["어디서"] ? `<p class="err-row"><b>어디서</b> ${esc(h["어디서"])}</p>` : ""}
    ${h["이유"] ? `<p class="err-row"><b>이유</b> ${esc(h["이유"])}</p>` : ""}
    ${tips ? `<p class="err-row"><b>이렇게 해 보세요</b></p><ol class="err-tips">${tips}</ol>` : ""}
    <details class="err-detail"><summary>오류 정보</summary><pre>${esc(detail)}</pre>
      <button type="button" class="linkbtn" data-copy>오류 정보 복사</button></details>`;
  el.hidden = false;
  const btn = el.querySelector("[data-copy]");
  btn.addEventListener("click", async () => {
    const text = `[보고서 양식 맞춤 오류]\n${h["제목"]}\n${h["어디서"] ? "어디서: " + h["어디서"] + "\n" : ""}${detail}`;
    try { await navigator.clipboard.writeText(text); btn.textContent = "복사했습니다"; }
    catch { btn.textContent = "복사하지 못했습니다 — 위 글자를 직접 선택해 복사해 주세요"; }
  });
}

/* ---------------------------------------------------------------- 파일 받기 */
const state = { template: null, document: null, result: null, kind: "template" };
const ACCEPT = { template: ".hwpx", "template-add": ".hwpx", document: ".hwpx,.docx" };

document.querySelectorAll("[data-import]").forEach((b) =>
  b.addEventListener("click", () => { state.kind = b.dataset.import; openImport(); }));
function openImport() {
  openModal("import-modal");
  if (driveUsable()) googleReady().catch(() => {}); // 드라이브 버튼을 누르기 전에 미리 불러 둔다(팝업 차단 방지)
}
$("from-device").addEventListener("click", () => {
  closeModal("import-modal");
  const inp = $("file-input");
  inp.value = "";
  inp.accept = ACCEPT[state.kind];
  inp.multiple = state.kind !== "document"; // 양식은 여러 파일을 한꺼번에(앞표지·목차·본문 스타일·표 그림 양식 등)
  inp.click();
});
$("file-input").addEventListener("change", (e) => {
  const fs = [...e.target.files];
  if (fs.length) takeFile(state.kind, state.kind === "document" ? fs[0] : fs);
});

for (const kind of ["template", "document"]) {
  const zone = $("drop-" + kind);
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    const fs = [...e.dataTransfer.files];
    if (fs.length) takeFile(kind, kind === "document" ? fs[0] : fs);
  });
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); state.kind = kind; openImport(); } });
}
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => e.preventDefault());

/* ---------------------------------------------------------------- Google 드라이브
   사용자가 Picker에서 고른 파일만 이 브라우저로 내려받는다(drive.file 권한 — 다른 파일은 볼 수 없다).
   API 키·클라이언트 ID는 웹 페이지에 들어가는 공개 값이며, 이 사이트 주소와 Picker API로만 쓰이게 제한해 두었다. */
const GOOGLE = {
  apiKey: "AIzaSyCtdkUi5C7IIWu8TEDq-zJsBmq6ah-z100",
  clientId: "550438141886-5pcpdb8btlnupa89usmlkmo6ot31kid5.apps.googleusercontent.com",
  appId: "550438141886",
  scope: "https://www.googleapis.com/auth/drive.file",
};
const GDOC = "application/vnd.google-apps.document";
const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
let gLoad = null;
let gToken = null; // { value, until }

function driveUsable() { return location.protocol === "https:" || location.hostname === "localhost"; }
if (!driveUsable()) {
  $("from-drive").disabled = true;
  $("drive-sub").textContent = "인터넷 사이트 주소로 열었을 때만 쓸 수 있습니다";
}

function loadScript(src) {
  return new Promise((ok, no) => {
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.onload = ok;
    s.onerror = () => no(new Error("Google 드라이브 연결 도구를 불러오지 못했습니다. 인터넷 연결을 확인해 주세요."));
    document.head.appendChild(s);
  });
}
function googleReady() {
  gLoad ||= Promise.all([
    loadScript("https://accounts.google.com/gsi/client"),
    loadScript("https://apis.google.com/js/api.js").then(() => new Promise((ok, no) =>
      gapi.load("picker", { callback: ok, onerror: () => no(new Error("Google 드라이브 파일 고르기 창을 불러오지 못했습니다.")) }))),
  ]).catch((err) => { gLoad = null; throw err; });
  return gLoad;
}

function driveToken() {
  if (gToken && Date.now() < gToken.until) return Promise.resolve(gToken.value);
  return new Promise((ok, no) => {
    const client = google.accounts.oauth2.initTokenClient({
      client_id: GOOGLE.clientId,
      scope: GOOGLE.scope,
      callback: (r) => {
        if (r.error) { no(new Error(r.error === "access_denied" ? "cancel" : (r.error_description || r.error))); return; }
        gToken = { value: r.access_token, until: Date.now() + (Number(r.expires_in || 3600) - 60) * 1000 };
        ok(gToken.value);
      },
      error_callback: (e) => no(new Error(e && e.type === "popup_closed" ? "cancel"
        : e && e.type === "popup_failed_to_open" ? "로그인 창이 열리지 않았습니다. 브라우저의 팝업 차단을 이 사이트에 대해 풀어 주세요."
        : "Google 로그인에 실패했습니다.")),
    });
    client.requestAccessToken({ prompt: "" });
  });
}

function drivePick(token, kind) {
  return new Promise((ok) => {
    const P = google.picker;
    const mine = new P.DocsView(P.ViewId.DOCS).setIncludeFolders(true).setMode(P.DocsViewMode.LIST);
    const shared = new P.DocsView(P.ViewId.DOCS).setEnableDrives(true).setIncludeFolders(true).setMode(P.DocsViewMode.LIST);
    const b = new P.PickerBuilder()
      .setAppId(GOOGLE.appId)
      .setDeveloperKey(GOOGLE.apiKey)
      .setOAuthToken(token)
      .setLocale("ko")
      .setTitle(kind === "document" ? "바꿀 문서(.docx·.hwpx) 고르기" : "양식 파일(.hwpx) 고르기 — 여러 개를 함께 골라도 됩니다")
      .addView(mine)
      .addView(shared)
      .enableFeature(P.Feature.SUPPORT_DRIVES);
    if (kind !== "document") b.enableFeature(P.Feature.MULTISELECT_ENABLED);
    b.setCallback((d) => {
      if (d[P.Response.ACTION] === P.Action.PICKED) ok(d[P.Response.DOCUMENTS]);
      else if (d[P.Response.ACTION] === P.Action.CANCEL) ok(null);
    })
      .build()
      .setVisible(true);
  });
}

async function driveDownload(token, doc, kind) {
  const id = encodeURIComponent(doc[google.picker.Document.ID]);
  let name = doc[google.picker.Document.NAME] || "드라이브 파일";
  const mime = doc[google.picker.Document.MIME_TYPE] || "";
  let url = `https://www.googleapis.com/drive/v3/files/${id}?alt=media&supportsAllDrives=true`;
  if (mime === GDOC) {
    // 구글 문서로 저장된 글은 워드(.docx)로 내보내 받는다
    if (kind !== "document") throw new Error("양식은 한글 .hwpx 파일이어야 합니다. 구글 문서는 바꿀 문서로만 쓸 수 있습니다.");
    url = `https://www.googleapis.com/drive/v3/files/${id}/export?mimeType=${encodeURIComponent(DOCX)}`;
    if (!/\.docx$/i.test(name)) name += ".docx";
  } else if (mime.startsWith("application/vnd.google-apps.")) {
    throw new Error("구글 스프레드시트·프레젠테이션 등은 받을 수 없습니다. .hwpx 또는 .docx 파일을 골라 주세요.");
  } else {
    const bad = extOk(kind, name);
    if (bad) throw new Error(bad);
  }
  const r = await fetch(url, { headers: { Authorization: "Bearer " + token } });
  if (r.status === 401) { gToken = null; throw new Error("Google 로그인이 만료되었습니다. 다시 시도해 주세요."); }
  if (!r.ok) throw new Error(`드라이브에서 파일을 받지 못했습니다 (오류 ${r.status}).`);
  return new File([await r.blob()], name);
}

$("from-drive").addEventListener("click", async () => {
  const kind = state.kind;
  const errId = (kind === "document" ? "document" : "template") + "-error";
  closeModal("import-modal");
  showError(errId, "");
  try {
    await googleReady();
    const token = await driveToken();
    const docs = await drivePick(token, kind);
    if (!docs || !docs.length) return;
    showBusy("드라이브에서 파일을 받는 중…");
    const files = [];
    for (const doc of docs) files.push(await driveDownload(token, doc, kind));
    hideBusy();
    await takeFile(kind, kind === "document" ? files[0] : files);
  } catch (err) {
    hideBusy();
    const msg = String(err.message || err);
    if (msg !== "cancel") showError(errId, msg);
  }
});

function extOk(kind, name) {
  const ext = name.toLowerCase().split(".").pop();
  if (ext === "hwp") return "한글(.hwp) 파일은 먼저 한글에서 [파일] → [다른 이름으로 저장] → 파일 형식 'HWPX'로 저장한 뒤 올려 주세요.";
  if (kind !== "document" && ext !== "hwpx") return `양식은 한글 .hwpx 파일만 받을 수 있습니다(${name}).`;
  if (kind === "document" && !["hwpx", "docx"].includes(ext)) return "문서는 .docx 또는 .hwpx 파일만 받을 수 있습니다.";
  return "";
}

/* 받은 파일 처리. kind: "document"(문서 하나) / "template"(양식 — 파일 하나 또는 여러 개) /
   "template-add"(지금 양식에 파일을 더함). saved: 양식 저장소에서 고른 양식이면 그 목록 항목(이름·해시) */
async function takeFile(kind, input, saved) {
  let files = Array.isArray(input) ? input : [input];
  if (kind === "template-add") {
    const had = state.template ? state.template.files : [];
    const key = (f) => f.name + "/" + f.size;
    files = [...had, ...files.filter((f) => !had.some((h) => key(h) === key(f)))];
    kind = "template";
  }
  const errId = kind + "-error";
  showError(errId, "");
  const bad = files.map((f) => extOk(kind, f.name)).find(Boolean);
  if (bad) { showError(errId, bad); return; }
  try {
    await waitEngine();
    showBusy(kind === "template" ? (files.length > 1 ? `양식 파일 ${files.length}개를 분석하는 중…` : "양식을 분석하는 중…") : "문서를 살펴보는 중…");
    const list = [];
    for (const f of files) list.push({ name: f.name, bytes: await f.arrayBuffer() });
    // 양식은 내용 해시로 '이미 저장한 양식인지' 알아본다(작업자로 넘기면 bytes를 더 못 쓰므로 먼저)
    let hash = "";
    if (kind === "template") {
      if (saved && saved.hash) hash = saved.hash;
      else {
        const hs = [];
        for (const x of list) hs.push(await fingerprint(x.bytes));
        hash = hs.length === 1 ? hs[0] : "set:" + hs.sort().join("+"); // 묶음은 파일 순서와 상관없이 같은 양식
      }
    }
    // 저장소에 있는 양식이면(목록에서 골랐거나, 같은 파일을 다시 올렸거나) 그때 고쳐 둔 제목·본문 줄(picks)도 함께 쓴다
    const rec = kind === "template" ? (saved || vault.items.find((v) => v.hash === hash)) : null;
    const picks = rec && rec.picks ? rec.picks : null;
    const m = await call(kind, kind === "template" ? { list, picks } : { list }, list.map((x) => x.bytes));
    hideBusy();
    if (!m.res.ok) {
      // 양식 분석이 실패하면 엔진 쪽 양식도 이미 바뀌었으므로 화면의 양식도 비운다(다시 고르게)
      if (kind === "template" && state.template) resetTemplate();
      showProblem(errId, m.res);
      return;
    }
    if (kind === "template") onTemplate(files, m.res.data, hash, saved, picks);
    else onDocument(files[0].name, m.res.data);
  } catch (err) {
    hideBusy();
    showError(errId, String(err.message || err));
  }
}
function setName(files, s) { // 저장소에 넣을 때 기본 이름: 파일 하나면 그 이름, 여러 개면 '본문 파일 외 n개'
  const stem = (n) => n.replace(/\.hwpx$/i, "");
  if (files.length === 1) return stem(files[0].name);
  const body = (s["파일"] && s["파일"]["본문"]) || files[0].name;
  return `${stem(body)} 외 ${files.length - 1}개`;
}

/* ---------------------------------------------------------------- 1. 양식 */
/* 양식 진단표: 엔진이 검사한 항목(있음·없음, 없을 때 어떻게 처리하는지, 한글에서 넣는 법)을 그대로 보여 준다 */
function diagHtml(s) {
  const d = s["진단"];
  if (!d) return "";
  const row = (x) => {
    const ok = x["상태"] === "있음";
    const cls = ok ? "ok" : x["구분"] === "선택" ? "opt" : "no";
    let body;
    if (ok && x["단계"] && x["단계"].length) {
      body = `<ul class="d-levels">${x["단계"].map((h) => `<li><span class="d-lv">${h["단계"]}단계</span>
        ${h["번호"] ? `<b>${esc(h["번호"])}</b>` : ""} <span class="d-how">${esc(h["방식"])}</span> ${esc(h["모양"])}
        <span class="d-ex">‘${esc(h["보기"])}’</span></li>`).join("")}</ul>`;
    } else if (ok) {
      body = esc(x["찾은 것"]);
    } else {
      body = `<span class="d-miss">양식에 없음</span> ${esc(x["없으면"])}`
        + (x["고치는 법"] ? `<small class="d-fix">양식에 넣으려면: ${esc(x["고치는 법"])}</small>` : "");
    }
    return `<li class="${cls}"><span class="d-mark" aria-hidden="true">${ok ? "✓" : cls === "opt" ? "·" : "!"}</span>
      <span class="d-name">${esc(x["이름"])}</span><span class="d-text">${body}</span></li>`;
  };
  const lack = d["없는 것"] || [];
  const verdict = lack.length
    ? `<p class="verdict warn">양식으로 쓸 수 있습니다. 다만 양식에 없는 ${lack.length}가지(${esc(lack.join(", "))})는 아래에 적은 대로 처리합니다.</p>`
    : `<p class="verdict ok">✓ 양식으로 쓸 수 있습니다. 필요한 모양을 모두 찾았습니다.</p>`;
  return `${verdict}<ul class="diag">${d["항목"].map(row).join("")}</ul>`;
}

function onTemplate(files, data, hash, saved, picks) {
  const s = data["요약"];
  const name = setName(files, s);
  // files는 [+ 양식 저장]·파일 더하기 때 다시 읽는다. picks: 사용자가 고친 제목·본문 줄(없으면 자동으로 찾은 것)
  state.template = { name, s, files, hash, picks: picks || null };
  state.document = null;
  const notes = (s["알림"] || []).map((n) => `<li>${esc(n)}</li>`).join("");
  const tag = saved ? ` <span class="tag" id="tmpl-tag">저장된 양식</span>` : "";
  $("template-card").dataset.saved = saved ? saved.id : "";
  // 여러 파일 양식: 어느 부분을 어느 파일에서 가져왔는지
  const fmap = s["파일"];
  const roleOf = (n) => fmap ? ["표지", "차례", "본문", "표·그림"].filter((k) => fmap[k] === n) : [];
  const flist = files.length > 1 ? `<ul class="tfiles">${files.map((f) => {
    const r = roleOf(f.name);
    return `<li><span class="tf-name">${esc(f.name)}</span> ${r.length ? r.map((x) => `<span class="tf-role">${esc(x)}</span>`).join("")
      : '<span class="tf-role no">안 씀</span>'}</li>`;
  }).join("")}</ul>` : "";
  const shown = saved ? saved.name : files.length === 1 ? files[0].name : name;
  $("template-card").innerHTML = `
    <div class="file"><span>📄 <b id="tmpl-name">${esc(shown)}</b>${tag}</span>
      <span class="file-acts"><button type="button" class="linkbtn" id="tmpl-add">+ 파일 더하기</button>
      <button type="button" class="linkbtn" id="tmpl-change">다른 양식으로 바꾸기</button></span></div>
    ${flist}
    ${diagHtml(s)}
    <div class="row-actions"><button type="button" class="btn small" id="tmpl-pick">제목·본문 줄 고치기</button>
      <span class="pick-state">${picks ? "직접 고른 줄을 쓰는 중" : "제목이나 본문을 잘못 알아봤으면 여기서 고칠 수 있습니다"}</span></div>
    ${notes ? `<ul class="notes">${notes}</ul>` : ""}`;
  $("template-card").hidden = false;
  $("drop-template").hidden = true;
  $("template-guide").hidden = true;
  $("step1").classList.add("done");
  $("tmpl-change").addEventListener("click", resetTemplate);
  $("tmpl-add").addEventListener("click", () => { state.kind = "template-add"; openImport(); });
  $("tmpl-pick").addEventListener("click", openPick);
  lock("step2", false);
  resetDocument();
  syncVault();
  $("drop-document").focus();
}
function resetTemplate() {
  state.template = null;
  $("template-card").hidden = true;
  $("drop-template").hidden = false;
  $("template-guide").hidden = false;
  $("step1").classList.remove("done");
  lock("step2", true);
  resetDocument();
  syncVault();
}

/* 제목·본문 줄 고치기: 엔진이 양식에서 찾은 줄(후보)마다 무엇으로 쓸지 고른다 → 같은 양식을 그 선택으로 다시 분석 */
const PICK_OPTS = [["", "쓰지 않음"], ["본문", "본문"], ["h1", "제목 1단계"], ["h2", "제목 2단계"], ["h3", "제목 3단계"],
  ["h4", "제목 4단계"], ["h5", "제목 5단계"]];
const HOW = { "자동": "자동 번호", "글자": "직접 친 번호·기호", "없음": "번호 없음" };
function pickValue(role) { return /^[1-5]수준$/.test(role) ? "h" + role[0] : role === "본문" ? "본문" : ""; }
function openPick() {
  const t = state.template;
  if (!t) return;
  const cands = t.s["후보"] || [];
  $("pick-list").innerHTML = cands.map((c) => {
    const meta = [`${c["글꼴"]} ${c["크기"]}pt${c["굵게"] ? " 굵게" : ""}`,
      c["방식"] === "없음" ? HOW["없음"] : `${HOW[c["방식"]] || ""} ${c["번호"]}`.trim(),
      c["수"] > 1 ? `양식에 ${c["수"]}줄` : ""].filter(Boolean).join(" · ");
    const ctrl = c["역할"] === "장 제목" ? `<span class="pick-fixed">장 제목(큰 제목)</span>`
      : `<select data-ref="${esc(c["문단"])}" data-was="${pickValue(c["역할"])}" aria-label="‘${esc(c["보기"])}’ 줄을 무엇으로 쓸지">
          ${PICK_OPTS.map(([v, label]) => `<option value="${v}"${v === pickValue(c["역할"]) ? " selected" : ""}>${label}</option>`).join("")}</select>`;
    return `<li class="pick-row"><div class="pick-text"><span class="pick-sample">‘${esc(c["보기"])}’</span>
      <span class="pick-meta">${esc(meta)}</span></div>${ctrl}</li>`;
  }).join("") || `<li class="pick-row">고를 수 있는 줄이 없습니다.</li>`;
  $("pick-auto").hidden = !t.picks;
  syncPick();
  openModal("pick-modal");
}
function pickState() {
  const sel = [...$("pick-list").querySelectorAll("select")];
  const body = sel.filter((x) => x.value === "본문");
  const heads = sel.filter((x) => x.value.startsWith("h")).sort((a, b) => a.value.localeCompare(b.value));
  const levels = heads.map((x) => +x.value[1]);
  const dup = levels.find((v, i) => levels.indexOf(v) !== i);
  const moved = (x) => x.value !== x.dataset.was;
  const headChanged = sel.some((x) => moved(x) && (x.value.startsWith("h") || x.dataset.was.startsWith("h")));
  const bodyChanged = sel.some((x) => moved(x) && (x.value === "본문" || x.dataset.was === "본문"));
  let need = "";
  let note = "";
  if (body.length === 0) need = "본문으로 쓸 줄을 하나 골라 주세요.";
  else if (body.length > 1) need = "본문은 한 줄만 고를 수 있습니다.";
  else if (dup) need = `제목 ${dup}단계를 두 줄에 골랐습니다 — 한 줄만 골라 주세요.`;
  else if (levels.some((v, i) => v !== i + 1)) note = `제목은 빈 단계 없이 차례로 씁니다 — 고르신 ${levels.join("·")}단계를 ${levels.map((_, i) => i + 1).join("·")}단계로 맞춥니다.`;
  // 바꾼 것만 보낸다(앞서 고쳐 둔 것은 그대로 둔다) — 제목 줄(1단계부터 차례로)과 본문 줄
  const picks = { ...((state.template && state.template.picks) || {}) };
  if (headChanged) picks["제목"] = heads.map((x) => x.dataset.ref);
  if (bodyChanged && body.length) picks["본문"] = body[0].dataset.ref;
  return { need, note, changed: headChanged || bodyChanged, picks };
}
function syncPick() {
  const st = pickState();
  $("pick-need").textContent = st.need || st.note;
  $("pick-need").classList.toggle("info", !st.need && !!st.note);
  $("pick-apply").disabled = !!st.need;
}
$("pick-list").addEventListener("change", syncPick);
async function repick(picks) {
  const t = state.template;
  if (!t) return;
  closeModal("pick-modal");
  showError("template-error", "");
  try {
    await waitEngine();
    showBusy("고르신 줄로 양식을 다시 살펴보는 중…");
    const m = await call("repick", { picks });
    hideBusy();
    if (!m.res.ok) { showProblem("template-error", m.res); return; }
    const hit = savedNow();
    if (hit) { // 저장해 둔 양식이면 고친 줄도 함께 기억해 다음에도 그대로 쓴다
      try { await store.patch(hit.id, { picks }); hit.picks = picks; announce(); } catch (err) { console.warn("고친 줄을 저장하지 못함:", err); }
    }
    onTemplate(t.files, m.res.data, t.hash, hit, picks);
  } catch (err) {
    hideBusy();
    showError("template-error", String(err.message || err));
  }
}
$("pick-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const st = pickState();
  if (st.need) return;
  if (!st.changed) { closeModal("pick-modal"); return; } // 바꾼 것이 없으면 그대로
  repick(st.picks);
});
$("pick-auto").addEventListener("click", () => repick(null));

/* ---------------------------------------------------------------- 양식 저장소
   [+ 양식 저장]을 누른 양식을 이 브라우저의 저장 공간(IndexedDB)에 보관해 두고, 다음에 목록에서 눌러 바로 쓴다.
   파일은 이 컴퓨터 밖으로 나가지 않는다. 목록(meta)과 파일 내용(files)을 따로 두어 목록을 그릴 때 큰 파일을 읽지 않는다.
   같은 양식인지는 파일 내용의 해시로 알아본다(저장한 양식을 다시 올리면 '저장됨'). */
const store = (() => {
  let dbp = null;
  function open() {
    if (!dbp) {
      dbp = new Promise((ok, no) => {
        const r = indexedDB.open("hwpx-yangsik", 1); // indexedDB가 없거나 막혀 있으면 여기서 던져 no로 간다
        r.onupgradeneeded = () => {
          r.result.createObjectStore("meta", { keyPath: "id", autoIncrement: true });
          r.result.createObjectStore("files");
        };
        r.onsuccess = () => {
          const db = r.result;
          db.onversionchange = () => { db.close(); dbp = null; };
          ok(db);
        };
        r.onerror = () => no(r.error);
        r.onblocked = () => no(new Error("다른 창에서 양식 저장소를 쓰는 중입니다. 그 창을 닫고 다시 열어 주세요."));
      });
      dbp.catch(() => { dbp = null; });
    }
    return dbp;
  }
  async function run(names, mode, body) {
    const db = await open();
    return new Promise((ok, no) => {
      const t = db.transaction(names, mode);
      let out;
      body(t, (v) => { out = v; });
      t.oncomplete = () => ok(out);
      t.onerror = () => no(t.error);
      t.onabort = () => no(t.error || new Error("저장소 작업이 취소되었습니다."));
    });
  }
  return {
    list: () => run("meta", "readonly", (t, set) => {
      const r = t.objectStore("meta").getAll();
      r.onsuccess = () => set(r.result.sort((a, b) => a.id - b.id));
    }),
    add: (rec, buf) => run(["meta", "files"], "readwrite", (t, set) => {
      const r = t.objectStore("meta").add(rec);
      r.onsuccess = () => { t.objectStore("files").put(buf, r.result); set({ ...rec, id: r.result }); };
    }),
    file: (id) => run("files", "readonly", (t, set) => {
      const r = t.objectStore("files").get(id);
      r.onsuccess = () => set(r.result);
    }),
    rename: (id, name) => run("meta", "readwrite", (t) => {
      const s = t.objectStore("meta");
      const r = s.get(id);
      r.onsuccess = () => { if (r.result) s.put({ ...r.result, name }); };
    }),
    patch: (id, fields) => run("meta", "readwrite", (t) => { // 목록 항목에 값 덧붙이기(예: 고친 제목·본문 줄 picks)
      const s = t.objectStore("meta");
      const r = s.get(id);
      r.onsuccess = () => { if (r.result) s.put({ ...r.result, ...fields }); };
    }),
    remove: (id) => run(["meta", "files"], "readwrite", (t) => {
      t.objectStore("meta").delete(id);
      t.objectStore("files").delete(id);
    }),
  };
})();

async function fingerprint(buf) {
  try {
    const h = new Uint8Array(await crypto.subtle.digest("SHA-256", buf));
    return "sha256:" + Array.from(h, (b) => b.toString(16).padStart(2, "0")).join("");
  } catch (_) { // 보안 연결이 아닌 주소(file:// 등)에는 crypto.subtle이 없을 수 있다 → 간단한 해시
    const a = new Uint8Array(buf);
    let h = 0x811c9dc5;
    for (let i = 0; i < a.length; i++) h = Math.imul(h ^ a[i], 0x01000193);
    return `fnv:${a.length}:${(h >>> 0).toString(16)}`;
  }
}

const vault = { ok: false, items: [], busy: false, editing: null, confirm: null, flash: null };
const PEN = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';
const BIN = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function savedNow() { const t = state.template; return t ? vault.items.find((v) => v.hash === t.hash) || null : null; }
const nb = (s) => s.replace(/ /g, "\u00a0"); // '11월 4일 저장'·'3.8 MB'가 줄 끝에서 갈라지지 않게
function sizeText(n) { return n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`; }
function dateText(ms) {
  const d = new Date(ms);
  const opt = d.getFullYear() === new Date().getFullYear() ? { month: "long", day: "numeric" } : { year: "numeric", month: "long", day: "numeric" };
  return d.toLocaleDateString("ko-KR", opt);
}
let msgTimer = 0;
function vaultMsg(text, bad) {
  const el = $("vault-msg");
  el.textContent = text || "";
  el.classList.toggle("bad", !!bad);
  clearTimeout(msgTimer);
  if (text && !bad) msgTimer = setTimeout(() => { el.textContent = ""; }, 8000);
}

function itemHtml(v, i, cur) {
  const n = `<span class="vi-num" aria-hidden="true">${i + 1}</span>`;
  if (vault.editing === v.id) {
    return `<li class="vi editing" data-id="${v.id}">${n}
      <input class="vi-input" type="text" value="${esc(v.name)}" maxlength="60" aria-label="${i + 1}번 양식의 새 이름">
      <button type="button" class="icon ok" data-act="rename-ok" aria-label="이름 저장" title="이름 저장">✓</button>
      <button type="button" class="icon" data-act="rename-cancel" aria-label="이름 바꾸기 취소" title="취소">✕</button></li>`;
  }
  if (vault.confirm === v.id) {
    return `<li class="vi confirm" data-id="${v.id}"><p>‘${esc(v.name)}’ 양식을 저장소에서 지울까요?</p>
      <div class="vi-ask"><button type="button" class="btn small danger" data-act="delete-ok">지우기</button>
      <button type="button" class="btn small ghost" data-act="delete-cancel">취소</button></div></li>`;
  }
  const on = cur && cur.id === v.id;
  return `<li class="vi${on ? " on" : ""}${vault.flash === v.id ? " flash" : ""}" data-id="${v.id}">
    <button type="button" class="vi-main" data-act="use"${on ? ' aria-current="true"' : ""} title="원래 파일: ${esc((v.files || [{ name: v.fileName }]).map((f) => f.name).join(", "))}">${n}
      <span class="vi-text"><span class="vi-name">${esc(v.name)}</span>
      <span class="vi-meta">${on ? "<b>사용\u00a0중</b> · " : ""}${v.files && v.files.length > 1 ? nb(`파일 ${v.files.length}개`) + " · " : ""}${nb(dateText(v.savedAt) + " 저장")} · ${nb(sizeText(v.size))}</span></span></button>
    <button type="button" class="icon" data-act="rename" aria-label="${esc(v.name)} 이름 바꾸기" title="이름 바꾸기">${PEN}</button>
    <button type="button" class="icon del" data-act="delete" aria-label="${esc(v.name)} 지우기" title="지우기">${BIN}</button></li>`;
}
function renderVault() {
  const cur = savedNow();
  const items = vault.items;
  $("vault").classList.toggle("empty", !items.length);
  $("vault-count").textContent = items.length ? `${items.length}개` : "";
  $("vault-empty").hidden = !vault.ok || items.length > 0;
  $("vault-list").innerHTML = items.map((v, i) => itemHtml(v, i, cur)).join("");
  vault.flash = null;
}
function renderItem(id) { // 한 항목만 다시 그린다(다른 항목을 누르는 중이면 그 단추가 그대로 남도록)
  const li = $("vault-list").querySelector(`[data-id="${id}"]`);
  const i = vault.items.findIndex((v) => v.id === id);
  if (li && i >= 0) li.outerHTML = itemHtml(vault.items[i], i, savedNow());
}
function setMode(editing, confirm) {
  const touched = new Set([vault.editing, vault.confirm, editing, confirm].filter((x) => x != null));
  vault.editing = editing;
  vault.confirm = confirm;
  touched.forEach(renderItem);
}
function focusItem(id, sel = ".vi-main") {
  const el = $("vault-list").querySelector(`[data-id="${id}"] ${sel}`);
  if (el) el.focus();
}
function syncSave() {
  const t = state.template;
  const hit = savedNow();
  const b = $("save-template");
  b.disabled = !vault.ok || !t || !!hit || vault.busy;
  b.classList.toggle("saved", !!hit);
  b.textContent = hit ? "✓ 저장됨" : vault.busy ? "저장 중…" : "+ 양식 저장";
  b.title = !vault.ok ? "이 브라우저에서는 양식을 저장할 수 없습니다"
    : !t ? "양식을 올리면 저장할 수 있습니다"
      : hit ? `양식 저장소 ${vault.items.indexOf(hit) + 1}번에 저장되어 있습니다` : "이 양식을 양식 저장소에 보관해 다음에도 씁니다";
}
function syncVault() { syncSave(); renderVault(); }

async function loadVault() {
  try {
    vault.items = await store.list();
    vault.ok = true;
  } catch (err) {
    console.warn("양식 저장소를 열지 못함:", err);
    vault.ok = false;
    vault.items = [];
    vaultMsg("이 브라우저에서는 양식을 저장할 수 없습니다(사이트 데이터 저장이 꺼져 있거나 사생활 보호 창일 수 있습니다).", true);
  }
  syncVault();
}

const channel = "BroadcastChannel" in self ? new BroadcastChannel("hwpx-yangsik-vault") : null;
if (channel) channel.onmessage = () => loadVault(); // 같은 사이트를 연 다른 창에서 저장·지움
function announce() { if (channel) channel.postMessage("changed"); }
let persistAsked = false;
function keepStorage() { // 저장 공간이 모자랄 때 브라우저가 먼저 지우지 않게 요청(브라우저가 정함)
  if (persistAsked || !navigator.storage || !navigator.storage.persist) return;
  persistAsked = true;
  navigator.storage.persisted().then((p) => p || navigator.storage.persist()).catch(() => {});
}
function uniqueName(base) {
  const names = new Set(vault.items.map((v) => v.name));
  base = base.trim().slice(0, 60) || "양식";
  let name = base;
  for (let k = 2; names.has(name); k++) name = `${base.slice(0, 54)} (${k})`;
  return name;
}

$("save-template").addEventListener("click", async () => {
  const t = state.template;
  if (!t || vault.busy || savedNow()) return;
  vault.busy = true;
  vaultMsg("");
  syncSave();
  try {
    vault.items = await store.list(); // 다른 창에서 같은 양식을 저장했을 수도 있다
    let rec = savedNow();
    if (!rec) {
      const bufs = [];
      for (const f of t.files) bufs.push(await f.arrayBuffer());
      // 파일 하나는 예전처럼 ArrayBuffer 하나로, 여러 개(묶음)는 배열로 보관한다
      rec = await store.add({ name: uniqueName(t.name), fileName: t.files[0].name,
        files: t.files.map((f) => ({ name: f.name, size: f.size })), size: bufs.reduce((n, b) => n + b.byteLength, 0),
        hash: t.hash, savedAt: Date.now(), picks: t.picks || null }, bufs.length === 1 ? bufs[0] : bufs);
      vault.items.push(rec);
      keepStorage();
      announce();
    }
    vault.flash = rec.id;
    vaultMsg(`‘${rec.name}’ 양식을 저장했습니다. 다음에는 양식 저장소에서 눌러 바로 쓸 수 있습니다.`);
  } catch (err) {
    vaultMsg(err && err.name === "QuotaExceededError"
      ? "저장 공간이 부족해 양식을 저장하지 못했습니다. 양식 저장소에서 쓰지 않는 양식을 지운 뒤 다시 눌러 주세요."
      : `양식을 저장하지 못했습니다: ${(err && err.message) || err}`, true);
  } finally {
    vault.busy = false;
    syncVault();
  }
});

async function useSaved(v) {
  setMode(null, null);
  const cur = savedNow();
  if (cur && cur.id === v.id && !$("template-card").hidden) { // 이미 쓰고 있는 양식
    $("step2").scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }
  vaultMsg("");
  try {
    const buf = await store.file(v.id);
    if (!buf) throw new Error("저장된 파일을 찾지 못했습니다. 목록에서 지우고 양식을 다시 저장해 주세요.");
    const bufs = Array.isArray(buf) ? buf : [buf];
    const names = v.files ? v.files.map((f) => f.name) : [v.fileName];
    await takeFile("template", bufs.map((b, i) => new File([b], names[i] || `양식${i + 1}.hwpx`)), v);
  } catch (err) {
    showError("template-error", String(err.message || err));
  }
}

async function finishRename(id, keep, refocus) {
  if (vault.editing !== id) return;
  const inp = $("vault-list").querySelector(`[data-id="${id}"] .vi-input`);
  const name = inp ? inp.value.trim().slice(0, 60) : "";
  const v = vault.items.find((x) => x.id === id);
  vault.editing = null;
  if (keep && v && name && name !== v.name) {
    try {
      await store.rename(id, name);
      v.name = name;
      announce();
      if ($("template-card").dataset.saved === String(id)) $("tmpl-name").textContent = name;
    } catch (err) {
      vaultMsg(`이름을 바꾸지 못했습니다: ${(err && err.message) || err}`, true);
    }
  }
  renderItem(id);
  syncSave();
  if (refocus) focusItem(id);
}

async function removeSaved(v) {
  vault.confirm = null;
  try {
    await store.remove(v.id);
    const i = vault.items.indexOf(v);
    vault.items = vault.items.filter((x) => x !== v);
    announce();
    if ($("template-card").dataset.saved === String(v.id)) {
      $("template-card").dataset.saved = "";
      const tag = $("tmpl-tag");
      if (tag) tag.remove();
    }
    vaultMsg(`‘${v.name}’ 양식을 지웠습니다.`);
    syncVault();
    const next = vault.items[Math.min(i, vault.items.length - 1)];
    if (next) focusItem(next.id); else $("vault-title").focus();
  } catch (err) {
    vaultMsg(`지우지 못했습니다: ${(err && err.message) || err}`, true);
    syncVault();
  }
}

const vlist = $("vault-list");
vlist.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-act]");
  if (!b) return;
  const id = +b.closest("[data-id]").dataset.id;
  const v = vault.items.find((x) => x.id === id);
  if (!v) return;
  const act = b.dataset.act;
  if (act === "use") useSaved(v);
  else if (act === "rename") {
    setMode(id, null);
    const inp = vlist.querySelector(`[data-id="${id}"] .vi-input`);
    if (inp) { inp.focus(); inp.select(); }
  } else if (act === "rename-ok") finishRename(id, true, true);
  else if (act === "rename-cancel") finishRename(id, false, true);
  else if (act === "delete") { setMode(null, id); focusItem(id, '[data-act="delete-cancel"]'); }
  else if (act === "delete-ok") removeSaved(v);
  else if (act === "delete-cancel") { setMode(null, null); focusItem(id); }
});
// 이름 칸의 ✓·✕를 누를 때 칸이 먼저 포커스를 잃어 '저장'되지 않게
vlist.addEventListener("mousedown", (e) => { if (e.target.closest(".vi.editing button")) e.preventDefault(); });
vlist.addEventListener("keydown", (e) => {
  if (!e.target.classList.contains("vi-input")) return;
  if (e.isComposing || e.keyCode === 229) return; // 한글 조합 중 Enter는 글자 확정용
  const id = +e.target.closest("[data-id]").dataset.id;
  if (e.key === "Enter") { e.preventDefault(); finishRename(id, true, true); }
  else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finishRename(id, false, true); }
});
vlist.addEventListener("focusout", (e) => { // 이름 칸 밖을 누르면 그대로 저장
  if (!e.target.classList.contains("vi-input")) return;
  const li = e.target.closest("[data-id]");
  if (e.relatedTarget && li.contains(e.relatedTarget)) return;
  finishRename(+li.dataset.id, true, false);
});
loadVault();

/* ---------------------------------------------------------------- 2. 문서 + 설문 */
function onDocument(name, data) {
  state.document = { name, data };
  const c = data["구성"];
  const asks = data["확인"] || [];
  const notes = (data["알림"] || []).map((n) => `<li>${esc(n)}</li>`).join("")
    + (asks.length ? `<li class="warn">문서에는 있는데 양식에 그 모양이 없는 것이 ${asks.length}가지 있습니다(${esc(asks.map((a) => a["키"]).join(", "))})
        — 변환 설정에서 어떻게 할지 여쭤봅니다.</li>` : "");
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
  setTemplateHeaderOption(data);
  syncTemplateQuestions();
  const big = data["큰 표"] || { "수": 0 };
  $("q-split").hidden = !(big["수"] > 0);  // 한 쪽보다 길 수 있는 표가 있을 때만 묻는다
  $("split-count").textContent = big["어림"] === false ? "(표가 있어 미리 여쭙니다)" : `(한 쪽을 넘는 표 ${big["수"]}개)`;
  renderExtra(asks);
  openSurvey();
}
/* 양식에 쪽 번호·머리말이 아예 없으면 그 질문은 묻지 않는다 — 만들 자리가 없는데 묻고서 안 만드는 일이 없게 */
function syncTemplateQuestions() {
  const s = (state.template && state.template.s) || {};
  const noHeader = s["머리말"] === undefined;
  const noPage = !s["쪽 번호"] && noHeader && s["꼬리말"] === undefined;
  $("q-header").hidden = noHeader;
  $("q-pn").hidden = noPage;
  const skipped = [noPage ? "쪽 번호" : "", noHeader ? "머리말" : ""].filter(Boolean);
  $("q-skipped").hidden = !skipped.length;
  $("q-skipped").textContent = skipped.length
    ? `양식에 ${skipped.join("·")}${skipped[skipped.length - 1] === "머리말" ? "이" : "가"} 없어 그 질문은 건너뜁니다(${skipped.join("·")} 없이 만듭니다).` : "";
}
/* 문서에는 있는데 양식에 그 모양이 없는 것(엔진이 만든 질문 '확인')을 설문 끝에 덧붙인다. 답은 options()의 '확인' {키: 값} */
function renderExtra(asks) {
  const first = $("q-split").hidden ? 5 : 6;
  $("q-extra").innerHTML = asks.map((a, i) => {
    const opts = a["선택"].map((c) => `<label><input type="radio" name="x${i}" value="${esc(c["값"])}"> ${esc(c["글"])}${
      c["값"] === a["기본"] ? ' <span class="rec">추천</span>' : ""}
      <span class="opt-desc">${esc(c["설명"] || "")}</span></label>`).join("");
    return `<fieldset class="extra" data-key="${esc(a["키"])}" data-no="${first + i}">
      <legend>${first + i}. ${esc(a["키"])} <small>(양식에 없는 모양)</small></legend>
      <p class="q-text">${esc(a["질문"])}</p><div class="opts col">${opts}</div></fieldset>`;
  }).join("");
}
/* 4-2 '양식에 있는 머리말 그대로': 양식 머리말(쪽 종류별)을 미리 보여 준다. 양식에 머리말이 없으면 고를 수 없게 */
function setTemplateHeaderOption(doc) {
  const s = (state.template && state.template.s) || {};
  const heads = (s["머리말 쪽"] || []).filter((h) => h["글자"]);
  const radio = $("header-template");
  radio.disabled = heads.length === 0;
  if (radio.disabled && radio.checked) radio.checked = false;
  $("header-template-preview").textContent = heads.length === 0 ? "양식에 머리말 글자가 없습니다"
    : heads.length === 1 ? `예: ${heads[0]["글자"]}`
    : "예: " + heads.map((h) => `${h["쪽"]} '${h["글자"]}'`).join(" · ");
  const chapters = doc && doc["구성"] ? doc["구성"]["장"] : 0;
  $("header-template-desc").textContent = chapters > 0
    ? `양식 머리말을 그대로 쓰고, 장 제목 자리만 문서의 장 제목(장 ${chapters}개)으로 바꿉니다.`
    : "양식 머리말을 그대로 씁니다(문서에 장이 없어 장 제목 자리도 양식 글자 그대로).";
}
function resetDocument() {
  state.document = null;
  state.result = null;
  $("document-card").hidden = true;
  $("drop-document").hidden = false;
  $("step2").classList.remove("done");
  $("done-card").hidden = true;
  $("q-extra").innerHTML = "";
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
  if ($("q-pn").hidden) { /* 양식에 쪽 번호 자리가 없음 — 묻지 않는다 */ }
  else if (!val("pn")) need.push("3");
  else if (val("pn") === "지정" && !(+$("pn-start").value >= 1)) need.push("3 시작 번호");
  if ($("q-header").hidden) { /* 양식에 머리말이 없음 — 묻지 않는다 */ }
  else if (!val("header")) need.push("4-1");
  else if (val("header") === "yes") {
    if (!val("headerMode")) need.push("4-2");
    else if (val("headerMode") === "manual" && !$("header-text").value.trim()) need.push("4-2 머리말 글자");
  }
  if (!$("q-split").hidden && !val("split")) need.push("5");
  $("q-extra").querySelectorAll("fieldset").forEach((f) => { if (!f.querySelector("input:checked")) need.push(f.dataset.no); });
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
    "쪽번호": { "방식": $("q-pn").hidden ? "없음" : val("pn"), "시작": val("pn") === "지정" ? +$("pn-start").value : 1 },
    "머리말": { "만들기": !$("q-header").hidden && val("header") === "yes",
              "글자": val("headerMode") === "manual" ? $("header-text").value.trim() : "",
              "방식": { manual: "직접", auto: "자동", template: "양식" }[val("headerMode")] || "자동" },
    "표": { "나누기": $("q-split").hidden ? "" : val("split") },
    "확인": Object.fromEntries([...$("q-extra").querySelectorAll("fieldset")]
      .map((f) => [f.dataset.key, (f.querySelector("input:checked") || {}).value || ""]).filter(([, v]) => v)),
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
    if (!m.res.ok) { showProblem("convert-error", m.res); return; }
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
  // 차례 쪽 번호: 상호 참조(쪽 번호)라 한글에서 파일을 열면 한글이 쪽을 계산해 채운다 — [참조 개수, 항목 개수]
  const [nRef, nAll] = made["차례 쪽 번호 참조"] || [0, 0];
  const tocNote = !made["차례"] ? ""
    : nAll && nRef === nAll ? `<li>차례 쪽 번호는 한글에서 파일을 열면 자동으로 채워집니다(제목·표·그림의 쪽이 바뀌어도 다시 열면 맞게 바뀝니다).</li>`
    : nRef ? `<li>차례 쪽 번호는 한글에서 파일을 열면 자동으로 채워집니다. 다만 ${nAll - nRef}개 항목은 비어 있으니 한글에서 확인해 주세요.</li>`
    : `<li>차례 쪽 번호를 비워 두었습니다 — 한글에서 열어 쪽을 확인해 주세요.</li>`;
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
  const checked = data["검증 실패"] !== null && data["검증 실패"] !== undefined;
  $("done-card").innerHTML = `
    <p class="done-msg">✓ 완성했습니다</p>
    <p style="margin:0">📥 <b>${esc(data["이름"])}</b> 파일을 <b>다운로드 폴더</b>에 저장했습니다.</p>
    <ul class="notes">
      <li>구성: ${esc(parts)}</li>
      <li>바뀐 번호·기호: ${data["바뀐 글자"]}곳 (글자는 그대로이고, 직접 친 번호를 양식 번호로 바꾼 곳 등)</li>
      ${data["지운 앞 빈칸"] ? `<li>문단 앞 빈칸을 지운 곳: ${data["지운 앞 빈칸"]}곳 (들여쓰기는 양식 본문 모양으로)</li>` : ""}
      <li>${ok ? "자동 검사: 문서 구조·글자 보존·서식 모두 통과" : checked ? `자동 검사에서 ${data["검증 실패"]}곳이 다릅니다 — 한글에서 열어 확인해 주세요` : "자동 검사를 끝내지 못했습니다 — 한글에서 열어 확인해 주세요"}</li>
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
