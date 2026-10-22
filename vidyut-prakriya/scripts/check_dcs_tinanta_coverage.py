#!/usr/bin/env python3
"""Check vidyut-prakriya's tinanta generation against the finite verbs of the DCS.

The Digital Corpus of Sanskrit (DCS, Oliver Hellwig, CC BY 4.0,
https://github.com/OliverHellwig/sanskrit) annotates every finite verb with
its lemma, person, number, tense, mood and (sometimes) voice. This script
collects the distinct finite verb items of the corpus, maps each DCS lemma to
one or more entries of `data/dhatupatha.tsv` (plus upasargas and sanadi
pratyayas), derives the matching forms with vidyut-prakriya, and reports how
many attested tokens and types vidyut can produce.

An attested item counts as covered if ANY candidate dhatu entry, with the
default pada behavior, produces the attested form in one of the lakaras
allowed by the DCS tag. Misses are then sorted into rough buckets for review.

Usage:

    # 1. Build the WASM engine (or use any existing `pkg/` build).
    make wasm_release        # creates vidyut-prakriya/pkg/

    # 2. Run the check against the DCS CoNLL-U dump.
    python3 scripts/check_dcs_tinanta_coverage.py \\
        PATH/TO/sanskrit/dcs/data/conllu \\
        --engine wasm --wasm-pkg pkg \\
        --out-dir /tmp/dcs-tinanta

The CoNLL-U path may point at `dcs/data/conllu` (which contains `files/` and
`lookup/`) or at `dcs/data/conllu/files`. The `lookup/` directory is needed
for preverbs (`dictionary.csv`) and for time slots (`chapter-info.xml`).

Engines:

- `--engine wasm` (default) runs `scripts/dcs_tinanta_wasm_engine.mjs` under
  Node 18 or later against the `pkg/` directory given by `--wasm-pkg`.
- `--engine python` uses `vidyut.prakriya` from `bindings-python` (install it
  with `maturin develop` or `pip install vidyut`).

Outputs (in `--out-dir`):

- `summary.json`: all headline numbers and breakdowns.
- `covered.tsv`: every covered item.
- `misses.tsv`: every missed item with its bucket.
- `corpus_sample.tsv`: a deterministic sample of covered items in the
  `tests/data/rv_let_corpus.tsv` style (written to `--sample-tsv` if given).

To regenerate the checked-in regression data, add
`--sample-tsv tests/data/dcs_tinanta_corpus.tsv`.

The script uses only the Python standard library and is deterministic: files
are read in sorted order, and every output is sorted.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PRAKRIYA = SCRIPTS.parent

# ---------------------------------------------------------------------------
# Transliteration
# ---------------------------------------------------------------------------

_IAST_MULTI = [
    ("ai", "E"), ("au", "O"),
    ("kh", "K"), ("gh", "G"), ("ch", "C"), ("jh", "J"),
    ("ṭh", "W"), ("ḍh", "Q"), ("th", "T"), ("dh", "D"),
    ("ph", "P"), ("bh", "B"),
]
_IAST_SINGLE = {
    "ā": "A", "ī": "I", "ū": "U", "ṛ": "f", "ṝ": "F", "ḷ": "x", "ḹ": "X",
    "ṃ": "M", "ṁ": "M", "ḥ": "H", "ṅ": "N", "ñ": "Y", "ṭ": "w", "ḍ": "q",
    "ṇ": "R", "ś": "S", "ṣ": "z",
    # The DCS dump writes vocalic l as U+FFB1 in some lemmas (kﾱp = kxp).
    "\uffb1": "x",
}
_SLP1_TO_IAST = {v: k for k, v in _IAST_MULTI}
_SLP1_TO_IAST.update({v: k for k, v in _IAST_SINGLE.items() if k not in ("ṁ", "\uffb1")})
SLP1_LETTERS = set("aAiIuUfFxXeEoOMHkKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh")
VOWELS = set("aAiIuUfFxXeEoO")


def iast_to_slp1(s: str) -> str:
    s = unicodedata.normalize("NFC", s.strip().lower())
    s = s.replace("'", "").replace("’", "")
    out = []
    i = 0
    while i < len(s):
        two = s[i : i + 2]
        hit = next((v for k, v in _IAST_MULTI if two == k), None)
        # "ai"/"au" are ambiguous only in hiatus, which DCS writes with a
        # separator, so a greedy match is safe here.
        if hit:
            out.append(hit)
            i += 2
            continue
        out.append(_IAST_SINGLE.get(s[i], s[i]))
        i += 1
    return "".join(out)


def slp1_to_iast(s: str) -> str:
    return "".join(_SLP1_TO_IAST.get(c, c) for c in s)


def is_slp1(s: str) -> bool:
    return bool(s) and all(c in SLP1_LETTERS for c in s)


# ---------------------------------------------------------------------------
# DCS reading
# ---------------------------------------------------------------------------

PERSON = {"1": "Uttama", "2": "Madhyama", "3": "Prathama"}
NUMBER = {"Sing": "Eka", "Dual": "Dvi", "Plur": "Bahu"}
NUMBER_DIGIT = {"Sing": "1", "Dual": "2", "Plur": "3"}

# (Tense, Mood) -> list of (lakara, skip_at_agama). `Formation` only refines
# the aorist and future types and does not change the allowed set.
TAGS = {
    ("Pres", "Ind"): [("Lat", False)],
    ("Pres", "Opt"): [("VidhiLin", False)],
    ("Pres", "Imp"): [("Lot", False)],
    ("Impf", "Ind"): [("Lan", False)],
    # DCS `Past` covers the perfect and the aorist (and, in older
    # annotation, some imperfects).
    ("Past", "Ind"): [("Lit", False), ("Lun", False), ("Lan", False)],
    ("Fut", "Ind"): [("Lrt", False), ("Lut", False)],
    ("Fut", "Cond"): [("Lrn", False)],
    ("Past", "Prec"): [("AshirLin", False)],
    # Subjunctive = leT.
    ("Pres", "Sub"): [("Let", False)],
    ("Past", "Sub"): [("Let", False)],
    # Injunctive = augmentless lan/lun (6.4.74 and 6.4.75).
    ("Pres", "Jus"): [("Lan", True), ("Lun", True)],
    ("Past", "Jus"): [("Lun", True), ("Lan", True)],
    # Vedic categories with no single Paninian lakara. We still try the
    # nearest ones and report them separately.
    ("Past", "Imp"): [("Lot", False)],
    ("Past", "Opt"): [("AshirLin", False), ("VidhiLin", False)],
    ("Plp", "Ind"): [("Lan", False), ("Lun", False), ("Lit", False)],
    ("Pqp", "Ind"): [("Lan", False), ("Lun", False), ("Lit", False)],
    ("Fut", "Pot"): [("VidhiLin", False)],
}
VEDIC_ONLY_TAGS = {("Past", "Imp"), ("Past", "Opt"), ("Plp", "Ind"), ("Pqp", "Ind"),
                   ("Fut", "Pot"), ("Pres", "Sub"), ("Past", "Sub"),
                   ("Pres", "Jus"), ("Past", "Jus")}
ALL_LAKARAS = ["Lat", "Lit", "Lut", "Lrt", "Let", "Lot", "Lan", "VidhiLin",
               "AshirLin", "Lun", "Lrn"]

TIME_SLOTS = {
    "1": "1 Vedic",
    "2": "2 Epic and early classical",
    "3": "3 Classical",
    "4": "4 Medieval",
    "5": "5 Late",
}


def parse_feats(s: str) -> dict:
    return dict(x.split("=", 1) for x in s.split("|") if "=" in x)


def find_dirs(path: Path) -> tuple[Path, Path]:
    if (path / "files").is_dir():
        return path / "files", path / "lookup"
    if path.name == "files":
        return path, path.parent / "lookup"
    raise SystemExit(f"Could not find `files/` under {path}")


def load_dictionary(lookup: Path) -> dict:
    """lemma id -> (lemma, grammar, preverbs)."""
    out = {}
    with open(lookup / "dictionary.csv", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for row in reader:
            if len(row) < 4:
                continue
            out[row[0]] = (row[1], row[2], row[3])
    return out


def load_time_slots(lookup: Path) -> dict:
    """chapter file path relative to files/ -> time slot."""
    path = lookup / "chapter-info.xml"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"<chapter>(.*?)</chapter>", text, re.S):
        body = m.group(1)
        p = re.search(r"<path>(.*?)</path>", body)
        t = re.search(r"<dcsTimeSlot>(.*?)</dcsTimeSlot>", body)
        if p:
            out[unicodedata.normalize("NFC", p.group(1))] = t.group(1) if t else ""
    return out


def read_items(files_dir: Path, time_slots: dict, limit: int = 0):
    """Yield one record per finite verb token."""
    paths = sorted(files_dir.glob("*/*.conllu"),
                   key=lambda p: unicodedata.normalize("NFC", str(p.relative_to(files_dir))))
    if limit:
        paths = paths[:limit]
    for path in paths:
        rel = unicodedata.normalize("NFC", f"{path.parent.name}/{path.name}")
        slot = time_slots.get(rel, "")
        chapter = ""
        sent_id = ""
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    if line.startswith("## chapter:"):
                        chapter = line.split(":", 1)[1].strip()
                    elif line.startswith("# sent_id"):
                        sent_id = line.split("=", 1)[1].strip()
                    continue
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 10 or not cols[0].isdigit() or cols[3] != "VERB":
                    continue
                feats = parse_feats(cols[5])
                if "Person" not in feats:
                    continue
                misc = parse_feats(cols[9])
                yield {
                    "chapter": chapter,
                    "sent_id": sent_id,
                    "pos": cols[0],
                    "form": cols[1],
                    "unsandhied": misc.get("Unsandhied", ""),
                    "lemma": cols[2],
                    "lemma_id": misc.get("LemmaId", ""),
                    "feats": feats,
                    "slot": slot,
                }


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------


class WasmEngine:
    def __init__(self, pkg: Path):
        helper = SCRIPTS / "dcs_tinanta_wasm_engine.mjs"
        self.proc = subprocess.Popen(
            ["node", str(helper), str(pkg)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def run(self, reqs: list) -> list:
        out = []
        for i in range(0, len(reqs), 500):
            chunk = reqs[i : i + 500]
            self.proc.stdin.write(json.dumps(chunk) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("WASM engine exited")
            out.extend(json.loads(line))
        return out

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()


class PythonEngine:
    def __init__(self):
        from vidyut import prakriya as vp  # type: ignore

        self.vp = vp
        self.v = vp.Vyakarana()

    def _dhatu(self, d):
        vp = self.vp
        kw = {}
        if d.get("antargana"):
            kw["antargana"] = getattr(vp.Antargana, d["antargana"])
        if d.get("prefixes"):
            kw["prefixes"] = list(d["prefixes"])
        if d.get("sanadi"):
            kw["sanadi"] = [getattr(vp.Sanadi, s) for s in d["sanadi"]]
        return vp.Dhatu.mula(d["aupadeshika"], getattr(vp.Gana, d["gana"]), **kw)

    def run(self, reqs: list) -> list:
        vp = self.vp
        out = []
        for r in reqs:
            try:
                dhatu = self._dhatu(r["d"])
                if r["k"] == "dhatu":
                    ps = self.v.derive(dhatu)
                else:
                    ps = self.v.derive(
                        vp.Pada.Tinanta(
                            dhatu=dhatu,
                            prayoga=getattr(vp.Prayoga, r["p"]),
                            lakara=getattr(vp.Lakara, r["l"]),
                            purusha=getattr(vp.Purusha, r["pu"]),
                            vacana=getattr(vp.Vacana, r["v"]),
                            skip_at_agama=bool(r["s"]),
                        )
                    )
                out.append(sorted({p.text for p in ps}))
            except Exception:
                out.append(None)
        return out

    def close(self):
        pass


class CachedEngine:
    def __init__(self, engine):
        self.engine = engine
        self.cache = {}

    @staticmethod
    def key(r):
        return json.dumps(r, sort_keys=True)

    def run(self, reqs):
        todo = []
        seen = set()
        for r in reqs:
            k = self.key(r)
            if k not in self.cache and k not in seen:
                seen.add(k)
                todo.append(r)
        if todo:
            for r, res in zip(todo, self.engine.run(todo)):
                self.cache[self.key(r)] = res
        return [self.cache[self.key(r)] for r in reqs]


# ---------------------------------------------------------------------------
# Dhatupatha and lemma mapping
# ---------------------------------------------------------------------------

GANAS = {
    "01": "Bhvadi", "02": "Adadi", "03": "Juhotyadi", "04": "Divadi",
    "05": "Svadi", "06": "Tudadi", "07": "Rudhadi", "08": "Tanadi",
    "09": "Kryadi", "10": "Curadi",
}


def antargana(gana: str, number: int):
    # Mirrors `maybe_find_antargana` in src/dhatupatha.rs.
    if gana == "Bhvadi" and 867 <= number <= 932:
        return "Ghatadi"
    if gana == "Tudadi" and 93 <= number <= 137:
        return "Kutadi"
    if gana == "Curadi" and 192 <= number <= 236:
        return "Akusmiya"
    if gana == "Curadi" and 279 <= number <= 337:
        return "Asvadiya"
    if gana == "Curadi" and 338 <= number <= 388:
        return "Adhrshiya"
    return None


# Prefixes that `create_dhatu` in src/dhatupatha.rs adds implicitly.
REQUIRED_PREFIX = {"i\\N": "aDi", "i\\k": "aDi", "SAsu~\\": "AN"}


def load_dhatupatha(path: Path) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 2 or cols[1] == "-":
                continue
            code, aup = cols[0], cols[1]
            g, n = code.split(".")
            gana = GANAS.get(g)
            if not gana:
                continue
            req = REQUIRED_PREFIX.get(aup)
            if aup == "za\\da~" and gana == "Curadi":
                req = "AN"
            rows.append({
                "code": code,
                "aupadeshika": aup,
                "gana": gana,
                "antargana": antargana(gana, int(n)),
                "required_prefix": req,
            })
    return rows


def dhatu_args(row, prefixes=(), sanadi=()):
    return {
        "aupadeshika": row["aupadeshika"],
        "gana": row["gana"],
        "antargana": row["antargana"],
        "sanadi": list(sanadi),
        "prefixes": list(prefixes),
    }


def tin_req(row, prefixes, sanadi, lakara, prayoga, purusha, vacana, skip):
    return {"k": "tin", "d": dhatu_args(row, prefixes, sanadi), "l": lakara,
            "p": prayoga, "pu": purusha, "v": vacana, "s": skip}


def strip_upadesha(aup: str) -> str:
    """Rough it-removal, used only for the Aya/IyaN/RiN roots above."""
    s = aup.replace("\\", "").replace("^", "")
    s = re.sub(r"^(Yi|wu|qu)", "", s)
    s = re.sub(r"[aAiIuUfFxeEoO]~.*$", "", s)
    return s


def build_root_index(rows, engine) -> dict:
    """Maps a DCS-style root string (SLP1) to a list of (row index, sanadi)."""
    index = collections.defaultdict(set)

    def base_prefixes(row):
        return [row["required_prefix"]] if row["required_prefix"] else []

    # The dhatu text is derived without prefixes, so that i\N gives "i".
    reqs = [{"k": "dhatu", "d": dhatu_args(r)} for r in rows]
    row_texts = collections.defaultdict(set)
    for i, res in enumerate(engine.run(reqs)):
        for text in res or []:
            index[text].add((i, ()))
            row_texts[i].add(text)
            # Roots whose dhatu text already includes Aya, IyaN, RiN or Ric
            # (gopAya, kAmi, cori): also index the bare root (gup, kam, cur).
            if (text.endswith(("Aya", "Iya")) or text in ("kAmi",)
                    or rows[i]["gana"] == "Curadi"):
                bare = strip_upadesha(rows[i]["aupadeshika"])
                if bare and bare != text:
                    index[bare].add((i, ()))
            index[norm_key(text)].add((i, ()))

    # Stems that DCS lists as lemmas: curadi and Aya/IyaN stems (coray,
    # gopAy, ftIy), causatives (darSay), desideratives (didfkz) and
    # intensives (darIdfS).
    plans = [((), "Eka"), (("Ric",), "Eka"), (("san",), "Eka"),
             (("yaN",), "Eka"), (("yaNluk",), "Bahu")]
    reqs = []
    meta = []
    for i, r in enumerate(rows):
        for sanadi, vacana in plans:
            reqs.append(tin_req(r, base_prefixes(r), sanadi, "Lat", "Kartari",
                                "Prathama", vacana, False))
            meta.append((i, sanadi))
    for (i, sanadi), res in zip(meta, engine.run(reqs)):
        if base_prefixes(rows[i]):
            continue
        texts = row_texts[i]
        for form in res or []:
            stems = []
            if sanadi == ():
                if rows[i]["gana"] == "Curadi" or re.search(r"(Aya|Iya)t[ie]$", form):
                    if form.endswith(("ayati", "ayate", "Iyati", "Iyate")):
                        stems.append(form[:-3])
                # Roots with a built-in san (3.1.5, 3.1.6): jugups, titikz,
                # cikits, mImAMs.
                stem = form[:-3]
                if (form.endswith(("ati", "ate")) and stem[-1:] in ("s", "z")
                        and not any(t[-1:] in ("s", "z") for t in texts)):
                    stems.append(stem)
            elif sanadi == ("yaN",):
                if form.endswith("yate"):
                    stems.append(form[:-4])
            elif form.endswith(("ati", "ate")):
                stems.append(form[:-3])
            for s in stems:
                index[s].add((i, sanadi))
                index[norm_key(s)].add((i, sanadi))
    # Citation conventions: DCS cites roots in E/e/O by their A form (gE as
    # gA, hve as hvA, 6.1.45) and some F roots with f (tF as tf).
    for k in list(index):
        if k[-1:] in ("E", "e", "O", "o") and len(k) > 1:
            index[k[:-1] + "A"] |= index[k]
        if k.endswith("F"):
            index[k[:-1] + "f"] |= index[k]
    # DCS often cites nasal-infix roots without the nasal (svaj for svaYj,
    # daB for damB).
    for k in list(index):
        m = re.match(r"^(.*[aAiIuUfF])[NYRnmM]([^aAiIuUfFeEoO])$", k)
        if m:
            index[m.group(1) + m.group(2)] |= index[k]
    # DCS lemmas for suppletive stems.
    for alias, target in LEMMA_ALIASES.items():
        for t in target:
            index[alias] |= index.get(t, set())
    return {k: sorted(v) for k, v in index.items() if v}


# Upasargas and gatis that DCS folds into lemmas, with their sandhi surface
# variants before a following consonant or vowel.
PREFIX_VARIANTS = {
    "pra": ["pra"], "parA": ["parA"], "apa": ["apa"], "anu": ["anu"],
    "ava": ["ava"], "vi": ["vi"], "AN": ["A"], "ni": ["ni", "Ri"], "aDi": ["aDi"],
    "api": ["api"], "ati": ["ati"], "su": ["su"], "aBi": ["aBi"],
    "prati": ["prati"], "pari": ["pari"], "upa": ["upa"],
    "sam": ["sam", "saM", "saY", "san", "saR", "saN", "saMs", "sams"],
    "ud": ["ud", "ut", "uc", "uj", "ul", "un", "ug", "ub", "uq"],
    "nis": ["nis", "nir", "niH", "niz", "niS", "nI"],
    "dus": ["dus", "dur", "duH", "duz", "duS", "dU"],
    "antar": ["antar", "antaH", "antas", "antaz", "antaS"],
    "alam": ["alam", "alaM", "alaN"],
    "namas": ["namas", "namaH", "namaz", "namaS"],
    "Avis": ["Avis", "Avir", "AviH", "Aviz", "AviS"],
    "prAdus": ["prAdus", "prAdur", "prAduH", "prAduz"],
    "puras": ["puras", "puraH", "puraz", "puro"],
    "tiras": ["tiras", "tiraH", "tiraz", "tiro"],
    "astam": ["astam", "astaM", "astaN"],
    # Other gatis (1.4.61 UryAdi, 1.4.63 sat, 1.4.69 acCa, 1.4.74 sAkzAt).
    "sat": ["sat", "sad"],
    "acCa": ["acCA", "acCa"],
    "sAkzAt": ["sAkzAt", "sAkzAd"],
    "Srat": ["Srad", "Srat"],
    "vazaw": ["vazaw", "vazaq"],
    "svAhA": ["svAhA"],
    "svaDA": ["svaDA"],
}
# Prefixes outside the 22 upasargas. Coverage that depends on them is
# reported separately, since vidyut accepts such prefixes as given.
GATI = {"antar", "alam", "namas", "Avis", "prAdus", "puras", "tiras", "astam",
        "sat", "acCa", "sAkzAt", "Srat", "vazaw", "svAhA", "svaDA"}
# Merged-vowel spellings: prefix-final vowel + next initial vowel.
UNMERGE = {"A": ["a", "A"], "e": ["i", "I"], "o": ["u", "U"], "E": ["e", "E"],
           "O": ["o", "O"], "I": ["i", "I"], "U": ["u", "U"]}


def prefix_surfaces(p):
    """(surface, mode) pairs. mode: '' plain, 'y' glide, 'm' merged vowel."""
    out = [(s, "") for s in PREFIX_VARIANTS[p]]
    base = PREFIX_VARIANTS[p][0]
    last = base[-1]
    if last in "iI":
        out.append((base[:-1] + "y", "y"))
        out.append((base[:-1], "m"))
    elif last in "uU":
        out.append((base[:-1] + "v", "y"))
        out.append((base[:-1], "m"))
    elif last in "aA":
        out.append((base[:-1], "m"))
    return out


def root_initial_variants(rest: str, prev_surface: str):
    """Undo common changes to a root's first sounds after a prefix."""
    out = {rest}
    if rest[:1] == "z":
        out.add("s" + rest[1:])
        if rest[1:2] == "W":
            out.add("sT" + rest[2:])
        if rest[1:2] == "w":
            out.add("st" + rest[2:])
    if rest[:1] == "R":
        out.add("n" + rest[1:])
    if "R" in rest[1:]:
        # pra + an -> prAR (8.4.19)
        out.add(rest[0] + rest[1:].replace("R", "n", 1))
    if prev_surface in ("ud", "ut"):
        # ud + sTA -> utTA, ud + stamB -> uttamB, ud + h -> udD
        if rest[:1] in "Tt":
            out.add("s" + rest)
        if rest[:1] == "D":
            out.add("h" + rest[1:])
        if rest[:1] == "C":
            out.add("S" + rest[1:])
    if prev_surface.endswith("z") and rest[:1] in "wW":
        # nis + tap -> nizwap
        out.add({"w": "t", "W": "T"}[rest[0]] + rest[1:])
    if prev_surface.endswith(("c", "j")) and rest[:1] == "C":
        out.add("S" + rest[1:])
    return out


