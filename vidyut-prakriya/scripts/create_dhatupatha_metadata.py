#!/usr/bin/env python3
"""Creates `data/dhatupatha-metadata.tsv`: an English meaning and a corpus
frequency for each dhatu in `data/dhatupatha.tsv`.

Usage:

    # English meanings (ashtadhyayi.com)
    curl -L -o /tmp/data.txt https://raw.githubusercontent.com/ashtadhyayi-com/data/master/dhatu/data.txt

    # Corpus (Digital Corpus of Sanskrit, CoNLL-U dump). Any checkout that
    # contains `dcs/data/conllu` works.
    git clone --depth=1 https://github.com/OliverHellwig/sanskrit.git /tmp/sanskrit

    uv run create_dhatupatha_metadata.py \\
        --ashtadhyayi-dhatus /tmp/data.txt \\
        --dcs-conllu /tmp/sanskrit/dcs/data/conllu \\
        --output ../data/dhatupatha-metadata.tsv \\
        [--report /tmp/report.md] [--trace /tmp/trace.tsv]

The output is deterministic for fixed inputs. For details on the columns and
on how corpus counts are assigned to dhatus, see `data/README.md`.

Summary of the counting method:

1. A DCS lemma counts as a verb if its grammar label has a gana class such as
   "1. P." or "10.Ā.,10.P.". Each token of such a lemma counts once (finite
   forms, participles, infinitives, and absolutives are all lemmatized to the
   verb in DCS).
2. Prefixed lemmas (for example `uddhṛ`, preverb `ut`) are reduced to their
   base by re-joining the DCS preverb string with each candidate base under a
   small set of sandhi rules and keeping the bases that reproduce the lemma.
3. A base is matched to dhatupatha entries by its plain root (the `dhatu`
   field of the ashtadhyayi.com data), with a few spelling normalizations
   (ṝ -> ṛ, final e/ai/o -> ā, ḷ -> ṛ, anusvara -> class nasal) and a short
   list of suppletive stems (paś -> dṛś, ah -> brū, dham -> dhmā, vadh -> han).
   DCS lemmas in "-ay" with a class 10 label are matched to curadi roots
   through their ṇic stem; causatives of other roots are not counted.
4. If several entries share the plain root (homonyms such as kṛ 08.0010 "to
   do" and kṛ 05.0007 "to kill"), the DCS dictionary meanings of the lemma are
   compared with the English meaning of each entry. A unique best match gets
   all tokens ("meaning"). Otherwise the assignment is an estimate
   ("estimated"): a prefixed lemma follows the split of its unprefixed base;
   failing that, the tokens go to the tied entries tagged "common" in the
   ashtadhyayi.com data, and failing that, they are split evenly.

DCS gana labels are not used: for the unprefixed lemmas that match exactly
one entry, the DCS label names a different gana about a third of the time
(DCS lists the main kṛ as class 2, for example).
"""

import argparse
import collections
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

from vidyut.lipi import Scheme, transliterate

DEFAULT_DHATUPATHA = Path(__file__).parent.parent / "data" / "dhatupatha.tsv"

# A gana class label in the DCS dictionary, e.g. "1. P." or "1.Ā.,1.P.".
DCS_VERB_LABEL = re.compile(r"(?:^|,)\s*(?:10|[1-9])\.\s?[PĀ]")
DCS_CLASS_10 = re.compile(r"(?:^|,)\s*10\.\s?[PĀ]")

# Characters that are garbled in some DCS dictionary entries.
DCS_FIXES = {chr(0xFFB1): "ḷ", chr(0xFFF8): "ū", chr(0xFFDE): "ṝ"}

# DCS lemmatizes a few verbs under a present stem or a suppletive root. Each
# key is a DCS spelling, each value the plain root of the dhatupatha entry.
SUPPLETIVE = {
    "paś": "dṛś",  # 7.3.78 pāghrādhmāsthā...dṛśi...paśya...
    "ah": "brū",  # 3.4.84 bruvaḥ pañcānām ādita āho bruvaḥ
    "dham": "dhmā",  # 7.3.78
    "vadh": "han",  # 2.4.42 hano vadha liṅi, 2.4.43 luṅi ca
    "bhṛjj": "bhrajj",  # bhrasj, 6.1.16 grahijyā...bhrasjatīnāṃ ṅiti ca
}

