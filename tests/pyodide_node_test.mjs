// 브라우저 안 파이썬(Pyodide)과 같은 환경에서 엔진을 돌려 본다(Node.js).
// 사용: node tests/pyodide_node_test.mjs <pyodide 폴더(node_modules/pyodide)> <양식.hwpx> <문서.hwpx|.docx> <결과 폴더> [설문 JSON]
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const [pyoDir, tmpl, doc, outDir, optJson] = process.argv.slice(2);
const { loadPyodide } = await import(pathToFileURL(path.join(pyoDir, "pyodide.mjs")).href);
const t0 = Date.now();
const py = await loadPyodide({ indexURL: pyoDir + path.sep });
await py.loadPackage("lxml");
console.log(`Pyodide ${py.version} + lxml 준비 ${(Date.now() - t0) / 1000}s`);

const engine = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "engine");
py.FS.mkdirTree("/app/engine");
for (const f of fs.readdirSync(engine).filter((n) => n.endsWith(".py"))) {  // 웹 묶음(build_web.py)과 같은 엔진 파일들
  py.FS.writeFile(`/app/engine/${f}`, fs.readFileSync(path.join(engine, f)));
}
py.FS.mkdirTree("/in");
const tName = "양식" + path.extname(tmpl), dName = path.basename(doc);
py.FS.writeFile(`/in/${tName}`, fs.readFileSync(tmpl));
py.FS.writeFile(`/in/${dName}`, fs.readFileSync(doc));
const opts = optJson || JSON.stringify({ 표지: { 만들기: true }, 차례: { 만들기: true }, 쪽번호: { 방식: "본문부터" }, 머리말: { 만들기: true } });
py.globals.set("OPTS", opts);
py.globals.set("T", `/in/${tName}`);
py.globals.set("D", `/in/${dName}`);
const t1 = Date.now();
const res = py.runPython(`
import sys, json
sys.path.insert(0, "/app/engine")
import service
a = service.analyze_template(T, "/work")
b = service.inspect_document(D, "/work")
c = service.convert("/work", json.loads(OPTS))
json.dumps({"양식": a["요약"]["부분"], "원고": b, "결과": c}, ensure_ascii=False)
`);
console.log(`변환 ${(Date.now() - t1) / 1000}s`);
const r = JSON.parse(res);
console.log(JSON.stringify({ 양식: r.양식, 원고: r.원고.구성, 자동제목: r.원고["자동 제목"], 큰표: r.원고["큰 표"], 검증실패: r.결과["검증 실패"],
  구성: r.결과.구성, 표나눔: r.결과["표 나눔"], 알림: r.결과.알림.slice(0, 3) }, null, 1));
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, r.결과.이름), py.FS.readFile(r.결과.파일));
console.log("저장:", path.join(outDir, r.결과.이름));