def norm_key(s: str) -> str:
    """Loose spelling key: nasals before stops become M, and cC becomes C
    (DCS often writes cicheda for cicCeda)."""
    s = s.replace("cC", "C").replace("jJ", "J")
    return re.sub(r"[NYRnmM](?=[kKgGcCjJwWqQtTdDpPbB])", "M", s)


def decompose(lemma: str, index: dict):
    """Yield (prefixes, root_string, index_entries) splits of `lemma`."""
    seen = set()

    def rec(s, prefixes, prev_surface):
        if prefixes:
            for r in sorted(root_initial_variants(s, prev_surface)):
                for k in sorted({r, norm_key(r)}):
                    if k in index:
                        key = (tuple(prefixes), k)
                        if key not in seen:
                            seen.add(key)
                            yield tuple(prefixes), k, index[k]
        elif s in index:
            key = ((), s)
            if key not in seen:
                seen.add(key)
                yield (), s, index[s]
        if len(prefixes) >= 3:
            return
        for p in PREFIX_VARIANTS:
            for surf, mode in prefix_surfaces(p):
                # Only AN can vanish entirely into a merged vowel (A + i = e).
                if not surf and not (p == "AN" and mode == "m"):
                    continue
                if not s.startswith(surf):
                    continue
                rest = s[len(surf):]
                if not rest:
                    continue
                if mode == "y":
                    if rest[0] not in VOWELS:
                        continue
                    yield from rec(rest, prefixes + [p], surf)
                elif mode == "m":
                    # Merged vowel: base ended in a vowel that fused with the
                    # next vowel.
                    first = rest[0]
                    base_last = PREFIX_VARIANTS[p][0][-1]
                    if base_last in "aA":
                        cands = UNMERGE.get(first, [])
                        if first == "A":
                            cands = ["a", "A"]
                        if first in "IU":
                            cands = []
                        if first in "eo" and p != "AN":
                            # pararUpa (6.1.94): upa + e(< A + i) = upe
                            cands = cands + [first]
                        if rest.startswith("ar"):
                            for nxt in ("f",):
                                yield from rec(nxt + rest[2:], prefixes + [p], surf)
                    elif base_last in "iI":
                        cands = ["i", "I"] if first == "I" else []
                    else:
                        cands = ["u", "U"] if first == "U" else []
                    for c in cands:
                        yield from rec(c + rest[1:], prefixes + [p], surf)
                else:
                    yield from rec(rest, prefixes + [p], surf)

    yield from rec(lemma, [], "")


