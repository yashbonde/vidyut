// Engine helper for `check_dcs_tinanta_coverage.py`.
//
// Loads a vidyut-prakriya WASM build (the `pkg/` directory produced by
// `make wasm_release`, which contains `vidyut_prakriya.js` and
// `vidyut_prakriya_bg.wasm`) and answers derivation requests over stdin and
// stdout. Each input line is a JSON array of requests. Each output line is a
// JSON array with one entry per request: a list of derived SLP1 strings, or
// `null` if the derivation threw.
//
// Request shapes:
//
//     {"k": "dhatu", "d": DHATU}
//     {"k": "tin", "d": DHATU, "l": LAKARA, "p": PRAYOGA, "pu": PURUSHA,
//      "v": VACANA, "s": SKIP_AT_AGAMA}
//
// where DHATU is {"aupadeshika", "gana", "antargana", "sanadi", "prefixes"}
// as accepted by `Vidyut.deriveDhatus` and `Vidyut.deriveTinantas`.
//
// Usage: node dcs_tinanta_wasm_engine.mjs PKG_DIR

import fs from "fs";
import path from "path";
import readline from "readline";

const pkgDir = process.argv[2];
if (!pkgDir) {
  console.error("usage: node dcs_tinanta_wasm_engine.mjs PKG_DIR");
  process.exit(2);
}

// Import the wasm-bindgen glue as a data URL so that it loads as an ES module
// regardless of its file extension or any surrounding package.json. A Rust
// panic can leave a WASM instance in a bad state, so after any exception we
// load a fresh instance (the counter makes each data URL distinct).
const glue = fs.readFileSync(path.join(pkgDir, "vidyut_prakriya.js"), "utf8");
const wasmBytes = fs.readFileSync(path.join(pkgDir, "vidyut_prakriya_bg.wasm"));
let generation = 0;
async function load() {
  generation += 1;
  const src = glue + `\n// instance ${generation}\n`;
  const mod = await import(
    "data:text/javascript;base64," + Buffer.from(src).toString("base64")
  );
  mod.initSync({ module: wasmBytes });
  return mod.Vidyut.init();
}
let vidyut = await load();

// The Rust side logs derivation errors to the console. Keep stdout clean.
console.error = () => {};
console.warn = () => {};

function run(req) {
  try {
    let ret;
    if (req.k === "dhatu") {
      ret = vidyut.deriveDhatus(req.d);
    } else {
      ret = vidyut.deriveTinantas({
        dhatu: req.d,
        lakara: req.l,
        prayoga: req.p,
        purusha: req.pu,
        vacana: req.v,
        skip_at_agama: !!req.s,
        pada: null,
      });
    }
    return [...new Set(ret.map((x) => x.text))].sort();
  } catch (e) {
    needsReload = true;
    return null;
  }
}

let needsReload = false;

const rl = readline.createInterface({ input: process.stdin, terminal: false });
for await (const line of rl) {
  if (!line.trim()) continue;
  const reqs = JSON.parse(line);
  const out = [];
  for (const req of reqs) {
    out.push(run(req));
    if (needsReload) {
      vidyut = await load();
      needsReload = false;
    }
  }
  process.stdout.write(JSON.stringify(out) + "\n");
}