VOWELS = ["ai", "au", "a", "ā", "i", "ī", "u", "ū", "ṛ", "ṝ", "ḷ", "e", "o"]
NASAL_FOR = {}
for _nasal, _stops in [("ṅ", "kg"), ("ñ", "cj"), ("ṇ", "ṭḍ"), ("n", "td"), ("m", "pb")]:
    for _c in _stops:
        NASAL_FOR[_c] = _nasal

STOPWORDS = set(
    """to the a an of or and in on at by for with from into upon as any one
    someone something anything oneself one's be is are being it its
    acc gen dat loc instr abl nom esp e g etc also very much well
    """.split()
)


# ---------------------------------------------------------------------------
# Spelling helpers
# ---------------------------------------------------------------------------


def initial_vowel(s):
    for v in VOWELS:
        if s.startswith(v):
            return v
    return None


def ends_with_vowel(s):
    return any(s.endswith(v) for v in VOWELS)


def nasal_norm(s):
    """Writes anusvara before a stop as the class nasal (saṃgam -> saṅgam)."""
    out = []
    for i, c in enumerate(s):
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if c == "ṃ" and nxt in NASAL_FOR:
            out.append(NASAL_FOR[nxt])
        else:
            out.append(c)
    return "".join(out)


def surface_norm(s):
    """Spelling normalization applied to everything we compare."""
    s = s.replace("ṝ", "ṛ").replace("ḷ", "ṛ").replace("cch", "ch").replace("jjh", "jh")
    return nasal_norm(s)


def root_key(s):
    """Normalizes a plain root or a DCS verb spelling for matching."""
    s = surface_norm(s)
    for end in ("ai", "e", "o"):
        if len(s) > len(end) and s.endswith(end):
            s = s[: -len(end)] + "ā"
            break
    return s


def alt_keys(key):
    """Looser keys for a root, used only when a DCS spelling matches no root
    at all: svañj -> svaj, dambh -> dabh, daṃś -> daś, kṣaṇ -> kṣan,
    div -> dīv, katha -> kath."""
    out = []
    for a, b in (("ñj", "j"), ("mbh", "bh"), ("ṃś", "ś"), ("ṇ", "n")):
        if a in key:
            out.append(key.replace(a, b))
    if key.endswith("iv"):
        out.append(key[:-2] + "īv")
    if key.endswith("a") and len(key) > 2:
        out.append(key[:-1])
    return out


def strip_svaras(slp1):
    return slp1.replace("\\", "").replace("^", "")


def nic_stems(root):
    """Plausible ṇic stems of a plain root (with "ay"), surface-normalized."""
    if root.endswith("a") and not root.endswith(("ai", "au")) and len(root) > 1:
        # adanta roots such as katha (kathayati) and gaṇa (gaṇayati)
        return {surface_norm(root[:-1] + "ay")}
    for end in ("ai", "e", "o"):
        if root.endswith(end):
            root = root[: -len(end)] + "ā"  # 6.1.45 ādeca upadeśe 'śiti
            break
    out = {root}
    v = next((vv for vv in VOWELS if root.endswith(vv)), None)
    if v is not None:
        head = root[: -len(v)]
        if v in ("i", "ī"):
            out.add(head + "āy")
        elif v in ("u", "ū"):
            out.add(head + "āv")
        elif v in ("ṛ", "ṝ"):
            out.add(head + "ār")
        elif v == "ā":
            out.add(head + "āp")
            out.add(head + "āy")
    else:
        # Find the last vowel.
        for i in range(len(root) - 1, -1, -1):
            vv = initial_vowel(root[i:])
            if vv is not None:
                head, tail = root[:i], root[i + len(vv) :]
                if vv == "i":
                    out.add(head + "e" + tail)
                elif vv == "ṝ":
                    out.add(head + "īr" + tail)  # 7.1.100 ṝta id dhātoḥ
                elif vv == "u":
                    out.add(head + "o" + tail)
                elif vv == "ṛ":
                    out.add(head + "ar" + tail)
                    if root == "kṛp":
                        out.add("kalp")
                elif vv == "a" and len(tail) == 1:
                    out.add(head + "ā" + tail)
                break
    return {surface_norm(x + "ay") for x in out}


