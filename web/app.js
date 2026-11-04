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
        // 양식은 여러 파일일 수 있다(앞표지·목차·본문 스타일 등) — 이름이 같아도 겹치지 않게 번호 폴더에
        const paths = m.list.map((f, i) => {
          const dir = m.type === "document" ? "/in" : `/in/t${i}`;
          py.FS.mkdirTree(dir);
          const path = dir + "/" + f.name.replace(/[\\/]/g, "_");
          py.FS.writeFile(path, new Uint8Array(f.bytes));
          return path;
        });
        args = [paths.length === 1 ? paths[0] : paths, "/work"];
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
    const m = await call(kind, { list }, list.map((x) => x.bytes));
    hideBusy();
    if (!m.res.ok) {
      // 양식 분석이 실패하면 엔진 쪽 양식도 이미 바뀌었으므로 화면의 양식도 비운다(다시 고르게)
      if (kind === "template" && state.template) resetTemplate();
      showError(errId, errorText(m.res));
      return;
    }
    if (kind === "template") onTemplate(files, m.res.data, hash, saved);
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
function onTemplate(files, data, hash, saved) {
  const s = data["요약"];
  const name = setName(files, s);
  state.template = { name, s, files, hash }; // files는 [+ 양식 저장]·파일 더하기 때 다시 읽는다
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
    <ul class="chips">${chips}</ul>
    <p class="hint" style="margin:6px 0 0">${font}${!s["부분"]["표지"] || !s["부분"]["차례"] ? " · 양식에 없는 표지·차례는 필요하면 간단한 모양으로 만들어 드려요." : ""}</p>
    ${notes ? `<ul class="notes">${notes}</ul>` : ""}`;
  $("template-card").hidden = false;
  $("drop-template").hidden = true;
  $("step1").classList.add("done");
  $("tmpl-change").addEventListener("click", resetTemplate);
  $("tmpl-add").addEventListener("click", () => { state.kind = "template-add"; openImport(); });
  lock("step2", false);
  resetDocument();
  syncVault();
  $("drop-document").focus();
}
function resetTemplate() {
  state.template = null;
  $("template-card").hidden = true;
  $("drop-template").hidden = false;
  $("step1").classList.remove("done");
  lock("step2", true);
  resetDocument();
  syncVault();
}

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
        hash: t.hash, savedAt: Date.now() }, bufs.length === 1 ? bufs[0] : bufs);
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