def parse_preverbs(pv: str):
    """Possible upasarga lists for a DCS `preverbs` string (SLP1)."""
    results = set()

    def rec(s, acc):
        if not s:
            results.add(tuple(acc))
            return
        if len(acc) >= 4:
            return
        for p in PREFIX_VARIANTS:
            for surf, mode in prefix_surfaces(p):
                if not surf:
                    continue
                if mode == "m":
                    if s.startswith(surf) and len(s) > len(surf):
                        rest = s[len(surf):]
                        for c in UNMERGE.get(rest[0], []):
                            rec(c + rest[1:], acc + [p])
                elif mode == "y":
                    if s.startswith(surf) and len(s) > len(surf) and s[len(surf)] in VOWELS:
                        rec(s[len(surf):], acc + [p])
                elif s == surf or s.startswith(surf):
                    rec(s[len(surf):], acc + [p])

    rec(pv, [])
    # "a" alone is not a prefix; leftovers like "saMs" are covered above.
    return results


CANON_PREFIX = {"nir": "nis", "dur": "dus"}

# DCS lemmas for stems that Panini derives from another dhatu. The alias
# keys are added to the root index, so they also work with prefixes.
LEMMA_ALIASES = {
    "ah": ["brU"],  # Aha, AhuH (3.4.84)
    "vaD": ["han"],  # avaDIt, vaDyAt (2.4.42, 2.4.43)
    "paS": ["dfS"],  # paSyati (7.3.78)
    "gA": ["i"],  # agAt (2.4.45)
    "Dam": ["DmA"],  # Damati (7.3.78)
    "kxp": ["kfp"],  # kalpate (8.2.18)
    "spfD": ["sparD"],
    "dIv": ["div"],  # dIvyati (8.2.77)
    "sIv": ["siv"],
    "zWIv": ["zWiv"],
    "sTIv": ["zWiv"],
    "kam": ["kAmi"],  # kAmayate (3.1.30)
    "uJ": ["ujJ"],
    "nU": ["nu"],  # Ru stutau: nOmi
    "vf": ["UrRu"],  # DCS lists UrRoti under vf
    "Di": ["Dinv"],  # Dinoti (3.1.80)
    "fC": ["f"],  # DCS lists iyarti, Arat under fC
    "DU": ["Du"],  # DCS lists Dunoti (Du\\Y, 5.9) under DU
}