def join_preverb(pre, root):
    """Candidate surface forms of `pre` + `root` at the final boundary only.

    `pre` is the DCS preverb string, whose internal sandhi is already done
    (e.g. "anvava", "saṃs", "ut").
    """
    # Variants with ṣatva (8.3.65 ff.) and ṇatva (8.4.14 ff.). Generating them
    # unconditionally is harmless: a variant only matters if it reproduces
    # the DCS lemma exactly.
    roots = {root}
    if root.startswith("s"):
        r2 = "ṣ" + root[1:]
        if r2.startswith("ṣth"):
            r2 = "ṣṭh" + r2[3:]
        elif r2.startswith("ṣt"):
            r2 = "ṣṭ" + r2[2:]
        roots.add(r2)
    if "n" in root:
        roots |= {r.replace("n", "ṇ", 1) for r in list(roots)}

    out = set()
    for r in roots:
        out |= _join(pre, r)
    return {surface_norm(x) for x in out}


def _join(p, r):
    out = {p + r}
    v = initial_vowel(r)
    if ends_with_vowel(p):
        if v is not None:
            rest = r[len(v) :]
            last = p[-1]
            if p.endswith(("ai", "au")):
                return out
            if last in "aā":
                b = p[:-1]
                if v in ("a", "ā"):
                    out.add(b + "ā" + rest)
                elif v in ("i", "ī"):
                    out.add(b + "e" + rest)
                elif v in ("u", "ū"):
                    out.add(b + "o" + rest)
                elif v in ("ṛ", "ṝ"):
                    out |= {b + "ār" + rest, b + "ar" + rest}
                elif v in ("e", "ai"):
                    out |= {b + "e" + rest, b + "ai" + rest}
                elif v in ("o", "au"):
                    out |= {b + "o" + rest, b + "au" + rest}
            elif last in "iī":
                out.add(p[:-1] + ("ī" + rest if v in ("i", "ī") else "y" + r))
            elif last in "uū":
                out.add(p[:-1] + ("ū" + rest if v in ("u", "ū") else "v" + r))
        elif r.startswith("ch"):
            out.add(p + "c" + r)
        return out

    stem, last = p[:-1], p[-1]
    c = r[:1]
    voiced = v is not None or c in set("gjḍdbyrvnmlhṇñṅ")
    if last in "td":
        if voiced and c != "h":
            out.add(stem + "d" + r)
        if c == "h":
            out.add(stem + "ddh" + r[1:])
        if c in ("n", "m"):
            out.add(stem + "n" + r)
        if c == "l":
            out.add(stem + "l" + r)
        if c == "c":
            out.add(stem + "c" + r)
        if c == "j":
            out.add(stem + "j" + r)
        if c == "ś":
            out |= {stem + "cch" + r[1:], stem + "cś" + r[1:]}
        if c in ("k", "p", "t", "s", "ṣ"):
            out.add(stem + "t" + r)
        if r.startswith("st"):
            out.add(stem + "t" + r[1:])
    elif last in ("ḥ", "s", "r"):
        prev = stem[-1:] if stem else ""
        if voiced:
            out.add(stem + "r" + r)
            if prev == "a" and last != "r":
                out.add(stem[:-1] + "o" + r)
        elif c in ("k", "p"):
            out |= {stem + "ṣ" + r, stem + "s" + r, stem + "ḥ" + r}
        elif c == "c":
            out.add(stem + "ś" + r)
        elif c == "t":
            out |= {stem + "s" + r, stem + "ṣṭ" + r[1:]}  # 8.3.102 nisas tapatāv
        elif c == "ṭ":
            out.add(stem + "ṣ" + r)
        elif c in ("ś", "ṣ", "s"):
            out |= {stem + "ḥ" + r, stem + c + r}
    elif last in ("m", "ṃ"):
        if v is not None:
            out.add(stem + "m" + r)
        else:
            out |= {stem + "ṃ" + r, stem + "m" + r}
    return out


