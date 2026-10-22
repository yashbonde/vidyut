// Batch subanta engine for `check_dcs_subanta_coverage.py`.
//
// Usage:
//
//     node dcs_subanta_engine.mjs <glue.js> <glue_bg.wasm> <requests.jsonl> <results.jsonl>
//
// `<glue.js>` and `<glue_bg.wasm>` are the files produced by `wasm-pack build
// --target web` for vidyut-prakriya (see `vidyut-prakriya/www` and the
// `wasm.rs` bindings). Each input line is a JSON object
//
//     {"p": <PratipadikaArgs>, "l": <Linga>, "vi": <Vibhakti>, "va": <Vacana>}
//
// and each output line is either a JSON array of distinct derived forms
// (SLP1, sorted) or `{"error": "..."}`.
//
// `wasm.rs` silently replaces a malformed pratipadika object with the
// placeholder stem "doza", so every request is validated here before it
// reaches the engine. A Rust panic surfaces as a thrown exception and is
// reported as an error for that request only.

import fs from "fs";
import path from "path";
import { pathToFileURL } from "url";

const [gluePath, wasmPath, reqPath, outPath] = process.argv.slice(2);
if (!outPath) {
  console.error("usage: node dcs_subanta_engine.mjs <glue.js> <glue_bg.wasm> <requests.jsonl> <results.jsonl>");
  process.exit(2);
}

// Some builds log to the console from Rust. Keep stdout clean.
console.log = (...args) => console.error(...args);

async function loadGlue(p) {
  try {
    return await import(pathToFileURL(path.resolve(p)).href);
  } catch (e) {
    // A `.js` file outside an ES-module package may not be detected as ESM by
    // older Node versions. Fall back to a data URL import.
    const src = fs.readFileSync(p, "utf8");
    return await import("data:text/javascript;base64," + Buffer.from(src).toString("base64"));
  }
}

const glue = await loadGlue(gluePath);
glue.initSync({ module: fs.readFileSync(wasmPath) });
const vidyut = glue.Vidyut.init();

const LINGAS = new Set(["Pum", "Stri", "Napumsaka"]);
const VIBHAKTIS = new Set(["Prathama", "Dvitiya", "Trtiya", "Caturthi", "Panchami", "Sasthi", "Saptami", "Sambodhana"]);
const VACANAS = new Set(["Eka", "Dvi", "Bahu"]);
const SLOTS = ["basic", "nyap", "krdanta", "taddhitanta"];

function validate(req) {
  const p = req.p;
  if (!p || typeof p !== "object") return "missing pratipadika";
  const keys = Object.keys(p).sort().join(",");
  if (keys !== "basic,krdanta,nyap,taddhitanta") return "pratipadika must have exactly basic, nyap, krdanta, taddhitanta";
  const set = SLOTS.filter((k) => p[k] !== null);
  if (set.length !== 1) return "exactly one pratipadika slot must be non-null";
  if ((set[0] === "basic" || set[0] === "nyap") && !/^[a-zA-Z|'~\\^]+$/.test(p[set[0]])) return "bad stem text";
  if (!LINGAS.has(req.l) || !VIBHAKTIS.has(req.vi) || !VACANAS.has(req.va)) return "bad linga/vibhakti/vacana";
  return null;
}

const lines = fs.readFileSync(reqPath, "utf8").split("\n").filter((x) => x.length > 0);
const out = [];
for (const line of lines) {
  const req = JSON.parse(line);
  const err = validate(req);
  if (err) {
    out.push(JSON.stringify({ error: err }));
    continue;
  }
  try {
    const res = vidyut.deriveSubantas({ pratipadika: req.p, linga: req.l, vibhakti: req.vi, vacana: req.va });
    const forms = [...new Set(res.map((x) => x.text))].sort();
    out.push(JSON.stringify(forms));
  } catch (e) {
    out.push(JSON.stringify({ error: String(e).slice(0, 200) }));
  }
}
fs.writeFileSync(outPath, out.join("\n") + "\n");