def is_cvi_gati(pv: str) -> bool:
    """A cvi word (BasmI, svI, ekI; 1.4.61) or the onomatopoeic hiM."""
    return len(pv) > 1 and (pv.endswith(("I", "U")) or pv in ("hiM", "hiN"))


def map_lemma(lemma_slp, preverbs_slp, index):
    """Return (list of (prefixes, root, entries), note)."""
    splits = list(decompose(lemma_slp, index))
    if not splits and is_cvi_gati(preverbs_slp) and lemma_slp.startswith(preverbs_slp):
        rest = lemma_slp[len(preverbs_slp):]
        if rest in ("kf", "BU", "as") and rest in index:
            return [((preverbs_slp,), rest, index[rest])], "gati"
    if not splits:
        return [], "unmapped"
    if preverbs_slp:
        wanted = parse_preverbs(preverbs_slp)
        good = [s for s in splits if s[0] in wanted]
        if good:
            return good, "preverbs"
        # A cvi word or other gati that is not in our list (BasmIkf,
        # svIkf, hiMkf): pass the preverb string through as one gati.
        if is_cvi_gati(preverbs_slp) and lemma_slp.startswith(preverbs_slp):
            rest = lemma_slp[len(preverbs_slp):]
            if rest in ("kf", "BU", "as") and rest in index:
                return [((preverbs_slp,), rest, index[rest])], "gati"
        # Lemma decomposes, but not with the listed preverbs.
        best = min(len(s[0]) for s in splits if s[0]) if any(s[0] for s in splits) else 0
        return [s for s in splits if len(s[0]) == best], "preverbs-mismatch"
    fewest = min(len(s[0]) for s in splits)
    return [s for s in splits if len(s[0]) == fewest], "plain" if fewest == 0 else "split"