# ---------------------------------------------------------------------------
# Meaning comparison
# ---------------------------------------------------------------------------


def meaning_phrases(text):
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text.lower())
    out = set()
    for part in re.split(r"[;,]", text):
        part = " ".join(part.split())
        if part.startswith("to "):
            part = part[3:]
        if part:
            out.add(part)
    return out


def meaning_words(text):
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text.lower())
    return {w for w in re.findall(r"[a-z]+", text) if w not in STOPWORDS and len(w) > 1}


def similarity(dcs_meanings, en):
    """Shared phrases count 10, shared content words count 1."""
    p = len(meaning_phrases(dcs_meanings) & meaning_phrases(en))
    w = len(meaning_words(dcs_meanings) & meaning_words(en))
    return 10 * p + w


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def read_dhatupatha(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:
                continue
            line = line.rstrip("\n")
            if not line:
                continue
            code, dhatu, artha = line.split("\t")
            if dhatu == "-":
                continue
            out.append((code, dhatu, artha))
    return out


def clean_english(s):
    s = " ".join((s or "").split())
    s = re.sub(r"\s*,\s*", ", ", s).strip(" ,;")
    return s.replace("\t", " ")


def read_ashtadhyayi(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {row["baseindex"]: row for row in data["data"]}


def fix_dcs(s):
    s = "".join(DCS_FIXES.get(ch, ch) for ch in s)
    return unicodedata.normalize("NFC", s).strip()


def read_dcs_dictionary(conllu_dir):
    """lemma id -> (lemma, grammar, preverbs, meanings) for verbal lemmas."""
    path = Path(conllu_dir) / "lookup" / "dictionary.csv"
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        next(reader)
        for row in reader:
            if len(row) < 5 or not row[0].isdigit():
                continue
            lid, lemma, grammar, preverbs, meanings = row[:5]
            if not DCS_VERB_LABEL.search(grammar):
                continue
            out[int(lid)] = (fix_dcs(lemma), grammar, fix_dcs(preverbs), meanings)
    return out


def count_dcs_tokens(conllu_dir, lemma_ids):
    counts = collections.Counter()
    files = sorted((Path(conllu_dir) / "files").rglob("*.conllu"))
    if not files:
        sys.exit(f"No .conllu files under {conllu_dir}/files")
    for path in files:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line[:1].isdigit():
                    continue
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 10 or not cols[0].isdigit():
                    continue
                m = re.search(r"(?:^|\|)LemmaId=(\d+)", cols[9])
                if m:
                    lid = int(m.group(1))
                    if lid in lemma_ids:
                        counts[lid] += 1
    return counts, len(files)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def to_int(x):
    """Rounds half up, so that output does not depend on float formatting."""
    return int(x + 0.5)


class Entry:
    def __init__(self, code, aupadeshika, en, root, common=False):
        self.code = code
        self.aupadeshika = aupadeshika
        self.gana = int(code.split(".")[0])
        self.en = en
        self.root = root
        self.key = root_key(root) if root else ""
        # Tagged "common" in the ashtadhyayi.com data.
        self.common = common
        self.total = 0.0
        self.prefixed = 0.0
        self.estimated = 0.0
        self.by_method = collections.Counter()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dhatupatha", default=str(DEFAULT_DHATUPATHA))
    parser.add_argument(
        "--ashtadhyayi-dhatus", required=True, help="ashtadhyayi.com dhatu/data.txt"
    )
    parser.add_argument(
        "--dcs-conllu", required=True, help="DCS dcs/data/conllu directory"
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", help="optional Markdown report for review")
    parser.add_argument(
        "--trace", help="optional TSV with the assignment of every DCS lemma"
    )
    args = parser.parse_args()

    report = collections.defaultdict(list)

    # 1. English meanings and plain roots from ashtadhyayi.com
    dp = read_dhatupatha(args.dhatupatha)
    ad = read_ashtadhyayi(args.ashtadhyayi_dhatus)
    entries = []
    for code, dhatu, _artha in dp:
        row = ad.get(code)
        if row is None:
            report["no_source_row"].append((code, dhatu))
            entries.append(Entry(code, dhatu, "", ""))
            continue
        theirs = transliterate(row["aupadeshik"], Scheme.Devanagari, Scheme.Slp1)
        if strip_svaras(dhatu) != theirs:
            report["aupadeshika_mismatch"].append((code, dhatu, theirs, row["dhatu"]))
        en = clean_english(row.get("artha_english", ""))
        if not en:
            report["no_english"].append((code, dhatu))
        root = transliterate(row["dhatu"], Scheme.Devanagari, Scheme.Iast).strip()
        tags = {t.strip() for t in row.get("tags", "").split(",")}
        entries.append(Entry(code, dhatu, en, root, "common" in tags))

    # Indexes from spellings to dhatupatha entries.
    by_key = collections.defaultdict(list)  # root key -> entries
    by_alt = collections.defaultdict(list)  # looser root key -> entries
    nic10 = collections.defaultdict(list)  # ṇic stem -> curadi entries
    nic_other = collections.defaultdict(list)  # ṇic stem -> other entries
    spellings = {}  # surface spelling a prefixed lemma may contain -> key
    for e in entries:
        if not e.key:
            continue
        by_key[e.key].append(e)
        for alt in alt_keys(e.key):
            by_alt[alt].append(e)
        spellings[surface_norm(e.root)] = e.key
        spellings[e.key] = e.key
        for stem in nic_stems(e.root):
            (nic10 if e.gana == 10 else nic_other)[stem].append(e)
            spellings[stem] = stem
    aliases = {root_key(k): root_key(v) for k, v in SUPPLETIVE.items()}
    for k in aliases:
        spellings[k] = k

    # 2. DCS lemmas and token counts
    lemmas = read_dcs_dictionary(args.dcs_conllu)
    counts, n_files = count_dcs_tokens(args.dcs_conllu, set(lemmas))
    attested = set()  # keys of unprefixed DCS verbs that occur in the corpus
    for lid, (lemma, _g, pre, _m) in lemmas.items():
        if not pre and counts.get(lid):
            attested.add(root_key(lemma))
            spellings.setdefault(surface_norm(lemma), root_key(lemma))
            spellings.setdefault(root_key(lemma), root_key(lemma))

    def plain_candidates(key):
        if key in aliases:
            pool = by_key.get(aliases[key], [])
        else:
            pool = by_key.get(key) or by_alt.get(key, [])
        # Curadi entries have "-ay" forms; use them only as a last resort.
        return [e for e in pool if e.gana != 10] or list(pool)

    def candidates(base, is_class10):
        """(entries, causative readings) for a DCS base key."""
        if is_class10 and base.endswith("ay"):
            c10 = list(nic10.get(base, []))
            caus = [e for e in nic_other.get(base, []) if e.gana != 10]
            if c10 or caus:
                return c10, caus
        return plain_candidates(base), []

    by_last = collections.defaultdict(set)
    for sp in spellings:
        by_last[sp[-1:]].add(sp)
    short = {sp for sp in spellings if len(sp) <= 2 or sp.endswith(("n", "ṇ"))}

    def reduce_prefixed(lemma, pre):
        target = surface_norm(lemma)
        found = set()
        for sp in by_last.get(target[-1:], set()) | short:
            if len(sp) <= len(target) + 1 and target in join_preverb(pre, sp):
                found.add(spellings[sp])
        found = sorted(found)
        if len(found) > 1:
            # Prefer bases that DCS also attests without a preverb.
            found = [b for b in found if b in attested] or found
        return found

    # Pass 1 handles unprefixed lemmas, pass 2 prefixed ones, whose unresolved
    # tokens are split in proportion to the unprefixed counts from pass 1.
    unprefixed_share = collections.defaultdict(collections.Counter)
    order = sorted(lemmas.items(), key=lambda kv: (bool(kv[1][2]), kv[0]))
    unassigned = collections.Counter()
    causative = collections.Counter()
    single_no_overlap = []
    ambiguous_base = []
    trace = []
    for lid, (lemma, grammar, pre, meanings) in order:
        n = counts.get(lid, 0)
        if n == 0:
            continue
        is10 = bool(DCS_CLASS_10.search(grammar))
        if pre:
            bases = reduce_prefixed(lemma, pre)
            if len(bases) > 1:
                ambiguous_base.append((n, lemma, pre, bases))
        else:
            bases = [root_key(lemma)]

        cands, caus = [], []
        for b in bases:
            c, k = candidates(b, is10)
            cands += [e for e in c if e not in cands]
            caus += [e for e in k if e not in caus]
        if not cands:
            if caus:
                causative[(lemma, pre, caus[0].root)] += n
                trace.append((lid, lemma, pre, grammar, n, bases, "causative", {}))
            else:
                unassigned[(lemma, pre, grammar)] += n
                trace.append((lid, lemma, pre, grammar, n, bases, "unmatched", {}))
            continue

        scores = {e.code: similarity(meanings, e.en) for e in cands}
        best = max(scores.values())
        weight = 1.0
        forced_estimate = False
        if caus:
            # An "-ay" lemma that may be a curadi root or the causative of a
            # homonym. The better meaning match decides. On a tie, the
            # "common" tag decides; if it does not, half of the tokens go to
            # the curadi entry (marked estimated).
            caus_best = max(similarity(meanings, e.en) for e in caus)
            if caus_best == best:
                c10_common = any(e.common for e in cands)
                caus_common = any(e.common for e in caus)
                if caus_common and not c10_common:
                    caus_best += 1
                elif c10_common and not caus_common:
                    best += 1
            if caus_best > best:
                causative[(lemma, pre, caus[0].root)] += n
                trace.append((lid, lemma, pre, grammar, n, bases, "causative", {}))
                continue
            if caus_best == best:
                weight = 0.5
                forced_estimate = True
                causative[(lemma, pre, caus[0].root)] += n * 0.5
            best = max(scores.values())

        if len(cands) == 1:
            shares = {cands[0].code: 1.0}
            method = "exact"
            if best == 0 and meanings.strip() and cands[0].en:
                single_no_overlap.append(
                    (n, lemma, pre, cands[0].code, cands[0].en, meanings[:90])
                )
        else:
            winners = [e for e in cands if scores[e.code] == best] if best > 0 else []
            if len(winners) == 1:
                shares = {winners[0].code: 1.0}
                method = "meaning"
            else:
                method = "estimated"
                weights = collections.Counter()
                if pre:
                    # A prefixed verb follows the split of its base.
                    pool = cands
                    for b in bases:
                        for code, w in unprefixed_share[b].items():
                            if any(e.code == code for e in pool):
                                weights[code] += w
                else:
                    pool = winners or cands
                if not weights:
                    common = [e for e in pool if e.common]
                    if common:
                        pool = common
                    weights = {e.code: 1.0 for e in pool}
                total_w = sum(weights.values())
                shares = {code: w / total_w for code, w in sorted(weights.items())}
        if forced_estimate:
            method = "estimated"
        shares = {code: frac * weight for code, frac in shares.items()}
        trace.append((lid, lemma, pre, grammar, n, bases, method, shares))

        by_code = {e.code: e for e in cands}
        for code, frac in shares.items():
            e = by_code[code]
            t = n * frac
            e.total += t
            if pre:
                e.prefixed += t
            if method == "estimated":
                e.estimated += t
            e.by_method[method] += t
            if not pre:
                for b in bases:
                    unprefixed_share[b][code] += t

    if args.trace:
        with open(args.trace, "w", encoding="utf-8") as f:
            f.write(
                "lemma_id\tlemma\tpreverbs\tgrammar\ttokens\tbases\tmethod\tshares\n"
            )
            for lid, lemma, pre, grammar, n, bases, method, shares in trace:
                sh = " ".join(f"{c}={v:.3f}" for c, v in sorted(shares.items()))
                f.write(
                    f"{lid}\t{lemma}\t{pre}\t{grammar}\t{n}\t{' '.join(bases)}\t{method}\t{sh}\n"
                )

    # 3. Output
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        f.write(
            "code\tartha_en\tdcs_count\tdcs_count_prefixed\tdcs_count_estimated\tdcs_assign\n"
        )
        for e in entries:
            total = to_int(e.total)
            # The least certain method that contributed at least one token.
            assign = "none"
            if total > 0:
                assign = "exact"
                for method in ("meaning", "estimated"):
                    if to_int(e.by_method[method]) > 0:
                        assign = method
            f.write(
                f"{e.code}\t{e.en}\t{total}\t{to_int(e.prefixed)}\t"
                f"{to_int(e.estimated)}\t{assign}\n"
            )

    total_tokens = sum(counts.values())
    assigned = sum(e.total for e in entries)
    print(
        f"{len(entries)} entries, {sum(1 for e in entries if e.en)} with English; "
        f"{n_files} CoNLL-U files, {len(lemmas)} verbal lemmas, {total_tokens} verb tokens, "
        f"{assigned:.0f} assigned ({100 * assigned / max(total_tokens, 1):.1f}%), "
        f"{sum(causative.values())} causative, {sum(unassigned.values())} unmatched",
        file=sys.stderr,
    )

    if args.report:
        write_report(
            args.report,
            report,
            entries,
            unassigned,
            causative,
            single_no_overlap,
            ambiguous_base,
            total_tokens,
        )


def write_report(
    path,
    report,
    entries,
    unassigned,
    causative,
    single_no_overlap,
    ambiguous_base,
    total_tokens,
):
    with open(path, "w", encoding="utf-8") as f:

        def w(s=""):
            f.write(s + "\n")

        w("# dhatupatha-metadata.tsv build report")
        w()
        w(f"- entries: {len(entries)}")
        w(f"- entries with English: {sum(1 for e in entries if e.en)}")
        w(
            f"- entries with a DCS count: {sum(1 for e in entries if round(e.total) > 0)}"
        )
        w(
            f"- DCS verb tokens: {total_tokens}; assigned: {sum(e.total for e in entries):.0f}; "
            f"causatives not counted: {sum(causative.values())}; unmatched: {sum(unassigned.values())}"
        )
        w()
        w("## Rows with no ashtadhyayi.com entry")
        for r in report["no_source_row"]:
            w(f"- {r}")
        w()
        w("## Aupadeshika mismatches (vidyut vs ashtadhyayi.com, svaras removed)")
        w()
        w("| code | vidyut | ashtadhyayi.com (SLP1) | plain root (ashtadhyayi.com) |")
        w("|---|---|---|---|")
        for code, mine, theirs, root in report["aupadeshika_mismatch"]:
            w(f"| {code} | `{mine}` | `{theirs}` | {root} |")
        w()
        w("## Entries without an English meaning")
        for code, dhatu in report["no_english"]:
            w(f"- {code} `{dhatu}`")
        w()
        w("## Top 60 by count")
        w()
        w("| code | root | count | prefixed | estimated | assign | English |")
        w("|---|---|---|---|---|---|---|")
        for e in sorted(entries, key=lambda e: (-e.total, e.code))[:60]:
            w(
                f"| {e.code} | {e.root} | {e.total:.0f} | {e.prefixed:.0f} | {e.estimated:.0f} | "
                f"{','.join(sorted(m for m, t in e.by_method.items() if t >= 0.5))} | {e.en[:60]} |"
            )
        w()
        w("## Unmatched DCS verb lemmas (top 80 by tokens)")
        w()
        for (lemma, pre, grammar), n in unassigned.most_common(80):
            w(f"- {lemma} (preverbs `{pre}`, {grammar}): {n}")
        w()
        w("## Causatives not counted (top 40)")
        w()
        for (lemma, pre, root), n in causative.most_common(40):
            w(f"- {lemma} (preverbs `{pre}`) <- {root}: {n}")
        w()
        w("## Single-candidate matches with no meaning overlap (top 60 by tokens)")
        w()
        for n, lemma, pre, code, en, m in sorted(single_no_overlap, reverse=True)[:60]:
            w(f'- {lemma} (`{pre}`) -> {code} "{en}" | DCS: {m} | {n}')
        w()
        w("## Prefixed lemmas with more than one possible base (top 40)")
        w()
        for n, lemma, pre, bases in sorted(ambiguous_base, reverse=True)[:40]:
            w(f"- {lemma} (`{pre}`): {', '.join(bases)} | {n}")


if __name__ == "__main__":
    main()
