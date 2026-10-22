#!/usr/bin/env python3
"""Check vidyut-prakriya subanta generation against the nominal forms of the DCS.

The Digital Corpus of Sanskrit (DCS, Oliver Hellwig, CC BY 4.0,
<https://github.com/OliverHellwig/sanskrit>) annotates every word of its texts
with a lemma and, for nominals, case, number and gender. This script reads the
DCS CoNLL-U dump, collects every distinct attested (form, stem, gender, case,
number) item, asks vidyut-prakriya to derive that slot of that stem, and
reports how many attested items and tokens vidyut covers. Misses are sorted
into rough categories so that the frequent ones can be checked by hand.

Usage:

    python3 -I check_dcs_subanta_coverage.py <sanskrit repo>/dcs/data/conllu/files \\
        --wasm-dir <dir with vidyut_prakriya.js and vidyut_prakriya_bg.wasm> \\
        --summary-out summary.json --misses-out misses.tsv --alt-out alt.tsv \\
        --corpus-out ../tests/data/dcs_subanta_corpus.tsv

    # Regression mode: re-derive every row of a corpus TSV.
    python3 -I check_dcs_subanta_coverage.py --check-corpus ../tests/data/dcs_subanta_corpus.tsv \\
        --wasm-dir <dir>

Only the `*.conllu` files are read; the `*.conllu_parsed` files repeat many of
the same sentences. `chapter-info.xml` and `dictionary.csv` are read from
`<files>/../lookup` (or `--lookup-dir`) for the DCS periods and grammar notes.

Engines:

- `--engine wasm` (default) runs `dcs_subanta_engine.mjs` under Node (tested
  with Node 22) with a WASM build of vidyut-prakriya (`make wasm_release` in
  vidyut-prakriya runs `wasm-pack build --target web --release -- --features
  serde` and writes `pkg/vidyut_prakriya.js` and `pkg/vidyut_prakriya_bg.wasm`).
  Point it at a build with `--wasm-dir` (or `--wasm-js` and `--wasm-bin`).
- `--engine python` uses the `vidyut.prakriya` Python bindings that are
  importable by the running interpreter (for example after `make develop` in
  `bindings-python`).

The output is deterministic: files are read in sorted order and every table
is sorted by count and then by key.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Transliteration
# ---------------------------------------------------------------------------

_IAST = [
    ("ai", "E"),
    ("au", "O"),
    ("kh", "K"),
    ("gh", "G"),
    ("ch", "C"),
    ("jh", "J"),
    ("ṭh", "W"),
    ("ḍh", "Q"),
    ("th", "T"),
    ("dh", "D"),
    ("ph", "P"),
    ("bh", "B"),
    ("ḻh", "|"),
    ("ā", "A"),
    ("ī", "I"),
    ("ū", "U"),
    ("ṛ", "f"),
    ("ṝ", "F"),
    ("ḷ", "x"),
    ("ḹ", "X"),
    ("ṃ", "M"),
    ("ṁ", "M"),
    ("ḥ", "H"),
    ("ṅ", "N"),
    ("ñ", "Y"),
    ("ṭ", "w"),
    ("ḍ", "q"),
    ("ṇ", "R"),
    ("ś", "S"),
    ("ṣ", "z"),
    ("ḻ", "L"),
]
_PLAIN = set("aiueokgcjtdnpbmyrlvsh")


def iast_to_slp1(s):
    """Convert a DCS IAST string to SLP1. Return None for unexpected characters."""
    if s.startswith("'"):
        s = "a" + s[1:]  # avagraha: an initial a elided after e or o (te 'pi)
    out = []
    i = 0
    while i < len(s):
        for src, dst in _IAST:
            if s.startswith(src, i):
                out.append(dst)
                i += len(src)
                break
        else:
            c = s[i]
            if c in _PLAIN:
                out.append(c)
                i += 1
            else:
                return None
    return "".join(out)


# ---------------------------------------------------------------------------
# DCS tags and vidyut enums
# ---------------------------------------------------------------------------

CASES = {
    "Nom": "Prathama",
    "Acc": "Dvitiya",
    "Ins": "Trtiya",
    "Dat": "Caturthi",
    "Abl": "Panchami",
    "Gen": "Sasthi",
    "Loc": "Saptami",
    "Voc": "Sambodhana",
}
NUMBERS = {"Sing": "Eka", "Dual": "Dvi", "Plur": "Bahu"}
GENDERS = {"Masc": "Pum", "Fem": "Stri", "Neut": "Napumsaka"}
VIBHAKTIS = list(CASES.values())
VACANAS = list(NUMBERS.values())
LINGAS = list(GENDERS.values())
NOMINAL_UPOS = {"NOUN", "ADJ", "PRON", "NUM"}

# DCS pronoun and numeral lemmas whose citation form differs from the
# pratipadika that vidyut expects.
LEMMA_MAP = {
    "ahar": "ahan",
    "puMs": "pums",
    "mad": "asmad",
    "tvad": "yuzmad",
    "ka": "kim",
    "tya": "tyad",
    "uB": "uBa",
}

# Indefinites: DCS lemma -> (pratipadika, particle). The particle is stripped
# from the attested form before comparison (kenacit -> kena).
INDEFINITES = {
    "kaScit": ("kim", "cit"),
    "kaScana": ("kim", "cana"),
    "ekaScana": ("eka", "cana"),
}

# Feminine I-stems that are not formed with a NI-pratyaya and so are not
# passed as `nyap` (SK on lakzmI: avI-tarI-tantrI-lakzmI ...).
AVYUTPANNA_I = {"lakzmI", "tarI", "tantrI", "avI", "starI"}


# Stems that are kfdantas or taddhitantas whose behaviour depends on their
# derivation. `basic` cannot express that, so these are tried as alternatives.
def DHATU(u, gana, pre=()):
    return {
        "aupadeshika": u,
        "gana": gana,
        "antargana": None,
        "sanadi": [],
        "prefixes": list(pre),
    }


def ANC(*pre):
    return [("krdanta", "ancu~", "Bhvadi", "kvin", None, pre)]


def RAJ(*pre):
    return [("krdanta", "rAjf~^", "Bhvadi", "kvip", None, pre)]


DERIVED = {
    "Bavat": [("krdanta", "BA\\", "Adadi", None, "qavatu", ())],
    "mahat": [("krdanta", "maha~", "Bhvadi", None, "ati", ())],
    "vidvas": [("krdanta", "vida~", "Adadi", "Satf", None, ())],
    "vidvAMs": [("krdanta", "vida~", "Adadi", "Satf", None, ())],
    "SrI": [("krdanta", "SriY", "Bhvadi", "kvip", None, ())],
    "DI": [("krdanta", "DyE\\", "Bhvadi", "kvip", None, ())],
    "BI": [("krdanta", "YiBI\\", "Juhotyadi", "kvip", None, ())],
    "hrI": [("krdanta", "hrI\\", "Juhotyadi", "kvip", None, ())],
    "BU": [("krdanta", "BU", "Bhvadi", "kvip", None, ())],
    "ASis": [("krdanta", "SAsu~", "Adadi", "kvip", None, ("AN",))],
    "gir": [("krdanta", "gF", "Kryadi", "kvip", None, ())],
    "pur": [("krdanta", "pF", "Kryadi", "kvip", None, ())],
    "prAYc": ANC("pra"),
    "pratyaYc": ANC("prati"),
    "udaYc": ANC("ud"),
    "tiryaYc": ANC("tiras"),
    "samyaYc": ANC("sam"),
    "avAYc": ANC("ava"),
    "nyaYc": ANC("ni"),
    "apAYc": ANC("apa"),
    "anvaYc": ANC("anu"),
    "rAj": RAJ(),
    "virAj": RAJ("vi"),
    "samrAj": RAJ("sam"),
    "sat": [("krdanta", "asa~", "Adadi", "Satf", None, ())],
    "bfhat": [("krdanta", "bfha~", "Bhvadi", None, "ati", ())],
    "yAvat": [("taddhitanta", "yad", "vatup")],
    "tAvat": [("taddhitanta", "tad", "vatup")],
    "etAvat": [("taddhitanta", "etad", "vatup")],
    "iyat": [("taddhitanta", "idam", "vatup")],
    "kiyat": [("taddhitanta", "kim", "vatup")],
}
# Comparatives in -Iyas (Iyasun, 5.3.57 ff.) and their positive bases.
for _base, _cmp in [
    ("guru", "garIyas"),
    ("laGu", "laGIyas"),
    ("pApa", "pApIyas"),
    ("alpa", "kanIyas"),
    ("yuvan", "yavIyas"),
    ("bahu", "BUyas"),
    ("praSasya", "Sreyas"),
    ("vfdDa", "jyAyas"),
    ("balin", "balIyas"),
    ("uru", "varIyas"),
    ("dIrGa", "drAGIyas"),
    ("kzudra", "kzodIyas"),
    ("mahat", "mahIyas"),
    ("sTUla", "sTavIyas"),
    ("priya", "preyas"),
    ("antika", "nedIyas"),
]:
    DERIVED[_cmp] = [("taddhitanta", _base, "Iyasun")]

# Texts written in Buddhist Hybrid Sanskrit; their forms are often outside
# the Paninian paradigm.
BHS_TEXTS = {
    "Avadānaśataka",
    "Aṣṭasāhasrikā",
    "Divyāvadāna",
    "Lalitavistara",
    "Saddharmapuṇḍarīkasūtra",
    "Laṅkāvatārasūtra",
    "Saṅghabhedavastu",
    "Śikṣāsamuccaya",
}
# Epic and puranic texts, whose grammar is freer than the classical norm.
EPIC_TEXTS = {"Mahābhārata", "Rāmāyaṇa", "Harivaṃśa", "Devīmāhātmya", "Maṇimāhātmya"}


def is_epic(text_name):
    return text_name in EPIC_TEXTS or "purāṇa" in text_name.lower()


def ending_class(stem, upos):
    """A coarse stem class used for the coverage tables."""
    if upos == "PRON":
        return "pronoun"
    if upos == "NUM":
        return "numeral"
    s = stem
    for suffix, name in [
        ("mat", "-mat/-vat"),
        ("vat", "-mat/-vat"),
        ("vas", "-vas"),
        ("vAMs", "-vas"),
        ("at", "-at/-ant"),
        ("ant", "-at/-ant"),
        ("in", "-in"),
        ("as", "-as"),
        ("is", "-is/-us"),
        ("us", "-is/-us"),
        ("an", "-an"),
        ("ac", "-ac/-aYc"),
        ("aYc", "-ac/-aYc"),
    ]:
        if s.endswith(suffix) and len(s) > len(suffix):
            return name
    last = s[-1]
    if last in "aAiIuUfF":
        return {"f": "f", "F": "f"}.get(last, last)
    if last in "eEoO":
        return "e/ai/o/au"
    if last in "cjSCJ":
        return "palatal (c j S)"
    if last == "r":
        return "-r"
    if last in "tTdD":
        return "other dental"
    return "other consonant"


# ---------------------------------------------------------------------------
# Reading the DCS
# ---------------------------------------------------------------------------


def read_chapter_info(lookup_dir):
    """Map chapter file path (relative to files/) to the DCS time slot."""
    path = Path(lookup_dir) / "chapter-info.xml"
    slots = {}
    if not path.exists():
        return slots
    text = path.read_text(encoding="utf-8")
    for m in re.finditer(
        r"<path>(.*?)</path>.*?<dcsTimeSlot>(.*?)</dcsTimeSlot>", text, re.S
    ):
        slots[m.group(1)] = m.group(2)
    return slots


def read_dictionary(lookup_dir):
    path = Path(lookup_dir) / "dictionary.csv"
    grammar = {}
    if not path.exists():
        return grammar
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) >= 3 and row[0].isdigit():
                grammar[row[0]] = row[2]
    return grammar


def period_of(text_name, slot):
    if slot == "1":
        return "vedic"
    if text_name in BHS_TEXTS:
        return "bhs"
    if is_epic(text_name):
        return "epic"
    return "classical"


class Item:
    __slots__ = (
        "count",
        "periods",
        "ref",
        "sent_id",
        "upos",
        "lemma_id",
        "surface",
        "contexts",
    )

    def __init__(self):
        self.count = 0
        self.periods = Counter()
        self.ref = None
        self.sent_id = None
        self.upos = Counter()
        self.lemma_id = None
        self.surface = Counter()
        # For words inside a multiword token whose pausa form was reconstructed
        # automatically: (position in the token, surface of the whole token).
        self.contexts = Counter()


def read_dcs(files_dir, slots, texts=None, stats=None):
    """Collect nominal items keyed by (lemma, linga, vibhakti, vacana, form)."""
    items = {}
    files_dir = Path(files_dir)
    for text_dir in sorted(p for p in files_dir.iterdir() if p.is_dir()):
        if texts and text_dir.name not in texts:
            continue
        for path in sorted(text_dir.glob("*.conllu")):
            rel = f"{text_dir.name}/{path.name}"
            slot = slots.get(rel)
            period = period_of(text_dir.name, slot)
            chapter = sent_id = mwt = None
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or line == "\n":
                        mwt = None
                        if line.startswith("## chapter:"):
                            chapter = line.split(":", 1)[1].strip()
                        elif line.startswith("# sent_id"):
                            sent_id = line.split("=", 1)[1].strip()
                        continue
                    cols = line.rstrip("\n").split("\t")
                    if len(cols) < 10 or "." in cols[0]:
                        continue
                    if "-" in cols[0]:
                        start, end = cols[0].split("-")
                        mwt = (int(start), int(end), cols[1])
                        continue
                    upos = cols[3]
                    if upos not in NOMINAL_UPOS:
                        continue
                    feats = dict(
                        kv.split("=", 1) for kv in cols[5].split("|") if "=" in kv
                    )
                    case = feats.get("Case")
                    if case not in CASES:
                        stats["skipped: compound member or no case"] += 1
                        continue
                    if feats.get("Number") not in NUMBERS:
                        stats["skipped: no number"] += 1
                        continue
                    misc = dict(
                        kv.split("=", 1) for kv in cols[9].split("|") if "=" in kv
                    )
                    # `Unsandhied` is the annotator's pausa form, except when
                    # `UnsandhiedReconstructed=True`: then it was generated
                    # automatically and is often wrong (tāta -> "tātaiḥ",
                    # patyuḥ -> "pateḥ"), so the surface form is used instead.
                    unsandhied = misc.get("Unsandhied")
                    if unsandhied and misc.get("UnsandhiedReconstructed") != "True":
                        form = unsandhied
                    else:
                        form = cols[1] if cols[1] != "_" else (unsandhied or "_")
                    key = (
                        cols[2],
                        feats.get("Gender", ""),
                        case,
                        feats["Number"],
                        form,
                    )
                    item = items.get(key)
                    if item is None:
                        item = items[key] = Item()
                        item.ref = chapter
                        item.sent_id = sent_id
                        item.lemma_id = misc.get("LemmaId", "")
                    item.count += 1
                    item.periods[period] += 1
                    item.upos[upos] += 1
                    item.surface[cols[1]] += 1
                    reconstructed = misc.get("UnsandhiedReconstructed") == "True"
                    if (
                        reconstructed
                        and mwt
                        and mwt[0] <= int(cols[0]) <= mwt[1]
                        and len(item.contexts) < 8
                    ):
                        pos = (
                            "first"
                            if int(cols[0]) == mwt[0]
                            else ("last" if int(cols[0]) == mwt[1] else "mid")
                        )
                        item.contexts[(pos, mwt[2])] += 1
    return items


# ---------------------------------------------------------------------------
# Mapping DCS items to vidyut inputs
# ---------------------------------------------------------------------------


def P(kind, *args):
    """A hashable pratipadika spec."""
    return (kind,) + tuple(args)


def spec_to_wasm(spec):
    p = {"basic": None, "nyap": None, "krdanta": None, "taddhitanta": None}
    kind = spec[0]
    if kind in ("basic", "nyap"):
        p[kind] = spec[1]
    elif kind == "taddhitanta":
        p["taddhitanta"] = {"stem": spec[1], "taddhita": spec[2]}
    elif kind == "krdanta":
        _, u, gana, krt, unadi, pre = spec
        p["krdanta"] = {
            "dhatu": DHATU(u, gana, pre),
            "krt": krt,
            "unadi": unadi,
            "lakara": None,
            "prayoga": None,
        }
    return p


def spec_to_str(spec):
    """Compact text form of a spec, as used in the corpus TSV.

    basic:deva, nyap:ramA, taddhitanta:SrI/matup,
    krdanta:pra+ancu~/Bhvadi/kvin, krdanta:BA\\/Adadi/unadi:qavatu
    """
    kind = spec[0]
    if kind in ("basic", "nyap"):
        return f"{kind}:{spec[1]}"
    if kind == "taddhitanta":
        return f"taddhitanta:{spec[1]}/{spec[2]}"
    _, u, gana, krt, unadi, pre = spec
    head = "+".join(list(pre) + [u])
    return f"krdanta:{head}/{gana}/{krt if krt else 'unadi:' + unadi}"


def spec_from_str(text):
    kind, _, rest = text.partition(":")
    if kind in ("basic", "nyap"):
        return P(kind, rest)
    if kind == "taddhitanta":
        base, taddhita = rest.split("/")
        return P(kind, base, taddhita)
    head, gana, last = rest.split("/")
    parts = head.split("+")
    krt, unadi = (None, last[6:]) if last.startswith("unadi:") else (last, None)
    return P(kind, parts[-1], gana, krt, unadi, tuple(parts[:-1]))


def primary_spec(stem, linga):
    """How a user would most naturally pass this stem to vidyut."""
    if linga == "Stri" and stem.endswith("A"):
        return P("nyap", stem)
    if (
        linga == "Stri"
        and stem.endswith("I")
        and stem not in AVYUTPANNA_I
        and len(re.findall(r"[aAiIuUfFxXeEoO]", stem)) > 1
    ):
        return P("nyap", stem)
    return P("basic", stem)


def alternative_specs(stem, linga):
    """Other reasonable constructions, used to diagnose misses."""
    alts = []
    for d in DERIVED.get(stem, []):
        alts.append(P(*d))
    if linga == "Stri":
        if stem.endswith("A") or stem.endswith("I"):
            alts.append(
                P("basic", stem)
                if primary_spec(stem, linga)[0] == "nyap"
                else P("nyap", stem)
            )
        if stem.endswith("a"):
            alts.append(P("nyap", stem[:-1] + "A"))
            alts.append(P("nyap", stem[:-1] + "I"))
            if stem.endswith("aka"):
                alts.append(P("nyap", stem[:-3] + "ikA"))
        if stem.endswith(("at", "in")):
            alts.append(P("nyap", stem + "I"))
        if stem.endswith("tf"):
            alts.append(P("nyap", stem[:-1] + "rI"))
        if stem.endswith("u"):
            alts.append(P("nyap", stem[:-1] + "vI"))
            alts.append(P("nyap", stem[:-1] + "U"))
        if stem.endswith("i"):
            alts.append(P("nyap", stem[:-1] + "I"))
        if stem.endswith("I"):
            alts.append(P("basic", stem[:-1] + "i"))
        if stem.endswith("yas"):
            alts.append(P("nyap", stem + "I"))
    elif stem[-1] in "AIU" and len(stem) > 2:
        # A feminine noun at the end of a bahuvrihi: AKyA -> nAmAKyaH (1.2.48).
        alts.append(P("basic", stem[:-1] + {"A": "a", "I": "i", "U": "u"}[stem[-1]]))
    if stem.endswith(("mat", "vat")) and len(stem) > 4 and stem not in DERIVED:
        base = stem[:-3]
        if re.search(r"[iIuUfFeEoO]z$", base):  # Ayuz-mat -> Ayus + matup (8.3.59)
            base = base[:-1] + "s"
        alts.append(P("taddhitanta", base, "matup"))
    seen = set()
    out = []
    for a in alts:
        if a not in seen and a != primary_spec(stem, linga):
            seen.add(a)
            out.append(a)
    return out


# Final-sound changes of external sandhi, undone to recover pausa forms from
# the DCS surface (FORM) column: (surface ending, possible pausa endings).
_PAUSA = [
    ("nn", ["n"]),
    ("NN", ["N"]),
    ("RR", ["R"]),
    ("MS", ["n"]),
    ("Ms", ["n"]),
    ("Mz", ["n"]),
    ("Av", ["O"]),
    ("Ay", ["E"]),
    ("M", ["m"]),
    ("o", ["aH"]),
    ("A", ["AH", "E"]),
    ("a", ["aH", "e"]),
    ("S", ["H"]),
    ("z", ["H"]),
    ("s", ["H"]),
    ("r", ["H"]),
    ("g", ["k"]),
    ("q", ["w"]),
    ("d", ["t"]),
    ("b", ["p"]),
    ("j", ["t", "k"]),
    ("c", ["t"]),
    ("l", ["t"]),
    ("Y", ["n"]),
    ("N", ["k"]),
    ("n", ["t", "m"]),
    ("y", ["i", "I"]),
    ("v", ["u", "U"]),
]


def pausa_variants(s):
    out = {s}
    for end, repls in _PAUSA:
        if s.endswith(end) and len(s) > len(end):
            out.update(s[: -len(end)] + r for r in repls)
    return out


_NASAL_BEFORE_CONS = re.compile(r"[NYRnm](?=[kKgGNcCjJYwWqQRtTdDnpPbBm])")


def norm(s):
    """Write every nasal before a consonant as anusvara, as the DCS does (saMdeha, not sandeha)."""
    return _NASAL_BEFORE_CONS.sub("M", s)


def map_item(key, surfaces):
    """Return ((stem, linga, vibhakti, vacana, form_slp1, candidates), None) or (None, reason).

    `candidates` holds the normalized pausa forms that count as a match: the
    item's form and the pausa variants of its DCS surface forms.
    """
    lemma, gender, case, number, form = key
    stem = iast_to_slp1(lemma) if lemma not in ("_", "") else None
    form_s = iast_to_slp1(form)
    if not stem or not form_s:
        return None, "unconvertible lemma or form"
    stem = LEMMA_MAP.get(stem, stem)
    if stem.endswith("ant") and len(stem) > 4:
        stem = (
            stem[:-3] + "at"
        )  # the DCS cites some stems strong: Bagavant, hanumant, jagant
    cands = {form_s}
    for surf in surfaces:
        surf_s = iast_to_slp1(surf)
        if surf_s:
            cands |= pausa_variants(surf_s)
    if stem in INDEFINITES:
        stem, particle = INDEFINITES[stem]
        stripped = set()
        shapes = {"cit": ("cit", "cid", "cin", "cic", "cij", "cil"), "cana": ("cana",)}[
            particle
        ]
        for c in cands:
            # kaScit, kaScid, kenacin: strip the particle in any sandhi shape.
            if c.endswith(shapes) and len(c) > len(particle):
                base = c[: -len(particle)]
                # Undo the internal sandhi before the particle: kaS-cit, kiM-cit.
                if base.endswith("S"):
                    base = base[:-1] + "H"
                elif base.endswith("M"):
                    base = base[:-1] + "m"
                elif base.endswith("d"):
                    base = base[:-1] + "t"
                stripped.add(base)
        if not stripped:
            return None, "indefinite without particle"
        cands = stripped
        form_s = sorted(stripped)[0]
    linga = GENDERS.get(gender)
    if linga is None:
        linga = "Pum"  # asmad, yuzmad and the numerals do not mark gender
    return (
        stem,
        linga,
        CASES[case],
        NUMBERS[number],
        form_s,
        frozenset(norm(c) for c in cands),
    ), None


def match(cands, forms):
    """Return the first derived form whose normalized spelling is a candidate."""
    for f in forms:
        if norm(f) in cands:
            return f
    return None


def context_match(contexts, forms):
    """Match a derived form against the surface of the multiword token around it.

    The DCS splits a sandhi string such as `bharatarzaBa` into words and, for
    much of the corpus, reconstructs each word's pausa form automatically.
    Those reconstructions are often wrong (bharata + "fzaBEH" for a vocative),
    so a word is also accepted if its derived form fits the token surface: the
    last word must end the token (its first sound may merge with the previous
    word), the first word must begin it (its last sound or visarga may change).
    """
    for (pos, surface), _ in contexts.most_common():
        surf = iast_to_slp1(surface)
        if not surf:
            continue
        variants = {norm(v) for v in pausa_variants(surf)}
        for f in forms:
            nf = norm(f)
            if (
                pos == "last"
                and len(nf) > 2
                and any(v.endswith(nf[1:]) for v in variants)
            ):
                return f
            if pos == "first":
                head = nf[:-2] if nf.endswith("H") else nf[:-1]
                if len(head) >= 2 and norm(surf).startswith(head):
                    return f
    return None


def loose(s):
    """Spelling-insensitive key: n for R, single for doubled consonants, ch for cch, nasal before consonant as M."""
    s = norm(s).replace("R", "n").replace("cC", "C").replace("b", "v").replace("q", "d")
    return re.sub(r"([kKgGcCjJwWqQtTdDpPbBmnyrlvSzs])\1", r"\1", s)


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------


def run_wasm(requests, args):
    js = args.wasm_js or os.path.join(args.wasm_dir, "vidyut_prakriya.js")
    wasm = args.wasm_bin or os.path.join(args.wasm_dir, "vidyut_prakriya_bg.wasm")
    helper = Path(__file__).with_name("dcs_subanta_engine.mjs")
    with tempfile.TemporaryDirectory() as tmp:
        req_path = Path(tmp) / "req.jsonl"
        out_path = Path(tmp) / "out.jsonl"
        with open(req_path, "w") as f:
            for spec, li, vi, va in requests:
                f.write(
                    json.dumps({"p": spec_to_wasm(spec), "l": li, "vi": vi, "va": va})
                    + "\n"
                )
        subprocess.run(
            [args.node, str(helper), js, wasm, str(req_path), str(out_path)], check=True
        )
        results = []
        with open(out_path) as f:
            for line in f:
                results.append(json.loads(line))
    return results


def run_python(requests, args):
    from vidyut import prakriya as vp

    v = vp.Vyakarana()
    cache = {}

    def build(spec):
        kind = spec[0]
        if kind == "basic":
            return vp.Pratipadika.basic(spec[1])
        if kind == "nyap":
            return vp.Pratipadika.nyap(spec[1])
        if kind == "taddhitanta":
            return vp.Pratipadika.taddhitanta(
                vp.Pratipadika.basic(spec[1]), getattr(vp.Taddhita, spec[2])
            )
        _, u, gana, krt, unadi, pre = spec
        dhatu = vp.Dhatu.mula(u, getattr(vp.Gana, gana))
        if pre:
            dhatu = dhatu.with_prefixes(list(pre))
        if krt:
            return vp.Pratipadika.krdanta(dhatu, getattr(vp.Krt, krt))
        return vp.Pratipadika.krdanta(dhatu, getattr(vp.Unadi, unadi))

    results = []
    for spec, li, vi, va in requests:
        try:
            if spec not in cache:
                cache[spec] = build(spec)
            pada = vp.Pada.Subanta(
                pratipadika=cache[spec],
                linga=getattr(vp.Linga, li),
                vibhakti=getattr(vp.Vibhakti, vi),
                vacana=getattr(vp.Vacana, va),
            )
            results.append(sorted({p.text for p in v.derive(pada)}))
        except Exception as e:  # unsupported input or a panic in the bindings
            results.append({"error": str(e)[:200]})
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def pct(a, b):
    return f"{100.0 * a / b:.1f}" if b else "-"


STRONG = {
    ("Prathama", "Eka"),
    ("Prathama", "Dvi"),
    ("Prathama", "Bahu"),
    ("Dvitiya", "Eka"),
    ("Dvitiya", "Dvi"),
    ("Sambodhana", "Dvi"),
    ("Sambodhana", "Bahu"),
}
PADA_SLOTS = {
    ("Prathama", "Eka"),
    ("Sambodhana", "Eka"),
    ("Trtiya", "Dvi"),
    ("Caturthi", "Dvi"),
    ("Panchami", "Dvi"),
    ("Trtiya", "Bahu"),
    ("Caturthi", "Bahu"),
    ("Panchami", "Bahu"),
    ("Saptami", "Bahu"),
}
# Sarvadi words that are pronouns only in some senses (1.1.34 to 1.1.36).
SARVADI_BY_SENSE = {
    "pUrva",
    "para",
    "avara",
    "dakziRa",
    "uttara",
    "apara",
    "aDara",
    "sva",
    "antara",
}
MAT_WEAK = {
    ("Caturthi", "Eka"),
    ("Panchami", "Eka"),
    ("Sasthi", "Eka"),
    ("Sasthi", "Bahu"),
    ("Saptami", "Eka"),
}
PRONOUNS_A = {
    "tad",
    "etad",
    "yad",
    "kim",
    "idam",
    "adas",
    "sarva",
    "anya",
    "para",
    "pUrva",
    "apara",
    "itara",
    "eka",
    "tyad",
    "enad",
    "sva",
    "uBa",
}


def known_issue(stem, linga, vi, va, form, upos):
    """Tag a miss with the open upstream issue whose description it matches."""
    slot = (vi, va)
    if upos not in ("PRON", "NUM"):
        if stem.endswith("S") and slot in PADA_SLOTS:
            return "#255"
        if stem.endswith(("is", "us")) and "z" in form:
            return "#260"
        if (
            re.search(r"[twD]f$", stem)
            and linga != "Napumsaka"
            and slot in STRONG
            and stem[:-1] + "Ar" in form
        ):
            return "#261"
        if (
            stem.endswith("in")
            and linga == "Stri"
            and slot in {("Saptami", "Eka"), ("Sasthi", "Bahu")}
        ):
            return "#258"
        if stem.endswith("in") and linga == "Napumsaka" and slot == ("Dvitiya", "Bahu"):
            return "#258"
        if linga == "Napumsaka" and stem in {"akzi", "daDi", "asTi", "sakTi"}:
            return "#257"
        if stem.endswith("i") and linga == "Napumsaka" and slot == ("Dvitiya", "Bahu"):
            return "#257"
        if stem.endswith(("zmat", "zvat")) and "z" in form:
            return "#260"
        if (
            stem.endswith(("mat", "vat"))
            and linga != "Stri"
            and slot in MAT_WEAK
            and form.startswith(stem[:-1])
        ):
            return "#271"
        if stem.endswith(("at", "ant")) and not stem.endswith(("mat", "vat")):
            return "#256"
        if stem.endswith("aka") and linga == "Stri" and "ik" in form[len(stem) - 4 :]:
            return "#247"
    if stem in ("tri", "catur") and va != "Bahu" or stem == "dvi" and va != "Dvi":
        return "#259"
    return None


def issue_cells(stem, linga, vi, va, upos):
    """The open upstream issues whose affected cells include this slot of this stem."""
    slot = (vi, va)
    out = []
    nominal = upos not in ("PRON", "NUM")
    if nominal and stem.endswith("S") and slot in PADA_SLOTS:
        out.append("#255")
    if (
        nominal
        and stem.endswith("at")
        and not stem.endswith(("mat", "vat"))
        and (
            slot in STRONG or linga == "Stri" or (linga == "Napumsaka" and va == "Bahu")
        )
    ):
        out.append("#256")
    if linga == "Napumsaka" and (
        stem in {"akzi", "daDi", "asTi", "sakTi"}
        or stem.endswith("i")
        and slot == ("Dvitiya", "Bahu")
    ):
        out.append("#257")
    if (
        nominal
        and stem.endswith("in")
        and (
            linga == "Napumsaka"
            and slot == ("Dvitiya", "Bahu")
            or linga == "Stri"
            and slot in {("Saptami", "Eka"), ("Sasthi", "Bahu")}
        )
    ):
        out.append("#258")
    if stem in ("tri", "catur") and va != "Bahu" or stem == "dvi" and va != "Dvi":
        out.append("#259")
    if nominal and stem.endswith(("is", "us")) and slot not in PADA_SLOTS:
        out.append("#260")
    if (
        nominal
        and re.search(r"[twD]f$", stem)
        and linga == "Pum"
        and slot in STRONG
        and slot != ("Prathama", "Eka")
    ):
        out.append("#261")
    if (
        nominal
        and stem.endswith(("mat", "vat"))
        and linga != "Stri"
        and slot in MAT_WEAK
    ):
        out.append("#271")
    if (
        stem == "eka"
        and va == "Eka"
        and vi in ("Caturthi", "Panchami", "Saptami", "Sasthi")
    ):
        out.append("#250")
    if nominal and stem.endswith("aka") and linga == "Stri":
        out.append("#247")
    if stem == "alpa" and linga == "Stri":
        out.append("#229")
    return out


def dcs_mapping_problem(stem, vi, form, upos):
    """Misses caused by how the DCS lemmatizes, not by vidyut."""
    if stem == "tva" and upos == "NOUN":
        return "a: DCS lemma is the suffix -tva"
    if (
        vi == "Panchami"
        and form.endswith(("taH", "tas", "to", "ta"))
        and (
            upos == "PRON"
            or stem in ("asmad", "yuzmad")
            or not stem.endswith(("t", "d"))
        )
    ):
        return "a: -tas adverb tagged as ablative"
    if stem == "enad":
        return "a: enad is a substitute (2.4.34), not an input stem"
    if stem == "sama" and upos == "PRON":
        return "a: sama 'equal' is not sarvadi"
    if (
        stem in SARVADI_BY_SENSE
        and not form.startswith(stem[:-1] + "e")
        and form.endswith(("ARAm", "AnAm", "e", "At", "Aya", "AH"))
    ):
        return "a: sarvadi word in a sense where it is not a pronoun (1.1.34 to 1.1.36)"
    return None


# The ajadi gana (4.1.4) as listed in vidyut's ganapatha.rs.
AJADI_STRI = {
    "ajA",
    "eqakA",
    "kokilA",
    "cawakA",
    "aSvA",
    "mUzikA",
    "bAlA",
    "hoqA",
    "pAkA",
    "vatsA",
    "mandA",
    "vilAtA",
    "pUrvApihARA",
    "pUrvApahARA",
    "aparApahARA",
    "kruYcA",
    "uzRihA",
    "devaviSA",
    "jyezWA",
    "kanizWA",
    "maDyamA",
    "daMzwrA",
}
ANC_STEMS = {
    "prAYc",
    "pratyaYc",
    "udaYc",
    "tiryaYc",
    "samyaYc",
    "avAYc",
    "nyaYc",
    "apAYc",
    "anvaYc",
}


def candidate_bug(stem, linga, vi, va, form, upos, spec_forms):
    """Misses that match a vidyut defect verified by hand (see dcs_subanta_report.md)."""
    if (
        stem == "idam"
        and linga == "Napumsaka"
        and va == "Bahu"
        and form.startswith("im")
    ):
        return "c: new (idam neuter plural, 7.2.109 not applied)"
    if stem in AJADI_STRI and linga == "Stri":
        return "c: new (nyap stem in ajadi gets a second wAp)"
    if stem in ANC_STEMS:
        return "c: new (kvin stems of ancu, 6.3.138 and related rules)"
    if stem == "mahat" and form.startswith("mahAn") and linga == "Pum":
        return "c: new (mahat as a kfdanta, 6.4.10 not applied)"
    if (
        stem == "samrAj"
        and form.startswith("samrA")
        and any(f.startswith("saMrA") for f in spec_forms)
    ):
        return "c: new (samrAj, 8.3.25 not applied)"
    if (
        stem == "maGavan"
        and "maGavat" in form
        or stem == "maGavan"
        and form.startswith("maGavAn")
        and va == "Eka"
    ):
        return "c: new (maghavan, 6.4.128 not applied)"
    return None


# (stem, form) pairs reviewed by hand and found to be outside the classical
# paradigm or DCS lemmatization noise.
REVIEWED = {
    ("pati", "pateH"): "b: pati as a ghi stem outside compounds (1.4.8)",
    ("pati", "patinA"): "b: pati as a ghi stem outside compounds (1.4.8)",
    ("pati", "pataye"): "b: pati as a ghi stem outside compounds (1.4.8)",
    ("pati", "patO"): "b: pati as a ghi stem outside compounds (1.4.8)",
    ("saKi", "saKiH"): "b: sakhi as a plain i-stem (7.1.93)",
    ("saKi", "saKim"): "b: sakhi as a plain i-stem (7.1.93)",
    ("paTin", "paTini"): "b: pathin without ti-lopa (7.1.88)",
    ("paTin", "paTinam"): "b: pathin without ti-lopa (7.1.88)",
}


def reviewed(stem, va, form):
    if stem == "uBaya" and va == "Dvi":
        return "a: ubhaya has no dual; the DCS lemma should be ubha"
    return REVIEWED.get((stem, form))


def vedic_form(stem, linga, vi, va, form, upos):
    """Endings that the grammar allows only in chandas."""
    a_stem = (
        stem.endswith("a") and linga != "Stri" or stem in PRONOUNS_A and linga != "Stri"
    )
    if a_stem and (vi, va) == ("Trtiya", "Bahu") and form.endswith("eBiH"):
        return "b: Vedic -ebhiH (7.1.10)"
    if (
        a_stem
        and va == "Bahu"
        and vi in ("Prathama", "Sambodhana")
        and form.endswith("AsaH")
    ):
        return "b: Vedic -AsaH (7.1.50)"
    if stem.endswith("a") and linga != "Stri" and form == stem[:-1] + "A":
        if (
            va == "Dvi"
            or (linga == "Napumsaka" and va == "Bahu")
            or (vi, va) == ("Trtiya", "Eka")
        ):
            return "b: Vedic -A (7.1.39, 6.1.70)"
    if stem in ("asmad", "yuzmad") and form in (
        "asme",
        "yuzme",
        "tve",
        "tvA",
        "tvAt",
        "mat",
        "asmat",
    ):
        return "b: Vedic pronoun (7.1.39)"
    return None


def alt_label(prim, spec, stem):
    kind = spec[0]
    if kind in ("krdanta", "taddhitanta"):
        return "kfdanta or taddhitanta input"
    if spec[1] == stem:
        return "nyap instead of basic or the reverse"
    if spec[1][:-1] == stem[:-1] and spec[1][-1] in "aiu":
        return "short upasarjana stem (1.2.48)"
    return "explicit feminine stem"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files_dir", nargs="?", help="DCS conllu/files directory")
    ap.add_argument(
        "--check-corpus",
        metavar="TSV",
        help="instead of reading the DCS, check that every row of a corpus TSV is still derived",
    )
    ap.add_argument(
        "--lookup-dir",
        help="DCS conllu/lookup directory (default: <files_dir>/../lookup)",
    )
    ap.add_argument("--engine", choices=["wasm", "python"], default="wasm")
    ap.add_argument("--wasm-dir", default=".")
    ap.add_argument("--wasm-js")
    ap.add_argument("--wasm-bin")
    ap.add_argument("--node", default="node")
    ap.add_argument("--texts", nargs="*", help="only read these DCS text folders")
    ap.add_argument("--summary-out", help="write the summary as JSON")
    ap.add_argument("--misses-out", help="write every missed item as TSV")
    ap.add_argument(
        "--alt-out", help="write the items covered only by an alternative input as TSV"
    )
    ap.add_argument("--corpus-out", help="write a sample of covered items as TSV")
    ap.add_argument("--corpus-rows", type=int, default=12000)
    args = ap.parse_args()
    engine = run_wasm if args.engine == "wasm" else run_python
    if args.check_corpus:
        sys.exit(check_corpus(args.check_corpus, engine, args))
    if not args.files_dir:
        ap.error(
            "the DCS conllu/files directory is required unless --check-corpus is given"
        )

    lookup = (
        Path(args.lookup_dir)
        if args.lookup_dir
        else Path(args.files_dir).parent / "lookup"
    )
    slots = read_chapter_info(lookup)
    grammar = read_dictionary(lookup)
    stats = Counter()
    raw = read_dcs(
        args.files_dir, slots, set(args.texts) if args.texts else None, stats
    )

    # Map items to vidyut inputs.
    rows = []
    for key in sorted(raw):
        item = raw[key]
        mapped, reason = map_item(key, sorted(item.surface))
        if mapped is None:
            stats[f"skipped: {reason}"] += item.count
            continue
        stem, linga, vi, va, form_s, cands = mapped
        upos = item.upos.most_common(1)[0][0]
        rows.append((key, item, stem, linga, vi, va, form_s, cands, upos))
        stats["tokens used"] += item.count

    requests = set()
    for key, item, stem, linga, vi, va, form_s, cands, upos in rows:
        requests.add((primary_spec(stem, linga), linga, vi, va))
        for alt in alternative_specs(stem, linga):
            requests.add((alt, linga, vi, va))
    requests = sorted(requests)
    print(
        f"[dcs] {len(rows)} items, {stats['tokens used']} tokens, {len(requests)} engine requests",
        file=sys.stderr,
    )
    derived = dict(zip(requests, engine(requests, args)))

    def forms_of(spec, li, vi, va):
        out = derived.get((spec, li, vi, va))
        return out if isinstance(out, list) else []

    # Second round: the whole paradigm, in all three genders, of every stem
    # that missed, so that a miss can be checked against the other slots.
    missed_specs = set()
    for key, item, stem, linga, vi, va, form_s, cands, upos in rows:
        prim_forms = forms_of(primary_spec(stem, linga), linga, vi, va)
        if not (match(cands, prim_forms) or context_match(item.contexts, prim_forms)):
            for li in LINGAS:
                missed_specs.add((stem, li))
    para_requests = sorted(
        {
            (primary_spec(st, li), li, vi2, va2)
            for st, li in missed_specs
            for vi2 in VIBHAKTIS
            for va2 in VACANAS
        }
        - set(derived)
    )
    print(
        f"[dcs] {len(para_requests)} paradigm requests for missed stems",
        file=sys.stderr,
    )
    if para_requests:
        derived.update(zip(para_requests, engine(para_requests, args)))

    # How often each (stem, form) is attested in each slot, for the noise test.
    attested_slots = defaultdict(Counter)
    for key, item, stem, linga, vi, va, form_s, cands, upos in rows:
        attested_slots[(stem, form_s)][(linga, vi, va)] += item.count

    tables = {
        name: defaultdict(Counter)
        for name in ("ending", "linga", "vibhakti", "vacana", "upos", "period")
    }
    totals = Counter()
    issue_evidence = defaultdict(Counter)
    alt_rows = []
    misses = []
    covered_rows = []
    for key, item, stem, linga, vi, va, form_s, cands, upos in rows:
        prim = primary_spec(stem, linga)
        out = derived[(prim, linga, vi, va)]
        error = out.get("error") if isinstance(out, dict) else None
        forms = forms_of(prim, linga, vi, va)
        status = None
        spec_used = prim
        hit = match(cands, forms) or context_match(item.contexts, forms)
        if hit:
            status = "covered"
        else:
            for alt in alternative_specs(stem, linga):
                alt_forms = forms_of(alt, linga, vi, va)
                hit = match(cands, alt_forms) or context_match(item.contexts, alt_forms)
                if hit:
                    status = "covered-alt"
                    spec_used = alt
                    totals[f"alt: {alt_label(prim, alt, stem)}"] += item.count
                    alt_rows.append(
                        {
                            "tokens": item.count,
                            "label": alt_label(prim, alt, stem),
                            "form": key[4],
                            "lemma": key[0],
                            "primary": spec_to_str(prim),
                            "primary_forms": "/".join(forms),
                            "alternative": spec_to_str(alt),
                            "hit": hit,
                            "linga": linga,
                            "vibhakti": vi,
                            "vacana": va,
                            "upos": upos,
                        }
                    )
                    break
        ec = ending_class(stem, upos)
        main_period = item.periods.most_common(1)[0][0]
        groups = {
            "ending": ec,
            "linga": linga,
            "vibhakti": vi,
            "vacana": va,
            "upos": upos,
            "period": main_period,
        }
        for name, value in groups.items():
            t = tables[name][value]
            t["types"] += 1
            t["tokens"] += item.count
            if status == "covered":
                t["cov_types"] += 1
                t["cov_tokens"] += item.count
            if status:
                t["best_types"] += 1
                t["best_tokens"] += item.count
        totals["types"] += 1
        totals["tokens"] += item.count
        for iss in issue_cells(stem, linga, vi, va, upos):
            ev = issue_evidence[iss]
            ev["tokens"] += item.count
            ev["types"] += 1
            ev[f"tokens {status or 'missed'}"] += item.count
            ev[f"tokens {item.periods.most_common(1)[0][0]}"] += item.count
        if status:
            totals[f"{status}_types"] += 1
            totals[f"{status}_tokens"] += item.count
            covered_rows.append(
                (key, item, stem, linga, vi, va, hit, upos, ec, spec_used)
            )
            continue

        # Classify the miss. The order matters: the first rule that applies wins.
        other_slots = sorted(
            f"{li}.{vi2}.{va2}"
            for li in LINGAS
            for vi2 in VIBHAKTIS
            for va2 in VACANAS
            if match(cands, forms_of(primary_spec(stem, li), li, vi2, va2))
        )
        issue = known_issue(stem, linga, vi, va, form_s, upos)
        classical = item.periods["classical"]
        vedic_majority = item.periods["vedic"] * 2 >= item.count
        alt_forms_all = [
            f
            for a in alternative_specs(stem, linga)
            for f in forms_of(a, linga, vi, va)
        ]
        if error:
            category = "c: engine error"
        elif reviewed(stem, va, form_s):
            category = reviewed(stem, va, form_s)
        elif candidate_bug(stem, linga, vi, va, form_s, upos, forms + alt_forms_all):
            category = candidate_bug(
                stem, linga, vi, va, form_s, upos, forms + alt_forms_all
            )
        elif form_s == stem and stem[-1] not in "aAiIuUfF" and not vedic_majority:
            category = (
                "a: form identical to the lemma (anukarana or DCS reconstruction)"
            )
        elif dcs_mapping_problem(stem, vi, form_s, upos):
            category = dcs_mapping_problem(stem, vi, form_s, upos)
        elif issue:
            category = f"known issue {issue}"
        elif any(loose(c) == loose(f) for c in cands for f in forms):
            category = "a: spelling variant in the source (n/R, doubled consonant)"
        elif vedic_form(stem, linga, vi, va, form_s, upos):
            category = vedic_form(stem, linga, vi, va, form_s, upos)
        elif vedic_majority:
            category = "b: mostly in Vedic texts"
        elif classical * 5 < item.count:
            category = "b: mostly in epic, puranic or BHS texts"
        elif other_slots:
            here = attested_slots[(stem, form_s)][(linga, vi, va)]
            elsewhere = sum(
                attested_slots[(stem, form_s)][tuple(x.split("."))] for x in other_slots
            )
            same_gender = any(x.startswith(linga + ".") for x in other_slots)
            if not same_gender:
                category = "a: form belongs to another gender"
            elif elsewhere >= here:
                category = "a: tagged slot differs from the usual one"
            else:
                category = "c?: form generated in another slot only"
        else:
            category = "c: not generated"
        totals[f"miss: {category}"] += item.count
        misses.append(
            {
                "tokens": item.count,
                "category": category,
                "form": key[4],
                "form_slp1": form_s,
                "lemma": key[0],
                "stem": stem,
                "pratipadika": spec_to_str(prim),
                "ending": ec,
                "upos": upos,
                "dcs_grammar": grammar.get(item.lemma_id, ""),
                "linga": linga,
                "vibhakti": vi,
                "vacana": va,
                "vidyut": "/".join(forms)
                if forms
                else (f"ERROR {error}" if error else ""),
                "vidyut_alt": " ".join(
                    f"{spec_to_str(a)}={'/'.join(forms_of(a, linga, vi, va))}"
                    for a in alternative_specs(stem, linga)[:3]
                ),
                "other_slots": " ".join(other_slots[:6]),
                "vedic": item.periods["vedic"],
                "epic": item.periods["epic"],
                "bhs": item.periods["bhs"],
                "classical": classical,
                "surface": " ".join(f"{k}:{v}" for k, v in item.surface.most_common(3)),
                "token_context": " ".join(
                    f"{p}:{t}" for (p, t), _ in item.contexts.most_common(2)
                ),
                "ref": item.ref,
                "sent_id": item.sent_id,
            }
        )

    misses.sort(
        key=lambda m: (
            -m["tokens"],
            m["stem"],
            m["form_slp1"],
            m["linga"],
            m["vibhakti"],
            m["vacana"],
        )
    )

    summary = {
        "skips": dict(sorted(stats.items())),
        "totals": dict(sorted(totals.items())),
        "issues": {
            k: dict(sorted(v.items())) for k, v in sorted(issue_evidence.items())
        },
        "tables": {
            name: {
                k: dict(v)
                for k, v in sorted(t.items(), key=lambda kv: (-kv[1]["tokens"], kv[0]))
            }
            for name, t in tables.items()
        },
    }
    if args.summary_out:
        with open(args.summary_out, "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1)

    if args.misses_out:
        cols = list(misses[0].keys()) if misses else []
        with open(args.misses_out, "w", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(cols)
            for m in misses:
                w.writerow([m[c] for c in cols])

    if args.alt_out:
        alt_rows.sort(
            key=lambda r: (
                -r["tokens"],
                r["lemma"],
                r["form"],
                r["linga"],
                r["vibhakti"],
                r["vacana"],
            )
        )
        with open(args.alt_out, "w", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            cols = list(alt_rows[0].keys()) if alt_rows else []
            w.writerow(cols)
            for r in alt_rows:
                w.writerow([r[c] for c in cols])

    if args.corpus_out:
        write_corpus(args.corpus_out, covered_rows, args.corpus_rows)

    t = totals
    print(f"items: {t['types']}  tokens: {t['tokens']}")
    print(
        f"covered (primary input): {t['covered_types']} types ({pct(t['covered_types'], t['types'])}%), "
        f"{t['covered_tokens']} tokens ({pct(t['covered_tokens'], t['tokens'])}%)"
    )
    best_types = t["covered_types"] + t["covered-alt_types"]
    best_tokens = t["covered_tokens"] + t["covered-alt_tokens"]
    print(
        f"covered (with alternatives): {best_types} types ({pct(best_types, t['types'])}%), "
        f"{best_tokens} tokens ({pct(best_tokens, t['tokens'])}%)"
    )
    for name in ("ending", "linga", "vibhakti", "vacana", "period"):
        print(
            f"\n{name:<18} {'types':>8} {'tokens':>9} {'%types':>7} {'%tokens':>8} {'%tok best':>9}"
        )
        for k, v in sorted(
            tables[name].items(), key=lambda kv: (-kv[1]["tokens"], kv[0])
        ):
            print(
                f"{k:<18} {v['types']:>8} {v['tokens']:>9} {pct(v['cov_types'], v['types']):>7} "
                f"{pct(v['cov_tokens'], v['tokens']):>8} {pct(v['best_tokens'], v['tokens']):>9}"
            )
    print("\ncovered only with an alternative input (tokens):")
    for k, v in sorted(
        ((k, v) for k, v in t.items() if k.startswith("alt: ")),
        key=lambda kv: (-kv[1], kv[0]),
    ):
        print(f"  {k[5:]:<45} {v:>8}")
    print("\nopen upstream issues: attested tokens in the affected cells")
    for k, v in sorted(issue_evidence.items()):
        print(
            f"  {k:<6} cells {v['tokens']:>7}  covered {v['tokens covered']:>7}  "
            f"alt {v['tokens covered-alt']:>6}  missed {v['tokens missed']:>6}"
        )
    print("\nmisses by category (tokens):")
    for k, v in sorted(
        ((k, v) for k, v in t.items() if k.startswith("miss: ")),
        key=lambda kv: (-kv[1], kv[0]),
    ):
        print(f"  {k[6:]:<45} {v:>8}")


def check_corpus(path, engine, args):
    """Regression mode: every (pratipadika, linga, vibhakti, vacana, form) row must still be derived."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    requests = sorted(
        {
            (spec_from_str(r["pratipadika"]), r["linga"], r["vibhakti"], r["vacana"])
            for r in rows
        }
    )
    derived = dict(zip(requests, engine(requests, args)))
    failures = []
    for r in rows:
        out = derived[
            (spec_from_str(r["pratipadika"]), r["linga"], r["vibhakti"], r["vacana"])
        ]
        if not isinstance(out, list) or r["form"] not in out:
            failures.append(r)
    for r in failures:
        print(
            "FAIL",
            r["pratipadika"],
            r["linga"],
            r["vibhakti"],
            r["vacana"],
            r["form"],
            derived[
                (
                    spec_from_str(r["pratipadika"]),
                    r["linga"],
                    r["vibhakti"],
                    r["vacana"],
                )
            ],
            sep="\t",
        )
    print(f"{len(rows) - len(failures)} of {len(rows)} corpus rows derived")
    return 1 if failures else 0