# ---------------------------------------------------------------------------
# Form matching
# ---------------------------------------------------------------------------


def pausa_candidates(form: str) -> set:
    """Possible pausa (word-final) forms behind a sandhied DCS token."""
    out = {form}
    f = form
    if not f:
        return out
    last = f[-1]
    if last == "M":
        out |= {f[:-1] + "m", f[:-1] + "n"}
    if last in "sSzr":
        out.add(f[:-1] + "H")
    if f.endswith("o"):
        out.add(f[:-1] + "aH")
    if last in "aAiIuU":
        out.add(f + "H")
    if last in "dcjnlw":
        out.add(f[:-1] + "t")
    if f.endswith(("Ms", "Mz", "MS")):
        out.add(f[:-2] + "n")
    if f.endswith("nn"):
        out.add(f[:-1])
    if last == "y":
        out |= {f[:-1] + "i", f[:-1] + "I"}
    if last == "v":
        out |= {f[:-1] + "u", f[:-1] + "U"}
    if last in "YRN":
        out |= {f[:-1] + "m", f[:-1] + "n"}
    if last == "g":
        out.add(f[:-1] + "k")
    if last == "q":
        out.add(f[:-1] + "w")
    if last == "a":
        out.add(f[:-1] + "e")
    if last == "A":
        out.add(f[:-1] + "E")
    return {norm_key(x) for x in out}


# Atmanepada endings by (person, number), across all lakaras. Used only to
# classify misses, never to decide coverage.
ATM_ENDINGS = {
    ("3", "Sing"): ("te", "ta", "tAm", "e"),
    ("3", "Dual"): ("ete", "Ate", "etAm", "AtAm"),
    ("3", "Plur"): ("nte", "nta", "ntAm", "ran", "re", "ate", "ata", "atAm"),
    ("2", "Sing"): ("se", "ze", "TAH", "sva", "zva"),
    ("2", "Dual"): ("eTe", "ATe", "eTAm", "ATAm"),
    ("2", "Plur"): ("Dve", "Dvam", "qve", "qvam"),
    ("1", "Sing"): ("e", "E", "i"),
    ("1", "Dual"): ("vahe", "vahi", "vahE"),
    ("1", "Plur"): ("mahe", "mahi", "mahE"),
}
PAR_ENDINGS = {
    ("3", "Sing"): ("ti", "t", "tu", "a", "O", "tAt", "d"),
    ("3", "Dual"): ("taH", "tAm", "tuH", "tuH"),
    ("3", "Plur"): ("nti", "n", "ntu", "uH", "ti"),
    ("2", "Sing"): ("si", "H", "hi", "Di", "a", "u", "Ta", "tAt", "s"),
    ("2", "Dual"): ("TaH", "tam", "TuH"),
    ("2", "Plur"): ("Ta", "ta"),
    ("1", "Sing"): ("mi", "m", "Ani", "a", "M"),
    ("1", "Dual"): ("vaH", "va", "Ava"),
    ("1", "Plur"): ("maH", "ma", "Ama"),
}


def possible_padas(form: str, person: str, number: str) -> set:
    """Padas whose ending best matches `form` (longest match wins)."""
    key = (person, number)
    atm = max((len(e) for e in ATM_ENDINGS.get(key, ()) if form.endswith(e)), default=0)
    par = max((len(e) for e in PAR_ENDINGS.get(key, ()) if form.endswith(e)), default=0)
    if atm > par:
        return {"A"}
    if par > atm:
        return {"P"}
    return {"A", "P"}


def attested_keys(item) -> set:
    keys = set()
    for s in (item.unsandhied, item.form):
        if s:
            s = iast_to_slp1(s)
            if is_slp1(s):
                keys |= pausa_candidates(s)
    return keys


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("conllu", type=Path, help="DCS dcs/data/conllu directory")
    ap.add_argument("--engine", choices=["wasm", "python"], default="wasm")
    ap.add_argument("--wasm-pkg", type=Path, default=PRAKRIYA / "pkg",
                    help="directory with vidyut_prakriya.js and _bg.wasm")
    ap.add_argument("--dhatupatha", type=Path,
                    default=PRAKRIYA / "data" / "dhatupatha.tsv")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--sample-tsv", type=Path,
                    help="write the regression sample here (default: out-dir)")
    ap.add_argument("--sample-rows", type=int, default=9000)
    ap.add_argument("--limit-files", type=int, default=0,
                    help="read only the first N chapter files (for testing)")
    args = ap.parse_args()

    files_dir, lookup = find_dirs(args.conllu)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dictionary = load_dictionary(lookup)
    time_slots = load_time_slots(lookup)

    # 1. Collect distinct items.
    print("Reading DCS ...", file=sys.stderr)
    Item = collections.namedtuple(
        "Item", "lemma_id lemma form unsandhied person number tense mood formation voice")
    items = {}
    item_count = collections.Counter()
    item_slots = collections.defaultdict(collections.Counter)
    item_ref = {}
    for tok in read_items(files_dir, time_slots, args.limit_files):
        f = tok["feats"]
        key = Item(tok["lemma_id"], unicodedata.normalize("NFC", tok["lemma"]),
                   unicodedata.normalize("NFC", tok["form"]),
                   unicodedata.normalize("NFC", tok["unsandhied"]),
                   f.get("Person", ""), f.get("Number", ""), f.get("Tense", ""),
                   f.get("Mood", ""), f.get("Formation", ""), f.get("Voice", ""))
        item_count[key] += 1
        item_slots[key][tok["slot"]] += 1
        if key not in item_ref:
            item_ref[key] = (tok["chapter"], tok["sent_id"], tok["pos"])
    print(f"  {sum(item_count.values())} finite tokens, {len(item_count)} items",
          file=sys.stderr)

    # 2. Engine and dhatu index.
    if args.engine == "wasm":
        raw = WasmEngine(args.wasm_pkg)
    else:
        raw = PythonEngine()
    engine = CachedEngine(raw)
    rows = load_dhatupatha(args.dhatupatha)
    print(f"Indexing {len(rows)} dhatus ...", file=sys.stderr)
    index = build_root_index(rows, engine)

    # 3. Map lemmas.
    lemma_map = {}
    for key in item_count:
        lid = key.lemma_id
        if lid in lemma_map:
            continue
        lemma, grammar, preverbs = dictionary.get(lid, (key.lemma, "", ""))
        lemma_slp = iast_to_slp1(unicodedata.normalize("NFC", lemma))
        pv_slp = iast_to_slp1(unicodedata.normalize("NFC", preverbs))
        splits, note = map_lemma(lemma_slp, pv_slp, index) if is_slp1(lemma_slp) else ([], "unmapped")
        lemma_map[lid] = (lemma, grammar, preverbs, splits, note)

    # 4. Build requests.
    def candidates(lid):
        out = []
        for prefixes, root, entries in lemma_map[lid][3]:
            for alt in expand_prefixes(prefixes):
                for i, sanadi in entries:
                    row = rows[i]
                    pre = list(alt)
                    req = row["required_prefix"]
                    if req and req not in pre:
                        continue
                    out.append((i, tuple(pre), sanadi, root))
        return out

    def expand_prefixes(prefixes):
        alts = [[]]
        for p in prefixes:
            opts = [p] + ([{"nis": "nir", "dus": "dur"}[p]] if p in ("nis", "dus") else [])
            alts = [a + [o] for a in alts for o in opts]
        return alts

    def reqs_for(cands, lakaras, prayogas, person, number):
        out = []
        for (i, pre, sanadi, root) in cands:
            for lak, skip in lakaras:
                for prayoga in prayogas:
                    out.append(((i, pre, sanadi, root, lak, skip, prayoga),
                                tin_req(rows[i], pre, sanadi, lak, prayoga,
                                        person, number, skip)))
        return out

    print("Deriving ...", file=sys.stderr)
    results = {}
    keys_sorted = sorted(item_count, key=lambda k: (-item_count[k], k))
    batch = []
    BATCH = 20000

    def flush(batch):
        allreqs = [r for (_, pending) in batch for (_, r) in pending]
        res = engine.run(allreqs)
        j = 0
        for key, pending in batch:
            out = []
            for meta, _ in pending:
                out.append((meta, res[j]))
                j += 1
            results.setdefault(key, []).extend(out)

    stage = {}
    for key in keys_sorted:
        tag = (key.tense, key.mood)
        person = PERSON.get(key.person)
        number = NUMBER.get(key.number)
        cands = candidates(key.lemma_id)
        if not cands or tag not in TAGS or not person or not number:
            stage[key] = "skip"
            continue
        prayogas = ["Karmani"] if key.voice == "Pass" else ["Kartari"]
        batch.append((key, reqs_for(cands, TAGS[tag], prayogas, person, number)))
        stage[key] = "primary"
        if sum(len(p) for _, p in batch) > BATCH:
            flush(batch)
            batch = []
    if batch:
        flush(batch)

    def match(key, res_list):
        att = attested_keys(key)
        hits = []
        for meta, forms in res_list:
            for form in forms or []:
                if norm_key(form) in att:
                    hits.append((meta, form))
        return hits

    covered = {}
    secondary = []
    for key in keys_sorted:
        if stage[key] != "primary":
            continue
        hits = match(key, results.get(key, []))
        if hits:
            covered[key] = ("primary", hits)
        else:
            secondary.append(key)

    # 5. Second pass for misses: any lakara, either voice, with and without
    # the augment. Hits here point to tag or lemma noise.
    print(f"Second pass for {len(secondary)} items ...", file=sys.stderr)
    results2 = {}
    batch = []

    def flush2(batch):
        allreqs = [r for (_, pending) in batch for (_, r) in pending]
        res = engine.run(allreqs)
        j = 0
        for key, pending in batch:
            for meta, _ in pending:
                results2.setdefault(key, []).append((meta, res[j]))
                j += 1

    for key in secondary:
        cands = candidates(key.lemma_id)
        # DCS lists some causative forms (ajIjanat) under the base root.
        cands = cands + [(i, pre, ("Ric",), root) for (i, pre, san, root) in cands
                         if san == ()]
        laks = [(lk, False) for lk in ALL_LAKARAS] + [("Lun", True), ("Lan", True)]
        batch.append((key, reqs_for(cands, laks, ["Kartari", "Karmani"],
                                    PERSON[key.person], NUMBER[key.number])))
        if sum(len(p) for _, p in batch) > BATCH:
            flush2(batch)
            batch = []
    if batch:
        flush2(batch)
    raw.close()

    # 6. Classify.
    def bucket(key):
        lid = key.lemma_id
        lemma, grammar, preverbs, splits, note = lemma_map[lid]
        tag = (key.tense, key.mood)
        if not splits:
            if "Denom" in grammar:
                return "a1 denominative lemma (not a dhatupatha root)"
            if "Int" in grammar:
                return "a2 intensive lemma not mapped"
            if "Desid" in grammar:
                return "a3 desiderative lemma not mapped"
            return "a4 root not in vidyut dhatupatha or not mappable"
        if not candidates(lid):
            return "a5 mapped only to dhatus that need another prefix"
        if tag not in TAGS or not PERSON.get(key.person) or not NUMBER.get(key.number):
            return "b0 unusable DCS tag"
        att = attested_keys(key)
        if not att:
            return "b1 form not in plain IAST"
        if key in covered:
            return "covered"
        hits = match(key, results2.get(key, []))
        if hits and all(m[2] == ("Ric",) for m, _ in hits):
            return "b5 produced as a causative (DCS lists it under the base root)"
        hits = [h for h in hits if h[0][2] != ("Ric",)]
        if hits:
            voices = {m[6] for m, _ in hits}
            want = "Karmani" if key.voice == "Pass" else "Kartari"
            if want not in voices:
                return "b2 produced only in the other voice (DCS voice tag missing, or epic atmanepada)"
            return "b3 produced in another lakara or without the augment (DCS tag differs from the Paninian analysis)"
        if note == "preverbs-mismatch":
            return "b4 lemma does not split into its listed preverbs"
        forms = {fm for _, fs in results.get(key, []) for fm in (fs or [])}
        if forms:
            mine = set()
            for s_ in (key.unsandhied, key.form):
                s_ = iast_to_slp1(s_) if s_ else ""
                if is_slp1(s_):
                    mine |= possible_padas(s_, key.person, key.number)
            theirs = set()
            for fm in forms:
                theirs |= possible_padas(fm, key.person, key.number)
            if mine and not (mine & theirs):
                return "c4 pada that Panini does not assign to this root (epic and Vedic usage)"
        slots = item_slots[key]
        vedic_tokens = slots.get("1", 0)
        if tag in VEDIC_ONLY_TAGS:
            return "c1 Vedic category (subjunctive, injunctive, aorist imperative/optative, pluperfect)"
        if vedic_tokens * 2 >= item_count[key]:
            return "c2 attested mainly in Vedic texts"
        if slots.get("2", 0) * 2 >= item_count[key]:
            return "c3 attested mainly in epic texts"
        return "d candidate (classical, standard category)"

    summary = collections.OrderedDict()
    total_tok = sum(item_count.values())
    total_typ = len(item_count)
    buckets_tok = collections.Counter()
    buckets_typ = collections.Counter()
    by_tag = collections.defaultdict(lambda: [0, 0, 0, 0])
    by_gana = collections.defaultdict(lambda: [0, 0, 0, 0])
    by_slot = collections.defaultdict(lambda: [0, 0, 0, 0])
    by_lakara = collections.Counter()
    gati_tok = gati_typ = 0
    item_bucket = {}
    for key in keys_sorted:
        b = bucket(key)
        item_bucket[key] = b
        n = item_count[key]
        buckets_tok[b] += n
        buckets_typ[b] += 1
        mapped = not b.startswith("a")
        is_cov = b == "covered"
        tag = f"{key.tense} {key.mood}" + (" Pass" if key.voice == "Pass" else "")
        rec = by_tag[tag]
        rec[0] += n
        rec[1] += n if mapped else 0
        rec[2] += n if is_cov else 0
        rec[3] += 1 if is_cov else 0
        for slot, c in item_slots[key].items():
            r = by_slot[TIME_SLOTS.get(slot, "unknown")]
            r[0] += c
            r[1] += c if mapped else 0
            r[2] += c if is_cov else 0
        if mapped:
            ganas = sorted({rows[i]["gana"] for (_, _, ents) in lemma_map[key.lemma_id][3]
                            for i, _ in ents})
            if is_cov:
                ganas = sorted({rows[m[0]]["gana"] for m, _ in covered[key][1]})
                g = ganas[0] if len(ganas) == 1 else "/".join(ganas)
            else:
                g = ganas[0] if len(ganas) == 1 else "/".join(ganas)
            # Collapse multi-gana labels to "several" to keep the table short.
            g = g if "/" not in g else "more than one gana"
            r = by_gana[g]
            r[0] += n
            r[1] += n
            r[2] += n if is_cov else 0
        if is_cov and all(any(p not in PREFIX_VARIANTS or p in GATI for p in m[1])
                          for m, _ in covered[key][1]):
            gati_tok += n
            gati_typ += 1
        if is_cov:
            for lk in sorted({m[4] + ("-noat" if m[5] else "") for m, _ in covered[key][1]}):
                by_lakara[lk] += n

    mapped_tok = sum(v for k, v in buckets_tok.items() if not k.startswith("a"))
    mapped_typ = sum(v for k, v in buckets_typ.items() if not k.startswith("a"))
    summary["engine"] = args.engine
    summary["engine_build"] = str(args.wasm_pkg) if args.engine == "wasm" else "python"
    summary["finite_tokens"] = total_tok
    summary["finite_types"] = total_typ
    summary["mapped_tokens"] = mapped_tok
    summary["mapped_types"] = mapped_typ
    summary["covered_tokens"] = buckets_tok["covered"]
    summary["covered_types"] = buckets_typ["covered"]
    summary["covered_only_with_gati_prefix_tokens"] = gati_tok
    summary["covered_only_with_gati_prefix_types"] = gati_typ
    summary["buckets_tokens"] = dict(sorted(buckets_tok.items()))
    summary["buckets_types"] = dict(sorted(buckets_typ.items()))
    summary["by_tag"] = {k: dict(zip(["tokens", "mapped_tokens", "covered_tokens", "covered_types"], v))
                         for k, v in sorted(by_tag.items(), key=lambda x: -x[1][0])}
    summary["by_gana"] = {k: dict(zip(["tokens", "mapped_tokens", "covered_tokens"], v[:3]))
                          for k, v in sorted(by_gana.items())}
    summary["by_time_slot"] = {k: dict(zip(["tokens", "mapped_tokens", "covered_tokens"], v[:3]))
                               for k, v in sorted(by_slot.items())}
    summary["covered_tokens_by_lakara"] = dict(sorted(by_lakara.items()))
    lemma_notes = collections.Counter()
    for lid, (_, _, _, splits, note) in lemma_map.items():
        lemma_notes[note] += 1
    summary["lemma_mapping"] = dict(sorted(lemma_notes.items()))

    with open(args.out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 7. Write covered and misses.
    def fmt_ref(key):
        ch, sid, pos = item_ref[key]
        return ch, sid, pos

    def tense_mode(key):
        parts = [f"Tense={key.tense}", f"Mood={key.mood}"]
        if key.formation:
            parts.append(f"Formation={key.formation}")
        return "|".join(parts)

    head = ["ref", "sent_id", "pos", "word", "surface_form", "lemma", "root",
            "prefixes", "person", "number", "tense_mode", "voice", "count",
            "dhatu_code", "aupadeshika", "gana", "sanadi", "lakara",
            "prayoga", "skip_at_agama", "vidyut_form"]

    def covered_row(key):
        hits = covered[key][1]
        # Deterministic choice: earliest code, then fewest prefixes, then lakara order.
        hits = sorted(hits, key=lambda h: (rows[h[0][0]]["code"], len(h[0][1]), h[0][1],
                                           h[0][2], "M" in h[0][3], h[0][3],
                                           ALL_LAKARAS.index(h[0][4]), h[0][5], h[1]))
        (i, pre, sanadi, root, lak, skip, prayoga), form = hits[0]
        ch, sid, pos = fmt_ref(key)
        return [ch, sid, pos, key.form, key.unsandhied or key.form,
                lemma_map[key.lemma_id][0], slp1_to_iast(root), ",".join(pre),
                key.person, NUMBER_DIGIT[key.number], tense_mode(key), key.voice,
                str(item_count[key]), rows[i]["code"], rows[i]["aupadeshika"],
                rows[i]["gana"], ",".join(sanadi), lak, prayoga,
                "1" if skip else "0", form]

    cov_rows = [covered_row(k) for k in keys_sorted if k in covered]
    with open(args.out_dir / "covered.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(head) + "\n")
        for r in cov_rows:
            f.write("\t".join(r) + "\n")

    miss_head = ["bucket", "count", "word", "unsandhied", "lemma", "grammar",
                 "preverbs", "person", "number", "tense_mode", "voice",
                 "time_slots", "ref", "sent_id", "candidates", "vidyut_forms"]
    with open(args.out_dir / "misses.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(miss_head) + "\n")
        for key in keys_sorted:
            b = item_bucket[key]
            if b == "covered":
                continue
            lemma, grammar, preverbs, splits, note = lemma_map[key.lemma_id]
            ch, sid, pos = fmt_ref(key)
            cands = sorted({f"{rows[i]['code']}:{'+'.join(pre)}{'+' if pre else ''}"
                            f"{rows[i]['aupadeshika']}{'+' + '+'.join(san) if san else ''}"
                            for (i, pre, san, root) in candidates(key.lemma_id)})
            forms = sorted({fm for _, fs in results.get(key, []) for fm in (fs or [])})
            slots = ",".join(f"{s}:{c}" for s, c in sorted(item_slots[key].items()))
            f.write("\t".join([b, str(item_count[key]), key.form, key.unsandhied,
                               lemma, grammar, preverbs, key.person, key.number,
                               tense_mode(key), key.voice, slots, ch, sid,
                               " ".join(cands[:12]), " ".join(forms[:20])]) + "\n")

    # 8. Regression sample in the rv_let_corpus style: per (dhatu, lakara,
    # prayoga, prefixes) keep the most frequent item, then fill by frequency.
    picked = []
    seen = set()
    for r in cov_rows:
        k = (r[13], r[17], r[18], r[7], r[16])
        if k in seen:
            continue
        seen.add(k)
        picked.append(r)
    if len(picked) > args.sample_rows:
        picked = picked[: args.sample_rows]
    order = {id(r): n for n, r in enumerate(cov_rows)}
    picked.sort(key=lambda r: order[id(r)])
    sample_path = args.sample_tsv or (args.out_dir / "corpus_sample.tsv")
    with open(sample_path, "w", encoding="utf-8") as f:
        f.write("\t".join(head) + "\n")
        for r in picked:
            f.write("\t".join(r) + "\n")

    # 9. Print a short report.
    pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "-"
    print(f"Finite verb tokens: {total_tok}, types: {total_typ}")
    print(f"Mapped to the dhatupatha: {mapped_tok} tokens ({pct(mapped_tok, total_tok)}), "
          f"{mapped_typ} types ({pct(mapped_typ, total_typ)})")
    print(f"Covered: {buckets_tok['covered']} tokens ({pct(buckets_tok['covered'], total_tok)} of all, "
          f"{pct(buckets_tok['covered'], mapped_tok)} of mapped), {buckets_typ['covered']} types "
          f"({pct(buckets_typ['covered'], mapped_typ)} of mapped)")
    for b in sorted(buckets_tok):
        print(f"  {b}: {buckets_tok[b]} tokens, {buckets_typ[b]} types")
    print(f"Sample: {len(picked)} rows -> {sample_path}")


if __name__ == "__main__":
    main()