def write_corpus(path, covered_rows, budget):
    """A deterministic sample of covered items for regression testing.

    Every (stem class, linga, vibhakti, vacana) cell contributes its five most
    frequent items first; the rest of the budget goes to the most frequent
    items overall. Each row names the input that covered it, so items covered
    only by an alternative input appear with that input.
    """
    by_cell = defaultdict(list)
    for r in covered_rows:
        key, item, stem, linga, vi, va, hit, upos, ec, spec = r
        by_cell[(ec, linga, vi, va)].append(r)

    def order(r):
        return (-r[1].count, r[2], r[6], r[3], r[4], r[5])

    chosen = {}
    for cell in sorted(by_cell):
        for r in sorted(by_cell[cell], key=order)[:5]:
            chosen[(r[2], r[6], r[3], r[4], r[5])] = r
    for r in sorted(covered_rows, key=order):
        if len(chosen) >= budget:
            break
        chosen.setdefault((r[2], r[6], r[3], r[4], r[5]), r)
    vi_order = {v: i for i, v in enumerate(VIBHAKTIS)}
    va_order = {v: i for i, v in enumerate(VACANAS)}
    out = sorted(
        chosen.values(),
        key=lambda r: (r[2], r[3], vi_order[r[4]], va_order[r[5]], r[6]),
    )
    with open(path, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(
            [
                "pratipadika",
                "linga",
                "vibhakti",
                "vacana",
                "form",
                "form_iast",
                "lemma",
                "stem_class",
                "tokens",
                "ref",
                "sent_id",
            ]
        )
        for key, item, stem, linga, vi, va, hit, upos, ec, spec in out:
            w.writerow(
                [
                    spec_to_str(spec),
                    linga,
                    vi,
                    va,
                    hit,
                    key[4],
                    key[0],
                    ec,
                    item.count,
                    item.ref,
                    item.sent_id,
                ]
            )


if __name__ == "__main__":
    main()
